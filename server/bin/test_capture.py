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


class CaptureTest:
    """ This class represents the combined state of a capture test."""

    def __init__(self, fileName):
        # Load core test data
        self.testData = json.load(open(fileName, 'r'))

        # Load the annotation data
        self.annotations = json.load(open(os.path.join(os.path.dirname(sys.argv[1]), self.testData['annotationsFile']), 'r'))
        
        # Load the store map
        self.loadStoreMap()

        # Create the image analyzer instance.
        self.imageAnalyzer = ImageAnalyzer.sharedInstance()


    def breakApartImage(self, captureFullImage, cameras):
        """Break it apart into separate images for each camera"""
        cameraImages = []
        for camera in cameras:
            cameraImage = captureFullImage.crop((camera['x'], camera['y'], camera['x']+camera['width'], camera['y']+camera['height']))
            cameraImage.load()
            cameraImageArray = numpy.array(cameraImage.getdata(), numpy.uint8).reshape(camera['height'], camera['width'], 3)
            cameraImageArray = cv2.cvtColor(cameraImageArray, cv2.COLOR_RGB2BGR)
    
            cameraImages.append(cameraImageArray)
        return cameraImages
    
    
    def drawDebugStoreMap(self, points, textScale=0.5, boxSize=50):
        frameMap = self.storeMap.copy()
    
        for pointIndex, point in enumerate(points):
            ids = [pointIndex]
            if 'detectionIds' in point:
                ids = point['detectionIds']
            elif 'visitorId' in point:
                ids = [point['visitorId']]
            elif 'id' in point:
                ids = [point['id']]
    
            if 'zone' in point:
                ids += ['zone-' + str(point['zone'])]
    
            color = (0, 255, 0)
            if 'color' in point:
                color = point['color']
    
            cv2.rectangle(frameMap, (int(point['x'] - boxSize/2), int(point['y'] - boxSize/2)),
                          (int(point['x'] + boxSize/2), int(point['y'] + boxSize/2)), color, 3)
    
            for index, id in enumerate(ids):
                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(frameMap, str(id), (int(point['x'] - boxSize/2 + 5), int(point['y'] - boxSize/2 + (index+1.2)*15)), font, textScale, color, 1,
                            cv2.LINE_AA)
    
        return frameMap

    def loadStoreMap(self):
        # Now render the results onto a store-map
        storeMapImagePath = os.path.join(os.path.dirname(sys.argv[1]), 'storemap.png')
        storeMapImage = Image.open(storeMapImagePath)
        storeMapImage.load()
        storeMapImageArray = numpy.array(storeMapImage.getdata(), numpy.uint8).reshape(storeMapImage.height, storeMapImage.width, 4)
        storeMapImageArray = cv2.cvtColor(storeMapImageArray, cv2.COLOR_RGBA2BGR)
        
        self.storeMap = storeMapImageArray

    def loadCalibrationImage(self):
        # Load calibration image
        calibrationImagePath = os.path.join(os.path.dirname(sys.argv[1]), self.testData['directory'], 'calibration.jpg')
        fullCalibrationImage = Image.open(calibrationImagePath)
        self.calibrationImages = self.breakApartImage(fullCalibrationImage, self.testData['cameras'])
    
        self.annotationWidthAdjust = fullCalibrationImage.width / self.annotations['frames']["0"][0]["width"]
        self.annotationHeightAdjust = (fullCalibrationImage.height + self.testData['storeMap']['height']) / self.annotations['frames']["0"][0]["height"]

    def createCameraConfigurations(self):
        # Detect the calibration object for each camera, and generate its configuration object
        singleCameraConfigurations = []
        for cameraIndex, cameraImage in enumerate(self.calibrationImages):
            camera = self.testData['cameras'][cameraIndex]
            debugImage = cameraImage.copy()
    
            calibrationDetectionState = {}
            calibrationObject, calibrationDetectionState, debugImage = self.imageAnalyzer.detectCalibrationObject(cameraImage, calibrationDetectionState, debugImage)
    
            cameraConfiguration = {
                "storeId": 1,
                "cameraId": "test-camera-" + str(cameraIndex),
                "width": camera['width'],
                "height": camera['height'],
                "calibrationReferencePoint": {
                    "x": (self.annotations["frames"]["0"][0]["x1"] * self.annotationWidthAdjust - self.testData['storeMap']['x']), # TODO: Technically this isn't correct, as it could be any one of x1, y1, x2, y2 depending on the angle of the camera.
                    "y": (self.annotations["frames"]["0"][0]["y1"] * self.annotationHeightAdjust - self.testData['storeMap']['y']),
                    "unitWidth": abs(self.annotations["frames"]["0"][0]["x2"] - self.annotations["frames"]["0"][0]["x1"])/4,
                    "unitHeight": abs(self.annotations["frames"]["0"][0]["y2"] - self.annotations["frames"]["0"][0]["y1"])/4,
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

        self.singleCameraConfigurations = singleCameraConfigurations
        return singleCameraConfigurations


    def showDebugCameraGrid(self):
        positions = []
        for cameraIndex, camera in enumerate(self.singleCameraConfigurations):
            for x in range(11):
                for y in range(11):
                    location = [(camera['width']/10)*x, (camera['height']/10)*y]
                    position = self.imageAnalyzer.inverseScreenLocation(
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
    
        debugMap = self.drawDebugStoreMap(positions, textScale=0.50)
        cv2.imshow('store-map-test', debugMap)
        cv2.waitKey(2000)
    
    
    def createSingleCameraFrames(self):

        states = {}
        for camera in test.testData['cameras']:
            states[camera['name']] = {}

        # Process each of the main sequence images
        resultDebugImages = []
        resultSingleCameraFrames = []
        for i in range(self.testData['numberOfImages']):
            imagePath = os.path.join(os.path.dirname(sys.argv[1]), self.testData['directory'], 'image-' + str(i).zfill(5) + '.jpg')
    
            captureFullImage = Image.open(imagePath)
    
            # Break it apart into separate images for each camera
            cameraImages = self.breakApartImage(captureFullImage, self.testData['cameras'])
    
            debugImages = []
    
            now = datetime.datetime.now()
    
            singleCameraFrames = []
    
            # Now process each image
            for cameraIndex, cameraImage in enumerate(cameraImages):
                camera = self.testData['cameras'][cameraIndex]
    
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
                singleCameraFrame, newState = self.imageAnalyzer.processSingleCameraImage(cameraImage, metadata, currentState,
                                                                                     debugImage)
    
                states[camera['name']] = newState
    
                singleCameraFrames.append(singleCameraFrame)
    
                cv2.waitKey(25)
    
                debugImages.append(debugImage)

            resultSingleCameraFrames.append(singleCameraFrames)
            resultDebugImages.append(debugImages)
        return resultSingleCameraFrames, resultDebugImages

    def getStoreConfiguration(self):
        return {
            "storeId": 1,
            "name": "Test Store",
            "address": "20 Camden Street, Toronto, Ontario",
            "storeMap": {
                "height": self.testData['storeMap']['height'],
                "width": self.testData['storeMap']['width']
            },
            "cameras": self.singleCameraConfigurations,
            "zones": self.testData['zones']
        }

    def createMultiCameraFrames(self, allSingleCameraFrames):
        multiCameraFrames = []

        for singleCameraFrames in allSingleCameraFrames:
            # Now we merge them all together to produce a multi-camera-frame, and add that to the list.
            multiCameraFrame = self.imageAnalyzer.processMultipleCameraFrames(singleCameraFrames, self.singleCameraConfigurations)
            multiCameraFrames.append(multiCameraFrame)

        return multiCameraFrames

    def frameHasVisitor(self, timeSeriesFrame, visitorId):
        hasPerson = False
        for person in timeSeriesFrame['people']:
            if person['visitorId'] == visitorId:
                hasPerson = True
        return hasPerson

    def runTimeSeriesAnalysis(self, multiCameraFrames):
        # Now we process all the multi camera frames through a time-series analysis
        currentState = {}
        timeSeriesFrames = []
        visitSummaries = []
        for frameIndex, multiCameraFrame in enumerate(multiCameraFrames):
            timeSeriesFrame, state = self.imageAnalyzer.processMultiCameraFrameTimeSeries(multiCameraFrame,
                                                                                          currentState,
                                                                                          self.getStoreConfiguration())

            timeSeriesFrames.append(timeSeriesFrame)

            # If any of the people in the frame are declared "exited", compute their visit summary
            for person in timeSeriesFrame['people']:
                if person['state'] == 'exited':
                    # Grab all of the frames which contained this visitId
                    visitorFrames = [frame for frame in timeSeriesFrames if self.frameHasVisitor(frame, person['visitorId'])]

                    visitSummary = self.imageAnalyzer.createVisitSummary(person['visitorId'], visitorFrames, self.getStoreConfiguration())

                    visitSummaries.append(visitSummary)

                    # pprint(visitSummary)

            currentState = state
        return timeSeriesFrames, visitSummaries

    def drawStoreMapResults(self, multiCameraFrames, timeSeriesFrames):
        storeMapImages = []

        for frameIndex in range(len(multiCameraFrames)):
            multiCameraFrame = multiCameraFrames[frameIndex]
            timeSeriesFrame = timeSeriesFrames[frameIndex]

            groundTruthPoints = [{
                "x": (annotation['x1'] / 2 + annotation['x2'] / 2) * self.annotationWidthAdjust - self.testData['storeMap'][
                    'x'],
                "y": (annotation['y1'] / 2 + annotation['y2'] / 2) * self.annotationHeightAdjust - self.testData['storeMap'][
                    'y'],
                "id": annotation['tags'][0],
                "color": (255, 0, 0)
            } for annotation in self.annotations['frames'][str(frameIndex + 1)]]

            for person in timeSeriesFrame['people']:
                person['color'] = (0, 255, 0)
            for person in multiCameraFrame['people']:
                person['color'] = (0, 0, 255)

            storeMapImages.append(self.drawDebugStoreMap(multiCameraFrame['people'] + timeSeriesFrame['people'] + groundTruthPoints, boxSize=100))
        return storeMapImages

if __name__ == '__main__':
    if len(sys.argv) != 2:
        usage(sys.argv)

    test = CaptureTest(sys.argv[1])
    
    test.loadStoreMap()

    # Load calibration image
    test.loadCalibrationImage()
    test.createCameraConfigurations()
    test.showDebugCameraGrid()

    # Either load the singleCameraFrame objects from a cache, or compute them fresh
    cacheFileName = sys.argv[1] + "-cached.json"
    if os.path.exists(cacheFileName):
        resultSingleCameraFrames = json.load(open(cacheFileName, 'r'))
        resultDebugImages = [[] for fame in range(test.testData['numberOfImages'])]
    else:
        # Process each of the main sequence images
        resultSingleCameraFrames, resultDebugImages = test.createSingleCameraFrames()
        json.dump(resultSingleCameraFrames, open(cacheFileName, 'w'), indent=4)


    multiCameraFrames = test.createMultiCameraFrames(resultSingleCameraFrames)

    cv2.waitKey(50)

    # Now we process all the multi camera frames through a time-series analysis
    timeSeriesFrames, visitSummaries = test.runTimeSeriesAnalysis(multiCameraFrames)

    storeMapDebugImages = test.drawStoreMapResults(multiCameraFrames, timeSeriesFrames)
    for frameIndex in range(len(multiCameraFrames)):
        resultDebugImages[frameIndex].append(storeMapDebugImages[frameIndex])

    for i in range(test.testData['numberOfImages']):
        debugImages = resultDebugImages[i]

        for imageIndex, debugImage in enumerate(debugImages):
            if imageIndex < (len(debugImages)-1):
                frameName = test.testData['cameras'][imageIndex]['name']
            else:
                frameName = 'Store Map (Individual Frames)'
            cv2.imshow(frameName, debugImage)
        cv2.waitKey(2000)


