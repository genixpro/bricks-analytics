import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

import json

from pprint import pprint
from ebretail.components.image_analyzer import ImageAnalyzer
from PIL import Image
import numpy
import cv2
import time
import datetime

def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <capture_file>\n'
          '(example: "%s ~/bricks-analytics-data/session1/capture1.json")' % (cmd, cmd))
    sys.exit(1)


def breakApartImage(captureFullImage, cameras):
    """Break it apart into separate images for each camera"""
    cameraImages = []
    for camera in cameras:
        cameraImage = captureFullImage.crop((camera['x'], camera['y'], camera['x']+camera['width'], camera['y']+camera['height']))
        cameraImage.load()
        cameraImageArray = numpy.array(cameraImage.getdata(), numpy.uint8).reshape(camera['height'], camera['width'], 3)
        cameraImageArray = cv2.cvtColor(cameraImageArray, cv2.COLOR_RGB2BGR)

        cameraImages.append(cameraImageArray)
    return cameraImages


if __name__ == '__main__':
    if len(sys.argv) != 2:
        usage(sys.argv)

    data = json.load(open(sys.argv[1], 'r'))
    
    # Load the annotation data
    annotations = json.load(open(os.path.join(os.path.dirname(sys.argv[1]), data['annotationsFile']), 'r'))

    states = {}
    for camera in data['cameras']:
        states[camera['name']] = {}

    # Load calibration image
    calibrationImagePath = os.path.join(os.path.dirname(sys.argv[1]), data['directory'], 'calibration.jpg')
    fullCalibrationImage = Image.open(calibrationImagePath)
    calibrationImages = breakApartImage(fullCalibrationImage, data['cameras'])

    annotationWidthAdjust = fullCalibrationImage.width / annotations['frames']["0"][0]["width"]
    annotationHeightAdjust = fullCalibrationImage.height / annotations['frames']["0"][0]["height"]

    # Create the image analyzer instance.
    imageAnalyzer = ImageAnalyzer.sharedInstance()

    # Detect the calibration object for each camera, and generate its configuration object
    singleCameraConfigurations = []
    for cameraIndex, cameraImage in enumerate(calibrationImages):
        camera = data['cameras'][cameraIndex]
        debugImage = cameraImage.copy()
        currentState = states[camera['name']]

        calibrationDetectionState = {}
        calibrationObject, calibrationDetectionState, debugImage = imageAnalyzer.detectCalibrationObject(cameraImage, calibrationDetectionState, debugImage)

        cameraConfiguration = {
            "storeId": 1,
            "cameraId": "test-camera-" + str(cameraIndex),
            "calibrationReferencePoint": {
                "x": annotations["frames"]["0"][0]["x1"] * annotationWidthAdjust - data['storeMap']['x'], # TODO: Technically this isn't correct, as it could be any one of x1, y1, x2, y2 depending on the angle of the camera.
                "y": annotations["frames"]["0"][0]["y1"] * annotationHeightAdjust - data['storeMap']['y']
            },
            "cameraMatrix": calibrationObject["cameraMatrix"],
            "rotationVector": calibrationObject["rotationVector"],
            "translationVector": calibrationObject["translationVector"]
        }
        singleCameraConfigurations.append(cameraConfiguration)

    # Process each of the main sequence images
    resultDebugImages = []
    multiCameraFrames = []
    for i in range(data['numberOfImages']):
        imagePath = os.path.join(os.path.dirname(sys.argv[1]), data['directory'], 'image-' + str(i).zfill(5) + '.jpg')

        captureFullImage = Image.open(imagePath)

        # Break it apart into separate images for each camera
        cameraImages = breakApartImage(captureFullImage,data['cameras'])

        debugImages = []

        now = datetime.datetime.now()

        singleCameraFrames = []

        # Now process each image
        for cameraIndex, cameraImage in enumerate(cameraImages):
            camera = data['cameras'][cameraIndex]

            # pprint(states)

            currentState = states[camera['name']]

            # Copy for the debug image
            debugImage = cameraImage.copy()

            metadata = {
                'storeId': 1,
                'cameraId': 'test-camera-' + str(cameraIndex),
                'timestamp': (now + datetime.timedelta(seconds=0.5)).strftime("%Y-%m-%dT%H:%M:%S.%f")
            }

            # Use the image analyzer to produce the SingleCameraFrame object for this camera image.
            # This first step mostly just detects people and detects the calibration object.
            singleCameraFrame, newState = imageAnalyzer.processSingleCameraImage(cameraImage, metadata, currentState, debugImage)

            states[camera['name']] = newState

            singleCameraFrames.append(singleCameraFrame)

            debugImages.append(debugImage)

        # Now we merge them all together to produce a multi-camera-frame, and add that to the list.
        multiCameraFrame = imageAnalyzer.processMultipleCameraFrames(singleCameraFrames, singleCameraConfigurations)
        multiCameraFrames.append(multiCameraFrame)

        resultDebugImages.append(debugImages)

    # Now render the results onto a store-map
    storeMapImagePath = os.path.join(os.path.dirname(sys.argv[1]), 'storemap.png')
    storeMapImage = Image.open(storeMapImagePath)
    storeMapImage.load()
    storeMapImageArray = numpy.array(storeMapImage.getdata(), numpy.uint8).reshape(storeMapImage.height, storeMapImage.width, 4)
    storeMapImageArray = cv2.cvtColor(storeMapImageArray, cv2.COLOR_RGBA2BGR)

    for multiCameraFrameIndex, multiCameraFrame in enumerate(multiCameraFrames):
        frameMap = storeMapImageArray.copy()

        for personIndex, person in enumerate(multiCameraFrame['people']):
            cv2.rectangle(frameMap, (int(person['x']-25), int(person['y']-25)), (int(person['x']+25), int(person['y']+25)), (0, 255, 0), 3)

            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(frameMap, str(personIndex), (int(person['x']), int(person['y'])), font, 1, (0, 255, 0), 2, cv2.LINE_AA)

        resultDebugImages[multiCameraFrameIndex].append(frameMap)

    for i in range(data['numberOfImages']):
        debugImages = resultDebugImages[i]
        for imageIndex, debugImage in enumerate(debugImages):
            if imageIndex < (len(debugImages)-1):
                frameName = data['cameras'][imageIndex]['name']
            else:
                frameName = 'Store Map'
            cv2.imshow(frameName, debugImage)
            cv2.waitKey(1)
        time.sleep(0.5)


