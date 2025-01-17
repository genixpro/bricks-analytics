"""
    SORT: A Simple, Online and Realtime Tracker
    Copyright (C) 2016 Alex Bewley alex@dynamicdetection.com

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from __future__ import print_function

from numba import jit
import os.path
import numpy as np
from scipy.optimize import linear_sum_assignment
import scipy.spatial
import scipy.special
import argparse
from filterpy.kalman import KalmanFilter
import math

@jit
def iou(bb_test,bb_gt):
  """
  Computes IUO between two bboxes in the form [x1,y1,x2,y2]
  """
  xx1 = np.maximum(bb_test[0], bb_gt[0])
  yy1 = np.maximum(bb_test[1], bb_gt[1])
  xx2 = np.minimum(bb_test[2], bb_gt[2])
  yy2 = np.minimum(bb_test[3], bb_gt[3])
  w = np.maximum(0., xx2 - xx1)
  h = np.maximum(0., yy2 - yy1)
  wh = w * h
  o = wh / ((bb_test[2]-bb_test[0])*(bb_test[3]-bb_test[1])
    + (bb_gt[2]-bb_gt[0])*(bb_gt[3]-bb_gt[1]) - wh)
  return(o)

def convert_bbox_to_z(bbox):
  """
  Takes a bounding box in the form [x1,y1,x2,y2] and returns z in the form
    [x,y,s,r] where x,y is the centre of the box and s is the scale/area and r is
    the aspect ratio
  """
  w = bbox[2]-bbox[0]
  h = bbox[3]-bbox[1]
  x = bbox[0]+w/2.
  y = bbox[1]+h/2.
  s = w*h    #scale is just area
  r = w/float(h)
  return np.array([x,y,s,r]).reshape((4,1))

def convert_x_to_bbox(x,score=None):
  """
  Takes a bounding box in the centre form [x,y,s,r] and returns it in the form
    [x1,y1,x2,y2] where x1,y1 is the top left and x2,y2 is the bottom right
  """
  w = np.sqrt(x[2]*x[3])
  h = x[2]/w
  if(score==None):
    return np.array([x[0]-w/2.,x[1]-h/2.,x[0]+w/2.,x[1]+h/2.]).reshape((1,4))
  else:
    return np.array([x[0]-w/2.,x[1]-h/2.,x[0]+w/2.,x[1]+h/2.,score]).reshape((1,5))


class KalmanBoxTracker(object):
  """
  This class represents the internel state of individual tracked objects observed as bbox.
  """
  count = 0
  def __init__(self,bbox):
    """
    Initialises a tracker using initial bounding box.
    """
    #define constant velocity model
    self.kf = KalmanFilter(dim_x=7, dim_z=4)
    self.kf.F = np.array([[1,0,0,0,1,0,0],[0,1,0,0,0,1,0],[0,0,1,0,0,0,1],[0,0,0,1,0,0,0],  [0,0,0,0,1,0,0],[0,0,0,0,0,1,0],[0,0,0,0,0,0,1]])
    self.kf.H = np.array([[1,0,0,0,0,0,0],[0,1,0,0,0,0,0],[0,0,1,0,0,0,0],[0,0,0,1,0,0,0]])

    self.kf.R[2:,2:] *= 10.
    self.kf.P[4:,4:] *= 1000. #give high uncertainty to the unobservable initial velocities
    self.kf.P *= 10.
    self.kf.Q[-1,-1] *= 0.01
    self.kf.Q[4:,4:] *= 0.01

    self.kf.x[:4] = convert_bbox_to_z(bbox)
    self.time_since_update = 0
    self.id = KalmanBoxTracker.count
    self.detIndex = None
    KalmanBoxTracker.count += 1
    self.history = []
    self.hits = 0
    self.hit_streak = 0
    self.age = 0
    self.featureVector = None
    self.allowDeletion = True

  def update(self,bbox):
    """
    Updates the state vector with observed bbox.
    """
    self.time_since_update = 0
    self.history = []
    self.hits += 1
    self.hit_streak += 1
    self.kf.update(convert_bbox_to_z(bbox))

  def predict(self):
    """
    Advances the state vector and returns the predicted bounding box estimate.
    """
    if((self.kf.x[6]+self.kf.x[2])<=0):
      self.kf.x[6] *= 0.0
    self.kf.predict()
    self.age += 1
    if(self.time_since_update>0):
      self.hit_streak = 0
    self.time_since_update += 1
    self.history.append(convert_x_to_bbox(self.kf.x))
    return self.history[-1]

  def get_state(self):
    """
    Returns the current bounding box estimate.
    """
    return convert_x_to_bbox(self.kf.x)

def associate_detections_to_trackers(detections,trackers,mode, match_score_threshold = 0.2, feature_vector_threshold = 0.3, euclid_threshold = 200, iou_mode_iou_weight=1.0, iou_mode_similarity_weight=1.5, euclid_mode_similarity_weight=2.0, euclid_mode_distance_weight=1.0):
  """
  Assigns detections to tracked object (both represented as bounding boxes)

  Returns 3 lists of matches, unmatched_detections and unmatched_trackers
  """
  if(len(trackers)==0):
    return np.empty((0,2),dtype=int), np.arange(len(detections)), np.empty((0,5),dtype=int)
  iou_matrix = np.zeros((len(detections),len(trackers)),dtype=np.float32)

  for d,det in enumerate(detections):
    for t,trk in enumerate(trackers):
      # Compute similarity metric for their feature vectors
      if np.count_nonzero(det[5:]) == 0 or np.count_nonzero(trk[5:]) == 0:
        similarityMetric = 0
      else:
        similarityMetric = 1.0 - scipy.spatial.distance.cosine(det[5:], trk[5:])

      if mode == 'iou':
        if similarityMetric < feature_vector_threshold:
          similarityMetric = 0.0
        iou_metric = iou(det,trk)

        finalMetric = iou_metric * iou_mode_iou_weight + similarityMetric*iou_mode_similarity_weight

        iou_matrix[d, t] = finalMetric
      elif mode == 'euclidean':
        cx1 = det[0]/2 + det[2]/2
        cy1 = det[1]/2 + det[3]/2

        cx2 = trk[0]/2 + trk[2]/2
        cy2 = trk[1]/2 + trk[3]/2

        dist = math.sqrt((cx2-cx1)*(cx2-cx1) + (cy2-cy1)*(cy2-cy1))

        distMetric = scipy.special.expit(dist / (euclid_threshold / 2))

        iou_matrix[d,t] = similarityMetric * euclid_mode_similarity_weight - distMetric * euclid_mode_distance_weight

  det_indices,trk_indices = linear_sum_assignment(-iou_matrix)

  unmatched_detections = []
  for d,det in enumerate(detections):
    if(d not in det_indices):
      unmatched_detections.append(d)
  unmatched_trackers = []
  for t,trk in enumerate(trackers):
    if(t not in trk_indices):
      unmatched_trackers.append(t)

  #filter out matched with low IOU
  matches = []
  for m in range(len(det_indices)):
    if(iou_matrix[det_indices[m],trk_indices[m]]<match_score_threshold):
      unmatched_detections.append(det_indices[m])
      unmatched_trackers.append(trk_indices[m])
    else:
      matches.append(np.array([[det_indices[m], trk_indices[m]]]))

  if(len(matches)==0):
    matches = np.empty((0,2),dtype=int)
  else:
    matches = np.concatenate(matches,axis=0)

  return matches, np.array(unmatched_detections), np.array(unmatched_trackers)



class Sort(object):
  def __init__(self,max_age=1,min_hits=3, featureVectorSize = 0, mode='iou', new_track_min_dist=0, feature_vector_update_speed=0.3, match_score_threshold=0.2, feature_vector_threshold=0.3, euclid_threshold=200, iou_mode_iou_weight=1.0, iou_mode_similarity_weight=1.5, euclid_mode_similarity_weight=2.0, euclid_mode_distance_weight=1.0):
    """
    Sets key parameters for SORT
    """
    self.max_age = max_age
    self.min_hits = min_hits
    self.trackers = []
    self.frame_count = 0
    self.mode = mode
    self.featureVectorSize = featureVectorSize
    self.new_track_min_dist = new_track_min_dist
    self.feature_vector_update_speed = feature_vector_update_speed
    self.match_score_threshold = match_score_threshold
    self.feature_vector_threshold = feature_vector_threshold
    self.euclid_threshold = euclid_threshold
    self.iou_mode_iou_weight=iou_mode_iou_weight
    self.iou_mode_similarity_weight = iou_mode_similarity_weight
    self.euclid_mode_similarity_weight = euclid_mode_similarity_weight
    self.euclid_mode_distance_weight = euclid_mode_distance_weight

  def update(self,dets):
    """
    Params:
      dets - a numpy array of detections in the format [[x1,y1,x2,y2,score,input_index],[x1,y1,x2,y2,score,index_index],...]
    Requires: this method must be called once for each frame even with empty detections.
    Returns the a similar array, where the last column is the object ID.

    NOTE: The number of objects returned may differ from the number of detections provided.
    """
    self.frame_count += 1
    #get predicted locations from existing trackers.
    trks = np.zeros((len(self.trackers), self.featureVectorSize + 5))
    to_del = []
    ret = []
    for t,trk in enumerate(trks):
      pos = self.trackers[t].predict()[0]
      trk[:4] = [pos[0], pos[1], pos[2], pos[3]]
      trk[4] = 1.0
      trk[5:] = self.trackers[t].featureVector
      if(np.any(np.isnan(pos))):
        to_del.append(t)
    trks = np.ma.compress_rows(np.ma.masked_invalid(trks))
    for t in reversed(to_del):
      self.trackers.pop(t)
    matched, unmatched_dets, unmatched_trks = associate_detections_to_trackers(detections=dets,
                                                                               trackers=trks,
                                                                               mode=self.mode,
                                                                               match_score_threshold=self.match_score_threshold,
                                                                               feature_vector_threshold=self.feature_vector_threshold,
                                                                               euclid_threshold=self.euclid_threshold,
                                                                               iou_mode_iou_weight=self.iou_mode_iou_weight,
                                                                               iou_mode_similarity_weight=self.iou_mode_similarity_weight,
                                                                               euclid_mode_similarity_weight=self.euclid_mode_similarity_weight,
                                                                               euclid_mode_distance_weight=self.euclid_mode_distance_weight)
    # print(matched, unmatched_dets, unmatched_trks)

    # Set all trackers detIndex to 0
    for trk in self.trackers:
      trk.detIndex = -1

    #update matched trackers with assigned detections and update the feature vector
    for t,trk in enumerate(self.trackers):
      if(t not in unmatched_trks):
        d = matched[np.where(matched[:,1]==t)[0],0]
        trk.update(dets[d,:][0][:4])
        trk.detIndex = d
        trk.allowDeletion = dets[d,:][0][4]

        # Update the feature vector using an exponential rolling average. This helps smooth out any sudden poor detections which
        # can screw up the feature vector, even if they are tracked well
        newFeatureVector = dets[d,:][0][5:]
        if np.count_nonzero(newFeatureVector) > 0:
          trk.featureVector = (trk.featureVector * (1.0 - self.feature_vector_update_speed)) + (newFeatureVector * self.feature_vector_update_speed)

    #create and initialise new trackers for unmatched detections
    for i in unmatched_dets:
        det_bbox = dets[i,:][5:]

        allow = bool(dets[i,:][4])
        if self.new_track_min_dist > 0:
          center = [det_bbox[0]/2 + det_bbox[2]/2, det_bbox[1]/2 + det_bbox[3]/2]
          for t,trk in enumerate(self.trackers):
            trk_bbox = trk.get_state()[0]
            trk_center = [trk_bbox[0]/2 + trk_bbox[2]/2, trk_bbox[1]/2 + trk_bbox[3]/2]
            if scipy.spatial.distance.euclidean(center, trk_center) < self.new_track_min_dist:
                allow = False

        if allow:
          trk = KalmanBoxTracker(dets[i,:])
          trk.detIndex = i
          trk.featureVector = dets[i,:][5:]
          trk.allowDeletion = dets[i,:][4]
          self.trackers.append(trk)

    i = len(self.trackers)
    for trk in reversed(self.trackers):
        d = trk.get_state()[0]
        if((trk.hits >= self.min_hits)): # ELECTRIC BRAIN MODIFIED THIS LINE
          ret.append(np.concatenate((d,[trk.id+1, trk.detIndex])).reshape(1,-1)) # +1 as MOT benchmark requires positive
        i -= 1
        #remove dead tracklet if its allowed
        if(trk.time_since_update > self.max_age and trk.allowDeletion):
          self.trackers.pop(i)
    if(len(ret)>0):
      return np.concatenate(ret)
    return np.empty((0,5))
    
def parse_args():
    """Parse input arguments."""
    parser = argparse.ArgumentParser(description='SORT demo')
    parser.add_argument('--display', dest='display', help='Display online tracker output (slow) [False]',action='store_true')
    args = parser.parse_args()
    return args
