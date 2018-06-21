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
import requests
import pika
import threading
import io
from scipy import ndimage
import scipy.optimize
import scipy.spatial
import pickle

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
        self.fileName = fileName

        # Load the annotation data
        self.annotations = json.load(
            open(os.path.join(os.path.dirname(fileName), self.testData['annotationsFile']), 'r'))

        # Load the store map
        self.loadStoreMap()

        # Create the image analyzer instance.
        self.imageAnalyzer = ImageAnalyzer.sharedInstance()

        # Setup all the URLs
        self.storeUrl = "http://localhost:1806/store"
        self.imageProcessorUrl = "http://localhost:1845/process_image"
        self.registrationUrl = "http://localhost:1806/register_collector"
        self.transactionUrl = "http://localhost:1806/transactions"
        self.amqpUri = "localhost"

        self.uploadTimeout = 5

        self.storeId = None
        self.collectorId = 'collector-1'

        self.amqpThread = threading.Thread(target=lambda: self.amqpConnectionThread())

    def breakApartImage(self, captureFullImage, cameras):
        """Break it apart into separate images for each camera"""
        cameraImages = []
        for camera in cameras:
            cameraImage = captureFullImage.crop(
                (camera['x'], camera['y'], camera['x'] + camera['width'], camera['y'] + camera['height']))
            cameraImage.load()
            cameraImageArray = numpy.array(cameraImage.getdata(), numpy.uint8).reshape(camera['height'],
                                                                                       camera['width'], 3)
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

            cv2.rectangle(frameMap, (int(point['x'] - boxSize / 2), int(point['y'] - boxSize / 2)),
                          (int(point['x'] + boxSize / 2), int(point['y'] + boxSize / 2)), color, 3)

            for index, id in enumerate(ids):
                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(frameMap, str(id),
                            (int(point['x'] - boxSize / 2 + 5), int(point['y'] - boxSize / 2 + (index + 1.2) * 15)),
                            font, textScale, color, 1,
                            cv2.LINE_AA)

        return frameMap

    def loadStoreMap(self):
        # Now render the results onto a store-map
        storeMapImagePath = os.path.join(os.path.dirname(self.fileName), 'storemap.png')
        storeMapImage = Image.open(storeMapImagePath)
        storeMapImage.load()
        storeMapImageArray = numpy.array(storeMapImage.getdata(), numpy.uint8).reshape(storeMapImage.height,
                                                                                       storeMapImage.width, 4)
        storeMapImageArray = cv2.cvtColor(storeMapImageArray, cv2.COLOR_RGBA2BGR)

        self.storeMap = storeMapImageArray

    def loadCalibrationImage(self):
        # Load calibration image
        calibrationImagePath = os.path.join(os.path.dirname(self.fileName), self.testData['directory'], 'calibration.jpg')
        fullCalibrationImage = Image.open(calibrationImagePath)
        self.calibrationImages = self.breakApartImage(fullCalibrationImage, self.testData['cameras'])

        self.annotationWidthAdjust = fullCalibrationImage.width / self.annotations['frames']["0"][0]["width"]
        self.annotationHeightAdjust = (fullCalibrationImage.height + self.testData['storeMap']['height']) / \
                                      self.annotations['frames']["0"][0]["height"]

    def createCameraConfigurations(self, showDebug=False):
        # Detect the calibration object for each camera, and generate its configuration object
        singleCameraConfigurations = []
        for cameraIndex, cameraImage in enumerate(self.calibrationImages):
            camera = self.testData['cameras'][cameraIndex]
            debugImage = cameraImage.copy()

            calibrationDetectionState = {}
            calibrationObject, calibrationDetectionState, debugImage = self.imageAnalyzer.detectCalibrationObject(
                cameraImage, calibrationDetectionState, debugImage)

            cameraConfiguration = {
                "storeId": 1,
                "cameraId": self.cameraId(cameraIndex),
                "width": camera['width'],
                "height": camera['height'],
                "calibrationReferencePoint": {
                    "x": (self.annotations["frames"]["0"][0]["x1"] * self.annotationWidthAdjust -
                          self.testData['storeMap']['x']),
                # TODO: Technically this isn't correct, as it could be any one of x1, y1, x2, y2 depending on the angle of the camera.
                    "y": (self.annotations["frames"]["0"][0]["y1"] * self.annotationHeightAdjust -
                          self.testData['storeMap']['y']),
                    "unitWidth": abs(
                        self.annotations["frames"]["0"][0]["x2"] - self.annotations["frames"]["0"][0]["x1"]) / 4,
                    "unitHeight": abs(
                        self.annotations["frames"]["0"][0]["y2"] - self.annotations["frames"]["0"][0]["y1"]) / 4,
                    "direction": camera['direction']
                },
                "cameraMatrix": calibrationObject["cameraMatrix"],
                "rotationVector": calibrationObject["rotationVector"],
                "translationVector": calibrationObject["translationVector"],
                "distortionCoefficients": calibrationObject["distortionCoefficients"]
            }

            if showDebug:
                axis = numpy.float32(
                    [[0, 0, 0], [0, 3, 0], [3, 3, 0], [3, 0, 0], [0, 0, -3], [0, 3, -3], [3, 3, -3], [3, 0, -3]])

                # project 3D points to image plane
                imgpts, jac = cv2.projectPoints(axis, numpy.array(cameraConfiguration['rotationVector']),
                                                numpy.array(cameraConfiguration['translationVector']),
                                                numpy.array(cameraConfiguration['cameraMatrix']),
                                                numpy.array(cameraConfiguration['distortionCoefficients']))

                def draw(img, imgpts):
                    img = cv2.line(img, tuple(imgpts[0].ravel()), tuple(imgpts[3].ravel()), (255, 0, 0), 5)
                    img = cv2.line(img, tuple(imgpts[0].ravel()), tuple(imgpts[1].ravel()), (0, 255, 0), 5)
                    img = cv2.line(img, tuple(imgpts[0].ravel()), tuple(imgpts[4].ravel()), (0, 0, 255), 5)
                    return img

                draw(debugImage, imgpts)

                # cv2.imshow('calibration-' + str(cameraIndex), debugImage)
                # cv2.waitKey(1000)

            singleCameraConfigurations.append(cameraConfiguration)

        self.singleCameraConfigurations = singleCameraConfigurations
        return singleCameraConfigurations

    def showDebugCameraGrid(self):
        positions = []
        for cameraIndex, camera in enumerate(self.singleCameraConfigurations):
            for x in range(11):
                for y in range(11):
                    location = [(camera['width'] / 10) * x, (camera['height'] / 10) * y]
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

                    positions.append({"x": position[0], "y": position[1], "id": str(x) + "," + str(y), "color": color})

        debugMap = self.drawDebugStoreMap(positions, textScale=0.50)
        cv2.imshow('store-map-test', debugMap)
        cv2.waitKey(2000)

    def createSingleCameraFrames(self):
        states = {}
        for camera in self.testData['cameras']:
            states[camera['name']] = {}

        imageCacheFile = os.path.join(os.path.dirname(self.fileName), os.path.basename(self.fileName).split('.')[0] + '-images.pickle')

        if os.path.exists(imageCacheFile):
            cameraFrameImages = pickle.load(open(imageCacheFile, 'rb'))
        else:
            cameraFrameImages = []
            for i in range(self.testData['numberOfImages']):
                imagePath = os.path.join(os.path.dirname(self.fileName), self.testData['directory'],
                                         'image-' + str(i).zfill(5) + '.jpg')

                captureFullImage = Image.open(imagePath)

                # Break it apart into separate images for each camera
                cameraImages = self.breakApartImage(captureFullImage, self.testData['cameras'])

                cameraFrameImages.append(cameraImages)
            pickle.dump(cameraFrameImages, open(imageCacheFile, 'wb'))

        # Process each of the main sequence images
        resultDebugImages = []
        resultSingleCameraFrames = []
        for i in range(self.testData['numberOfImages']):
            cameraImages = cameraFrameImages[i]

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
                    'cameraId': self.cameraId(cameraIndex),
                    'timestamp': (now + datetime.timedelta(seconds=0.5)).strftime("%Y-%m-%dT%H:%M:%S.%f"),
                }

                metadata['cacheId'] = str(metadata['cameraId']) + "-" + str(i)

                # Use the image analyzer to produce the SingleCameraFrame object for this camera image.
                # This first step mostly just detects people and detects the calibration object.
                singleCameraFrame, newState, personImages = self.imageAnalyzer.processSingleCameraImage(cameraImage,
                                                                                                        metadata,
                                                                                                        currentState,
                                                                                                        debugImage)

                states[camera['name']] = newState

                singleCameraFrames.append(singleCameraFrame)

                # cv2.imshow(camera['name'], debugImage)
                # cv2.waitKey(1)

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
            multiCameraFrame = self.imageAnalyzer.processMultipleCameraFrames(singleCameraFrames,
                                                                              self.singleCameraConfigurations)
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
                    visitorFrames = [frame for frame in timeSeriesFrames if
                                     self.frameHasVisitor(frame, person['visitorId'])]

                    # visitSummary = self.imageAnalyzer.createVisitSummary(person['visitorId'], visitorFrames,
                    #                                                      self.getStoreConfiguration())

                    # visitSummaries.append(visitSummary)

                    # pprint(visitSummary)

            currentState = state
        return timeSeriesFrames, visitSummaries

    def drawStoreMapResults(self, multiCameraFrames, timeSeriesFrames):
        storeMapImages = []

        for frameIndex in range(len(multiCameraFrames)):
            multiCameraFrame = multiCameraFrames[frameIndex]
            timeSeriesFrame = timeSeriesFrames[frameIndex]

            groundTruthPoints = [{
                "x": (annotation['x1'] / 2 + annotation['x2'] / 2) * self.annotationWidthAdjust -
                     self.testData['storeMap'][
                         'x'],
                "y": (annotation['y1'] / 2 + annotation['y2'] / 2) * self.annotationHeightAdjust -
                     self.testData['storeMap'][
                         'y'],
                "id": annotation['tags'][0],
                "color": (255, 0, 0)
            } for annotation in self.annotations['frames'][str(frameIndex + 1)]]

            for person in timeSeriesFrame['people']:
                person['color'] = (0, 255, 0)
                person['x'] = person['x'] * self.testData['storeMap']['width']
                person['y'] = person['y'] * self.testData['storeMap']['height']
            for person in multiCameraFrame['people']:
                person['color'] = (0, 0, 255)

            storeMapImages.append(
                self.drawDebugStoreMap(multiCameraFrame['people'] + timeSeriesFrame['people'] + groundTruthPoints,
                                       boxSize=100))
        return storeMapImages

    def startAmqp(self):
        self.amqpThread.start()

    def connectToAmqp(self):
        # Open a connection to the message broker
        self.amqpConnection = pika.BlockingConnection(pika.ConnectionParameters(self.amqpUri))
        self.amqpChannel = self.amqpConnection.channel()
        self.amqpChannel.queue_declare(queue=self.collectorId)

        for cameraIndex,camera in enumerate(self.testData['cameras']):
            cameraId = self.cameraId(cameraIndex)
            self.amqpChannel.exchange_declare(exchange=cameraId, exchange_type='fanout')
            self.amqpChannel.queue_bind(queue=self.collectorId, exchange=cameraId)

        # self.amqpChannel.basic_consume(
        #     lambda ch, method, properties, body: self.handleCameraQueueMessage(ch, method, properties, str(body, 'utf8')),
        #     queue=self.metadata['collectorId'],
        #     no_ack=True)

    def amqpConnectionThread(self):
        while True:
            try:
                self.connectToAmqp()
                self.amqpChannel.start_consuming()
            except pika.exceptions.ConnectionClosed as e:
                # Do nothing - all other exceptions are allowed to bubble up.
                # this one is ignored.
                print(e)
                pass

    def registerStore(self):
        """ This function registers this image collector with the main server. """
        data = {
                "name": self.testData['name'],
                "address": "36 blue jays",
                "coords": {
                    "lat": 44.2,
                    "lng": -61.7
                },
                "storeMap": {
                    "width": self.testData['storeMap']['width'],
                    "height": self.testData['storeMap']['height']
                },
                "inventory": self.testData['inventory'],
                "zones": self.testData['zones']
        }
        r = requests.post(self.storeUrl, json=data)

        body = r.json()

        self.storeId = body['storeId']

    def uploadStoreMap(self):
        """ This function uploads a store map to the server."""

        storeMapImagePath = os.path.join(os.path.dirname(self.fileName), 'storemap.png')
        files = {'image': open(storeMapImagePath, 'rb')}
        r = requests.put(self.storeUrl + "/" + str(self.storeId) + "/store_layout", data=files['image'])

    def cameraId(self, index):
        return "test-camera-" + str(index)

    def uploadImageToProcessor(self, image, timeStamp, cameraIndex):
        try:
            image = Image.fromarray(image, mode=None)
            b = io.BytesIO()
            image.save(b, "JPEG", quality=80)
            b.seek(0)
            metadata = {
                "storeId": self.storeId,
                "cameraId": self.cameraId(cameraIndex),
                "timestamp": timeStamp.strftime("%Y-%m-%dT%H:%M:%S.%f"),
                "cameraIndex": cameraIndex,
                "record": True
            }
            r = requests.post(self.imageProcessorUrl, files={'image': b, "metadata": json.dumps(metadata)}, timeout=self.uploadTimeout)
            print("Successfully uploaded " + metadata['timestamp'])
        except Exception as e:
            print("Failed to upload " + timeStamp.strftime("%Y-%m-%dT%H:%M:%S.%f") + ": " + str(e))
            pass


    def registerCameras(self):
        """ This function registers tni camears with the main server. """
        # Load calibration image
        self.loadCalibrationImage()
        self.createCameraConfigurations()

        data = {
            "store": self.storeId,
            "collectorId": "collector-1",
            "cameras": self.createCameraConfigurations()
        }
        r = requests.post(self.registrationUrl, json=data)


    def sendTransaction(self, transaction):
        """ Makes a fake transaction in the system. """

        transaction['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
        r = requests.post(self.transactionUrl, json=transaction)
        print("Sent transaction at " + transaction['timestamp'])


    def runSimulation(self):
        timeStamp = datetime.datetime.now()

        # Upload the calibration images to the image processor
        for imageIndex, image in enumerate(self.calibrationImages):
            self.uploadImageToProcessor(image, timeStamp, imageIndex)

        for i in range(self.testData['numberOfImages']):
            imagePath = os.path.join(os.path.dirname(self.fileName), self.testData['directory'],
                                     'image-' + str(i).zfill(5) + '.jpg')

            captureFullImage = Image.open(imagePath)

            # Break it apart into separate images for each camera
            cameraImages = self.breakApartImage(captureFullImage, self.testData['cameras'])

            for imageIndex, image in enumerate(cameraImages):
                self.uploadImageToProcessor(image, timeStamp, imageIndex)

            for transaction in self.testData['transactions']:
                if transaction['frame'] == i:
                    self.sendTransaction(transaction)

            timeStamp = timeStamp + datetime.timedelta(seconds=0.5)

        # Now send up a few blank images to force the system to finish all of the tracks.
        for i in range(15):
            for cameraIndex in range(len(self.testData['cameras'])):
                image = Image.new('RGB', (self.testData['cameras'][cameraIndex]['width'], self.testData['cameras'][cameraIndex]['height']), (0,0,0))
                self.uploadImageToProcessor(numpy.array(image), timeStamp, cameraIndex)

            timeStamp = timeStamp + datetime.timedelta(seconds=0.5)


    def measureAccuracy(self, timeSeriesFrames):
        score = 0

        allTags = set()
        personTags = {}

        allAnnotations = json.loads(json.dumps(self.annotations))

        for frameIndex, timeSeriesFrame in enumerate(timeSeriesFrames):
            people = timeSeriesFrame['people']
            annotations = allAnnotations['frames'][str(frameIndex + 1)]
            for annotation in annotations:
                tag = annotation['tags'][0]
                allTags.add(tag)

            for person in people:
                # Now associate this time series frame to this assignment
                person['annotation'] = None
                person['groundTruth'] = None
                personTags[person['visitorId']] = {}

        for frameIndex, timeSeriesFrame in enumerate(timeSeriesFrames):
            matrix = []

            people = timeSeriesFrame['people']
            annotations = allAnnotations['frames'][str(frameIndex + 1)]

            # Create a cost matrix to perform linear assignment between detections and ground truth data
            for person in people:
                distances = []

                for annotation in annotations:
                    annotationPoint = [
                        (annotation['x1'] / 2 + annotation['x2'] / 2) * self.annotationWidthAdjust -
                        self.testData['storeMap']['x'],
                        (annotation['y1'] / 2 + annotation['y2'] / 2) * self.annotationHeightAdjust -
                        self.testData['storeMap']['y'],
                    ]

                    personPoint = [
                        person['x'],
                        person['y']
                    ]

                    distance = scipy.spatial.distance.euclidean(annotationPoint, personPoint)

                    distances.append(distance)

                # Compute distance between this person and each of the ground truth points
                matrix.append(distances)

            if len(matrix) == 0:
                assignments = [[], []]
            else:
                assignments = scipy.optimize.linear_sum_assignment(numpy.array(matrix))

            for assignmentIndex in range(len(assignments[0])):
                personIndex = assignments[0][assignmentIndex]
                annotationIndex = assignments[1][assignmentIndex]

                person = people[personIndex]
                annotation = annotations[annotationIndex]
                tag = annotation['tags'][0]

                if person['visitorId'] in personTags:
                    if tag in personTags[person['visitorId']]:
                        personTags[person['visitorId']][tag] += 1
                    else:
                        personTags[person['visitorId']][tag] = 1
                else:
                    personTags[person['visitorId']] = {tag: 1}

                # Now associate this time series frame to this assignment
                person['annotation'] = annotation
                person['groundTruth'] = tag
                person['groundTruthDistance'] = matrix[personIndex][annotationIndex]

        # Now having processed all of the frames, we only find the dominant ground truth track that each visitorId
        # was associated with. We eliminate the others, since a track can only be for one person
        for frameIndex, timeSeriesFrame in enumerate(timeSeriesFrames):
            people = timeSeriesFrame['people']
            annotations = allAnnotations['frames'][str(frameIndex + 1)]
            for person in people:
                if person['visitorId'] in personTags and len(personTags[person['visitorId']]) > 0:
                    # Determine the dominant ground truth for this person
                    bestGroundTruth = max(*personTags[person['visitorId']].keys(), key=lambda tag: personTags[person['visitorId']][tag] if tag in personTags[person['visitorId']] else 0)
                else:
                    bestGroundTruth = None

                if person['groundTruth'] != bestGroundTruth:
                    person['groundTruth'] = None
                elif person['groundTruth'] is not None:
                    person['annotation']['visitorId'] = person['visitorId']

        # Now we add up all the distances as score, and all the extras as punishment
        falsePositiveCostEach = 1000
        falseNegativeCostEach = 1000
        falsePositiveCostTotal = 0
        falseNegativeCostTotal = 0
        distanceCostTotal = 0
        for frameIndex, timeSeriesFrame in enumerate(timeSeriesFrames):
            people = timeSeriesFrame['people']
            annotations = allAnnotations['frames'][str(frameIndex + 1)]
            for person in people:
                if person['groundTruth'] is None:
                    # Punishment - this person should have had ground truth associated with them
                    score += falsePositiveCostEach
                    falsePositiveCostTotal += falsePositiveCostEach
                else:
                    score += person['groundTruthDistance']
                    distanceCostTotal += person['groundTruthDistance']
            for annotation in annotations:
                if 'visitorId' not in annotation or annotation['visitorId'] is None:
                    # Punishment - this ground truth should have had a track associated with it
                    score += falseNegativeCostEach
                    falseNegativeCostTotal += falseNegativeCostEach

        # Lastly, punish every detected person over and above the number of known tags
        extraTracksCostTotal = max(0, len(personTags) - len(allTags)) * falseNegativeCostEach
        score += extraTracksCostTotal

        details = {
            "falsePositiveCost": falsePositiveCostTotal / len(timeSeriesFrames),
            "falseNegativeCostTotal": falseNegativeCostTotal / len(timeSeriesFrames),
            "distanceCostTotal": distanceCostTotal / len(timeSeriesFrames),
            "extraTracksCostTotal": extraTracksCostTotal / len(timeSeriesFrames),
        }

        # Average for each frame
        score = score / len(timeSeriesFrames)

        return score, details

    def setHyperParameters(self, hyperParameters):
        # Set the hyper parameters on the image analyzer
        self.imageAnalyzer.setHyperParameters(hyperParameters)

    def reloadDetectionCache(self, cacheFile):
        if os.path.exists(cacheFile):
            self.imageAnalyzer.detectionCache = pickle.load(open(cacheFile, 'rb'))

    def saveDetectionCache(self, cacheFile):
        pickle.dump(self.imageAnalyzer.detectionCache, open(cacheFile, 'wb'))
