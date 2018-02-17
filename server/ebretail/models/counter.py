
from pymongo import ReturnDocument


def get_next_object_id(db, collection_name):
    """ This function is a convenience method which returns the next object id for the given collection name.
        This function should not be used on high-volume collections where there may be a lot of collision."""

    counters = db.counters

    result = counters.find_one_and_update({'collection_name': collection_name}, {'$inc': {'count': 1}, '$set': {
        'collection_name': collection_name,
    }}, upsert=True, return_document=ReturnDocument.AFTER)

    return result['count']


