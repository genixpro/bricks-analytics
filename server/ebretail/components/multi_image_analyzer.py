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


class ImageAnalyzer:
    """
       This is the image collecting micro-service. This has to be installed on-site, possibly
       executing in an embedded environment.

       This codes job is find all cameras attached to the device, and start recording images
       from those cameras. It then takes those images and forwards them to the image processor.
    """
    def __init__(self, db):
        self.db = db
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
                data = change['fullDocument']

                if data['frameNumber'] in self.scheduledFrames:
                    self.scheduledFrames[data['frameNumber']].cancel()

                self.scheduler.enter(5, 0, self.processFrame, (data['frameNumber'],))
        except pymongo.errors.PyMongoError as e:
            # The ChangeStream encountered an unrecoverable error or the
            # resume attempt failed to recreate the cursor.
            print(e)

    def runSchedulerThread(self):
        while True:
            self.scheduler.run()
            time.sleep(0.1)


    def processFrame(self, frameNumber):
        imagesCollection = self.db.processedImages
        images = imagesCollection.find({"frameNumber": frameNumber})

        for image in images:
            print(image)





