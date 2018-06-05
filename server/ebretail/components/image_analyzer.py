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
import datetime
import math
from datetime import datetime
import requests
from pyramid.response import Response
from PIL import Image
from pyramid.view import view_config
from ebretail.models.validate import validateSingleCameraFrame

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

        # How frequent does the person detector run
        self.personDetectorFrequency = 1
        self.detectorTrackerMaxDistance = 50
        self.trackerBoxWidth = 30
        self.trackerBoxHeight = 30
        self.trackerMaxAverageDist = 50

        self.poseSess = None

        # We need to double check all of the indexes - some of these might not actually be correlated with the correct body parts
        self.keypointNames = [
            'left_ear',
            'left_eye',
            'nose',
            'right_eye',
            'right_ear',
            'left_shoulder',
            'right_shoulder',
            'left_elbow',
            'right_elbow',
            'left_hand',
            'right_hand',
            'left_hip',
            'right_hip',
            'left_knee',
            'right_knee',
            'left_foot',
            'right_foot'
        ]

    def processSingleCameraImage(self, image, metadata, state, debugImage):
        """
            This method is used to process a single image from a single camera. It produces a SingleCameraFrame object.

            :param image: A numpy array representing the image.
            :param metadata: A python dictionary containing storeId, cameraId, and timestamp metadata objects.
            :param state: A state object, representing carryover state from the previous processed image.
            :param debugImage: A numpy array, representing a clone of the image, to which debug information can be written to.
            :return: A tuple (singleCameraFrame, state) representing the resulting SingleCameraFrame object, and state to be carried over to the next image.
        """

        peopleState = state.get('peopleState', None)
        calibrationDetectionState = state.get('calibrationDetectionState', None)

        try:
            # Use the global image analyzer to do all the general purpose detections
            people, peopleState, debugImage = self.detectPeople(image, peopleState, debugImage)

            for person in people:
                person['detectionId'] = metadata['cameraId'] + "-" + str(person['detectionId'])

            calibrationObject, calibrationDetectionState, debugImage = self.detectCalibrationObject(image, calibrationDetectionState, debugImage)
        except Exception as e:
            # Reset the state if something went wrong.
            peopleState = None
            calibrationDetectionState = None
            raise  # Reraise the exception
        finally:
            state['timestamp'] = datetime.strptime(metadata['timestamp'], "%Y-%m-%dT%H:%M:%S.%f")
            state['peopleState'] = peopleState
            state['calibrationDetectionState'] = calibrationDetectionState

        # cv2.imshow('frame', debugImage)
        # cv2.waitKey(1)

        singleCameraFrame = {
            "storeId": metadata['storeId'],
            "cameraId": metadata['cameraId'],
            "timestamp": metadata['timestamp'],
            "people": people,
            "calibrationObject": calibrationObject
        }

        validateSingleCameraFrame(singleCameraFrame)

        return (singleCameraFrame, state)


    def inverseScreenLocation(self, location, height, rotationVector, translationVector, cameraMatrix, calibrationReference):
        rotationMatrix = cv2.Rodrigues(np.array(rotationVector))[0]

        # Add in another dimension
        location = np.array([[location[0]], [location[1]], [1]])

        calibrationPointsSize = 10 # Our calibration checkboard consists of 10cm squares

        tempMatrix = np.matmul(np.matmul(scipy.linalg.inv(rotationMatrix), scipy.linalg.inv(cameraMatrix)), location)

        tempMatrix2 = np.matmul(scipy.linalg.inv(rotationMatrix), translationVector)

        s = (-height) / calibrationPointsSize + tempMatrix2[2][0]

        s /= tempMatrix[2][0]

        final = np.matmul(scipy.linalg.inv(rotationMatrix),
                          (s * np.matmul(scipy.linalg.inv(cameraMatrix), location) - translationVector))

        # Now we need to rotate the coordinates based on the direction of the camera
        if calibrationReference['direction'] == 'east':
            x = final[0][0]
            y = final[1][0]
            final[0][0] = -y
            final[1][0] = x
        elif calibrationReference['direction'] == 'west':
            x = final[0][0]
            y = final[1][0]
            final[0][0] = y
            final[1][0] = -x
        elif calibrationReference['direction'] == 'south':
            x = final[0][0]
            y = final[1][0]
            final[0][0] = -x
            final[1][0] = -y

        final[0][0] *= calibrationReference['unitWidth']
        final[1][0] *= calibrationReference['unitHeight']

        final[0][0] += calibrationReference['x']
        final[1][0] += calibrationReference['y']

        return final

    def processMultipleCameraFrames(self, singleCameraFrames, singleCameraConfigurations):
        """
            This function takes multiple SingleCameraFrame objects, along with the associated SingleCameraConfiguration object for each camera,
            and produces a single MultiCameraFrame object, indicating where it thinks all the people are."""

        multiCameraFrame = {
            "timestamp": singleCameraFrames[0]['timestamp'],
            "people": []
        }

        for frame in singleCameraFrames:
            cameraId = frame['cameraId']

            cameraInfo = None
            for camera in singleCameraConfigurations:
                if camera['cameraId'] == cameraId:
                    cameraInfo = camera
                    break

            if 'rotationVector' in cameraInfo and 'translationVector' in cameraInfo:
                rotationMatrix = cv2.Rodrigues(np.array(cameraInfo['rotationVector']))[0]

                for index, person in enumerate(frame['people']):
                    feet = []
                    knees = []
                    hips = []
                    shoulders = []
                    head = []
                    if person['keypoints']['left_foot']['x'] != 0:
                        feet.append(list(person['keypoints']['left_foot'].values()))
                    if person['keypoints']['right_foot']['y'] != 0:
                        feet.append(list(person['keypoints']['right_foot'].values()))

                    if person['keypoints']['left_knee']['x'] != 0:
                        knees.append(list(person['keypoints']['left_knee'].values()))
                    if person['keypoints']['right_knee']['y'] != 0:
                        knees.append(list(person['keypoints']['right_knee'].values()))

                    if person['keypoints']['left_hip']['x'] != 0:
                        hips.append(list(person['keypoints']['left_hip'].values()))
                    if person['keypoints']['right_hip']['y'] != 0:
                        hips.append(list(person['keypoints']['right_hip'].values()))

                    if person['keypoints']['left_shoulder']['x'] != 0:
                        shoulders.append(list(person['keypoints']['left_shoulder'].values()))
                    if person['keypoints']['right_shoulder']['y'] != 0:
                        shoulders.append(list(person['keypoints']['right_shoulder'].values()))

                    if person['keypoints']['left_ear']['x'] != 0:
                        head.append(list(person['keypoints']['left_ear'].values()))
                    if person['keypoints']['right_ear']['y'] != 0:
                        head.append(list(person['keypoints']['right_ear'].values()))
                    if person['keypoints']['left_eye']['x'] != 0:
                        head.append(list(person['keypoints']['left_eye'].values()))
                    if person['keypoints']['right_eye']['y'] != 0:
                        head.append(list(person['keypoints']['right_eye'].values()))
                    if person['keypoints']['nose']['y'] != 0:
                        head.append(list(person['keypoints']['nose'].values()))

                    def getStoreLocation(group, height):
                        screenLocation = np.mean(np.array(group), axis=0)

                        storeLocation = self.inverseScreenLocation(screenLocation,
                                                                   height,
                                                                   np.array(cameraInfo['rotationVector']),
                                                                   np.array(cameraInfo['translationVector']),
                                                                   np.array(cameraInfo['cameraMatrix']),
                                                                   cameraInfo['calibrationReferencePoint']
                                                                   )
                        return storeLocation

                    # Build up a list of estimated screen locations, using approximated heights

                    estimates = []
                    if (len(feet) > 0):
                        estimates.append((10, getStoreLocation(group=feet, height=10)))# 10cm, approximate height of shin off the ground, which is where the

                    if (len(knees) > 0):
                        estimates.append((5, getStoreLocation(group=knees, height=50)))# 50cm, approx where knees are

                    if (len(hips) > 0):
                        estimates.append((3, getStoreLocation(group=hips, height=80)))# 80cm where hips are

                    if (len(shoulders) > 0):
                        estimates.append((1, getStoreLocation(group=shoulders, height=150)))# 150cm where shoulders are

                    if (len(head) > 0):
                        estimates.append((1, getStoreLocation(group=head, height=165)))# 165cm eye level

                    if len(estimates) > 0:
                        # Now we create a weighted average of the various estimates, giving more weight
                        # to estimates for body parts close to the ground (so there is less uncertainty)
                        totalWeight = 0
                        for estimate in estimates:
                            totalWeight += estimate[0]

                        x = 0
                        y = 0
                        for estimate in estimates:
                            x += estimate[1][0][0] * (estimate[0] / totalWeight)
                            y += estimate[1][1][0] * (estimate[0] / totalWeight)

                        multiCameraFrame['people'].append({
                            "x": x,
                            "y": y,
                            "detectionIds": [person['detectionId']],
                            "cameraIds": [cameraInfo['cameraId']]
                        })

        # Crude algorithm - merge together any detections from different cameras which are < 50 px from each other
        # TODO: Replace this crude algorithm

        didMerge = True
        while didMerge:
            didMerge = False

            mergeDistance = 100
            personIndex1 = 0
            personIndex2 = 0
            mergePerson1 = None
            mergePersonIndex1 = None
            mergePerson2 = None
            mergePersonIndex2 = None
            minDistance = None

            while personIndex1 < len(multiCameraFrame['people']):
                personIndex2 = 0
                while personIndex2 < len(multiCameraFrame['people']):
                    if personIndex1 != personIndex2:
                        person1 = multiCameraFrame['people'][personIndex1]
                        person2 = multiCameraFrame['people'][personIndex2]

                        if len(set(person1['cameraIds']).intersection(set(person2['cameraIds']))) == 0:
                            dist = scipy.spatial.distance.euclidean(
                                [person1['x'], person1['y']],
                                [person2['x'], person2['y']]
                            )

                            if dist < mergeDistance and (minDistance is None or dist < minDistance):
                                minDistance = dist
                                mergePerson1 = person1
                                mergePersonIndex1 = personIndex1

                                mergePerson2 = person2
                                mergePersonIndex2 = personIndex2
                                break

                    personIndex2 += 1
                personIndex1 += 1

            if mergePerson1 is not None:
                mergePerson1['x'] = mergePerson1['x'] / 2 + mergePerson2['x'] / 2
                mergePerson1['y'] = mergePerson1['y'] / 2 + mergePerson2['y'] / 2

                mergePerson1['detectionIds'] = mergePerson1['detectionIds'] + mergePerson2['detectionIds']
                mergePerson1['cameraIds'] = mergePerson1['cameraIds'] + mergePerson2['cameraIds']

                del multiCameraFrame['people'][mergePersonIndex2]

        multiCameraFrame['storeId'] = singleCameraFrames[0]['storeId']

        return multiCameraFrame

    def boundingBoxForPerson(self, keypoints):
        epsilon = 1e-6
        left = min(point[0] for point in keypoints if point[0] != 0 or point[1] != 0) - epsilon
        top = min(point[1] for point in keypoints if point[0] != 0 or point[1] != 0) - epsilon
        right = max(point[0] for point in keypoints if point[0] != 0 or point[1] != 0) + epsilon
        bottom = max(point[1] for point in keypoints if point[0] != 0 or point[1] != 0) + epsilon

        return {
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
            "width": right-left,
            "height": bottom-top
        }

    def getKeypointsObject(self, keypointsArray):
        data = {}
        for index,keypoint in enumerate(self.keypointNames):
            data[keypoint] = {
                "x": keypointsArray[index][0],
                "y": keypointsArray[index][1]
            }

        return data


    def getKeypointsArray(self, keypointsObject):
        data = []
        for index,keypoint in enumerate(self.keypointNames):
            data.append([
                keypointsObject[keypoint]['x'],
                keypointsObject[keypoint]['y']
            ])

        return data


    def detectPeople(self, image, state, debugImage):
        """
            This method processes the given image, provided as a standard np [width,height,channels] array,
            and extracts the locations of people within it.

            :param image: The image to be processed
            :param state: The current state of the people detector, from the last image. None if there is no current state.
            :param debugImage: The image upon which debug information can be written
            :return: (people, state, debugImage)
        """
        if not self.poseSess:
            self.poseSess, self.poseInputs, self.poseOutputs = predict.setup_pose_prediction(self.cfg)

        if not state:
            state = {}

        # Each person data has {id, keypoints, trackers}
        currentPeople = state.get('people', [])

        # Create the tracker if it doesn't exist
        if 'tracker' not in state:
            state['tracker'] = Sort(max_age=1, min_hits=1.0)

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
                box = self.boundingBoxForPerson(detectedPerson)

                detectedPointCount = 0
                for point in detectedPerson:
                    if point[0] != 0 or point[1] != 0:
                        detectedPointCount += 1

                detection = [box['left'], box['top'], box['right'], box['bottom'], detectedPointCount / 17.0]  # the last entry is the score, which is the number of keypoints detected

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
                        'detectionId': box[4],
                        'keypoints': self.getKeypointsObject(bestMatch),
                        "bounding_box": self.boundingBoxForPerson(bestMatch)
                    }
                    newPeople.append(personData)

            currentPeople = newPeople

            self.draw_multi.draw(debugImage, self.dataset, peoplePoints)
        else:
            for person in currentPeople:
                box = person['bounding_box']
                cv2.rectangle(debugImage, (int(box['left']), int(box['top'])), (int(box['right']), int(box['bottom'])), (0, 255, 0), 3)

                textX = int(box['left']) + 10
                textY = int(box['top']) + 35

                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(debugImage, str(int(person['id'])), (textX, textY), font, 1, (0, 255, 0), 2, cv2.LINE_AA)

            # Draw people the based the result from the trackers
            if len(currentPeople) == 0:
                peoplePoints = np.reshape(np.array([]), newshape=[0, 2])
            else:
                peoplePoints = np.reshape(np.array([[self.getKeypointsArray(person['keypoints']) for person in currentPeople]]), newshape=[len(currentPeople), 17, 2])

            self.draw_multi.draw(debugImage, self.dataset, peoplePoints)

        state['people'] = currentPeople
        state['frameIndex'] = frameIndex

        for person in currentPeople:
            print("Person: ", person['detectionId'])

        return currentPeople, state, debugImage


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
            cameraMatrix = np.array([[640.0, 0.0, 320], [0.0, 480.0, 240], [0.0, 0.0, 1.0]])
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
                "distortionCoefficients": cameraDistortionCoefficients.tolist()
            }, state, debugImage)
        else:
            return (None, state, debugImage)


    def processMultiCameraFrameTimeSeries(self, multiCameraFrame, state, storeConfiguration):
        """
            This method is used to process the sequence of multi-camera-frame objects. It creates TimeSeriesFrame objects.

            :param multiCameraFrame: The current multi camera frame.
            :param state: The current state of the multi-camera-frame system. This contains arbitrary data which can be pickled in python
            :param storeConfiguration: The store configuration
            :return: (timeSeriesFrame, state)
        """
        if 'tracker' not in state:
            state['tracker'] = Sort(max_age=5, min_hits=4, mode='euclidean')

        if 'people' not in state:
            state['people'] = {}

        trackerBoxSize = 500

        tracker = state['tracker']
        detections = [[person['x']-trackerBoxSize/2, person['y']-trackerBoxSize/2, person['x']+trackerBoxSize/2, person['y']+trackerBoxSize/2, 1.0] for person in multiCameraFrame['people']]

        tracked = tracker.update(np.array(detections))

        timeSeriesFrame = {
            'storeId': multiCameraFrame['storeId'],
            'timestamp': multiCameraFrame['timestamp'],
            'people': []
        }

        # Set all existing people as invisible
        for personKey, person in state['people'].items():
            if person['state'] != 'exited':
                person['state'] = 'hidden'

        for personIndex, boundingBox in enumerate(tracked):
            visitorId = str(multiCameraFrame['storeId']) + "-" + str(boundingBox[4])
            newPersonData = {
                'visitorId': visitorId,
                "x": (boundingBox[0]/2 + boundingBox[2]/2) / storeConfiguration['storeMap']['width'],
                "y": (boundingBox[1]/2 + boundingBox[3]/2) / storeConfiguration['storeMap']['height'],
                "timestamp": multiCameraFrame['timestamp'],
                "zone": None
            }

            relX = newPersonData["x"]
            relY = newPersonData["y"]

            # Determine what zone this person is located within
            for zone in storeConfiguration['zones']:
                if relX >= zone['left'] and relX <= zone['right'] and relY >= zone['top'] and relY <= zone['bottom']:
                    newPersonData['zone'] = zone['id']
                    break

            if visitorId in state['people']:
                newPersonData['state'] = 'visible'
            else:
                newPersonData['state'] = 'entered'

            state['people'][visitorId] = newPersonData
            timeSeriesFrame['people'].append(newPersonData)

        # Anyone remaining, we assume has exited
        for personKey, person in state['people'].items():
            if person['state'] == 'hidden':
                person['state'] = 'exited'
                timeSeriesFrame['people'].append(person)

        timeSeriesFrame['visitorIds'] = [person['visitorId'] for person in timeSeriesFrame['people']]

        return timeSeriesFrame, state


    def createVisitSummary(self, visitorId, timeSeriesFrames, storeConfiguration):
        """
            :param visitorId: The visitor id to produce the summary for.
            :param timeSeriesFrames: An array containing all of the time series frames which contained the visitor
            :param storeConfiguration: The store configuration
            :return: (timeSeriesFrame, state)
        :return:
        """
        visitSummary = {
            "storeId": storeConfiguration['storeId'],
            "visitorId": visitorId
        }

        # Compute the track
        visitSummary['track'] = []

        for frame in timeSeriesFrames:
            for person in frame['people']:
                if person['visitorId'] == visitorId:
                    visitSummary['track'].append({
                        "x": person['x'],
                        "y": person['y'],
                        "zoneId": person['zone'],
                        "timestamp": person['timestamp']
                    })

        # pprint(visitSummary['track'])

        # Now we compute the amount of time spent in each zone
        # for each track.
        # Minimum value is applied here just in case a track was a result of a fleeting detection
        totalTime = max(0.1, (datetime.strptime(visitSummary['track'][-1]['timestamp'], "%Y-%m-%dT%H:%M:%S.%f") - datetime.strptime(visitSummary['track'][0]['timestamp'], "%Y-%m-%dT%H:%M:%S.%f")).total_seconds())
        visitSummary['timeSpentSeconds'] = totalTime

        zoneMap = {}
        zones = []
        for zone in storeConfiguration['zones']:
            newZone = {
                "zoneId": str(zone['id']),
                "timeSpentSeconds": 0,
                "timeSpentPercentage": 0
            }
            zones.append(newZone)
            zoneMap[str(zone['id'])] = newZone

        # Add in a zone for when a person falls outside a zone
        nullZone = {
            "zoneId": 'None',
            "timeSpentSeconds": 0,
            "timeSpentPercentage": 0
        }
        zoneMap['None'] = nullZone
        zones.append(nullZone)

        # Compute the time spent in each zone
        for pointIndex, point in enumerate(visitSummary['track'][:-1]):
            currentPoint = visitSummary['track'][pointIndex]
            nextPoint = visitSummary['track'][pointIndex + 1]

            # Compute the time between the next entry and this one
            elapsed = (datetime.strptime(nextPoint['timestamp'], "%Y-%m-%dT%H:%M:%S.%f") - datetime.strptime(currentPoint['timestamp'], "%Y-%m-%dT%H:%M:%S.%f")).total_seconds()

            # Allocate half the time to the current zone, half the time to the next zone
            zoneMap[str(currentPoint['zoneId'])]['timeSpentSeconds'] += elapsed/2
            zoneMap[str(nextPoint['zoneId'])]['timeSpentSeconds'] += elapsed/2

        # Now compute the percentage time in each zone
        maxZonePercent = 0
        for zone in zones:
            zone['timeSpentPercentage'] = zone['timeSpentSeconds'] / totalTime
            if zone['timeSpentPercentage'] > maxZonePercent:
                maxZonePercent = zone['timeSpentPercentage']
                visitSummary['concentrationZoneId'] = str(zone['zoneId'])

        return visitSummary

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

