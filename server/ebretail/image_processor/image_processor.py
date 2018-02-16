import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", "lib", "pose-tensorflow"))

import os
import uuid
import shutil
import io
import numpy
import cv2
import json
import requests
from pyramid.response import Response
from PIL import Image
from pyramid.view import view_config


from config import load_config
from dataset.factory import create as create_dataset
from nnet import predict
from dataset.pose_dataset import data_to_input
from multiperson.detections import extract_detections
from multiperson.predict import SpatialModel, eval_graph, get_person_conf_multicut
from multiperson.visualize import PersonDraw, visualize_detections



# Configure the pose detection model
cfg = load_config(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "config", "pose_cfg_multi.yaml"))
dataset = create_dataset(cfg)
sm = SpatialModel(cfg)
sm.load()
draw_multi = PersonDraw()

# Load and setup CNN part detector
poseSess, poseInputs, poseOutputs = predict.setup_pose_prediction(cfg)

# The main server URL
mainServerURL = "http://localhost:1806/collect_images"

@view_config(route_name='process_image')
def processImage(request):
    """
       This is the main route for the image processing micro-service.
       This micro-service is put onto powerful GPU servers
       and does the bulk of the heavy lifting on the incoming
       images

       This is meant to be able to be hosted either in the cloud
       or on-site if necessary due to internet or privacy constraints,
       so it is very scaled down and doesn't touch backend
       services. Just process and forward
    """
    # Get the data for the file
    input_file = request.POST['image'].file
    metadataText = "".join([str(s, 'utf8') for s in request.POST['metadata'].file.readlines()])
    metadata = json.loads(metadataText)

    # write file to memory buffer
    fileData = io.BytesIO()
    input_file.seek(0)
    shutil.copyfileobj(input_file, fileData)

    fileData.seek(0)
    image_np = numpy.array(Image.open(fileData))


    image_batch = data_to_input(image_np)

    # Compute prediction with the CNN
    outputs_np = poseSess.run(poseOutputs, feed_dict={poseInputs: image_batch})
    scmap, locref, pairwise_diff = predict.extract_cnn_output(outputs_np, cfg, dataset.pairwise_stats)

    detections = extract_detections(cfg, scmap, locref, pairwise_diff)
    unLab, pos_array, unary_array, pwidx_array, pw_array = eval_graph(sm, detections)
    person_conf_multi = get_person_conf_multicut(sm, unLab, unary_array, pos_array)

    # For each person, if we can find their feet, measure the distance
    # if cameraRotationMatrix is not None:
    #     for person in person_conf_multi:
    #         feet = []
    #         if person[15][0] != 0:
    #             feet.append(person[15])
    #         if person[16][0] != 0:
    #             feet.append(person[16])
    #         if len(feet) > 0:
    #             location = np.mean(np.array(feet), axis=0)
    #
    #             lastKnownLocation = inverseScreenLocation(location)


    draw_multi.draw(image_np, dataset, person_conf_multi)
    image_np = visualize_detections(cfg, image_np, detections)

    # Forward the results onwards to the main server cluster
    r = requests.post(mainServerURL, json={
        "images": [{
            "detections": person_conf_multi.tolist(),
            "metadata": metadata
        }]
    })

    return Response('OK')

