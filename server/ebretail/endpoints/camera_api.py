from cornice import Service
from cornice.resource import resource
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.security import Allow
from pyramid.security import Everyone
from ebretail.models.counter import get_next_object_id
from ebretail.components.image_analyzer import ImageAnalyzer
import gridfs
import json
import io
import numpy
from PIL import Image


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
    # print(request.matchdict['cameraId'])
    amqpChannel.basic_publish(exchange=request.matchdict['cameraId'], routing_key='', body=json.dumps(message))
    amqpChannel.close()

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
        amqpChannel.close()

        return None


@resource(path='/store/{storeId}/cameras/{cameraId}/calibration', cors_origins=('*',), cors_max_age=3600, renderer='file')
class CameraCurrentImageWithCalibration(object):
    """This RESTful endpoint is used for retrieving a version of the current camera image which has calibration information drawn on top."""
    def __init__(self, request, context=None):
        self.request = request

        self.cameraImages = gridfs.GridFS(request.registry.db, collection='cameraImages')
        self.storesCollection = request.registry.db.stores

    def __acl__(self):
        return [(Allow, Everyone, 'everything')]


    def get(self):
        try:
            # Prepare variables
            imageAnalyzer = ImageAnalyzer.sharedInstance()
            storeId = int(self.request.matchdict['storeId'])

            cameraId = self.request.matchdict['cameraId']

            # Fetch the objects from the database
            image = self.cameraImages.get(cameraId)
            store = self.storesCollection.find_one({"_id": storeId})

            # Return nothing if no objects were found
            if image is None:
                return None
            if store is None:
                return None

            # Convert the raw data store map into a numpy array
            rawImage = Image.open(image)
            width = rawImage.width
            height = rawImage.height
            cameraImage = numpy.array(rawImage.getdata(), numpy.uint8).reshape(height,width, 3)

            # Find the camera that we are getting calibration for
            camera = None
            for storeCamera in store['cameras']:
                if str(storeCamera['cameraId']) == str(self.request.matchdict['cameraId']):
                    camera = storeCamera

            # If the camera is not found, return nothing
            if camera is None:
                return None

            # Finally, add the calibration grid onto the camera image
            cameraImage = imageAnalyzer.showCameraCalibrationGridOnCameraImage(cameraImage, camera)

            # Convert the numpy array for the image back into a png file.
            image = Image.fromarray(cameraImage, mode=None)
            b = io.BytesIO()
            image.save(b, "JPEG", quality=90)
            b.seek(0)

            return b
        except gridfs.errors.NoFile:
            return None


@resource(path='/store/{storeId}/cameras/{cameraId}/frame/{frameNumber}', cors_origins=('*',), cors_max_age=3600, renderer='bson')
class CameraFrames(object):
    """
        This RESTful endpoint is used for retrieving the processed data for specific frames of this camera.
    """
    def __init__(self, request, context=None):
        self.request = request

        self.singleCameraFrames = request.registry.db.singleCameraFrames

    def __acl__(self):
        return [(Allow, Everyone, 'everything')]


    def get(self):
        storeId = int(self.request.matchdict['storeId'])
        cameraId = self.request.matchdict['cameraId']

        query = {
            "storeId": storeId,
            "cameraId": cameraId,
        }
        sort = []

        if self.request.matchdict['frameNumber'] == 'current':
            sort.append(('frameNumber', -1))
        elif self.request.matchdict['frameNumber'] == 'calibration':
            query['calibrationObject'] = {"$type": "object"}
            sort.append(('frameNumber', -1))
        else:
            query['frameNumber'] = int(self.request.matchdict['frameNumber'])

        image = self.singleCameraFrames.find_one(query, sort=sort)

        if image is None:
            return None
        else:
            return image
