#!/usr/bin/python3

import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

import json

from pprint import pprint, pformat
import ebretail.components.optimization
from hyperopt.mongoexp import MongoTrials
from ebretail.components.CaptureTest import CaptureTest
import hyperopt
import random
import datetime
import traceback


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s\n'
          '(example: "%s")' % (cmd, cmd))
    sys.exit(1)


def optimizeCapture(roundNumber):
    space = {
            'store_map_tracker_min_hits': hyperopt.hp.quniform('store_map_min_hits', 0, 10, 1),
            'store_map_tracker_max_age': hyperopt.hp.quniform('store_map_max_age', 1, 20, 1),
            'calibration_point_size': hyperopt.hp.uniform('calibration_point_size', 9, 11),
            'foot_height': hyperopt.hp.uniform('foot_height', 0, 20),
            'knee_height': hyperopt.hp.uniform('knee_height', 20, 80),
            'hip_height': hyperopt.hp.uniform('hip_height', 50, 100),
            'shoulder_height': hyperopt.hp.uniform('shoulder_height', 120, 180),
            'eye_height': hyperopt.hp.uniform('eye_height', 120, 180),
            'foot_location_estimate_weight': hyperopt.hp.uniform('foot_location_estimate_weight', 1, 10),
            'knee_location_estimate_weight': hyperopt.hp.uniform('knee_location_estimate_weight', 1, 10),
            'hip_location_estimate_weight': hyperopt.hp.uniform('hip_location_estimate_weight', 1, 10),
            'shoulder_location_estimate_weight': hyperopt.hp.uniform('shoulder_location_estimate_weight', 1, 10),
            'eye_location_estimate_weight': hyperopt.hp.uniform('eye_location_estimate_weight', 1, 10),
            'store_map_merge_distance': hyperopt.hp.quniform('store_map_merge_distance', 0, 300, 1),
            'image_tracker_max_age': hyperopt.hp.quniform('image_tracker_max_age', 0, 10, 1),
            'image_tracker_feature_vector_update_speed': hyperopt.hp.uniform('image_tracker_feature_vector_update_speed', 0, 1),
            'image_tracker_min_hits': hyperopt.hp.quniform('image_tracker_min_hits', 0, 10, 1),
            'image_tracker_min_keypoints': hyperopt.hp.quniform('image_tracker_min_keypoints', 0, 10, 1),
            'image_tracker_match_score_threshold': hyperopt.hp.uniform('image_tracker_match_score_threshold', 0, 0.8),
            'image_tracker_feature_vector_threshold': hyperopt.hp.uniform('image_tracker_feature_vector_threshold', 0, 0.8),
            'image_tracker_iou_weight': hyperopt.hp.uniform('image_tracker_iou_weight', 0, 4.0),
            'image_tracker_similarity_weight': hyperopt.hp.uniform('image_tracker_similarity_weight', 0, 4.0),
            'store_map_tracker_feature_vector_update_speed': hyperopt.hp.uniform('store_map_tracker_feature_vector_update_speed', 0, 1.0),
            'store_map_tracker_new_track_min_dist': hyperopt.hp.uniform('store_map_tracker_new_track_min_dist', 0, 500),
            'store_map_tracker_match_score_threshold': hyperopt.hp.uniform('store_map_tracker_match_score_threshold', 0, 0.8),
            'store_map_tracker_feature_vector_threshold': hyperopt.hp.uniform('store_map_tracker_feature_vector_threshold', 0, 0.8),
            'store_map_tracker_euclid_threshold': hyperopt.hp.uniform('store_map_tracker_euclid_threshold', 0, 300),
            'store_map_tracker_euclid_mode_similarity_weight': hyperopt.hp.uniform('store_map_tracker_euclid_mode_similarity_weight', 0, 4.0),
            'store_map_tracker_euclid_mode_distance_weight': hyperopt.hp.uniform('store_map_tracker_euclid_mode_distance_weight', 0, 4.0)
    }

    def printResults(results, name):
        for i in range(2):
            print('*' * 50)
        print('*' * 20 + " " + name + " " + '*' * 20)
        for i in range(2):
            print('*' * 50)
        pprint(results)
        for i in range(5):
            print('*' * 50)

    test = CaptureTest(testFile)

    # Start from the default hyper parameters
    hyperParameters = dict(test.imageAnalyzer.humanHyperParameters)

    # Compute our baseline
    best = ebretail.components.optimization.computeAccuracy(hyperParameters)

    printResults(best, "Baseline")

    experiment = 0
    maxTrialsWithoutImprovement = 25
    trialsWithoutImprovement = 0

    while trialsWithoutImprovement < maxTrialsWithoutImprovement:
        start = datetime.datetime.now()

        # Pick two variables to optimize
        keysToOptimize = random.sample(space.keys(), random.randint(1,4))

        # Clone the space
        trialSpace = dict(space)

        # We allow the optimization hyper parameters to be sampled, all the others we keep fixed
        for key in trialSpace.keys():
            if key not in keysToOptimize:
                trialSpace[key] = hyperParameters[key]

        print("Testing fields: ", keysToOptimize)

        try:
            # pprint(trialSpace)
            trials = MongoTrials('mongo://localhost:27017/ebretail_optimization/jobs', exp_key='round' + str(roundNumber) + '-exp' + str(experiment))
            hyperopt.fmin(fn=ebretail.components.optimization.computeAccuracy,
                        space=trialSpace,
                        algo=hyperopt.tpe.suggest,
                        max_evals=10+experiment, # We make the optimization sequences longer as the system moves along, since it gets harder and harder to find a good optimization
                        trials=trials)
        except Exception as e:
            print("Crashed! Retrying.")
            print(traceback.format_exc())
            continue

        optimizedBest = min(*trials.results, key=lambda result: result['loss'])

        # print("Tested:")
        # for result in trials.results:
        #     filteredHyperParameters = {key: value for key, value in result['hyperParameters'].items() if key in keysToOptimize}
        #     print(pformat(filteredHyperParameters, width=200), "  Loss: ", result['loss'])

        # for l in range(4):
        #     print('=' * 20)

        # Only accept the change if its at least 1 point better.
        # This will prevent meaningless changes that had almost
        # no impact on the score.
        if optimizedBest['loss'] < (best['loss'] - 1):
            print("New Best!")
            print("Changing:")
            filteredHyperParameters = {key: value for key, value in best['hyperParameters'].items() if key in keysToOptimize}
            print(pformat(filteredHyperParameters, width=160))
            print(pformat(best['detailedLoss'], width=160))
            print("To:")
            filteredHyperParameters = {key: value for key, value in optimizedBest['hyperParameters'].items() if key in keysToOptimize}
            print(pformat(filteredHyperParameters, width=160))
            print(pformat(optimizedBest['detailedLoss'], width=160))
            print("Accepting changed hyper-parameters.")
            for key in keysToOptimize:
                hyperParameters[key] = optimizedBest['hyperParameters'][key]
            best = optimizedBest
            trialsWithoutImprovement = 0
        else:
            print("Did not beat existing benchmark by at least 1 point.")
            print("Keeping:")
            filteredHyperParameters = {key: value for key, value in best['hyperParameters'].items() if key in keysToOptimize}
            print(pformat(filteredHyperParameters, width=160))
            print(pformat(best['detailedLoss'], width=160))
            print("Rejected:")
            filteredHyperParameters = {key: value for key, value in optimizedBest['hyperParameters'].items() if key in keysToOptimize}
            print(pformat(filteredHyperParameters, width=160))
            print(pformat(optimizedBest['detailedLoss'], width=160))
            print("Rejected this update.")
            trialsWithoutImprovement += 1

        printResults(best, "Current Best")

        end = datetime.datetime.now()

        print("Taken: ", end-start)

        experiment += 1

    for l in range(4):
        print('=' * 20)
    printResults(best, "Final Results")
    with open('round-' + str(roundNumber) + '.json', 'wt') as file:
        json.dump(best, file, indent=4)

if __name__ == '__main__':
    testFile = '/home/bricks/bricks-analytics-data/session1/capture1.json'


    round = 0

    while True:
        optimizeCapture(round)
        round += 1
