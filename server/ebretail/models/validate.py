import sys
import os


import jsonschema
import json

refStore = {}

singleCameraFrameSchemaFile = os.path.join(os.path.dirname(os.path.realpath(__file__)), "SingleCameraFrame.json")
singleCameraFrameSchema = json.load(open(singleCameraFrameSchemaFile, 'r'))
singleCameraFrameResolver = jsonschema.RefResolver(base_uri="file://" + singleCameraFrameSchemaFile, referrer=singleCameraFrameSchema, store=refStore, cache_remote=True)
singleCameraFrameValidator = jsonschema.Draft4Validator(singleCameraFrameSchema, resolver=singleCameraFrameResolver)




def validateSingleCameraFrame(data):
    return singleCameraFrameValidator.validate(data)

validateSingleCameraFrame({
    "stuff": "awesomesauces"
})
