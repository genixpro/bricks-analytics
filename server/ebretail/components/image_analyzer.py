import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", "lib"))
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", "lib", "pose-tensorflow"))

import os
import uuid
import shutil
import io
import threading
import numpy as np
from pprint import pprint
import scipy
import scipy.spatial
import cv2
import json
import math
from datetime import datetime
import requests
from pyramid.response import Response
from PIL import Image
from pyramid.view import view_config

from config import load_config
from dataset.factory import create as create_dataset
from nnet import predict
from dataset.pose_dataset import data_to_input
from multiperson.detections import extract_detections
from multiperson.predict import SpatialModel, eval_graph, get_person_conf_multicut
from multiperson.visualize import PersonDraw, visualize_detections

from sort import Sort


globalSharedInstanceLock = threading.RLock()
globalSharedInstance = None

class ImageAnalyzer:
    """
        This class is responsible for handling the core processing of images. It does not handle the
        surrounding logic such as maintaining database records or dividing the work between different
        workers.

        This class is meant to handle just that core image processing piece.
    """

    def __init__(self):
        # Configure the pose detection model
        self.cfg = load_config(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "config", "pose_cfg_multi.yaml"))
        self.dataset = create_dataset(self.cfg)
        self.sm = SpatialModel(self.cfg)
        self.sm.load()
        self.draw_multi = PersonDraw()

        # Load and setup CNN part detector
        self.poseSess, self.poseInputs, self.poseOutputs = predict.setup_pose_prediction(self.cfg)

        # How frequent does the person detector run
        self.personDetectorFrequency = 3
        self.detectorTrackerMaxDistance = 50
        self.trackerBoxWidth = 30
        self.trackerBoxHeight = 30
        self.trackerMaxAverageDist = 50

    def boundingBoxForPerson(self, keypoints):
        epsilon = 1e-6
        left = min(point[0] for point in keypoints if point[0] != 0 or point[1] != 0) - epsilon
        top = min(point[1] for point in keypoints if point[0] != 0 or point[1] != 0) - epsilon
        right = max(point[0] for point in keypoints if point[0] != 0 or point[1] != 0) + epsilon
        bottom = max(point[1] for point in keypoints if point[0] != 0 or point[1] != 0) + epsilon

        return [left, top, right, bottom]


    def detectPeople(self, image, state, debugImage):
        """
            This method processes the given image, provided as a standard np [width,height,channels] array,
            and extracts the locations of people within it.

            :param image: The image to be processed
            :param state: The current state of the people detector, from the last image. None if there is no current state.
            :param debugImage: The image upon which debug information can be written
            :return: (people, state, debugImage)
        """
        if not state:
            state = {}

        # Each person data has {id, keypoints, trackers}
        currentPeople = state.get('people', [])

        # Create the tracker if it doesn't exist
        if 'tracker' not in state:
            state['tracker'] = Sort(max_age=10, min_hits=3.0)

        tracker = state['tracker']

        # Every nth frame, we call the heavy weight detection model and feed it to the tracker
        frameIndex = state.get('frameIndex', 0)
        frameIndex += 1
        if frameIndex % self.personDetectorFrequency == 0:
            time = datetime.now()

            # Compute prediction with the CNN
            image_batch = data_to_input(image)
            outputs_np = self.poseSess.run(self.poseOutputs, feed_dict={self.poseInputs: image_batch})
            scmap, locref, pairwise_diff = predict.extract_cnn_output(outputs_np, self.cfg, self.dataset.pairwise_stats)

            # Convert the cnn output into the set of detected people
            detections = extract_detections(self.cfg, scmap, locref, pairwise_diff)
            unLab, pos_array, unary_array, pwidx_array, pw_array = eval_graph(self.sm, detections)
            peoplePoints = get_person_conf_multicut(self.sm, unLab, unary_array, pos_array)

            newPeople = []

            # Filter out detections that have less then 3 keypoints ( use 6 here because there are two dimensions, x and y)
            peoplePoints = np.array([person for person in peoplePoints if np.count_nonzero(person) >= 6])

            # Now feed these detections through the tracker
            detectionBoxes = []
            for detectedPersonIndex, detectedPerson in enumerate(peoplePoints):
                # Compute this persons outer bounding box
                left, top, right, bottom = self.boundingBoxForPerson(detectedPerson)

                detectedPointCount = 0
                for point in detectedPerson:
                    if point[0] != 0 or point[1] != 0:
                        detectedPointCount += 1

                detection = [left, top, right, bottom, detectedPointCount / 17.0]  # the last entry is the score, which is the number of keypoints detected

                detectionBoxes.append(detection)


            for box in detectionBoxes:
                cv2.rectangle(debugImage, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), (0, 0, 255), 3)

            trackedBoxes = tracker.update(np.array(detectionBoxes))

            for box in trackedBoxes:
                cv2.rectangle(debugImage, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), (0, 255, 0), 3)

                textX = int(box[0]) + 10
                textY = int(box[1]) + 35

                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(debugImage, str(int(box[4])), (textX, textY), font, 1, (0, 255, 0), 2, cv2.LINE_AA)


            # Now we have a bunch of tracked boxes. Find which person goes with which tracked box
            for box in trackedBoxes:
                bestMatch = None
                bestDistance = 0
                for person in peoplePoints:
                    distances = []
                    for point in person:
                        if point[0] == 0 and point[1] == 0:
                            pass
                        elif point[0] >= box[0] and point[0] <= box[2] and point[1] >= box[1] and point[1] <= box[3]:
                            # Point is in the box, distance is 0
                            distances.append(0)
                        else:
                            if point[0] < box[0] or point[0] > box[2]:
                                distanceX = min(abs(point[0] - box[0]), abs(point[0] - box[2]))
                                distances.append(distanceX * distanceX)

                            if point[1] < box[1] or point[1] > box[3]:
                                distanceY = min(abs(point[1] - box[1]), abs(point[1] - box[3]))
                                distances.append(distanceY * distanceY)

                    distance = np.mean(np.array(distances))

                    if bestMatch is None or (distance < bestDistance and distance < self.trackerMaxAverageDist):
                        bestMatch = person
                        bestDistance = distance
                if bestMatch is not None:
                    personData = {
                        'id': box[4],
                        'keypoints': bestMatch
                    }
                    newPeople.append(personData)

            currentPeople = newPeople

            self.draw_multi.draw(debugImage, self.dataset, peoplePoints)
        else:
            for person in currentPeople:
                box = self.boundingBoxForPerson(person['keypoints'])
                cv2.rectangle(debugImage, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), (0, 255, 0), 3)

                textX = int(box[0]) + 10
                textY = int(box[1]) + 35

                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(debugImage, str(int(person['id'])), (textX, textY), font, 1, (0, 255, 0), 2, cv2.LINE_AA)

            # Draw people the based the result from the trackers
            if len(currentPeople) == 0:
                peoplePoints = np.reshape(np.array([]), newshape=[0, 2])
            else:
                peoplePoints = np.reshape(np.array([[person['keypoints'] for person in currentPeople]]), newshape=[len(currentPeople), 17, 2])
            self.draw_multi.draw(debugImage, self.dataset, peoplePoints)


        state['people'] = currentPeople
        state['frameIndex'] = frameIndex

        for person in currentPeople:
            print("Person: ", person['id'])

        return peoplePoints.tolist(), state, debugImage


    def detectCalibrationObject(self, image, state, debugImage):
        """
            Tries to detect the presence of the calibration object, which is just a standard checkerboard pattern.

            :param image: A standard np image array, [width, height, batchSize]
            :param state: The current state of the calibration object detector, from the last image. None if there is no current state.
            :param debugImage: An image upon which the debugging information can be written
            :return (calibrationData, state, debugImage)
        """
        chessBoardSize = (4,4)

        # prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
        objp = np.zeros((chessBoardSize[0] * chessBoardSize[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:chessBoardSize[0], 0:chessBoardSize[1]].T.reshape(-1, 2)

        # Convert image to greyscale
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Attempt to find chessboard corners.
        # We include default options of adaptive thresholding and image normalization, but we add in the
        # fast-check flag since this is being done on every frame.
        flags = cv2.CALIB_CB_FAST_CHECK + cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        found, corners = cv2.findChessboardCorners(image=gray_image, patternSize=chessBoardSize, flags=flags)

        if found:
            cameraMatrix = np.array([[320.0, 0.0, 320.0], [0.0, 240.0, 240.0], [0.0, 0.0, 1.0]])
            cameraDistortionCoefficients = np.array([[0.0, 0.0, 0.0, 0.0, 0.0]])
            cameraRotationVector = None
            cameraTranslationVector = None

            (ret, cameraRotationVector, cameraTranslationVector) = cv2.solvePnP(objp, corners, cameraMatrix, cameraDistortionCoefficients)

            # Update the debug image with the calibration object drawn on
            cv2.drawChessboardCorners(debugImage, chessBoardSize, corners, found)

            return ({
                "cameraMatrix": cameraMatrix.tolist(),
                "rotationVector": cameraRotationVector.tolist(),
                "translationVector": cameraTranslationVector.tolist(),
            }, state, debugImage)
        else:
            return (None, state, debugImage)

    @staticmethod
    def sharedInstance():
        global globalSharedInstance
        global globalSharedInstanceLock
        with globalSharedInstanceLock:
            if globalSharedInstance is not None:
                return globalSharedInstance
            else:
                globalSharedInstance = ImageAnalyzer()
                return globalSharedInstance

