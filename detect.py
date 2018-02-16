#
# Copyright 2018 Electric Brain Software Corporation
#
# All Rights Reserved.
#


import numpy as np
import os
import six.moves.urllib as urllib
import sys
import tarfile
import tensorflow as tf
import zipfile
import cv2
import scipy
import time

import concurrent.futures

from collections import defaultdict
from io import StringIO
from matplotlib import pyplot as plt
from PIL import Image

from scipy.misc import imread, imsave

sys.path.append("../pose-tensorflow")

from config import load_config
from dataset.factory import create as create_dataset
from nnet import predict
from util import visualize
from dataset.pose_dataset import data_to_input

from multiperson.detections import extract_detections
from multiperson.predict import SpatialModel, eval_graph, get_person_conf_multicut
from multiperson.visualize import PersonDraw, visualize_detections



if tf.__version__ < '1.4.0':
  raise ImportError('Please upgrade your tensorflow installation to v1.4.* or later!')

# This is needed since the notebook is stored in the object_detection folder.
sys.path.append("../models/research")
sys.path.append("../models/research/object_detection")

from utils import label_map_util

from utils import visualization_utils as vis_util


MODEL_NAME = 'ssd_mobilenet_v1_coco_2017_11_17'
MODEL_FILE = MODEL_NAME + '.tar.gz'
DOWNLOAD_BASE = 'http://download.tensorflow.org/models/object_detection/'

# Path to frozen detection graph. This is the actual model that is used for the object detection.
PATH_TO_CKPT = MODEL_NAME + '/frozen_inference_graph.pb'

# List of the strings that is used to add correct label for each box.
PATH_TO_LABELS = os.path.join('data', 'mscoco_label_map.pbtxt')

NUM_CLASSES = 90



# opener = urllib.request.URLopener()
# opener.retrieve(DOWNLOAD_BASE + MODEL_FILE, MODEL_FILE)
# tar_file = tarfile.open(MODEL_FILE)
# for file in tar_file.getmembers():
#   file_name = os.path.basename(file.name)
#   if 'frozen_inference_graph.pb' in file_name:
#     tar_file.extract(file, os.getcwd())


detection_graph = tf.Graph()
with detection_graph.as_default():
  od_graph_def = tf.GraphDef()
  with tf.gfile.GFile(PATH_TO_CKPT, 'rb') as fid:
    serialized_graph = fid.read()
    od_graph_def.ParseFromString(serialized_graph)
    tf.import_graph_def(od_graph_def, name='')


label_map = label_map_util.load_labelmap(PATH_TO_LABELS)
categories = label_map_util.convert_label_map_to_categories(label_map, max_num_classes=NUM_CLASSES, use_display_name=True)
category_index = label_map_util.create_category_index(categories)


def load_image_into_numpy_array(image):
  (im_width, im_height) = image.size
  return np.array(image.getdata()).reshape(
      (im_height, im_width, 3)).astype(np.uint8)


# For the sake of simplicity we will use only 2 images:
# image1.jpg
# image2.jpg
# If you want to test the code with your images, just add path to the images to the TEST_IMAGE_PATHS.
PATH_TO_TEST_IMAGES_DIR = 'test_images'
TEST_IMAGE_PATHS = [ os.path.join(PATH_TO_TEST_IMAGES_DIR, 'image{}.jpg'.format(i)) for i in range(1, 3) ]

# Size, in inches, of the output images.
IMAGE_SIZE = (12, 8)

cap = cv2.VideoCapture(0)



cfg = load_config("pose_cfg_multi.yaml")
dataset = create_dataset(cfg)
sm = SpatialModel(cfg)
sm.load()
draw_multi = PersonDraw()

# Load and setup CNN part detector
poseSess, poseInputs, poseOutputs = predict.setup_pose_prediction(cfg)

locations = []

from pyzbar.pyzbar import decode as qrdecode

