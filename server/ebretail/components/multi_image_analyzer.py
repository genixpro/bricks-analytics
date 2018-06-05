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
from ebretail.components.image_analyzer import ImageAnalyzer


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

        self.imageAnalyzer = ImageAnalyzer()

    def main(self):
        singleCameraFramesCollection = self.db.singleCameraFrames
        multiCameraFramesCollection = self.db.multiCameraFrames

        # First, get all the frames which haven't been processed
        try:
            for change in multiCameraFramesCollection.watch([{'$match': {'operationType': {"$in": ['insert', 'update']}}}]):
                if 'fullDocument' in change:
                    data = change['fullDocument']
                else:
                    data = multiCameraFramesCollection.find_one(change['documentKey'])

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


    def processFrame(self, frame):
        singleCameraFramesCollection = self.db.singleCameraFrames
        multiCameraFramesCollection = self.db.multiCameraFrames
        storesCollection = self.db.stores

        singleCameraFrames = list(singleCameraFramesCollection.find({"frameNumber": frame['frameNumber']}))
        currentMultiCameraFrame = multiCameraFramesCollection.find_one({"frameNumber": frame['frameNumber']})
        store = storesCollection.find_one({"_id": frame['storeId']})

        print("about to process")
        pprint(singleCameraFrames)
        pprint(store)

        newMultiCameraFrame = self.imageAnalyzer.processMultipleCameraFrames(singleCameraFrames, store['cameras'])

        newMultiCameraFrame['storeId'] = currentMultiCameraFrame['storeId']
        newMultiCameraFrame['timestamp'] = currentMultiCameraFrame['timestamp']
        newMultiCameraFrame['frameNumber'] = currentMultiCameraFrame['frameNumber']
        newMultiCameraFrame['needsUpdate'] = False

        pprint(newMultiCameraFrame)

        multiCameraFramesCollection.update_one({"_id": frame['_id']}, {"$set": newMultiCameraFrame})

        amqpChannel = self.getMessagingChannel()
        exchangeId = 'store-frames-' + str(frame['storeId'])
        amqpChannel.exchange_declare(exchange=exchangeId, exchange_type='fanout')
        amqpChannel.basic_publish(exchange=exchangeId, routing_key='', body=bson.json_util.dumps(frame))
