from cornice import Service
from cornice.resource import resource
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.security import Allow
from pyramid.security import Everyone
from ebretail.models.counter import get_next_object_id
import gridfs



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

    def collection_post(self):
        store = self.request.json_body

        # First, get the id
        id = get_next_object_id(self.request.registry.db, "stores")

        # Then create the new store with that id
        store['_id'] = id

        self.storesCollection.insert(store)

        return True

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
