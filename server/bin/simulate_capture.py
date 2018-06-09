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
from ebretail.components.CaptureTest import CaptureTest


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <capture_file>\n'
          '(example: "%s ~/bricks-analytics-data/session1/capture1.json")' % (cmd, cmd))
    sys.exit(1)




if __name__ == '__main__':
    if len(sys.argv) != 2:
        usage(sys.argv)

    test = CaptureTest(sys.argv[1])
    test.startAmqp()
    test.registerStore()
    test.registerCameras()
    test.uploadStoreMap()

    # Keep running and rerunning the simulation
    while True:
        test.runSimulation()

