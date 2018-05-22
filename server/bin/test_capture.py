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

    imageAnalyzer = ImageAnalyzer.sharedInstance()

    data = json.load(open(sys.argv[1], 'r'))

    annotations = json.load(os.path.join(os.path.dirname(sys.argv[1]), data['annotationsFile']))

    states = {}
    for camera in data['cameras']:
        states[camera['name']] = {}

    # Load calibration image
    calibrationImagePath = os.path.join(os.path.dirname(sys.argv[1]), data['directory'], 'calibration.jpg')
    fullCalibrationImage = Image.open(calibrationImagePath)
    calibrationImages = breakApartImage(fullCalibrationImage, data['cameras'])

    # Detect the calibration object for each camera
    for index, cameraImage in enumerate(calibrationImages):
        camera = data['cameras'][index]
        debugImage = cameraImage.copy()
        currentState = states[camera['name']]

        calibrationDetectionState = {}
        calibrationObject, calibrationDetectionState, debugImage = imageAnalyzer.detectCalibrationObject(cameraImage, calibrationDetectionState, debugImage)

        pprint(calibrationObject)
        currentState['calibrationDetectionState'] = calibrationDetectionState


    # Process each of the main sequence images
    results = []
    for i in range(data['numberOfImages']):
        imagePath = os.path.join(os.path.dirname(sys.argv[1]), data['directory'], 'image-' + str(i).zfill(5) + '.jpg')

        captureFullImage = Image.open(imagePath)

        # Break it apart into separate images for each camera
        cameraImages = breakApartImage(captureFullImage,data['cameras'])

        debugImages = []

        # Now process each image
        for index, cameraImage in enumerate(cameraImages):
            camera = data['cameras'][index]

            # pprint(states)

            currentState = states[camera['name']]

            peopleState = currentState.get('peopleState', None)
            calibrationDetectionState = currentState['calibrationDetectionState']

            # Copy for the debug image
            debugImage = cameraImage.copy()

            try:
                # Use the global image analyzer to do all the general purpose detections
                people, peopleState, debugImage = imageAnalyzer.detectPeople(cameraImage, peopleState, debugImage)
            except Exception as e:
                # Reset the state if something went wrong.
                peopleState = None
                raise  # Reraise the exception
            finally:
                currentState['peopleState'] = peopleState
                states[camera['name']] = currentState

            debugImages.append(debugImage)

        results.append(debugImages)

    for i in range(data['numberOfImages']):
        debugImages = results[i]
        for index, debugImage in enumerate(debugImages):
            camera = data['cameras'][index]
            cv2.imshow(camera['name'], debugImage)
            cv2.waitKey(1)
        time.sleep(0.5)


