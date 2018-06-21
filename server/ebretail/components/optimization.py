import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

import json
from pprint import pprint
from ebretail.components.CaptureTest import CaptureTest
import hyperopt
import cProfile



def computeAccuracy_impl(hyperParameters):
    testFile = '/home/bradley/bricks-analytics-data/session1/capture1.json'

    test = CaptureTest(testFile)

    # Disable validation to improve performance
    test.imageAnalyzer.disableValidation()

    # Load calibration image
    test.loadCalibrationImage()
    test.createCameraConfigurations(showDebug=True)
    test.setHyperParameters(hyperParameters)

    # Reload the cache
    cacheFile = testFile + "-cached.pickle"
    test.reloadDetectionCache(cacheFile)

    # Process each of the main sequence images
    resultSingleCameraFrames, resultDebugImages = test.createSingleCameraFrames()

    # resultDebugImages = [[] for frame in range(test.testData['numberOfImages'])]

    # Process each of the main sequence images
    # resultSingleCameraFrames, resultDebugImages = test.createSingleCameraFrames()

    # Process into multi camera frame objects
    multiCameraFrames = test.createMultiCameraFrames(resultSingleCameraFrames)

    # Now we produce time-series analysis
    timeSeriesFrames, visitSummaries = test.runTimeSeriesAnalysis(multiCameraFrames)

    test.saveDetectionCache(cacheFile)

    score, details = test.measureAccuracy(timeSeriesFrames)
    results = {
        "loss": score,
        'status': hyperopt.STATUS_OK,
        "hyperParameters": hyperParameters,
        "detailedLoss": details
    }

    # Print everything
    for i in range(2):
        print('=' * 30)
    pprint(results)
    for i in range(2):
        print('=' * 30)
    return results


def computeAccuracy(hyperParameters):
    return computeAccuracy_impl(hyperParameters)
#
#     script = """
# import ebretail.components.optimization
# import json
# ebretail.components.optimization.computeAccuracy_impl(json.loads(\"\"\"""" + json.dumps(hyperParameters) + """\"\"\"))
# """
#
#     cProfile.run(compile(script, "test.py", 'exec'), 'restats', sort='cumulative')
#
#     import pstats
#     p = pstats.Stats('restats')
#     p.strip_dirs().sort_stats(-1).print_stats()
#
#     p.sort_stats('cumulative').print_callers(25)
#
#
#
