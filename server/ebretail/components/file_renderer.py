
from pyramid.response import Response

class FileRenderer(object):
    def __init__(self, info):
        pass

    def __call__(self, value, system):
        """ Renders return values as if they are file objects."""

        if type(value) == 'string':
            return value
        elif value is None:
            return ""
        elif isinstance(value, Response):
            return value
        else:
            return value.read()

