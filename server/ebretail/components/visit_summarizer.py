import sys
import os

import os
import uuid
import shutil
import io
import threading
from pprint import pprint
import json
import datetime
import math
from datetime import datetime


class VisitSummarizer:
    """
        This class is responsible for the logic of summarizing a single users visit to a store
    """

    def __init__(self, db):
        self.transactionsCollection = db.transactions


    def createVisitSummary(self, visitorId, timeSeriesFrames, storeConfiguration):
        """
            :param visitorId: The visitor id to produce the summary for.
            :param timeSeriesFrames: An array containing all of the time series frames which contained the visitor
            :param storeConfiguration: The store configuration
            :return: (timeSeriesFrame, state)
        :return:
        """
        visitSummary = {
            "storeId": storeConfiguration['storeId'],
            "visitorId": visitorId,
            "detectionIds": []
        }

        # Compute the track
        visitSummary['track'] = []

        for frame in timeSeriesFrames:
            for person in frame['people']:
                if person['visitorId'] == visitorId:
                    visitSummary['track'].append({
                        "x": person['x'],
                        "y": person['y'],
                        "zoneId": person['zone'],
                        "timestamp": person['timestamp'],
                        "detectionIds": person['detectionIds']
                    })
                    visitSummary['detectionIds'] = list(set(visitSummary['detectionIds'] + person['detectionIds']))

        # Sort the track by the timestamps
        visitSummary['track'] = sorted(visitSummary['track'], key=lambda item: item['timestamp'])

        # pprint(visitSummary['track'])

        # Now we compute the amount of time spent in each zone
        # for each track.
        # Minimum value is applied here just in case a track was a result of a fleeting detection
        totalTime = max(0.1, (datetime.strptime(visitSummary['track'][-1]['timestamp'], "%Y-%m-%dT%H:%M:%S.%f") - datetime.strptime(visitSummary['track'][0]['timestamp'], "%Y-%m-%dT%H:%M:%S.%f")).total_seconds())
        visitSummary['timeSpentSeconds'] = totalTime

        zoneMap = {}
        zones = []
        for zone in storeConfiguration['zones']:
            newZone = {
                "zoneId": str(zone['id']),
                "timeSpentSeconds": 0,
                "timeSpentPercentage": 0,
                "totalSpend": 0,
                "lostSales": 0
            }
            zones.append(newZone)
            zoneMap[str(zone['id'])] = newZone

        # Add in a zone for when a person falls outside a zone
        nullZone = {
            "zoneId": 'None',
            "timeSpentSeconds": 0,
            "timeSpentPercentage": 0,
            "totalSpend": 0,
            "lostSales": 0
        }
        zoneMap['None'] = nullZone
        zones.append(nullZone)

        # Compute the time spent in each zone
        for pointIndex, point in enumerate(visitSummary['track'][:-1]):
            currentPoint = visitSummary['track'][pointIndex]
            nextPoint = visitSummary['track'][pointIndex + 1]

            # Compute the time between the next entry and this one
            elapsed = (datetime.strptime(nextPoint['timestamp'], "%Y-%m-%dT%H:%M:%S.%f") - datetime.strptime(currentPoint['timestamp'], "%Y-%m-%dT%H:%M:%S.%f")).total_seconds()

            if currentPoint['zoneId'] and str(currentPoint['zoneId']) in zoneMap:
                # Allocate half the time to the current zone, half the time to the next zone
                zoneMap[str(currentPoint['zoneId'])]['timeSpentSeconds'] += elapsed/2
            if nextPoint['zoneId'] and str(nextPoint['zoneId']) in zoneMap:
                zoneMap[str(nextPoint['zoneId'])]['timeSpentSeconds'] += elapsed/2

        # Now compute the percentage time in each zone
        maxZonePercent = 0
        for zone in zones:
            zone['timeSpentPercentage'] = zone['timeSpentSeconds'] / totalTime
            if zone['timeSpentPercentage'] > maxZonePercent:
                maxZonePercent = zone['timeSpentPercentage']
                visitSummary['concentrationZoneId'] = str(zone['zoneId'])

        # Add the zones onto the summary
        visitSummary['zones'] = zones


        # Now we must fetch any transactions that were associatted with this visit.
        # TODO: We are doing this in a wildly inaccurate way for now, by just fetching
        # TODO: All transactions during the persons visit. This needs to be improved

        start = datetime.strptime(visitSummary['track'][0]['timestamp'], "%Y-%m-%dT%H:%M:%S.%f")
        end = datetime.strptime(visitSummary['track'][-1]['timestamp'], "%Y-%m-%dT%H:%M:%S.%f")

        transactions = list(self.transactionsCollection.find({
            "timestamp": {"$gte": start, "$lte": end}
        }))
        visitSummary['transactions'] = transactions

        # Now we go through each transaction and each zone and compute the total spend for that zone.
        visitSummary['totalLostSales'] = 0
        if 'inventory' in storeConfiguration:
            # Go through each item in the transaction
            for transaction in transactions:
                for transactionItem in transaction['items']:
                    # Retrieve sku information on each item in the transaction
                    storeItem = None
                    for item in storeConfiguration['inventory']:
                        if item['barcode'] == transactionItem['barcode']:
                            storeItem = item
                            break
                    # Now find the zone for this item and increase its spend
                    for zone in zones:
                        if str(zone['zoneId']) == str(storeItem['zone']):
                            zone['totalSpend'] += transactionItem['price'] * transactionItem['quantity']
                if 'lostSales' in transaction:
                    for lostSaleItem in transaction['lostSales']:
                        # Retrieve sku information on each lost sale item
                        storeItem = None
                        for item in storeConfiguration['inventory']:
                            if item['barcode'] == lostSaleItem:
                                storeItem = item
                                break

                        # Add the number to the total for lost sales
                        visitSummary['totalLostSales'] += storeItem['price'] * 1
                        # Now find the zone for this item and increase lost sales
                        for zone in zones:
                            if str(zone['zoneId']) == str(storeItem['zone']):
                                zone['lostSales'] += storeItem['price'] * 1

        return visitSummary
