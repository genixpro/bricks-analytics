import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

import waitress
from ebretail import image_processor_microservice
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

    waitress.serve(image_processor_microservice(None, **settings), host='localhost', port=1845)
