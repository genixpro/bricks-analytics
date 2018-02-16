import time
from datetime import datetime, timedelta
import json

import concurrent.futures
import cv2
import requests
from PIL import Image
import io


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

    def main(self):
        # Try to capture all devices except first, which is
        # laptops onboard camera

        index = 0
        cameras = []
        while True:
            try:
                camera = cv2.VideoCapture(index)
                if camera is not None and camera.isOpened():
                    cameras.append(camera)
                    index += 1
                else:
                    break
            except Exception:
                break

        # Make sure we have at least one camera
        if len(cameras) == 0:
            raise Exception("No cameras available for capture besides first (laptop cam)")

        lastFrameTime = datetime.fromtimestamp(time.time() - (time.time() % 0.5))

        # Start grabbing frames and forwarding them with their time stamp
        while True:
            try:
                # Delay until the next frame time
                nextFrameTime = lastFrameTime + timedelta(milliseconds=500)
                delayTime = max(0, (nextFrameTime - datetime.now()).total_seconds())

                time.sleep(delayTime)

                # Do a grab for each device
                for index, camera in enumerate(cameras):
                    success = camera.grab()

                for index, camera in enumerate(cameras):
                    image = camera.retrieve()[1]
                    self.executor.submit(lambda i, c: self.uploadImage(i, nextFrameTime, c), image, index)

                lastFrameTime = nextFrameTime
            except Exception as e:
                print(e)

    def uploadImage(self, image, timeStamp, cameraIndex):
        try:
            image = Image.fromarray(image, mode=None)
            b = io.BytesIO()
            image.save(b, "JPEG", quality=80)
            b.seek(0)
            metadata = {
                "timestamp": timeStamp.isoformat(),
                "cameraIndex": cameraIndex
            }
            r = requests.post(self.imageProcessorUrl, files={'image': b, "metadata": json.dumps(metadata)})
            print(r)
        except Exception as e:
            print(e)
