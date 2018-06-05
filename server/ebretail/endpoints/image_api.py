from pyramid.view import view_config
from pyramid.response import Response
from datetime import datetime
import io
import json
import shutil
import gridfs


@view_config(route_name='register_collector')
def register_collector(request):
    """
        This function register a collector process.
    """
    body = request.json_body
    storeCollection = request.registry.db.stores

    storeId = int(body['store'])

    # Get store information for this collector
    store = storeCollection.find_one({"_id": storeId})

    if not store:
        return Response(status=404)

    if 'cameras' not in store:
        store['cameras'] = []

    newCameras = []
    for camera in body['cameras']:
        # See if there is already a camera with this id
        matchingCamera = None
        for existingCamera in store['cameras']:
            if camera['cameraId'] == existingCamera['cameraId']:
                matchingCamera = existingCamera
                break
        if not matchingCamera:
            newCameras.append(camera)

    # Add it to the list
    storeCollection.update({'_id': storeId}, {'$push': {
        'cameras': {"$each": newCameras},
    }})

    return Response('OK')



@view_config(route_name='collect_images')
def collect_images(request):
    """
        This endpoint is used by our main servers to receive images which have been
        processed by the ImageProcessor sub-module.

        These data received here are SingleCameraFrame objects.
    """

    singleCameraFrameCollection = request.registry.db.singleCameraFrames
    multiCameraFrameCollection = request.registry.db.multiCameraFrames

    data = request.json_body

    frameNumber = int(datetime.strptime(data['timestamp'], "%Y-%m-%dT%H:%M:%S.%f").timestamp() * 2)
    data['frameNumber'] = frameNumber
    singleCameraFrameCollection.insert(data)

    multiCameraFrameCollection.find_one_and_update({
        'frameNumber': frameNumber,
        'storeId': data['storeId']
    }, {'$set': {
        'frameNumber': frameNumber,
        'storeId': data['storeId'],
        'timestamp': data['timestamp'],
        'needsUpdate': True
    }}, upsert=True)

    return Response('OK')

