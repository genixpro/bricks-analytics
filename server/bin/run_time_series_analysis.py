#!/usr/bin/python3

import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), ".."))

from ebretail.components.time_series_analyzer import TimeSeriesAnalyzer
import pymongo
import pika
import pika.exceptions
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

    # Open a connection to the message broker
    amqpConnection = pika.BlockingConnection(pika.ConnectionParameters(settings['amqp.uri']))
    def getMessagingChannel():
        global amqpConnection
        try:
            return amqpConnection.channel()
        except pika.exceptions.ConnectionClosed:
            amqpConnection = pika.BlockingConnection(pika.ConnectionParameters(settings['amqp.uri']))
            return getMessagingChannel()

    analyzer = TimeSeriesAnalyzer(db, getMessagingChannel)
    analyzer.main()


