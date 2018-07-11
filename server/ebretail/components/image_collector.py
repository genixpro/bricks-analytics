import time
from datetime import datetime, timedelta
import json
from pprint import pprint, pformat
import concurrent.futures
import cv2
import requests
from PIL import Image
import io
import threading
import traceback
import random
import imageio
import numpy
import urllib
import os
import subprocess

import pika
import sys

class ImageCollector:
    """
       This is the image collecting micro-service. This has to be installed on-site, possibly
       executing in an embedded environment.

       This codes job is find all cameras attached to the device, and start recording images
       from those cameras. It then takes those images and forwards them to the image processor.
    """
    def __init__(self):
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=32)
        self.imageProcessorUrl = "http://localhost:1845/process_image"
        self.registrationUrl = "http://localhost:1806/register_collector"
        self.amqpUri = "localhost"
        self.metadata = {
            "collectorId": "a",
            "storeId": 1
        }

        self.recordNextImage = {}
        self.recordEverything = True

        self.collectionFrequency = 500
        self.uploadTimeout = 5

        self.bannedCameras = ['USB2.0 HD UVC WebCam: USB2.0 HD'] # This represents my laptop camera

        self.amqpThread = threading.Thread(target=lambda: self.amqpConnectionThread(), daemon=True)
        self.networkScanningThread = threading.Thread(target=lambda: self.scanNetworkThread(), daemon=True)
        self.localScanningThread = threading.Thread(target=lambda: self.scanLocalThread(), daemon=True)
        
        self.detectedNetworkCameras = []
        self.detectedLocalCameras = []
        self.openedNetworkCameras = []
        self.openedLocalCameras = []

        self.latestImage = {}

        self.showImageLock = threading.Lock()

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
                print('pika error', e, traceback.format_exc())
                pass


    def handleCameraQueueMessage(self, ch, method, properties, body):
        message = json.loads(body)
        if message['type'] == 'record-image':
            self.recordNextImage[message['cameraId']] = True

        # self.amqpChannel.basic_ack(delivery_tag=method.delivery_tag)
        return True


    def cameraId(self, i):
        id = self.metadata['collectorId']
        camera = self.cameras[i]
        if str(type(camera[1])) == 'string':
            id += '-' + camera[0]
        else:
            id += '-' + camera[0]

        return id
    
    def scanNetworkCameras(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=128) as executor:
            networkCameras = []

            def testURL(id, url):
                for attempt in range(3):
                    try:
                        # This request will cause an exception if the camera isn't found
                        requests.get(url, timeout=3.0, stream=True)
                        networkCameras.append((id, url))
                        return True
                    except Exception as e:
                        return False
            futures = []
            for subnet in random.sample([0,1,30,64], 4):
                for ip in random.sample(range(1, 255), 254):
                    url = 'http://192.168.' + str(subnet) + '.' + str(ip) + ':8080/video/mjpeg?fps=4'
                    id = str(int(str(subnet) + str(ip)))
                    futures.append(executor.submit(testURL, id, url))

            executor.shutdown(wait=True)

            self.detectedNetworkCameras = networkCameras

            return self.detectedNetworkCameras

    def scanNetworkThread(self):
        while True:
            self.scanNetworkCameras()
            time.sleep(10.0)

    def cameraDownloadThread(self, id, url):
        while True:
            try:
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
                            self.latestImage[id] = i
            except requests.exceptions.ConnectionError as e:
                for camera in self.detectedNetworkCameras:
                    if camera[0] == id:
                        self.detectedNetworkCameras.remove(camera)
                        break
                return


    def scanLocalCameras(self):
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

        self.detectedLocalCameras = [('usb' + str(device), device) for device in camerasToUse]
        return self.detectedLocalCameras

    def scanLocalThread(self):
        while True:
            self.scanLocalCameras()
            time.sleep(1.0)
    
    def openLocalCameras(self):
        localCameras = self.scanLocalCameras()

        cameras = []
        for id,device in localCameras:
            try:
                camera = cv2.VideoCapture(device)
                if camera is not None and camera.isOpened():
                    cameras.append((id, camera))
            except Exception as e:
                print('local camera error', traceback.format_exc())
        self.cameras = cameras


    def register(self):
        """ This function registers this image collector with the main server. """
        data = {
            "store": self.metadata['storeId'],
            "collectorId": self.metadata['collectorId'],
            "cameras": [{"cameraId": self.cameraId(i)} for i in range(len(self.cameras))]
        }
        r = requests.post(self.registrationUrl, json=data)


    def synchronizeLocalCameras(self):
        # We open cameras as needed.
        camerasToOpen = set(cam[0] for cam in self.detectedLocalCameras).difference(set(cam[0] for cam in self.openedLocalCameras))
        camerasToOpen = [list(filter(lambda item: item[0] == camera, self.detectedLocalCameras))[0] for camera in camerasToOpen]

        camerasToClose = set(cam[0] for cam in self.openedLocalCameras).difference(set(cam[0] for cam in self.detectedLocalCameras))

        for camera in camerasToOpen:
            print("Starting capture for ", camera[0])
        for camera in camerasToClose:
            print("Ending capture for ", camera)

        self.openedLocalCameras = list(filter(lambda item: item[0] not in camerasToClose, self.openedLocalCameras))
        self.openedLocalCameras = self.openedLocalCameras + [(id, cv2.VideoCapture(device)) for id,device in camerasToOpen]

        self.cameras = self.openedNetworkCameras + self.openedLocalCameras

        if len(camerasToOpen) > 0 or len(camerasToClose) > 0:
            return True
        return False

    def synchronizeNetworkCameras(self):
        # We open cameras as needed.
        camerasToOpen = set(cam[0] for cam in self.detectedNetworkCameras).difference(set(cam[0] for cam in self.openedNetworkCameras))
        camerasToOpen = [list(filter(lambda item: item[0] == camera, self.detectedNetworkCameras))[0] for camera in camerasToOpen]

        camerasToClose = set(cam[0] for cam in self.openedNetworkCameras).difference(set(cam[0] for cam in self.detectedNetworkCameras))

        for camera in camerasToOpen:
            print("Starting capture for ", camera[0])
        for camera in camerasToClose:
            print("Ending capture for ", camera)

        self.openedNetworkCameras = list(filter(lambda item: item[0] not in camerasToClose, self.openedNetworkCameras))

        for id, url in camerasToOpen:
            thread = threading.Thread(target=lambda: self.cameraDownloadThread(id, url), daemon=True)
            self.openedNetworkCameras.append(
                (id, url, thread)
            )
            thread.start()

        # Wait until the first images get loaded for each network camera
        tries = 0
        def firstImagesLoaded():
            for camera in self.openedNetworkCameras:
                if camera[0] not in self.latestImage:
                    return False
            return True

        while not firstImagesLoaded() and tries < 100:
            time.sleep(0.1)
            tries += 1

        self.cameras = self.openedNetworkCameras + self.openedLocalCameras

        if len(camerasToOpen) > 0 or len(camerasToClose) > 0:
            return True
        return False

    def runCollector(self):
        # First, start up threads for network and local usb scanning. 
        self.networkScanningThread.start()
        self.localScanningThread.start()

        self.synchronizeLocalCameras()
        self.synchronizeNetworkCameras()

        # Start the AMQP Thread
        self.amqpThread.start()

        lastFrameTime = datetime.fromtimestamp(time.time() - (time.time() % 0.5))

        maxInProgress = 1 * len(self.cameras)

        uploadFutures = []

        # Start grabbing frames and forwarding them with their time stamp
        while True:
            try:
                # Delay until the next frame time
                nextFrameTime = lastFrameTime + timedelta(milliseconds=self.collectionFrequency)
                delayTime = (nextFrameTime - datetime.now()).total_seconds()

                if delayTime < 0:
                    nextFrameTime = datetime.now()
                else:
                    time.sleep(delayTime)

                # Synchronize all the cameras
                changed = self.synchronizeLocalCameras() + self.synchronizeNetworkCameras()
                # If anything changed, reregister this collector with updated information
                if changed > 0:
                    self.register()

                # Capture all the images
                capturedImages = self.captureImages()

                # Wait for last frames images to finish being uploaded
                for future in concurrent.futures.as_completed(uploadFutures):
                    uploadFutures.remove(future)
                    if len(uploadFutures) < maxInProgress:
                        break

                # Grab all the images
                for image, cameraId in capturedImages:
                    # Skip any invalid images
                    if image is None:
                        continue

                    record = False
                    if self.recordEverything:
                        record = True
                    if cameraId in self.recordNextImage and self.recordNextImage[cameraId]:
                        record = True
                        self.recordNextImage[cameraId] = False

                    uploadFutures.append(self.executor.submit(lambda image, id, time, record: self.uploadImageToProcessor(image, id, time, record), numpy.copy(image), cameraId, nextFrameTime, record))

                lastFrameTime = nextFrameTime
            except Exception as e:
                print('capture error', traceback.format_exc())


    def uploadImageToProcessor(self, image, cameraId, timeStamp, record):
        try:
            image = Image.fromarray(image, mode=None)
            b = io.BytesIO()
            image.save(b, "JPEG", quality=80)
            b.seek(0)
            metadata = {
                "storeId": self.metadata['storeId'],
                "cameraId": cameraId,
                "timestamp": timeStamp.strftime("%Y-%m-%dT%H:%M:%S.%f"),
                "record": record
            }

            r = requests.post(self.imageProcessorUrl, files={'image': b, "metadata": json.dumps(metadata)}, timeout=self.uploadTimeout)
            print(metadata['cameraId'] + "  Successfully uploaded " + metadata['timestamp'])
        except Exception as e:
            print("Failed to upload " + timeStamp.strftime("%Y-%m-%dT%H:%M:%S.%f") + ": " + str(e), traceback.format_exc())
            pass

    def captureImages(self):
        images = []

        for index, camera in enumerate(self.cameras):
            if type(camera[1]) is not str:
                success = camera[1].grab()

        for index, camera in enumerate(self.cameras):
            cameraId = self.cameraId(index)
            if type(camera[1]) is not str:
                image = camera[1].retrieve()[1]
            elif camera[0] in self.latestImage:
                image = self.latestImage[camera[0]]
            else:
                image = numpy.zeros((480, 640, 3))

            images.append((image, cameraId))

        return images

    def captureDatasetMain(self):
        # First, start up threads for network and local usb scanning.
        self.networkScanningThread.start()
        self.localScanningThread.start()

        time.sleep(10)

        self.synchronizeLocalCameras()
        self.synchronizeNetworkCameras()

        # self.register()
        self.amqpThread.start()

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

        lastFrameTime = datetime.fromtimestamp(time.time() - (time.time() % 0.5))

        try:
            # Capture 50 photos, letting the webcams normalize
            for i in range(50):
                self.captureImages()
                time.sleep(0.05)

            self.captureSingleDatasetImage(lastFrameTime)
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
