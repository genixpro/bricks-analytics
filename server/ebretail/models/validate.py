import sys
import os


import jsonschema
import json


singleCameraFrameSchemaFile = os.path.join(os.path.dirname(os.path.realpath(__file__)), "SingleCameraFrame.json")
singleCameraFrameSchema = json.load(open(singleCameraFrameSchemaFile, 'r'))



def validateSingleCameraFrame(data):
    return jsonschema.validate(data, singleCameraFrameSchema)

validateSingleCameraFrame({
    "stuff": "awesomesauces"
})