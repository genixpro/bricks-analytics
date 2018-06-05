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
import pickle
from ebretail.components.image_analyzer import ImageAnalyzer


class TimeSeriesAnalyzer:
    """
       This is the time series analyzer. This is an ongoing system which analyzes the time-series of MultiCameraFrame objects, producing TimeSeriesFrame objects.

       Essentially, it tracks people on the store map, and determines when people have entered and exited. If they have exited, it computes a summary
       of their visit.
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
        multiCameraFramesCollection = self.db.multiCameraFrames
        timeSeriesFrameState = self.db.timeSeriesFrameState

        # First, get all the frames which haven't been processed
        try:
            for change in multiCameraFramesCollection.watch(
                    [{'$match': {'operationType': {"$in": ['insert', 'update']}}}]):
                if 'fullDocument' in change:
                    data = change['fullDocument']
                else:
                    data = multiCameraFramesCollection.find_one(change['documentKey'])

                if not data['needsUpdate']:
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

    def processFrame(self, multiCameraFrame):
        timeSeriesFrameState = self.db.timeSeriesFrameState
        timeSeriesFrames = self.db.timeSeriesFrames
        storesCollection = self.db.stores
        visitorsCollection = self.db.visitors

        # Get the current state, and process a time series frame
        currentStateObject = timeSeriesFrameState.find_one({"storeId": multiCameraFrame['storeId']})
        if currentStateObject is None:
            currentStateObject = {
                "storeId": multiCameraFrame['storeId']
            }
            currentState = {}
        else:
            currentState = pickle.loads(currentStateObject['data'])

        store = storesCollection.find_one({"_id": multiCameraFrame['storeId']})
        store['storeId'] = store['_id'] # quick hack, need to standardize id names

        timeSeriesFrame, newState = self.imageAnalyzer.processMultiCameraFrameTimeSeries(multiCameraFrame, currentState, store)
        timeSeriesFrames.insert(timeSeriesFrame)

        currentStateObject['data'] = pickle.dumps(newState)

        timeSeriesFrameState.find_one_and_update({'storeId': timeSeriesFrame['storeId']}, {'$set': currentStateObject}, upsert=True)

        # Now create visitor summaries for any visitors from this state
        for person in timeSeriesFrame['people']:
            if person['state'] == 'exited':
                # Fetch all of the time series state objects which contained this person.
                framesWithPerson = timeSeriesFrames.find(
                    filter={"visitorIds": {"$all": [person['visitorId']]}},
                    sort=[('timestamp', pymongo.DESCENDING)]
                )

                visitorSummary = self.imageAnalyzer.createVisitSummary(person['visitorId'], framesWithPerson, store)

                pprint(visitorSummary)

                visitorsCollection.insert(visitorSummary)

        amqpChannel = self.getMessagingChannel()
        exchangeId = 'store-time-series-frames-' + str(timeSeriesFrame['storeId'])
        amqpChannel.exchange_declare(exchange=exchangeId, exchange_type='fanout')
        amqpChannel.basic_publish(exchange=exchangeId, routing_key='', body=bson.json_util.dumps(timeSeriesFrame))