def draw(img, corners, imgpts):
    imgpts = np.int32(imgpts).reshape(-1,2)

    # draw ground floor in green
    img = cv2.drawContours(img, [imgpts[:4]],-1,(0,255,0),-3)

    # draw pillars in blue color
    for i,j in zip(range(4),range(4,8)):
        img = cv2.line(img, tuple(imgpts[i]), tuple(imgpts[j]),(255),3)

    # draw top layer in red color
    img = cv2.drawContours(img, [imgpts[4:]],-1,(0,0,255),3)

    return img

sess = tf.Session(graph=detection_graph)

# Definite input and output Tensors for detection_graph
image_tensor = detection_graph.get_tensor_by_name('image_tensor:0')
# Each box represents a part of the image where a particular object was detected.
detection_boxes = detection_graph.get_tensor_by_name('detection_boxes:0')
# Each score represent how level of confidence for each of the objects.
# Score is shown on the result image, together with the class label.
detection_scores = detection_graph.get_tensor_by_name('detection_scores:0')
detection_classes = detection_graph.get_tensor_by_name('detection_classes:0')
num_detections = detection_graph.get_tensor_by_name('num_detections:0')

rolling_average_detection = None

def computeFrame(image_np):
    global rolling_average_detection

    # Expand dimensions since the model expects images to have shape: [1, None, None, 3]
    image_np_expanded = np.expand_dims(image_np, axis=0)

    # # Actual detection.
    (boxes, scores, classes, num) = sess.run(
       [detection_boxes, detection_scores, detection_classes, num_detections],
       feed_dict={image_tensor: image_np_expanded})

    chessBoardSize = (4,4)

    # prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
    objp = np.zeros((chessBoardSize[0] * chessBoardSize[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:chessBoardSize[0], 0:chessBoardSize[1]].T.reshape(-1, 2)

    # Arrays to store object points and image points from all the images.
    objpoints = []  # 3d point in real world space
    imgpoints = []  # 2d points in image plane.

    gray_image = cv2.cvtColor(image_np,cv2.COLOR_BGR2GRAY)

    # image_np =  gray_image

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    found, corners = cv2.findChessboardCorners(gray_image, chessBoardSize)

    cameraMatrix = np.array([[320.0, 0.0, 320.0], [0.0, 240.0, 240.0], [0.0, 0.0, 1.0]])
    cameraDistortionCoefficients = np.array([[0.0, 0.0, 0.0, 0.0, 0.0]])
    cameraRotationMatrix = None
    cameraTranslationVector = None

    def rotate(corners):
        newCorners = []
        for x in range(chessBoardSize[0]):
            for y in range(chessBoardSize[1]):
                current = (x, y)
                centered = ((x - (chessBoardSize[0] - 1) / 2), (y - (chessBoardSize[1] - 1) / 2))
                rotated = (centered[1], -centered[0])

                rotatedIndexes = (int(rotated[0] + (chessBoardSize[0] - 1) / 2), int(rotated[1] + (chessBoardSize[1] - 1) / 2))

                newCorners.append(corners[rotatedIndexes[0] * chessBoardSize[1] + rotatedIndexes[1]])
        return np.array(newCorners)


    if found:
        if rolling_average_detection is None:
            rolling_average_detection = corners
        else:
            # Determine if the the detections need to be rotated
            rotated = corners
            smallest = np.mean(np.abs(rotated - rolling_average_detection))
            for r in range(4):
                rotated = rotate(rotated)
                distance = np.mean(np.abs(rotated - rolling_average_detection))
                if distance < smallest:
                    corners = rotated
                    smallest = distance

            # Ignore this detection if its too far from rolling average detection
            rolling_average_detection = rolling_average_detection * 0.9 + corners * 0.1

        objpoints.append(objp)

        # corners2 = cv2.cornerSubPix(gray_image,corners,(11,11),(-1,-1),criteria)
        imgpoints.append(rolling_average_detection)

        cv2.drawChessboardCorners(image_np, chessBoardSize, rolling_average_detection, found)

        # ret2, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray_image.shape[::-1], None, None)

        # try:
        #     with np.load('cameracalibration.npz') as X:
        #         mtx, dist, _, _ = [X[i] for i in ('mtx', 'dist', 'rvecs', 'tvecs')]
        # except:

        (ret, rvecs, tvecs) = cv2.solvePnP(objp, rolling_average_detection, cameraMatrix, cameraDistortionCoefficients)

        # print(outputs)
        axis = np.float32([[0, 0, 0], [0, 2, 0], [2, 2, 0], [2, 0, 0],
                           [0, 0, -2], [0, 2, -2], [2, 2, -2], [2, 0, -2]])

        imgpts, jac = cv2.projectPoints(axis, rvecs, tvecs, cameraMatrix, cameraDistortionCoefficients)
        image_np = draw(image_np, rolling_average_detection, imgpts)

        cameraRotationMatrix = cv2.Rodrigues(rvecs)[0]
        cameraTranslationVector = tvecs

    def inverseScreenLocation(location):
        # Add in another dimension
        location = np.array([[location[0]], [location[1]], [1]])

        # print(cameraRotationMatrix)
        # print(cameraMatrix)

        tempMatrix = np.matmul(np.matmul(scipy.linalg.inv(cameraRotationMatrix), scipy.linalg.inv(cameraMatrix)),
                               location)
        tempMatrix2 = np.matmul(scipy.linalg.inv(cameraRotationMatrix), cameraTranslationVector)

        s = tempMatrix2[2][0] / tempMatrix[2][0]

        final = np.matmul(scipy.linalg.inv(cameraRotationMatrix),
                          (s * np.matmul(scipy.linalg.inv(cameraMatrix), location) - cameraTranslationVector))

        return final

    for index,box in enumerate(boxes[0]):
        category = category_index[classes[0][index]]['name']
        score = scores[0][index]
        if score > 0.5 and category == 'clock':

            print(box)

            boxCenterX = ((box[0] + box[2]) / 2) * image_np.shape[0]
            boxBottomY = box[3] * image_np.shape[1]


            # print('box', box.shape)
            # print('score', score)
            # print('category', category)
            # bottomCenterX = box


            # print(boxCenterX, boxBottomY)

            location = inverseScreenLocation(np.array([boxCenterX, boxBottomY])) * 10

            print(location)

    lastKnownLocation = None


    image_batch = data_to_input(image_np)

    # Compute prediction with the CNN
    outputs_np = poseSess.run(poseOutputs, feed_dict={poseInputs: image_batch})
    scmap, locref, pairwise_diff = predict.extract_cnn_output(outputs_np, cfg, dataset.pairwise_stats)

    detections = extract_detections(cfg, scmap, locref, pairwise_diff)
    unLab, pos_array, unary_array, pwidx_array, pw_array = eval_graph(sm, detections)
    person_conf_multi = get_person_conf_multicut(sm, unLab, unary_array, pos_array)

    # Visualization of the results of a detection.
    vis_util.visualize_boxes_and_labels_on_image_array(
      image_np,
      np.squeeze(boxes),
      np.squeeze(classes).astype(np.int32),
      np.squeeze(scores),
      category_index,
      use_normalized_coordinates=True,
      line_thickness=8)

    # For each person, if we can find their feet, measure the distance

    if cameraRotationMatrix is not None:
        for person in person_conf_multi:
            feet = []
            if person[15][0] != 0:
                feet.append(person[15])
            if person[16][0] != 0:
                feet.append(person[16])
            if len(feet) > 0:
                location = np.mean(np.array(feet), axis=0)

                lastKnownLocation = inverseScreenLocation(location)


    draw_multi.draw(image_np, dataset, person_conf_multi)
    image_np = visualize_detections(cfg, image_np, detections)

    print(lastKnownLocation)

    return image_np

executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

loop = True

waitingOnFrames = []

def showFrame(future):
    global loop
    image_np = future.result()
    waitingOnFrames.remove(future)

    resized = scipy.misc.imresize(image_np, 200, interp='bilinear', mode=None)
    cv2.imshow('frame', resized)
    if cv2.waitKey(1) == 27:
        loop = False

futures = None

while (loop):
    # Capture frame-by-frame
    ret, image = cap.read()

    if len(waitingOnFrames) < 1:
        future = executor.submit(computeFrame, image)
        waitingOnFrames.append(future)
        future.add_done_callback(showFrame)




# When everything done, release the capture
cap.release()
cv2.destroyAllWindows()

