from cornice import Service
from cornice.resource import resource
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.security import Allow
from pyramid.security import Everyone
from ebretail.models.counter import get_next_object_id
import gridfs
import json


recordImage = Service(name='recordImage',
                            description='Tells a given camera to record a single image and upload it',
                            path='/store/{storeId}/cameras/{cameraId}/record',
                            cors_origins=('*',),
                            cors_max_age=3600)

@recordImage.post()
def record(request):
    storesCollection = request.registry.db.stores

    message = {
        "type": "record-image",
        "cameraId": request.matchdict['cameraId']
    }

    amqpChannel = request.registry.getMessagingChannel()
    print(request.matchdict['cameraId'])
    amqpChannel.basic_publish(exchange=request.matchdict['cameraId'], routing_key='', body=json.dumps(message))

    return Response(status=200)



@resource(path='/store/{storeId}/cameras/{cameraId}/image', cors_origins=('*',), cors_max_age=3600, renderer='file')
class CameraCurrentImage(object):
    """This RESTful endpoint is used for storing and retrieving the current image of the camera."""
    def __init__(self, request, context=None):
        self.request = request

        self.cameraImages = gridfs.GridFS(request.registry.db, collection='cameraImages')

    def __acl__(self):
        return [(Allow, Everyone, 'everything')]


    def get(self):
        storeId = int(self.request.matchdict['storeId'])
        cameraId = self.request.matchdict['cameraId']

        try:
            image = self.cameraImages.get(cameraId)

            if image is None:
                return None
            else:
                return image
        except gridfs.errors.NoFile:
            return None

    def post(self):
        image = self.request.POST['image'].file

        storeId = int(self.request.matchdict['storeId'])
        cameraId = self.request.matchdict['cameraId']

        if self.cameraImages.exists(cameraId):
            self.cameraImages.delete(cameraId)

        metadata = {"_id": cameraId}

        self.cameraImages.put(image, **metadata)

        message = {
            "type": "image-updated",
            "cameraId": cameraId
        }

        amqpChannel = self.request.registry.getMessagingChannel()
        amqpChannel.basic_publish(exchange=cameraId, routing_key='', body=json.dumps(message))

        return None


@resource(path='/store/{storeId}/cameras/{cameraId}/frame/{frameNumber}', cors_origins=('*',), cors_max_age=3600, renderer='bson')
class CameraFrames(object):
    """
        This RESTful endpoint is used for retrieving the processed data for specific frames of this camera.
    """
    def __init__(self, request, context=None):
        self.request = request

        self.processedImages = request.registry.db.processedImages

    def __acl__(self):
        return [(Allow, Everyone, 'everything')]


    def get(self):
        storeId = int(self.request.matchdict['storeId'])
        cameraId = self.request.matchdict['cameraId']

        query = {
            "metadata.storeId": storeId,
            "metadata.cameraId": cameraId,
        }
        sort = []

        if self.request.matchdict['frameNumber'] == 'current':
            sort.append(('frameNumber', -1))
        else:
            query['frameNumber'] = int(self.request.matchdict['frameNumber'])

        image = self.processedImages.find_one(query, sort=sort)

        if image is None:
            return None
        else:
            return image
