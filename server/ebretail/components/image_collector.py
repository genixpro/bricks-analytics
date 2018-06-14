import time
from datetime import datetime, timedelta
import json
from pprint import pprint
import concurrent.futures
import cv2
import requests
from PIL import Image
import io
import threading
import traceback
import imageio
import numpy
import urllib
import os
import subprocess

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
            "storeId": 1
        }

        self.recordNextImage = {}

        self.collectionFrequency = 500
        self.uploadTimeout = 5

        self.bannedCameras = ['USB2.0 HD UVC WebCam: USB2.0 HD'] # This represents my laptop camera

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
        if message['type'] == 'record-image':
            self.recordNextImage[message['cameraId']] = True

        # self.amqpChannel.basic_ack(delivery_tag=method.delivery_tag)
        return True


    def cameraId(self, i):
        return self.metadata['collectorId'] + "-camera-" + str(i)

    def openLocalCameras(self):
        # Find a list of all video devices
        videoDevices = [device for device in os.listdir('/dev/') if 'video' in device]
        videoDeviceIndexes = [int(device[len('video'):]) for device in videoDevices]

        camerasToUse = []
        for device in videoDeviceIndexes:
            info = subprocess.run(['v4l2-ctl', '--all', '-d', str(device)], stdout=subprocess.PIPE, encoding='utf8').stdout

            useCamera = True

            # Make sure this is a valid camera stream.
            # Some video streams are actually invalid and can't be opened.
            if 'Format Video Capture:' not in info:
                useCamera = False

            for bannedCameraName in self.bannedCameras:
                if bannedCameraName in info:
                    useCamera = False

            if useCamera:
                camerasToUse.append(device)

        cameras = []
        for device in camerasToUse:
            try:
                camera = cv2.VideoCapture(device)
                if camera is not None and camera.isOpened():
                    cameras.append(camera)
            except Exception as e:
                print(traceback.format_exc())
        self.cameras = cameras

    def openRemoteMJPEGCamera(self, url):
        camera = cv2.VideoCapture(url)
        self.cameras = [camera]


    def register(self):
        """ This function registers this image collector with the main server. """
        data = {
            "store": self.metadata['storeId'],
            "collectorId": self.metadata['collectorId'],
            "cameras": [{"cameraId": self.cameraId(i)} for i in range(len(self.cameras))]
        }
        r = requests.post(self.registrationUrl, json=data)


    def runLocalCapture(self):
        self.openLocalCameras()

        # Make sure we have at least one camera
        if len(self.cameras) == 0:
            raise Exception("No cameras available for capture besides first (laptop cam)")

        self.register()
        self.captureLoop()

    def runMJPEGCapture(self, url):
        # self.openRemoteMJPEGCamera(url)

        self.cameras = [url]

        self.register()
        self.captureLoop()

    def captureLoop(self):
        self.amqpThread.start()

        lastFrameTime = datetime.fromtimestamp(time.time() - (time.time() % 0.5))

        # Start grabbing frames and forwarding them with their time stamp
        while True:
            try:
                # Delay until the next frame time
                nextFrameTime = lastFrameTime + timedelta(milliseconds=self.collectionFrequency)
                delayTime = max(0, (nextFrameTime - datetime.now()).total_seconds())

                time.sleep(delayTime)

                # Grab all the images
                for index, image in enumerate(self.captureImages()):
                    cameraId = self.cameraId(index)

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

    def captureMJPEG(self, url):
        r = requests.get(url, stream=True)
        if (r.status_code == 200):
            byteArray = bytes()
            for chunk in r.iter_content(chunk_size=1024):
                byteArray += chunk
                a = byteArray.find(b'\xff\xd8')
                b = byteArray.find(b'\xff\xd9')
                if a != -1 and b != -1:
                    jpg = byteArray[a:b + 2]
                    byteArray = byteArray[b + 2:]
                    i = cv2.imdecode(numpy.fromstring(jpg, dtype=numpy.uint8), cv2.IMREAD_COLOR)
                    return i


    def captureImages(self):
        images = []

        for index, camera in enumerate(self.cameras):
            if type(camera) is not str:
                success = camera.grab()

        for index, camera in enumerate(self.cameras):
            if type(camera) is not str:
                cameraId = self.cameraId(index)
                image = camera.retrieve()[1]
            else:
                image = self.captureMJPEG(camera)

            images.append(image)

        return images

    def captureDatasetMain(self):
        self.openLocalCameras()

        # self.register()
        self.amqpThread.start()

        self.cameras = self.cameras[:-1]

        frameNumber = 0

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

                frameNumber += 1

                self.captureSingleDatasetImage(str(frameNumber).zfill(5))

                lastFrameTime = nextFrameTime
            except Exception as e:
                raise e

    def captureSingleDatasetImageMain(self):
        self.openLocalCameras()
        # self.register()
        self.amqpThread.start()

        self.cameras = self.cameras[:-1]

        lastFrameTime = datetime.fromtimestamp(time.time() - (time.time() % 0.5))

        try:
            # Capture 50 photos, letting the webcams normalize
            for i in range(50):
                self.captureImages()
                time.sleep(0.05)

            self.captureSingleDatasetImage(lastFrameTime)
            print("finished!")
        except Exception as e:
            raise e


    def captureSingleDatasetImage(self, frameName):
        maxWidth = 0
        maxHeight = 0
        for index, image in enumerate(self.captureImages()):
            cameraImage = Image.fromarray(image)

            maxWidth += cameraImage.size[0]
            maxHeight = max(maxHeight, cameraImage.size[1])

        newImage = Image.new('RGB', (maxWidth, maxHeight))
        x_offset = 0

        # Do a grab for each device
        for index, image in enumerate(self.captureImages()):
            cameraId = self.cameraId(index)

            cameraImage = Image.fromarray(image)

            newImage.paste(cameraImage, (x_offset, 0))
            x_offset += cameraImage.size[0]

        array = numpy.array(newImage.convert("RGB"))
        for x in range(maxWidth):
            for y in range(maxHeight):
                pixel = array[y][x]

                r = pixel[2]
                g = pixel[1]
                b = pixel[0]

                pixel[0] = r
                pixel[1] = g
                pixel[2] = b


        imageio.imsave('image-' + str(frameName) + '.jpg', array)