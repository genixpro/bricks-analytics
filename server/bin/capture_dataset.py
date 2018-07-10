#!/usr/bin/python3

import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

from ebretail.components.image_collector import ImageCollector


def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <config_uri>\n'
          '(example: "%s video_file_1.mp4 video_file_2.mp4 calibration_photo_1.jpeg")' % (cmd, cmd))
    sys.exit(1)


if __name__ == '__main__':
    # if len(sys.argv) < 3:
    #     usage(sys.argv)
    # config_uri = sys.argv[1]

    collector = ImageCollector()

    collector.captureDatasetMain()
