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

def drawDebugStoreMap(storeMap, points, textScale=0.5, boxSize=25):
    frameMap = storeMap.copy()

    for pointIndex, point in enumerate(points):
        ids = [pointIndex]
        if 'detectionIds' in point:
            ids = point['detectionIds']
        elif 'visitId' in point:
            ids = [point['visitId']]
        elif 'id' in point:
            ids = [point['id']]

        if 'zone' in point:
            ids += ['zone-' + str(point['zone'])]

        color = (0, 255, 0)
        if 'color' in point:
            color = point['color']

        cv2.rectangle(frameMap, (int(point['x'] - 25), int(point['y'] - 20)),
                      (int(point['x'] + 25), int(point['y'] + 20)), color, 3)

        for index, id in enumerate(ids):
            font = cv2.FONT_HERSHEY_SIMPLEX
            cv2.putText(frameMap, str(id), (int(point['x']), int(point['y'] + index*15)), font, textScale, color, 1,
                        cv2.LINE_AA)

    return frameMap

if __name__ == '__main__':
    if len(sys.argv) != 2:
        usage(sys.argv)

    data = json.load(open(sys.argv[1], 'r'))
    
    # Load the annotation data
    annotations = json.load(open(os.path.join(os.path.dirname(sys.argv[1]), data['annotationsFile']), 'r'))

    # Now render the results onto a store-map
    storeMapImagePath = os.path.join(os.path.dirname(sys.argv[1]), 'storemap.png')
    storeMapImage = Image.open(storeMapImagePath)
    storeMapImage.load()
    storeMapImageArray = numpy.array(storeMapImage.getdata(), numpy.uint8).reshape(storeMapImage.height, storeMapImage.width, 4)
    storeMapImageArray = cv2.cvtColor(storeMapImageArray, cv2.COLOR_RGBA2BGR)

    states = {}
    for camera in data['cameras']:
        states[camera['name']] = {}

    # Load calibration image
    calibrationImagePath = os.path.join(os.path.dirname(sys.argv[1]), data['directory'], 'calibration.jpg')
    fullCalibrationImage = Image.open(calibrationImagePath)
    calibrationImages = breakApartImage(fullCalibrationImage, data['cameras'])

    annotationWidthAdjust = fullCalibrationImage.width / annotations['frames']["0"][0]["width"]
    annotationHeightAdjust = (fullCalibrationImage.height + data['storeMap']['height']) / annotations['frames']["0"][0]["height"]

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
            "width": camera['width'],
            "height": camera['height'],
            "calibrationReferencePoint": {
                "x": (annotations["frames"]["0"][0]["x1"] * annotationWidthAdjust - data['storeMap']['x']), # TODO: Technically this isn't correct, as it could be any one of x1, y1, x2, y2 depending on the angle of the camera.
                "y": (annotations["frames"]["0"][0]["y1"] * annotationHeightAdjust - data['storeMap']['y']),
                "unitWidth": abs(annotations["frames"]["0"][0]["x2"] - annotations["frames"]["0"][0]["x1"])/4,
                "unitHeight": abs(annotations["frames"]["0"][0]["y2"] - annotations["frames"]["0"][0]["y1"])/4,
                "direction": camera['direction']
            },
            "cameraMatrix": calibrationObject["cameraMatrix"],
            "rotationVector": calibrationObject["rotationVector"],
            "translationVector": calibrationObject["translationVector"],
            "distortionCoefficients": calibrationObject["distortionCoefficients"]
        }

        axis = numpy.float32([[0, 0, 0], [0, 3, 0], [3, 3, 0], [3, 0, 0], [0, 0, -3], [0, 3, -3], [3, 3, -3], [3, 0, -3]])

        # project 3D points to image plane
        imgpts, jac = cv2.projectPoints(axis, numpy.array(cameraConfiguration['rotationVector']), numpy.array(cameraConfiguration['translationVector']), numpy.array(cameraConfiguration['cameraMatrix']), numpy.array(cameraConfiguration['distortionCoefficients']))

        def draw(img, imgpts):
            img = cv2.line(img, tuple(imgpts[0].ravel()), tuple(imgpts[3].ravel()), (255,0,0), 5)
            img = cv2.line(img, tuple(imgpts[0].ravel()), tuple(imgpts[1].ravel()), (0,255,0), 5)
            img = cv2.line(img, tuple(imgpts[0].ravel()), tuple(imgpts[4].ravel()), (0,0,255), 5)
            return img
        draw(debugImage, imgpts)

        cv2.imshow('calibration-'+str(cameraIndex), debugImage)
        cv2.waitKey(1000)

        singleCameraConfigurations.append(cameraConfiguration)

    positions = []
    for cameraIndex, camera in enumerate(singleCameraConfigurations):
        for x in range(11):
            for y in range(11):
                location = [(camera['width']/10)*x, (camera['height']/10)*y]
                position = imageAnalyzer.inverseScreenLocation(
                    location=location,
                    height=0,
                    rotationVector=numpy.array(camera['rotationVector']),
                    translationVector=numpy.array(camera['translationVector']),
                    cameraMatrix=numpy.array(camera['cameraMatrix']),
                    calibrationReference=camera['calibrationReferencePoint']
                )

                color = None
                if (cameraIndex % 3) == 0:
                    color = (0, 255, 0, 0.5)
                if (cameraIndex % 3) == 1:
                    color = (255, 0, 0, 0.5)
                if (cameraIndex % 3) == 2:
                    color = (0, 0, 255, 0.5)

                positions.append({"x": position[0], "y": position[1], "id": str(x) + ","+str(y), "color": color})

    storeConfiguration = {
        "storeId": 1,
        "name": "Test Store",
        "address":  "20 Camden Street, Toronto, Ontario",
        "storeMap": {
            "height": data['storeMap']['height'],
            "width": data['storeMap']['width']
        },
        "cameras": singleCameraConfigurations,
        "zones": data['zones']
    }

    debugMap = drawDebugStoreMap(storeMapImageArray, positions, textScale=0.50)
    cv2.imshow('store-map-test', debugMap)
    cv2.waitKey(2000)

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

            cv2.waitKey(25)

            debugImages.append(debugImage)

        # Now we merge them all together to produce a multi-camera-frame, and add that to the list.
        multiCameraFrame = imageAnalyzer.processMultipleCameraFrames(singleCameraFrames, singleCameraConfigurations)
        multiCameraFrames.append(multiCameraFrame)

        resultDebugImages.append(debugImages)

    cv2.waitKey(50)

    # Now we process all the multi camera frames through a time-series analysis
    currentState = {}
    timeSeriesFrames = []
    for frameIndex, multiCameraFrame in enumerate(multiCameraFrames):
        timeSeriesFrame, state = imageAnalyzer.processMultiCameraFrameTimeSeries(multiCameraFrame, currentState, storeConfiguration)
        currentState = state
        timeSeriesFrames.append(timeSeriesFrame)

    for frameIndex in range(len(multiCameraFrames)):
        multiCameraFrame = multiCameraFrames[frameIndex]
        timeSeriesFrame = timeSeriesFrames[frameIndex]

        groundTruthPoints = [{
            "x": (annotation['x1']/2 + annotation['x2']/2) * annotationWidthAdjust - data['storeMap']['x'],
            "y": (annotation['y1']/2 + annotation['y2']/2) * annotationHeightAdjust - data['storeMap']['y'],
            "id": annotation['tags'][0],
            "color": (255, 0, 0)
        } for annotation in annotations['frames'][str(frameIndex+1)]]

        resultDebugImages[frameIndex].append(drawDebugStoreMap(storeMapImageArray, multiCameraFrame['people'] + groundTruthPoints))
        resultDebugImages[frameIndex].append(drawDebugStoreMap(storeMapImageArray, timeSeriesFrame['people'] + groundTruthPoints))

    for i in range(data['numberOfImages']):
        debugImages = resultDebugImages[i]
        for imageIndex, debugImage in enumerate(debugImages):
            if imageIndex < (len(debugImages)-2):
                frameName = data['cameras'][imageIndex]['name']
            elif imageIndex == len(debugImages)-2:
                frameName = 'Store Map (Individual Frames)'
            else:
                frameName = 'Store Map (Time Series Analysis)'
            cv2.imshow(frameName, debugImage)
            cv2.waitKey(10)
        time.sleep(5.0)


