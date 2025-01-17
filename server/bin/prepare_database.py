#!/usr/bin/python3

import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

from ebretail.components.multi_image_analyzer import ImageAnalyzer
import pymongo
from wsgiref.simple_server import make_server
from pyramid.paster import (
    get_appsettings,
    setup_logging,
)


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri>\n'
          '(example: "%s development.ini")' % (cmd, cmd))
    sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        usage(sys.argv)
    config_uri = sys.argv[1]
    setup_logging(config_uri)
    settings = get_appsettings(config_uri)

    db = pymongo.MongoClient(settings['mongo.uri'])['ebretail']

    db.singleCameraFrames.ensureIndex({"frameNumber": 1})
    db.frames.ensureIndex({"frameNumber": 1})


