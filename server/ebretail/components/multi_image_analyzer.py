import time
from datetime import datetime, timedelta

import concurrent.futures
import sched
import threading
import cv2
import requests
from PIL import Image
import io
import pymongo
import numpy as np
import scipy
from pprint import pprint
import scipy.linalg
import bson.json_util


class MultiImageAnalyzer:
    """
       This is the multi-image analyzer. This is an ongoing process which continuously processes incoming frames
    """
    def __init__(self, db, getMessagingChannel):
        self.db = db
        # Admitably this is a bit of a hack the getMessagingChannel thing
        self.getMessagingChannel = getMessagingChannel
        self.scheduler = sched.scheduler()
        self.schedulerThread = threading.Thread(target=lambda: self.runSchedulerThread())
        self.scheduledFrames = {}
        self.frameExecutor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

        self.schedulerThread.start()

    def main(self):
        imagesCollection = self.db.processedImages
        framesCollection = self.db.frames

        # First, get all the frames which haven't been processed
        try:
            for change in framesCollection.watch([{'$match': {'operationType': {"$in": ['insert', 'update']}}}]):
                if 'fullDocument' in change:
                    data = change['fullDocument']
                else:
                    data = framesCollection.find_one(change['documentKey'])

                if data['needsUpdate']:
                    if data['frameNumber'] in self.scheduledFrames:
                        self.scheduledFrames[data['frameNumber']].cancel()

                    self.scheduler.enter(5, 0, self.processFrame, (data,))
        except pymongo.errors.PyMongoError as e:
            # The ChangeStream encountered an unrecoverable error or the
            # resume attempt failed to recreate the cursor.
            print(e)

    def runSchedulerThread(self):
        while True:
            self.scheduler.run()
            time.sleep(0.1)


    def getLocationInStore(self, pixelX, pixelY):
        """
            This method returns the location within the store for a given detection.
        """
        pass

    def inverseScreenLocation(self, location, height, rotationMatrix, translationVector, cameraMatrix):
        # Add in another dimension
        location = np.array([[location[0]], [location[1]], [1]])

        calibrationPointsSize = 10 # Our calibration checkboard consists of 10cm squares

        # print(rotationMatrix)
        # print(cameraMatrix)

        tempMatrix = np.matmul(np.matmul(scipy.linalg.inv(rotationMatrix), scipy.linalg.inv(cameraMatrix)),
                               location)
        tempMatrix2 = np.matmul(scipy.linalg.inv(rotationMatrix), translationVector)

        s = (height / calibrationPointsSize + tempMatrix2[2][0]) / tempMatrix[2][0]

        final = np.matmul(scipy.linalg.inv(rotationMatrix),
                          (s * np.matmul(scipy.linalg.inv(cameraMatrix), location) - translationVector))

        return final * calibrationPointsSize

    def processFrame(self, frame):
        imagesCollection = self.db.processedImages
        storesCollection = self.db.stores
        framesCollection = self.db.frames

        images = imagesCollection.find({"frameNumber": frame['frameNumber']})
        store = storesCollection.find_one({"_id": frame['storeId']})
        frame = framesCollection.find_one({"frameNumber": frame['frameNumber']})

        people = []

        for image in images:
            cameraId = image['cameraId']

            cameraInfo = None
            for camera in store['cameras']:
                if camera['id'] == cameraId:
                    cameraInfo = camera
                    break

            if 'rotationVector' in cameraInfo and 'translationVector' in cameraInfo:
                rotationMatrix = cv2.Rodrigues(np.array(cameraInfo['rotationVector']))[0]
                    
                for index, person in enumerate(image['people']):
                    feet = []
                    if person[15][0] != 0:
                        feet.append(person[15])
                    if person[16][0] != 0:
                        feet.append(person[16])
                    if len(feet) > 0:
                        screenLocation = np.mean(np.array(feet), axis=0)

                        height = 10.0 # 10cm, approximate height of shin off the ground, which is where the
                        storeLocation = self.inverseScreenLocation(screenLocation, height, rotationMatrix, np.array(cameraInfo['translationVector']), np.array(cameraInfo['cameraMatrix']))

                        people.append((index, (storeLocation[0][0], storeLocation[1][0])))

                        if index == 0:
                            print('person ' + str(index) + ': x:', storeLocation[0][0], 'y:', storeLocation[1][0])

        frame['people'] = people
        frame['needsUpdate'] = False

        framesCollection.update_one({"_id": frame['_id']}, {"$set": frame})

        amqpChannel = self.getMessagingChannel()
        exchangeId = 'store-frames-' + str(frame['storeId'])
        amqpChannel.exchange_declare(exchange=exchangeId, exchange_type='fanout')
        amqpChannel.basic_publish(exchange=exchangeId, routing_key='', body=bson.json_util.dumps(frame))
