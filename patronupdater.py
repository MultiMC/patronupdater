#!/usr/bin/env python3

import patreon
import sys
import os
import configparser
import json
import argparse
# DO NOT ENABLE IN PRODUCTION !!!!
# import pprint

def process_pledges(data, rewardToScanFor):
	"""Takes a 'page' of pledges returned by the Patreon API and filters out patrons that are eligible for the specified reward."""
	processed = []
	pledges = [
		pledge
		for pledge in data['data']
		if pledge['type'] == 'pledge'
		if pledge['attributes']['declined_since'] == None
		if pledge['relationships']['reward']['data'] != None
		if pledge['relationships']['reward']['data']['id'] == rewardToScanFor
	]
	# DO NOT ENABLE IN PRODUCTION !!!!
	# pprint.pprint(pledges)
	patrons = {
		patron['id']: patron['attributes']
		for patron in data['included']
		if patron['type'] == 'user'
	}
	processed = [
		patrons[pledge['relationships']['patron']['data']['id']]
		for pledge in pledges
	]
	# DO NOT ENABLE IN PRODUCTION !!!!
	# pprint.pprint(processed)
	return processed

def getCurrentRewardedPatrons(accessToken, rewardToScanFor):
	"""Gets all the patrons eligible for a specified reward."""
	patreonAPI = patreon.API(accessToken)
	campaign = patreonAPI.fetch_campaign()
	campaignId = campaign['data'][0]['id']
	pageSize = 20
	processed = []

	pledges = patreonAPI.fetch_page_of_pledges(campaignId, pageSize)
	cursor = patreonAPI.extract_cursor(pledges)
	processed += process_pledges(pledges, rewardToScanFor)

	while 'next' in pledges['links']:
		pledges = patreonAPI.fetch_page_of_pledges(campaignId, pageSize, cursor)
		cursor = patreonAPI.extract_cursor(pledges)
		processed += process_pledges(pledges, rewardToScanFor)

	# sort by full name
	processed.sort(key=lambda y: y['full_name'].lower())
	return processed


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

	rewarded = getCurrentRewardedPatrons(tokens['access_token'], config['Config']['reward'])

	# simple list with one name per line
	legacylist = [
		patron['full_name']
		for patron in rewarded
	]
	legacylistText = '\n'.join(legacylist)

	# JSON list with names, avatar images and URLs for clickable links to Patreon profiles
	modernlist = [
		{
			'name': patron['full_name'],
			'image_url': patron['thumb_url'] if patron['thumb_url'].startswith("http") else 'https:' + patron['thumb_url'],
			'patreon_url': patron['url']
		}
		for patron in rewarded
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
