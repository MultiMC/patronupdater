#!/usr/bin/env python3

import patreon
import sys
import os
import configparser
import json
import argparse
# DO NOT ENABLE IN PRODUCTION !!!!
# import pprint
import collections

RewardInfo = collections.namedtuple('RewardInfo', 'rewarded anons')

def process_pledges(data, rewardToScanFor):
	"""Takes a 'page' of pledges returned by the Patreon API and filters out patrons that are eligible for the specified reward."""
	processed = []
	valid_pledges = [
		pledge
		for pledge in data['data']
		if pledge['type'] == 'pledge'
		if pledge['attributes']['is_valid'] == True
	]
	rewarded_pledges = [
		pledge
		for pledge in valid_pledges
		if pledge['relationships']['reward']['data'] != None
		if pledge['relationships']['reward']['data']['id'] == rewardToScanFor
	]
	anon_pledges = [
		pledge
		for pledge in valid_pledges
		if pledge['relationships']['reward']['data'] == None
	]
	# DO NOT ENABLE IN PRODUCTION !!!!
	# pprint.pprint(rewarded_pledges)
	patrons = {
		patron['id']: patron['attributes']
		for patron in data['included']
		if patron['type'] == 'user'
	}
	processed = [
		patrons[pledge['relationships']['patron']['data']['id']]
		for pledge in rewarded_pledges
	]
	# DO NOT ENABLE IN PRODUCTION !!!!
	# pprint.pprint(processed)
	return RewardInfo(rewarded = processed, anons=len(anon_pledges))


class PledgeAttributes(object):
	amount_cents = 'amount_cents'
	total_historical_amount_cents = 'total_historical_amount_cents'
	declined_since = 'declined_since'
	created_at = 'created_at'
	pledge_cap_cents = 'pledge_cap_cents'
	patron_pays_fees = 'patron_pays_fees'
	unread_count = 'unread_count'
	is_valid = 'is_valid'


my_pledge_attributes = [
    PledgeAttributes.amount_cents,
    PledgeAttributes.is_valid,
    PledgeAttributes.total_historical_amount_cents,
]

def getCurrentRewardedPatrons(accessToken, rewardToScanFor):
	"""Gets all the patrons eligible for a specified reward."""
	patreonAPI = patreon.API(accessToken)
	campaign = patreonAPI.fetch_campaign()
	campaignId = campaign['data'][0]['id']
	pageSize = 20
	anons = 0
	all_rewarded = []
	fields = ["is_valid"]

	pledges = patreonAPI.fetch_page_of_pledges(campaignId, pageSize, None, None, { 'pledge': my_pledge_attributes })
	cursor = patreonAPI.extract_cursor(pledges)
	processed = process_pledges(pledges, rewardToScanFor)
	all_rewarded += processed.rewarded
	anons += processed.anons

	while 'next' in pledges['links']:
		pledges = patreonAPI.fetch_page_of_pledges(campaignId, pageSize, cursor, None, { 'pledge': my_pledge_attributes })
		cursor = patreonAPI.extract_cursor(pledges)
		processed = process_pledges(pledges, rewardToScanFor)
		all_rewarded += processed.rewarded
		anons += processed.anons

	# sort by full name
	all_rewarded.sort(key=lambda y: y['full_name'].lower())
	return RewardInfo(rewarded = all_rewarded, anons=anons)


def main(configPath, workPath):

	configPath = configPath + '/tokens.cfg'
	textPath = workPath + '/patrons.txt'
	jsonPath = workPath + '/patrons.json'

	# read the config
	config = configparser.RawConfigParser()
	config.read(configPath)

	# refresh the auth tokens
	auth = patreon.OAuth(config['Keys']['clientid'], config['Keys']['clientsecret'])
	tokens = auth.refresh_token(config['Keys']['refreshtoken'], "fake")
	config['Keys']['accesstoken'] = tokens['access_token']
	config['Keys']['refreshtoken'] = tokens['refresh_token']

	# write the refreshed auth tokens
	with open(configPath, 'w') as configFile:
		config.write(configFile)

	processed = getCurrentRewardedPatrons(tokens['access_token'], config['Config']['reward'])

	# simple list with one name per line
	legacylist = [
		patron['full_name']
		for patron in processed.rewarded
	]
	if processed.anons > 0:
		if processed.anons > 1:
			legacylist.append('And %d others who wish to remain anonymous.' % processed.anons)
		else:
			legacylist.append('And one other who wishes to remain anonymous.' % processed.anons)

	legacylistText = '\n'.join(legacylist)

	# JSON list with names, avatar images and URLs for clickable links to Patreon profiles
	modernlist = [
		{
			'name': patron['full_name'],
			'image_url': patron['thumb_url'] if patron['thumb_url'].startswith("http") else 'https:' + patron['thumb_url'],
			'patreon_url': patron['url']
		}
		for patron in processed.rewarded
	]
	modernlistJson = json.dumps(modernlist, separators=(',',':'))

	with open(textPath, 'w') as textFile:
		textFile.write(legacylistText)

	with open(jsonPath, 'w') as jsonFile:
		jsonFile.write(modernlistJson)

	return 0

scriptPath = os.path.dirname(os.path.realpath(__file__));
parser = argparse.ArgumentParser()
parser.add_argument("-c", "--config", type=str, help="folder with the configuration", default=scriptPath)
parser.add_argument("-w", "--work", type=str, help="folder for the resulting files", default=scriptPath)
args = parser.parse_args()

retval = main(args.config, args.work)
sys.exit(retval)
