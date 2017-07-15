import configparser
import os
import argparse
import configparser
import time

import requests

from json import loads as jload

defaultconfig = '''
# WARNING: COMMENTS IN THIS FILE WILL BE ERASED WHEN PROGRAM IS RUN!
[Connection]
# Specify the URL to the drone server, including port and protocol
host = https://drone.example.org
auth_key = eyJEXAMPLE.AUTH.KEY
# Specified in seconds (Default: 300)
# sleep_time = 300

#[ExampleGitHubBuild]
# Example shown uses githubs api to find and compare on the sha of the latest commit
# Name of the repo to trigger in drone
#drone_repo = Example/HelloWorld

# URL of the json structure that needs curling
#url = https://api.github.com/repos/Kaylee/ShinyRepo/git/refs/heads/master

# JSON Tree needed to resolve the value.
# structure = object.sha


#[ExampleGitHubRelease]
#drone_repo = Example/HelloRelease
#url = https://api.github.com/repos/Kaylee/ShinyRepo/releases/latest
#structure = name
'''


def runbuild(repo: str):
    url = drone_host + '/api/repos/' + repo
    latest = jload(requests.get(url + '/builds/latest',
                                headers={'Authorization': auth}).text)['number']
    buildurl = url + '/builds/' + str(latest) + '?fork=true'
    # [[TODO]] Add functionality for checking if build was triggered successfully?
    return (requests.post(buildurl, headers={'Authorization': drone_auth_key}))


def jsonVal(jraw, struct):
    try:
        dataDict = jload(jraw)
        for i in struct.split('.'):
            dataDict = dataDict[i]
        return dataDict
    except KeyError:
        print('Error: Invalid structure: ' + struct)
        print(dataDict)
        exit(1)
    except:
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

    config = configparser.ConfigParser()
    config.read(filepath + '/dronetrigger.cfg')
    if not ('Connection' in config):
        print('Error: Connection block not found, please check your config')
        exit(78)
    if not (config['Connection'].get('host', False)) or not (config['Connection'].get('auth_key', False)):
        print('Error: Missing connection details. please check your config')
        exit(78)
    if (len(config.sections()) < 2):
        print('Error: Please configure some monitoring blocks!')
        exit(78)
    # These can be assumed since we have verified
    drone_host = config['Connection']['host']
    drone_auth_key = config['Connection']['auth_key']
    sleep_time = config['Connection'].getint('sleep_time', 300)

    for service in config.sections():
        if service == 'Connection':
            continue
        if not (config[service].get('url', False)) or not (config[service].get('structure', False)) or not(config[service].get('drone_repo'), False):
            print('Error: Missing required value in status block ' + service)
            exit(78)
        try:
            r = requests.get(config[service].get('url'))
            r.raise_for_status()
            curr_value = jsonVal(r.text, config[service].get('structure'))
        except:
            raise
        if not (config[service].get('current_value', False)):
            print('Writing Initial value for ' + service + ': ' + curr_value)
            config[service]['current_value'] = curr_value
            with open(filepath + '/dronetrigger.cfg', 'w') as configfile:
                config.write(configfile)

    while(True):
        for service in config.sections():
            if service == 'Connection':
                continue
            try:
                r = requests.get(config[service].get('url'))
                r.raise_for_status()
                new_value = jsonVal(r.text, config[service].get('structure'))
                if (new_value != config[service]['current_value']):
                    print(date.strftime("%d/%m/%Y %H:%M:%S") +
                          ': Got new build - ' + new_value)
                    runbuild(config[service].get('drone_repo'))
                    config[service]['current_value'] = new_value
                    with open(filepath + '/dronetrigger.cfg', 'w') as configfile:
                        config.write(configfile)

            except:
                raise
        time.sleep(sleep_time)
