import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

import json
from PIL import Image
import numpy
import cv2
import io
import time
import datetime
import requests
import pika
import threading


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <capture_file>\n'
          '(example: "%s ~/bricks-analytics-data/session1/capture1.json")' % (cmd, cmd))
    sys.exit(1)


class CaptureSimulation:
    """ This class represents a capture simulation, which takes one of the bricks-analytics captures and makes http
        calls up to the server simulating the capture happening live."""

    def __init__(self, fileName):
        # Load core test data
        self.testData = json.load(open(fileName, 'r'))

        # Load the annotation data
        self.annotations = json.load(
            open(os.path.join(os.path.dirname(sys.argv[1]), self.testData['annotationsFile']), 'r'))

        self.storeUrl = "http://localhost:1806/store"
        self.imageProcessorUrl = "http://localhost:1845/process_image"
        self.registrationUrl = "http://localhost:1806/register_collector"
        self.amqpUri = "localhost"

        self.uploadTimeout = 5

        self.storeId = None
        self.collectorId = 'collector-1'

        self.amqpThread = threading.Thread(target=lambda: self.amqpConnectionThread())


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

    def registerStore(self):
        """ This function registers this image collector with the main server. """
        data = {
                "name": self.testData['name'],
                "address": "36 blue jays",
                "coords": {
                    "lat": 44.2,
                    "lng": -61.7
                },
                "more": "fixed"
        }
        r = requests.post(self.storeUrl, json=data)

        body = r.json()

        self.storeId = body['storeId']

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
        data = {
            "store": self.storeId,
            "collectorId": "collector-1",
            "cameras": [{"id": self.cameraId(i)} for i in range(len(self.testData['cameras']))]
        }
        r = requests.post(self.registrationUrl, json=data)


    def runSimulation(self):
        timeStamp = datetime.datetime.now()

        for i in range(self.testData['numberOfImages']):
            imagePath = os.path.join(os.path.dirname(sys.argv[1]), self.testData['directory'],
                                     'image-' + str(i).zfill(5) + '.jpg')

            captureFullImage = Image.open(imagePath)

            # Break it apart into separate images for each camera
            cameraImages = self.breakApartImage(captureFullImage, self.testData['cameras'])

            for imageIndex, image in enumerate(cameraImages):
                self.uploadImageToProcessor(image, timeStamp, imageIndex)

            timeStamp = timeStamp + datetime.timedelta(seconds=0.5)




if __name__ == '__main__':
    if len(sys.argv) != 2:
        usage(sys.argv)

    test = CaptureSimulation(sys.argv[1])
    test.startAmqp()
    test.registerStore()
    test.registerCameras()
    test.runSimulation()