from cornice import Service
from cornice.resource import resource
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.security import Allow
from pyramid.security import Everyone
from pprint import pprint
from ebretail.models.counter import get_next_object_id
from ebretail.components.image_analyzer import ImageAnalyzer
from PIL import Image
import gridfs
import pymongo
import numpy
import io


@resource(collection_path='/store', path='/store/{id}', cors_origins=('*',), cors_max_age=3600)
class Store(object):
    def __init__(self, request, context=None):
        self.request = request

        self.storesCollection = request.registry.db.stores

    def __acl__(self):
        return [(Allow, Everyone, 'everything')]

    def collection_get(self):

        stores = list(self.storesCollection.find())

        return {'stores': stores}

    def get(self):
        store = self.storesCollection.find_one({"_id": int(self.request.matchdict['id'])})

        if store is None:
            return None
        else:
            return store

    def post(self):
        data = self.request.json_body

        self.storesCollection.update_one({"_id": int(self.request.matchdict['id'])}, {"$set": data})

        return None

    def collection_post(self):
        store = self.request.json_body

        # First, get the id
        id = get_next_object_id(self.request.registry.db, "stores")

        # Then create the new store with that id
        store['_id'] = id

        self.storesCollection.insert(store)

        return {'storeId': id}

@resource(path='/store/{id}/store_layout', cors_origins=('*',), cors_max_age=3600, renderer='file')
class StoreLayout(object):
    def __init__(self, request, context=None):
        self.request = request

        self.storeLayouts = gridfs.GridFS(request.registry.db, collection='storeLayout')

    def __acl__(self):
        return [(Allow, Everyone, 'everything')]


    def get(self):
        id = int(self.request.matchdict['id'])
        layout = self.storeLayouts.get(id)

        if layout is None:
            return None
        else:
            return layout

    def put(self):
        layout = self.request.body

        id = int(self.request.matchdict['id'])
        if self.storeLayouts.exists(id):
            self.storeLayouts.delete(id)

        metadata = {"_id": id}

        self.storeLayouts.put(layout, **metadata)

        return None


@resource(path='/store/{id}/store_layout/calibrated/{cameraId}', cors_origins=('*',), cors_max_age=3600, renderer='file')
class StoreLayoutWithCalibration(object):
    def __init__(self, request, context=None):
        self.request = request

        self.storeLayouts = gridfs.GridFS(request.registry.db, collection='storeLayout')
        self.storesCollection = request.registry.db.stores

    def __acl__(self):
        return [(Allow, Everyone, 'everything')]

    def post(self):
        # Prepare variables
        imageAnalyzer = ImageAnalyzer.sharedInstance()
        id = int(self.request.matchdict['id'])

        # Fetch the objects from the database
        layout = self.storeLayouts.get(id)

        # Convert the raw data store map into a numpy array
        rawImage = Image.open(layout)
        width = rawImage.width
        height = rawImage.height
        storeMapImage = numpy.array(rawImage.getdata(), numpy.uint8).reshape(height,width, 4)
        storeMapImage = imageAnalyzer.showCameraCalibrationOnStoreMap(storeMapImage, dict(self.request.json_body))

        # Convert the numpy array for the image back into a png file.
        image = Image.fromarray(storeMapImage, mode=None)
        b = io.BytesIO()
        image.save(b, "PNG")
        b.seek(0)
        
        return b

    def get(self):
        # Prepare variables
        imageAnalyzer = ImageAnalyzer.sharedInstance()
        id = int(self.request.matchdict['id'])

        # Fetch the objects from the database
        layout = self.storeLayouts.get(id)
        store = self.storesCollection.find_one({"_id": id})

        # Return nothing if no objects were found
        if layout is None:
            return None
        if store is None:
            return None

        # Convert the raw data store map into a numpy array
        rawImage = Image.open(layout)
        width = rawImage.width
        height = rawImage.height
        storeMapImage = numpy.array(rawImage.getdata(), numpy.uint8).reshape(height,width, 4)


        # Find the camera that we are getting calibration for
        camera = None
        for storeCamera in store['cameras']:
            if str(storeCamera['cameraId']) == str(self.request.matchdict['cameraId']):
                camera = storeCamera

        # If the camera is not found, return nothing
        if camera is None:
            return None

        # Only draw the calibration information if it is present
        if 'calibrationReferencePoint' in camera:
            # Finally, compute the store map image with the calibration information added.
            storeMapImage = imageAnalyzer.showCameraCalibrationOnStoreMap(storeMapImage, camera)

        # Convert the numpy array for the image back into a png file.
        image = Image.fromarray(storeMapImage, mode=None)
        b = io.BytesIO()
        image.save(b, "PNG")
        b.seek(0)

        return b


@resource(collection_path='/store/{storeId}/visitors/', path='/store/{storeId}/visitors/{visitorId}', cors_origins=('*',), cors_max_age=3600, renderer='bson')
class RecentVisitors(object):
    def __init__(self, request, context=None):
        self.request = request

        self.visitors = request.registry.db.visitors

    def __acl__(self):
        return [(Allow, Everyone, 'everything')]

    def collection_get(self):
        storeId = int(self.request.matchdict['storeId'])
        visitors = self.visitors.find(
            filter={"storeId": storeId},
            projection=['_id', 'visitorId', 'timestamp'],
            sort=[("timestamp", pymongo.DESCENDING)],
            limit=20
        )

        return list(visitors)

    def get(self):
        id = str(self.request.matchdict['visitorId'])
        visitor = self.visitors.find_one({"visitorId": id})
        return visitor




@resource(path='/store/{storeId}/detections/{detectionId}/image', cors_origins=('*',), cors_max_age=3600, renderer='file')
class DetectionImage(object):
    """This RESTful endpoint is used for storing and retrieving images of various people that have been detected by the system."""
    def __init__(self, request, context=None):
        self.request = request

        self.detectionImages = gridfs.GridFS(request.registry.db, collection='detectionImages')

    def __acl__(self):
        return [(Allow, Everyone, 'everything')]


    def get(self):
        storeId = int(self.request.matchdict['storeId'])
        detectionId = self.request.matchdict['detectionId']

        try:
            image = self.detectionImages.get(detectionId)

            if image is None:
                return None
            else:
                return image
        except gridfs.errors.NoFile:
            return None

    def post(self):
        image = self.request.POST['image'].file

        storeId = int(self.request.matchdict['storeId'])
        detectionId = self.request.matchdict['detectionId']

        if self.detectionImages.exists(detectionId):
            self.detectionImages.delete(detectionId)

        metadata = {"_id": detectionId}

        result = self.detectionImages.put(image, **metadata)

        return None

