import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

from ebretail.components.image_collector import ImageCollector



def usage(argv):
    cmd = os.path.basename(argv[0])
    print('usage: %s <web_uri>\n'
          '(example: "%s http://192.168.1.2:8080/video/mjpeg?fps=4")' % (cmd, cmd))
    sys.exit(1)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        usage(sys.argv)

    webcam_uri = sys.argv[1]

    collector = ImageCollector()
    collector.runMJPEGCapture(webcam_uri)
