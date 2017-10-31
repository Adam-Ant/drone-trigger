#!/usr/bin/python3

import os
import time

import argparse
from configobj import ConfigObj

import requests

import json

defaultconfig = '''[Connection]
# Specify the URL to the drone server, including port and protocol
host = https://drone.example.org

# Auth key found on your Drone account page
auth_key = eyJEXAMPLE.AUTH.KEY

# Time to wait between checks. Note that too low may ban you from the api, especially on GitHub
# Specified in seconds (Default: 300)
#sleep_time = 300

#[ExampleGitHubBuild]
# Example shown uses githubs api to find and compare on the sha of the latest commit

# Name of the repo to trigger in drone
#drone_repo = Example/HelloWorld
# Branch to use for deciding which drone build to fork and trigger (Default: master)
#branch = master

# URL of the json structure to check against
#url = https://api.github.com/repos/Kaylee/ShinyRepo/git/refs/heads/master
# JSON Tree needed to resolve the value.
#structure = object.sha

#[ExampleGitHubRelease]
#drone_repo = Example/HelloRelease
#branch = release
#url = https://api.github.com/repos/Kaylee/ShinyRepo/releases/latest
#structure = name
'''


def runbuild(repo: str, branch: str):
    url = drone_host + '/api/repos/' + repo
    latest = json.loads(requests.get(url + '/builds/latest', headers={'Authorization': drone_auth_key}).text)
    build_num = False
    if (latest['branch'] != branch):
        while not build_num:
            latest = json.loads(requests.get(url + '/builds/' + str(latest['number'] - 1), headers={'Authorization': drone_auth_key}).text)
            if (latest['branch'] == branch):
                build_num = str(latest['number'])
    else:
        build_num = str(latest['number'])

    buildurl = url + '/builds/' + build_num + '?fork=true'
    # [[TODO]] Add functionality for checking if build was triggered successfully?
    return (requests.post(buildurl, headers={'Authorization': drone_auth_key}))


def jsonVal(url, struct):
    try:
        r = requests.get(url)
        r.raise_for_status()
        jsondata = r.text        
    except requests.HTTPError as e:
        print('[' + time.strftime("%d/%m/%Y %H:%M:%S") + '] ERROR: Got Response code ' + str(e.response.status_code) + ' for URL ' + str(url))
        raise e

    try:
        dataDict = json.loads(jsondata)
    except json.decoder.JSONDecodeError as e:
        # Probably Not Valid JSON?
        print('[' + time.strftime("%d/%m/%Y %H:%M:%S") + '] ERROR: Could not decode JSON: ')
        print(jsondata)
        raise e


    try:
        for i in struct.split('.'):
            if i.isdigit():
                dataDict = dataDict[int(i)]
            else:
                dataDict = dataDict[i]
        return dataDict
    except:
        print('Error: Invalid structure: ' + struct)
        print(dataDict)
        raise


if __name__ == '__main__':
    argparser = argparse.ArgumentParser(
        prog='DroneTrigger.py', description='Drone Triggerer triggers drone builds based on updates to arbitrary GitHub repos.')
    argparser.add_argument(
        '-c', '--config', help='Specify directory for config file')
    cmdargs = argparser.parse_args()

    if not (cmdargs.config):
        filepath = '.'
    else:
        filepath = cmdargs.config

    if not (os.path.isdir(filepath)):
        print('Error: Config directory does not exist. Exiting...')
        exit(1)

    if not (os.path.isfile(filepath + '/dronetrigger.cfg')):
        print('Warn: Config file does not exist, writing example config. Please configure and try again.')
        c = open(filepath + '/dronetrigger.cfg', 'w')
        c.write(defaultconfig)
        c.close()
        exit(78)  # 78 is the exit code for invalid config

    config = ConfigObj(filepath + '/dronetrigger.cfg')
    if not ('Connection' in config):
        print('Error: Connection block not found, please check your config')
        exit(78)
    if not (config['Connection'].get('host', False)) or not (config['Connection'].get('auth_key', False)):
        print('Error: Missing connection details. please check your config')
        exit(78)
    if (len(config) < 2):
        print('Error: Please configure some monitoring blocks!')
        exit(78)
    # These can be assumed since we have verified
    drone_host = config['Connection']['host']
    drone_auth_key = config['Connection']['auth_key']
    sleep_time = int(config['Connection'].get('sleep_time', 300))

    for service in config:
        if service == 'Connection':
            continue
        if not (config[service].get('url', False)) or not (config[service].get('structure', False)) or not(config[service].get('drone_repo'), False):
            print('Error: Missing required value in status block ' + service)
            exit(78)

        if not (config[service].get('current_value', False)):
            try:
                curr_value = jsonVal(config[service].get('url'), config[service].get('structure'))
            except:
                exit(1)
            print('Writing Initial value for ' + service + ': ' + curr_value)
            config[service]['current_value'] = curr_value
            config.write()

    while(True):
        for service in config:
            if service == 'Connection':
                continue
            
            try:
                new_value = jsonVal(config[service].get('url'), config[service].get('structure'))
            except:
                continue

            if (new_value != config[service]['current_value']):
                print('[' + time.strftime("%d/%m/%Y %H:%M:%S") + '] Got new build - ' + new_value)
                if not (config[service].get('branch', False)):
                    branch = 'master'
                else:
                    branch = config[service]['branch']
                if (runbuild(config[service].get('drone_repo'), branch)):
                    config[service]['current_value'] = new_value
                    with open(filepath + '/dronetrigger.cfg', 'w') as configfile:
                        config.write()
                    print('[' + time.strftime("%d/%m/%Y %H:%M:%S") + '] Successfully sent new build for ' + service)

        time.sleep(sleep_time)
