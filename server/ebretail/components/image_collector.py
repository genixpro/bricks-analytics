import time
from datetime import datetime, timedelta
import json

import concurrent.futures
import cv2
import requests
from PIL import Image
import io
import threading
import traceback

import pika


class ImageCollector:
    """
       This is the image collecting micro-service. This has to be installed on-site, possibly
       executing in an embedded environment.

       This codes job is find all cameras attached to the device, and start recording images
       from those cameras. It then takes those images and forwards them to the image processor.
    """
    def __init__(self):
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=12)
        self.imageProcessorUrl = "http://localhost:1845/process_image"
        self.registrationUrl = "http://localhost:1806/register_collector"
        self.amqpUri = "localhost"
        self.metadata = {
            "collectorId": "collector-0",
            "storeId": 4
        }

        self.recordNextImage = {}

        self.collectionFrequency = 100
        self.uploadTimeout = 5

        self.amqpThread = threading.Thread(target=lambda: self.amqpConnectionThread())

    def connectToAmqp(self):
        # Open a connection to the message broker
        self.amqpConnection = pika.BlockingConnection(pika.ConnectionParameters(self.amqpUri))
        self.amqpChannel = self.amqpConnection.channel()
        self.amqpChannel.queue_declare(queue=self.metadata['collectorId'])

        for cameraIndex,camera in enumerate(self.cameras):
            cameraId = self.cameraId(cameraIndex)
            self.amqpChannel.exchange_declare(exchange=cameraId, exchange_type='fanout')
            self.amqpChannel.queue_bind(queue=self.metadata['collectorId'], exchange=cameraId)

        self.amqpChannel.basic_consume(
            lambda ch, method, properties, body: self.handleCameraQueueMessage(ch, method, properties, str(body, 'utf8')),
            queue=self.metadata['collectorId'],
            no_ack=True)

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


    def handleCameraQueueMessage(self, ch, method, properties, body):
        message = json.loads(body)
        print(message)
        if message['type'] == 'record-image':
            self.recordNextImage[message['cameraId']] = True

        # self.amqpChannel.basic_ack(delivery_tag=method.delivery_tag)
        return True


    def cameraId(self, i):
        return self.metadata['collectorId'] + "-camera-" + str(i)

    def openCameras(self):
        # Try to capture all devices except first, which is
        # laptops onboard camera

        index = 1
        cameras = []
        while True:
            try:
                camera = cv2.VideoCapture(index)
                # camera.set(cv2.CAP_PROP_FPS, 4)
                if camera is not None and camera.isOpened():
                    cameras.append(camera)
                    index += 1
                else:
                    break
            except Exception as e:
                print(traceback.format_exc())
        self.cameras = cameras

    def register(self):
        """ This function registers this image collector with the main server. """
        data = {
            "store": self.metadata['storeId'],
            "collectorId": self.metadata['collectorId'],
            "cameras": [{"id": self.cameraId(i)} for i in range(len(self.cameras))]
        }
        r = requests.post(self.registrationUrl, json=data)


    def main(self):
        self.openCameras()
        self.register()
        self.amqpThread.start()

        # Make sure we have at least one camera
        if len(self.cameras) == 0:
            raise Exception("No cameras available for capture besides first (laptop cam)")

        lastFrameTime = datetime.fromtimestamp(time.time() - (time.time() % 0.5))

        # Start grabbing frames and forwarding them with their time stamp
        while True:
            try:
                # Delay until the next frame time
                nextFrameTime = lastFrameTime + timedelta(milliseconds=self.collectionFrequency)
                delayTime = max(0, (nextFrameTime - datetime.now()).total_seconds())

                time.sleep(delayTime)

                # Do a grab for each device
                for index, camera in enumerate(self.cameras):
                    success = camera.grab()

                for index, camera in enumerate(self.cameras):
                    cameraId = self.cameraId(index)
                    image = camera.retrieve()[1]

                    record = False
                    if cameraId in self.recordNextImage and self.recordNextImage[cameraId]:
                        record = True
                        self.recordNextImage[cameraId] = False

                    self.executor.submit(lambda i, c: self.uploadImageToProcessor(i, nextFrameTime, c, record=record), image.copy(), index)

                lastFrameTime = nextFrameTime
            except Exception as e:
                print(e)


    def uploadImageToProcessor(self, image, timeStamp, cameraIndex, record):
        try:
            image = Image.fromarray(image, mode=None)
            b = io.BytesIO()
            image.save(b, "JPEG", quality=80)
            b.seek(0)
            metadata = {
                "storeId": self.metadata['storeId'],
                "cameraId": self.cameraId(cameraIndex),
                "timestamp": timeStamp.strftime("%Y-%m-%dT%H:%M:%S.%f"),
                "cameraIndex": cameraIndex,
                "record": record
            }
            r = requests.post(self.imageProcessorUrl, files={'image': b, "metadata": json.dumps(metadata)}, timeout=self.uploadTimeout)
            print("Successfully uploaded " + metadata['timestamp'])
        except Exception as e:
            print("Failed to upload " + timeStamp.strftime("%Y-%m-%dT%H:%M:%S.%f") + ": " + str(e))
            pass
