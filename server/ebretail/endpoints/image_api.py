from pyramid.view import view_config
from pyramid.response import Response
from datetime import datetime


@view_config(route_name='collect_images')
def collect_images(request):
    """
        This endpoint is used by our main servers to receive images which have been
        processed by the ImageProcessor sub-module.

        So technically speaking we don't always get an image here, we usually just
        get the bounding boxes and other extracted data, which is stored for further processing.
    """

    imageCollection = request.registry.db.processedImages
    frameCollection = request.registry.db.frames

    for image in request.json_body['images']:
        frameNumber = int(datetime.strptime(image['metadata']['timestamp'], "%Y-%m-%dT%H:%M:%S.%f").timestamp() * 2)
        image['frameNumber'] = frameNumber
        imageCollection.insert(image)

        frameCollection.find_one_and_update({'frameNumber': frameNumber}, {'$set': {
            'frameNumber': frameNumber,
            'timeStamp': image['timeStamp'],
            'needsUpdate': True
        }}, upsert=True)

    return Response('OK')


