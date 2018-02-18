from pyramid.config import Configurator
import pymongo
import pika

def main_api(global_config, **settings):
    """
    This function returns a Pyramid WSGI application.
    """
    config = Configurator(settings=settings)

    config.registry.db = pymongo.MongoClient(settings['mongo.uri'])['ebretail']

    # Open a connection to the message broker
    amqpConnection = pika.BlockingConnection(pika.ConnectionParameters(settings['amqp.uri']))
    def getMessagingChannel():
        nonlocal amqpConnection
        try:
            return amqpConnection.channel()
        except pika.exceptions.ConnectionClosed:
            amqpConnection = pika.BlockingConnection(pika.ConnectionParameters(settings['amqp.uri']))
            return getMessagingChannel()

    config.registry.getMessagingChannel = getMessagingChannel

    # Add our custom file renderer, used for endpoints that serve files from Mongos GridFS
    config.add_renderer('file', 'ebretail.components.file_renderer.FileRenderer')

    config.add_static_view('static', 'static', cache_max_age=3600)
    config.add_route('collect_images', '/collect_images')
    config.add_route('register_collector', '/register_collector')


    config.add_route('home', '/')
    config.scan('ebretail.endpoints')

    return config.make_wsgi_app()


def image_processor_microservice(global_config, **settings):
    """
        This function returns a Pyramid WSGI application for the
        image processor microservice
    """
    config = Configurator(settings=settings)

    config.registry.db = pymongo.MongoClient(settings['mongo.uri'])

    # Open a connection to the message broker
    config.registry.amqpConnection = pika.BlockingConnection(pika.ConnectionParameters(settings['amqp.uri']))

    # Add our custom file renderer, used for endpoints that serve files from Mongos GridFS
    config.add_renderer('file', 'ebretail.components.file_renderer.FileRenderer')

    config.add_route('process_image', '/process_image')
    config.scan('ebretail.image_processor')
    return config.make_wsgi_app()


__all__ = ["main_api", "image_processor_microservice"]