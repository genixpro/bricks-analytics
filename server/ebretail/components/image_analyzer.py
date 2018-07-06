import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", "lib"))
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", "lib", "pose-tensorflow"))
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", "lib", "BlurDetection2"))

import os
import threading
import numpy as np
from pprint import pprint
import scipy.linalg
import scipy.spatial
import cv2
import uuid
import datetime
from datetime import datetime
from sort import Sort
from blur_detection import estimate_blur

globalSharedInstanceLock = threading.RLock()
globalSharedInstance = None

class ImageAnalyzer:
    """
        This class is responsible for handling the core processing of images. It does not handle the
        surrounding logic such as maintaining database records or dividing the work between different
        workers.

        This class is meant to handle just that core image processing piece.
    """

    def __init__(self, initializeTracking = False):
        self.trackingSession = None

        # How frequent does the person detector run
        self.personDetectorFrequency = 1
        self.detectorTrackerMaxDistance = 50
        self.trackerBoxWidth = 30
        self.trackerBoxHeight = 30
        self.trackerMaxAverageDist = 50

        self.poseSess = None
        
        self.validationEnabled = True

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
        #
        # # These hyper parameters were the human defined starting point
        # self.hyperParameters = {
        #     'calibration_point_size': 10, # Our calibration checkboard consists of 10cm squares
        #     'eye_height': 165, # 165cm eye level
        #     'eye_location_estimate_weight': 1,
        #     'foot_height': 10,# 10cm, approximate height of shin off the ground, which is where the detector usually detects
        #     'foot_location_estimate_weight': 10,
        #     'hip_height': 80, # 80cm where hips are
        #     'hip_location_estimate_weight': 3,
        #     'image_tracker_feature_vector_threshold': 0.3,
        #     'image_tracker_feature_vector_update_speed': 0.3,
        #     'image_tracker_iou_weight': 1.0,
        #     'image_tracker_match_score_threshold': 0.2,
        #     'image_tracker_max_age': 3,
        #     'image_tracker_min_hits': 4,
        #     'image_tracker_min_keypoints': 4,
        #     'image_tracker_similarity_weight': 1.5,
        #     'knee_height': 50,# 50cm, approx where knees are,
        #     'knee_location_estimate_weight': 5,
        #     'shoulder_height': 150, # 150cm where shoulders are
        #     'shoulder_location_estimate_weight': 1,
        #     'store_map_merge_distance': 100, # 100px merge distance
        #     'store_map_tracker_euclid_mode_distance_weight': 1.0,
        #     'store_map_tracker_euclid_mode_similarity_weight': 2.0,
        #     'store_map_tracker_euclid_threshold': 200,
        #     'store_map_tracker_feature_vector_threshold': 0.3,
        #     'store_map_tracker_feature_vector_update_speed': 0.3,
        #     'store_map_tracker_match_score_threshold': 0.2,
        #     'store_map_tracker_max_age': 5,
        #     'store_map_tracker_min_hits': 3,
        #     'store_map_tracker_new_track_min_dist': 300
        # }

        # These hyper parameters were optimized on bricks-analytics-data/session1/capture1 on June 21, 2018
        self.hyperParameters = {
            'calibration_point_size': 10,
             'eye_height': 165,
             'eye_location_estimate_weight': 1,
             'foot_height': 10,
             'foot_location_estimate_weight': 9.340166533733008,
             'hip_height': 81.27174673173252,
             'hip_location_estimate_weight': 3,
             'image_tracker_feature_vector_threshold': 0.3,
             'image_tracker_feature_vector_update_speed': 0.2347931112486611,
             'image_tracker_iou_weight': 3.2750416652073624,
             'image_tracker_match_score_threshold': 0.2,
             'image_tracker_max_age': 7.0,
             'image_tracker_min_hits': 3.0,
             'image_tracker_min_keypoints': 4,
             'image_tracker_similarity_weight': 2.6199129306999853,
             'knee_height': 50,
             'knee_location_estimate_weight': 9.954308615784647,
             'shoulder_height': 173.90076091454534,
             'shoulder_location_estimate_weight': 1,
             'store_map_merge_distance': 65.0,
             'store_map_tracker_euclid_mode_distance_weight': 1.0,
             'store_map_tracker_euclid_mode_similarity_weight': 2.0,
             'store_map_tracker_euclid_threshold': 207.15254555541597,
             'store_map_tracker_feature_vector_threshold': 0.3,
             'store_map_tracker_feature_vector_update_speed': 0.15995710971563637,
             'store_map_tracker_match_score_threshold': 0.2,
             'store_map_tracker_max_age': 6.0,
             'store_map_tracker_min_hits': 7.0,
             'store_map_tracker_new_track_min_dist': 300
        }

        self.trackingFeatureDim = 128

        self.detectionCache = {
            'people': {},
            'calibrationObjects': {}
        }

        if initializeTracking:
            self.initializeTrackingSession()

    def disableValidation(self):
        self.validationEnabled = False

    def setHyperParameters(self, hyperParameters):
        self.hyperParameters = hyperParameters

    def initializeTrackingSession(self):
        from multiperson.visualize import PersonDraw
        from multiperson.predict import SpatialModel
        from dataset.factory import create as create_dataset
        from config import load_config
        from nnet import predict
        import tensorflow as tf

        # Configure the pose detection model
        self.cfg = load_config(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "config", "pose_cfg_multi.yaml"))
        self.dataset = create_dataset(self.cfg)
        self.sm = SpatialModel(self.cfg)
        self.sm.load()
        self.draw_multi = PersonDraw()

        trackingCheckpointFilename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", "lib", "deep-sort", "mars-small128.pb")
        trackingInputName = 'images'
        trackingOutputName = 'features'

        config = tf.ConfigProto(
            device_count={'GPU': 0}
        )
        self.trackingSession = tf.Session(config=config)
        with tf.gfile.GFile(trackingCheckpointFilename, "rb") as file_handle:
            graph_def = tf.GraphDef()
            graph_def.ParseFromString(file_handle.read())
        tf.import_graph_def(graph_def, name="net")
        self.trackingInputVar = tf.get_default_graph().get_tensor_by_name("net/%s:0" % trackingInputName)
        self.trackingOutputVar = tf.get_default_graph().get_tensor_by_name("net/%s:0" % trackingOutputName)
        self.trackingFeatureDim = self.trackingOutputVar.get_shape().as_list()[-1]
        self.trackingImageShape = self.trackingInputVar.get_shape().as_list()[1:]

        self.poseSess, self.poseInputs, self.poseOutputs = predict.setup_pose_prediction(self.cfg)

    def extractTrackingCrop(self, image, bbox, crop_shape, padding=50):
        """Extract image patch for a given bounding box, to be used in creating the tracking sort metric.
            :param image: A numpy array representing the image
            :param box: Bounding box for the person
            :param crop_shape: Bounding box for the person
        """
        width = len(image)
        height = len(image[0])

        bbox = np.array(bbox)

        bbox[0] -= padding
        bbox[1] -= padding
        bbox[2] += padding
        bbox[3] += padding

        if crop_shape is not None:
            # correct aspect ratio to patch shape
            target_aspect = float(crop_shape[1]) / crop_shape[0]
            new_width = target_aspect * (bbox[3] - bbox[1])

            bbox[0] -= (new_width - (bbox[2] - bbox[0])) / 2
            bbox[2] += (new_width - (bbox[2] - bbox[0])) / 2

        bbox = bbox.astype(np.int)

        # clip at image boundaries
        bbox[:2] = np.maximum(0, bbox[:2])
        bbox[2:] = np.minimum(np.array([height-1, width-1]), bbox[2:])
        if np.any(bbox[:2] >= bbox[2:]):
            return None
        sx, sy, ex, ey = bbox
        image = image[sy:ey, sx:ex]
        image = cv2.resize(image, tuple(crop_shape[::-1]))
        return image

    def processSingleCameraImage(self, image, metadata, state, debugImage):
        """
            This method is used to process a single image from a single camera. It produces a SingleCameraFrame object.

            :param image: A numpy array representing the image.
            :param metadata: A python dictionary containing storeId, cameraId, and timestamp metadata objects.
            :param state: A state object, representing carryover state from the previous processed image.
            :param debugImage: A numpy array, representing a clone of the image, to which debug information can be written to.
            :return: A tuple (singleCameraFrame, state, personImages) representing the resulting SingleCameraFrame object, and state to be carried over to the next image. In addition, images of people to be saved to the server are returned.
        """

        peopleState = state.get('peopleState', None)
        calibrationDetectionState = state.get('calibrationDetectionState', None)
        cacheId = metadata.get('cacheId', None)

        try:
            # Use the global image analyzer to do all the general purpose detections
            people, peopleState, debugImage, personImages = self.detectPeople(image, peopleState, debugImage, cacheId)

            for person in people:
                oldDetectionId = person['detectionId']
                person['detectionId'] = str(metadata['storeId']) + "-" + str(metadata['cameraId']) + "-" + str(person['detectionId'])
                if oldDetectionId in personImages:
                    personImages[person['detectionId']] = personImages[oldDetectionId]
                    del personImages[oldDetectionId]

            calibrationObject, calibrationDetectionState, debugImage = self.detectCalibrationObject(image, calibrationDetectionState, debugImage, cacheId)
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

        if self.validationEnabled:
            from ebretail.models.validate import validateSingleCameraFrame
            validateSingleCameraFrame(singleCameraFrame)

        return (singleCameraFrame, state, personImages)


    def inverseScreenLocation(self, location, height, rotationVector, translationVector, cameraMatrix, calibrationReference):
        rotationMatrix = cv2.Rodrigues(np.array(rotationVector))[0]

        # Add in another dimension
        location = np.array([[location[0]], [location[1]], [1]])

        calibrationPointsSize = self.hyperParameters['calibration_point_size']

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
                        estimates.append((self.hyperParameters['foot_location_estimate_weight'], getStoreLocation(group=feet, height=self.hyperParameters['foot_height'])))

                    if (len(knees) > 0):
                        estimates.append((self.hyperParameters['knee_location_estimate_weight'], getStoreLocation(group=knees, height=self.hyperParameters['knee_height'])))

                    if (len(hips) > 0):
                        estimates.append((self.hyperParameters['hip_location_estimate_weight'], getStoreLocation(group=hips, height=self.hyperParameters['hip_height'])))

                    if (len(shoulders) > 0):
                        estimates.append((self.hyperParameters['shoulder_location_estimate_weight'], getStoreLocation(group=shoulders, height=self.hyperParameters['shoulder_height'])))

                    if (len(head) > 0):
                        estimates.append((self.hyperParameters['eye_location_estimate_weight'], getStoreLocation(group=head, height=self.hyperParameters['eye_height'])))

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
                            "averageFeatureVector": person['featureVector'],
                            "cameraIds": [cameraInfo['cameraId']]
                        })

        # Crude algorithm - merge together any detections from different cameras which are < mergeDistance px from each other
        # TODO: Replace this crude algorithm

        didMerge = True
        while didMerge:
            didMerge = False

            mergeDistance = self.hyperParameters['store_map_merge_distance']
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
                if mergePerson1['averageFeatureVector'] is not None and mergePerson2['averageFeatureVector'] is not None:
                    mergePerson1['averageFeatureVector'] = np.array(mergePerson1['averageFeatureVector']) + np.array(mergePerson2['averageFeatureVector'])
                elif mergePerson1['averageFeatureVector'] is None and mergePerson2['averageFeatureVector'] is not None:
                    mergePerson1['averageFeatureVector'] = np.array(mergePerson2['averageFeatureVector'])

                del multiCameraFrame['people'][mergePersonIndex2]
                didMerge = True

        # Now divide all the average feature vectors by the number of detections.
        for person in multiCameraFrame['people']:
            if person['averageFeatureVector'] is not None:
                person['averageFeatureVector'] = (np.array(person['averageFeatureVector']) / len(person['detectionIds'])).tolist()

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


    def detectPeople(self, image, state, debugImage, cacheId=None):
        """
            This method processes the given image, provided as a standard np [width,height,channels] array,
            and extracts the locations of people within it.

            :param image: The image to be processed
            :param state: The current state of the people detector, from the last image. None if there is no current state.
            :param debugImage: The image upon which debug information can be written
            :param cacheId: The cacheId for person detections, used for speeding up tests and optimization
            :return: (people, state, debugImage, personImages)
        """

        if not (cacheId is not None and cacheId in self.detectionCache['people']):
            if not self.trackingSession:
                self.initializeTrackingSession()
        if not state:
            state = {
                'stateId': str(uuid.uuid4())
            }

        width = len(image)
        height = len(image[0])

        # Each person data has {id, keypoints, trackers}
        currentPeople = state.get('people', [])

        # Create the tracker if it doesn't exist
        if 'tracker' not in state:
            state['tracker'] = Sort(
                max_age=self.hyperParameters['image_tracker_max_age'],
                min_hits=self.hyperParameters['image_tracker_min_hits'],
                featureVectorSize=self.trackingFeatureDim,
                feature_vector_update_speed=self.hyperParameters['image_tracker_feature_vector_update_speed'],
                match_score_threshold=self.hyperParameters['image_tracker_match_score_threshold'],
                feature_vector_threshold=self.hyperParameters['image_tracker_feature_vector_threshold'],
                iou_mode_iou_weight=self.hyperParameters['image_tracker_iou_weight'],
                iou_mode_similarity_weight=self.hyperParameters['image_tracker_similarity_weight'],
            )

        tracker = state['tracker']

        # Every nth frame, we call the heavy weight detection model and feed it to the tracker
        frameIndex = state.get('frameIndex', 0)
        frameIndex += 1
        if frameIndex % self.personDetectorFrequency == 0:
            time = datetime.now()

            detectionBoxes = []
            featureVectors = []
            newPeople = []
            peoplePoints = []
            if cacheId is not None and cacheId in self.detectionCache['people']:
                detectionBoxes = self.detectionCache['people'][cacheId]['detectionBoxes']
                featureVectors = self.detectionCache['people'][cacheId]['featureVectors']
                peoplePoints = self.detectionCache['people'][cacheId]['peoplePoints']
            else:
                # Only make these imports if we have to
                from multiperson.predict import eval_graph, get_person_conf_multicut
                from multiperson.detections import extract_detections
                from dataset.pose_dataset import data_to_input
                from nnet import predict

                # Compute prediction with the CNN
                image_batch = data_to_input(image)
                outputs_np = self.poseSess.run(self.poseOutputs, feed_dict={self.poseInputs: image_batch})
                scmap, locref, pairwise_diff = predict.extract_cnn_output(outputs_np, self.cfg, self.dataset.pairwise_stats)

                # Convert the cnn output into the set of detected people
                detections = extract_detections(self.cfg, scmap, locref, pairwise_diff)
                unLab, pos_array, unary_array, pwidx_array, pw_array = eval_graph(self.sm, detections)
                peoplePoints = get_person_conf_multicut(self.sm, unLab, unary_array, pos_array)

                # Filter out detections that have less then 4 keypoints ( use /2 here because there are two dimensions, x and y)
                peoplePoints = np.array([person for person in peoplePoints if (np.count_nonzero(person) / 2) >= self.hyperParameters['image_tracker_min_keypoints']])

                # Now feed these detections through the tracker
                for detectedPersonIndex, detectedPerson in enumerate(peoplePoints):
                    # Compute this persons outer bounding box
                    box = self.boundingBoxForPerson(detectedPerson)

                    detection = np.array([box['left'], box['top'], box['right'], box['bottom'], 1.0] + [0] * self.trackingFeatureDim)  # the middle entry is the score, which doesn't matter for this trackker. Feature vector after that.

                    croppedPerson = self.extractTrackingCrop(image, detection[:4], self.trackingImageShape[:-1])
                    if croppedPerson is not None:
                        featureVector = self.trackingSession.run(self.trackingOutputVar, feed_dict={self.trackingInputVar: [croppedPerson]})
                        detection[5:] = featureVector[0]
                        featureVectors.append(featureVector[0].tolist())
                    else:
                        featureVectors.append(None)

                    detectionBoxes.append(detection)

            if cacheId is not None:
                self.detectionCache['people'][cacheId] = {
                    'detectionBoxes': detectionBoxes,
                    'featureVectors': featureVectors,
                    'peoplePoints': peoplePoints
                }

            for box in detectionBoxes:
                cv2.rectangle(debugImage, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), (0, 0, 255), 3)

            trackedBoxes = tracker.update(np.array(detectionBoxes))

            trackedVectors = [box[5] != -1 and featureVectors[int(box[5])] or None for box in trackedBoxes]

            for box in trackedBoxes:
                cv2.rectangle(debugImage, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), (0, 255, 0), 3)

                textX = int(box[0]) + 10
                textY = int(box[1]) + 35

                font = cv2.FONT_HERSHEY_SIMPLEX
                cv2.putText(debugImage, str(int(box[4])), (textX, textY), font, 1, (0, 255, 0), 2, cv2.LINE_AA)

            # Now we have a bunch of tracked boxes. Find which person goes with which tracked box
            for boxIndex, box in enumerate(trackedBoxes):
                if int(box[5]) >= 0:
                    person = peoplePoints[int(box[5])]
                    personData = {
                        'detectionId': str(int(box[4])),
                        'keypoints': self.getKeypointsObject(person),
                        "bounding_box": self.boundingBoxForPerson(person),
                        "featureVector": trackedVectors[boxIndex]
                    }
                    newPeople.append(personData)

            currentPeople = newPeople

            # self.draw_multi.draw(debugImage, self.dataset, peoplePoints)
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

        # Now, grab an image of each person detection.
        # If the person detection has more points then has been detected for that person before,
        # or it has the same or -1 the number of points detected, but it is a less blurry image
        # of that person, then we include the image of that person.
        if 'bestImages' not in state:
            state['bestImages'] = {}

        personImages = {}
        for person in currentPeople:
            bestImage = state['bestImages'].get(person['detectionId'], None)

            personWidth = person['bounding_box']['right'] - person['bounding_box']['left']
            personHeight = person['bounding_box']['bottom'] - person['bounding_box']['top']

            cropWidth = max(150, personWidth + 100)
            cropHeight = max(150, personHeight + 100)

            centerX = person['bounding_box']['left']/2 + person['bounding_box']['right']/2
            centerY = person['bounding_box']['top']/2 + person['bounding_box']['bottom']/2

            cropTop = max(0, centerY - cropHeight / 2)
            cropBottom = min(centerY + cropHeight /2, height - 1)
            cropLeft = max(0, centerX - cropWidth/2)
            cropRight = min(centerX + cropWidth / 2, width - 1)

            personWithinCropLeft = person['bounding_box']['left'] - cropLeft
            personWithinCropRight = person['bounding_box']['right'] - cropLeft
            personWithinCropTop = person['bounding_box']['top'] - cropTop
            personWithinCropBottom = person['bounding_box']['bottom'] - cropTop

            # If we can't get a decent sized cropped image, and there is already an
            # image, then ignore this one.
            if ((cropRight - cropLeft) < 10 or (cropBottom - cropTop) < 10):
                continue

            croppedImage = np.copy(image[int(cropTop):int(cropBottom), int(cropLeft):int(cropRight)])
            croppedImage = cv2.cvtColor(croppedImage, cv2.COLOR_BGR2RGB)

            cv2.rectangle(croppedImage, (int(personWithinCropLeft), int(personWithinCropTop)), (int(personWithinCropRight), int(personWithinCropBottom)), (0, 255, 0), 3)

            try:
                blur_map, score, blurry = estimate_blur(croppedImage)
            except cv2.error:
                # Ignore error, assume maximum blurriness
                score = 0

            points = 0
            for key in self.keypointNames:
                if person['keypoints'][key]['x'] and person['keypoints'][key]['y']:
                    points += 1

            if bestImage is None:
                personImages[person['detectionId']] = croppedImage
                state['bestImages'][person['detectionId']] = {
                    'points': points,
                    'blurriness': score
                }
            elif points > (bestImage['points'] + 1):
                personImages[person['detectionId']] = croppedImage
                state['bestImages'][person['detectionId']] = {
                    'points': points,
                    'blurriness': score
                }
            elif points >= (bestImage['points']) and score > bestImage['blurriness']:
                personImages[person['detectionId']] = croppedImage
                state['bestImages'][person['detectionId']] = {
                    'points': points,
                    'blurriness': score
                }

        state['people'] = currentPeople
        state['frameIndex'] = frameIndex

        return currentPeople, state, debugImage, personImages


    def detectCalibrationObject(self, image, state, debugImage, cacheId=None):
        """
            Tries to detect the presence of the calibration object, which is just a standard checkerboard pattern.

            :param image: A standard np image array, [width, height, batchSize]
            :param state: The current state of the calibration object detector, from the last image. None if there is no current state.
            :param debugImage: An image upon which the debugging information can be written
            :return (calibrationData, state, debugImage)
        """
        if cacheId is not None:
            if cacheId in self.detectionCache['calibrationObjects']:
                return self.detectionCache['calibrationObjects'][cacheId]

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

        calibrationObject = None

        if found:
            cameraMatrix = np.array([[640.0, 0.0, 320], [0.0, 480.0, 240], [0.0, 0.0, 1.0]])
            cameraDistortionCoefficients = np.array([[0.0, 0.0, 0.0, 0.0, 0.0]])
            cameraRotationVector = None
            cameraTranslationVector = None

            (ret, cameraRotationVector, cameraTranslationVector) = cv2.solvePnP(objp, corners, cameraMatrix, cameraDistortionCoefficients)

            # Update the debug image with the calibration object drawn on
            cv2.drawChessboardCorners(debugImage, chessBoardSize, corners, found)

            calibrationObject = {
                "cameraMatrix": cameraMatrix.tolist(),
                "rotationVector": cameraRotationVector.tolist(),
                "translationVector": cameraTranslationVector.tolist(),
                "distortionCoefficients": cameraDistortionCoefficients.tolist()
            }

        if cacheId is not None:
            self.detectionCache['calibrationObjects'][cacheId] = (calibrationObject, state, debugImage)

        return (calibrationObject, state, debugImage)


    def processMultiCameraFrameTimeSeries(self, multiCameraFrame, state, storeConfiguration):
        """
            This method is used to process the sequence of multi-camera-frame objects. It creates TimeSeriesFrame objects.

            :param multiCameraFrame: The current multi camera frame.
            :param state: The current state of the multi-camera-frame system. This contains arbitrary data which can be pickled in python
            :param storeConfiguration: The store configuration
            :return: (timeSeriesFrame, state)
        """
        if 'tracker' not in state:
            state['tracker'] = Sort(
                max_age=self.hyperParameters['store_map_tracker_max_age'],
                min_hits=self.hyperParameters['store_map_tracker_min_hits'],
                mode='euclidean',
                featureVectorSize=128,
                new_track_min_dist=self.hyperParameters['store_map_tracker_new_track_min_dist'],
                feature_vector_update_speed=self.hyperParameters['store_map_tracker_feature_vector_update_speed'],
                match_score_threshold=self.hyperParameters['store_map_tracker_match_score_threshold'],
                feature_vector_threshold=self.hyperParameters['store_map_tracker_feature_vector_threshold'],
                euclid_threshold=self.hyperParameters['store_map_tracker_euclid_threshold'],
                euclid_mode_similarity_weight=self.hyperParameters['store_map_tracker_euclid_mode_similarity_weight'],
                euclid_mode_distance_weight=self.hyperParameters['store_map_tracker_euclid_mode_distance_weight']
            )

        if 'people' not in state:
            state['people'] = {}

        if 'zones' not in storeConfiguration:
            storeConfiguration['zones'] = []

        trackerBoxSize = 500

        tracker = state['tracker']

        featureVector = [[0] * 128] * len(multiCameraFrame['people'])
        for personIndex, person in enumerate(multiCameraFrame['people']):
            if person['averageFeatureVector'] is not None:
                featureVector[personIndex] = person['averageFeatureVector']

        detections = []
        for personIndex, person in enumerate(multiCameraFrame['people']):
            allowTrackCreationDeletion = True

            # Determine what zone this detection is located within
            for zone in storeConfiguration['zones']:
                relX = person['x'] / storeConfiguration['storeMap']['width']
                relY = person['y'] / storeConfiguration['storeMap']['height']
                if relX >= zone['left'] and relX <= zone['right'] and relY >= zone['top'] and relY <= zone['bottom']:
                    # This is the correct zone.
                    # If this is not an entry zone,
                    # we don't allow the track to appear or disappear
                    if 'zoneType' in zone and zone['zoneType'] != 'entry':
                        allowTrackCreationDeletion = False
                    break

            detection = [
                            person['x'] - trackerBoxSize / 2,
                            person['y'] - trackerBoxSize / 2,
                            person['x'] + trackerBoxSize / 2,
                            person['y'] + trackerBoxSize / 2,
                            float(allowTrackCreationDeletion)
                        ] + featureVector[personIndex]
            detections.append(detection)
            break

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
            visitorId = str(multiCameraFrame['storeId']) + "-" + str(int(boundingBox[4]))

            if int(boundingBox[5]) > -1:
                multiCameraFramePerson = multiCameraFrame['people'][int(boundingBox[5])]
                detectionIds = multiCameraFramePerson['detectionIds']
            else:
                detectionIds = []

            newPersonData = {
                'visitorId': visitorId,
                'detectionIds': detectionIds,
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

        pprint(timeSeriesFrame)

        return timeSeriesFrame, state

    def showCameraCalibrationOnStoreMap(self, storeMapImage, cameraConfiguration):
        """
            This function draws the ground plane of the camera onto the store map as a grid. This allows
            you to easily view the calibration of that store map.

            :param storeMapImage:
            :param cameraConfiguration:
            :return:
        """

        storeMapImage = storeMapImage.copy()
        gridWidth = 10
        gridHeight = 10

        columns = []
        for x in range(gridWidth+1):
            row = []
            for y in range(gridHeight+1):
                location = [(cameraConfiguration['width'] / 10) * x, (cameraConfiguration['height'] / 10) * y]
                position = self.inverseScreenLocation(
                    location=location,
                    height=0,
                    rotationVector=np.array(cameraConfiguration['rotationVector']),
                    translationVector=np.array(cameraConfiguration['translationVector']),
                    cameraMatrix=np.array(cameraConfiguration['cameraMatrix']),
                    calibrationReference=cameraConfiguration['calibrationReferencePoint']
                )

                row.append((int(position[0]), int(position[1])))

            columns.append(row)

        font = cv2.FONT_HERSHEY_SIMPLEX
        textScale = 0.5

        mainColor = (0, 0, 255, 255)
        lineThickness = 2
        textThickness = 1
        for x in range(gridWidth):
            for y in range(gridHeight):
                topLeft = columns[x][y]
                topRight = columns[x + 1][y]
                bottomLeft = columns[x][y + 1]
                bottomRight = columns[x + 1][y + 1]

                cv2.line(storeMapImage, topLeft, topRight, mainColor, lineThickness)
                cv2.line(storeMapImage, topLeft, bottomLeft, mainColor, lineThickness)
                cv2.line(storeMapImage, topRight, bottomRight, mainColor, lineThickness)
                cv2.line(storeMapImage, bottomLeft, bottomRight, mainColor, lineThickness)

                centerX = int(topLeft[0]/2 + bottomRight[0] / 2)
                centerY = int(topLeft[1]/2 + bottomRight[1] / 2)

                cv2.putText(storeMapImage, '(' + str(x) + ',' + str(y) + ')',(centerX - 15, centerY - 10), font, textScale, mainColor, textThickness, cv2.LINE_AA)

        return storeMapImage

    def showCameraCalibrationGridOnCameraImage(self, cameraImage, cameraConfiguration):
        cameraImage = cameraImage.copy()

        font = cv2.FONT_HERSHEY_SIMPLEX
        textScale = 0.5

        mainColor = (255, 255, 255, 255)
        outlineColor = (0, 0, 128, 255)

        lineThickness = 1
        outlineThickness = 3
        textThickness = 1
        textOutlineThickness = 3

        gridWidth = 10
        gridHeight = 10

        textOffsetX = 5
        textOffsetY = 18

        startX = outlineThickness/2
        startY = outlineThickness/2

        imageWidth = cameraConfiguration['width'] - startX*2
        imageHeight = cameraConfiguration['height'] - startY*2

        # First draw all the outlines
        for x in range(gridWidth):
            for y in range(gridHeight):
                left = int(imageWidth * x / gridWidth + startX)
                right = int(imageWidth * (x+1) / gridWidth + startX)

                top = int(imageHeight * y / gridHeight + startY)
                bottom = int(imageHeight * (y+1) / gridHeight + startY)

                topLeft = (left, top)
                topRight = (right, top)
                bottomLeft = (left, bottom)
                bottomRight = (right, bottom)

                cv2.line(cameraImage, topLeft, topRight, outlineColor, outlineThickness)
                cv2.line(cameraImage, topLeft, bottomLeft, outlineColor, outlineThickness)
                cv2.line(cameraImage, topRight, bottomRight, outlineColor, outlineThickness)
                cv2.line(cameraImage, bottomLeft, bottomRight, outlineColor, outlineThickness)
                cv2.putText(cameraImage, '(' + str(x) + ',' + str(y) + ')',(left + textOffsetX, top + textOffsetY), font, textScale, outlineColor, textOutlineThickness, cv2.LINE_AA)

        # Now draw the main lines and text in a different color and with a thinner line.
        # This helps the lines to be more visible whether the image is bright or dark
        for x in range(gridWidth):
            for y in range(gridHeight):
                left = int(imageWidth * x / gridWidth + startX)
                right = int(imageWidth * (x+1) / gridWidth + startX)

                top = int(imageHeight * y / gridHeight + startY)
                bottom = int(imageHeight * (y+1) / gridHeight + startY)

                topLeft = (left, top)
                topRight = (right, top)
                bottomLeft = (left, bottom)
                bottomRight = (right, bottom)

                cv2.line(cameraImage, topLeft, topRight, mainColor, lineThickness)
                cv2.line(cameraImage, topLeft, bottomLeft, mainColor, lineThickness)
                cv2.line(cameraImage, topRight, bottomRight, mainColor, lineThickness)
                cv2.line(cameraImage, bottomLeft, bottomRight, mainColor, lineThickness)

                # Draw the text one pixel up and to the left. This helps make it more legible and gives it a 3d effect.
                cv2.putText(cameraImage, '(' + str(x) + ',' + str(y) + ')',(left + textOffsetX - 1, top + textOffsetY - 1), font, textScale, mainColor, textThickness, cv2.LINE_AA)

        return cameraImage

    @staticmethod
    def sharedInstance(initializeTracking = False):
        global globalSharedInstance
        global globalSharedInstanceLock
        with globalSharedInstanceLock:
            if globalSharedInstance is not None:
                return globalSharedInstance
            else:
                globalSharedInstance = ImageAnalyzer(initializeTracking = initializeTracking)
                return globalSharedInstance

