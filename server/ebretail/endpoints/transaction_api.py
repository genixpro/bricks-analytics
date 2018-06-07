
from cornice import Service
from cornice.resource import resource
from pyramid.response import Response
from pyramid.view import view_config
from pyramid.security import Allow
from pyramid.security import Everyone
from ebretail.models.counter import get_next_object_id
import gridfs
import pymongo
from datetime import datetime


@resource(collection_path='/transactions', path='/transaction/{id}', cors_origins=('*',), cors_max_age=3600)
class Transaction(object):
    def __init__(self, request, context=None):
        self.request = request

        self.transactionsCollection = request.registry.db.transactions

    def __acl__(self):
        return [(Allow, Everyone, 'everything')]


    def collection_post(self):
        """ Used to send up a new transaction"""
        transaction = self.request.json_body

        # First, get the id
        id = get_next_object_id(self.request.registry.db, "transactions")

        # Then create the new store with that id
        transaction['_id'] = id
        transaction['transactionId'] = id
        transaction['timestamp'] = datetime.strptime(transaction['timestamp'], "%Y-%m-%dT%H:%M:%S.%f")

        self.transactionsCollection.insert(transaction)

        return {'transactionId': id}
