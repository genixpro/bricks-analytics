import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

import json

from pprint import pprint
from ebretail.components.image_analyzer import ImageAnalyzer
from PIL import Image
import numpy
import cv2
import time
import datetime
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
    
    test.loadStoreMap()

    # Load calibration image
    test.loadCalibrationImage()
    test.createCameraConfigurations()
    test.showDebugCameraGrid()

    # Either load the singleCameraFrame objects from a cache, or compute them fresh
    cacheFileName = sys.argv[1] + "-cached.json"
    if os.path.exists(cacheFileName):
        resultSingleCameraFrames = json.load(open(cacheFileName, 'r'))
        resultDebugImages = [[] for fame in range(test.testData['numberOfImages'])]
    else:
        # Process each of the main sequence images
        resultSingleCameraFrames, resultDebugImages = test.createSingleCameraFrames()
        json.dump(resultSingleCameraFrames, open(cacheFileName, 'w'), indent=4)


    multiCameraFrames = test.createMultiCameraFrames(resultSingleCameraFrames)

    cv2.waitKey(50)

    # Now we process all the multi camera frames through a time-series analysis
    timeSeriesFrames, visitSummaries = test.runTimeSeriesAnalysis(multiCameraFrames)

    storeMapDebugImages = test.drawStoreMapResults(multiCameraFrames, timeSeriesFrames)
    for frameIndex in range(len(multiCameraFrames)):
        resultDebugImages[frameIndex].append(storeMapDebugImages[frameIndex])

    for i in range(test.testData['numberOfImages']):
        debugImages = resultDebugImages[i]

        for imageIndex, debugImage in enumerate(debugImages):
            if imageIndex < (len(debugImages)-1):
                frameName = test.testData['cameras'][imageIndex]['name']
            else:
                frameName = 'Store Map (Individual Frames)'
            cv2.imshow(frameName, debugImage)
        cv2.waitKey(2000)


