import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", "lib", "pose-tensorflow"))

import os
import uuid
import shutil
import io
import cv2
import numpy
import json
import requests
from datetime import datetime
import pickle
from pyramid.response import Response
from PIL import Image
from pyramid.view import view_config
from ebretail.components.image_analyzer import ImageAnalyzer
import threading

# The main server URL
mainServerURL = "http://localhost:1806/collect_images"

# Temporary, keep state in main memory. Unfortunately, OpenCV objects are not serializable, presenting a great challenge.
globalState = {}
globalLocks = {}
globalLocksLock = threading.Lock()

# cv2.namedWindow('frame', flags=cv2.WINDOW_NORMAL)

@view_config(route_name='process_image')
def processImage(request):
    """
       This is the main route for the image processing micro-service.
       This micro-service is put onto powerful GPU servers
       and does the bulk of the heavy lifting on the incoming
       images

       This is meant to be able to be hosted either in the cloud
       or on-site if necessary due to internet or privacy constraints,
       so it is very scaled down and doesn't touch backend
       services. Just process and forward
    """
    global globalState
    global globalLocks, globalLocksLock

    # Get the data for the file out from the request object
    input_file = request.POST['image'].file

    # Seperate out the metadata as well, which should have been included as a second file object called 'metadata' thats JSON encoded
    metadataText = "".join([str(s, 'utf8') for s in request.POST['metadata'].file.readlines()])
    metadata = json.loads(metadataText)

    timestamp = datetime.strptime(metadata['timestamp'], "%Y-%m-%dT%H:%M:%S.%f")

    # Write file to memory buffer
    # fileData = io.BytesIO()
    # input_file.seek(0)
    # shutil.copyfileobj(input_file, fileData)
    # fileData.seek(0)

    # Convert binary data to a numpy array
    image = numpy.array(Image.open(input_file))
    input_file.close()

    # Copy for the debug image
    debugImage = image.copy()

    imageAnalyzer = ImageAnalyzer.sharedInstance(initializeTracking = True)

    # Only one process can be working on images for a camera at one time
    with globalLocksLock:
        lockId = "camera_processing_lock-" + str(metadata['cameraId'])
        if lockId not in globalLocks:
            globalLocks[lockId] = threading.Lock()
        lock = globalLocks[lockId]


    acquired = lock.acquire(timeout=0.1)
    if acquired:
        try:
            # Fet the current state for this camera.
            currentState = globalState.get(metadata['cameraId'], {})

            currentTimestamp = currentState.get('timestamp', None)

            # Only process this image if its timestamp is after the last processed image
            # otherwise we discard it from the sequence as out of order.
            # TODO: We need better handling for these out-of-order images, since this reduces
            # TODO: quality of the tracking, wastes bandwidth, etc..
            if currentTimestamp is None or timestamp > currentTimestamp:
                singleCameraFrame, newState, personImages = imageAnalyzer.processSingleCameraImage(image, metadata, currentState, debugImage)
                globalState[metadata['cameraId']] = newState

                # Forward the results onwards to the main server cluster
                r = requests.post(mainServerURL, json=singleCameraFrame)

                # If recording is enabled, save the debug image
                if metadata['record'] or singleCameraFrame['calibrationObject'] is not None:
                    recordMetadata = {
                        "storeId": metadata['storeId'],
                        "cameraId": metadata['cameraId'],
                        "timestamp": metadata['timestamp']
                    }

                    imageRecordUrl = "http://localhost:1806/store/" + str(recordMetadata['storeId']) + "/cameras/" + str(recordMetadata['cameraId']) + "/image"

                    imageToSend = cv2.cvtColor(debugImage, cv2.COLOR_BGR2RGB)
                    image = Image.fromarray(imageToSend, mode=None)
                    b = io.BytesIO()
                    image.save(b, "JPEG", quality=80)
                    b.seek(0)

                    r = requests.post(imageRecordUrl.format(recordMetadata['cameraId']), files={'image': b, "metadata": json.dumps(recordMetadata)})

                for detectionId, personImage in personImages.items():
                    imageRecordUrl = "http://localhost:1806/store/" + str(metadata['storeId']) + "/detections/" + str(detectionId) + "/image"

                    image = Image.fromarray(personImage, mode=None)
                    b = io.BytesIO()
                    image.save(b, "JPEG", quality=80)
                    b.seek(0)

                    detectionImageMetadata = {
                        "storeId": metadata['storeId'],
                        "cameraId": metadata['cameraId'],
                        "timestamp": metadata['timestamp'],
                        "detectionId": detectionId
                    }

                    r = requests.post(imageRecordUrl, files={'image': b, "metadata": json.dumps(detectionImageMetadata)})
            else:
                # print("Discarded image due to out-of-order: " + metadata['timestamp'])
                pass
        finally:
            lock.release()
    else:
        print("Discarded image because i can't get the lock: " + metadata['timestamp'])

    return Response('OK')


