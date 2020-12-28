#!/usr/bin/env python
import os
import sys
import subprocess
import datetime
from time import time
import argparse
import socket
import requests
import xmltodict as xtd
import traceback
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import json
except ImportError:
    import simplejson as json
class HMCInventory(object):
    
    def __init__(self):

        
        requests.packages.urllib3.disable_warnings()
        ''' Main execution path '''

        self.parse_cli_args()

        ''' Workflow begins. '''
        # Get the auth key.

        self.session = requests.Session()

        # Parse CLI arguments
        inventory_type = 'all'

        self.inventory = {
            '_meta': {
                'hostvars': {}
            },
            'lpars': {
                'hosts': [],
                'vars': {},
                'children': []

            }
        }

        self.hmc_address = ""
        self.hmc_port = 0
        self.hmc_username = ""
        self.hmc_password = ""
        self.verify_ssl = True

        auth_key, url = self.hmc_inventory(inventory_type)

        self.build_cluster_inventory(inventory_type, auth_key, url)

    @staticmethod
    def get_auth_key(url, hmc_user, hmc_password, verify_ssl):

        try:
            auth_body = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <LogonRequest xmlns="http://www.ibm.com/xmlns/systems/power/firmware/web/mc/2012_10/"
            schemaVersion="V1_1_0">
            <Metadata>
            <Atom/>
            </Metadata>
            <UserID kb="CUR" kxe="false">''' + hmc_user + '''</UserID>
            <Password kb="CUR" kxe="false">''' + hmc_password + '''</Password>
            </LogonRequest>
            '''
            auth_response = requests.put(url + 'web/Logon', headers={
                'Content-Type': 'application/vnd.ibm.powervm.web+xml; type=LogonRequest'}, data=auth_body, verify=verify_ssl,
                                         timeout=60)
            auth_key = json.loads(json.dumps(xtd.parse(auth_response.text)))['LogonResponse']['X-API-Session']['#text']
        except Exception as exception:
            print(url + " - Authentication Failure")
            raise Exception(exception)

        return auth_key, url


    def parse_cli_args(self):
        ''' Command line argument processing '''

        parser = argparse.ArgumentParser(
            description='Produce an Ansible inventory file from Nutanix')

        parser.add_argument('--list', action='store_true', default=True,
                            help='List instances by IP address (default: True)')
        parser.add_argument('--host', action='store',
                            help='Get all variables about a VM')
        parser.add_argument('--names', action='store_true',
                            help='List instances by VM name')
        parser.add_argument('--pretty', action='store_true',
                            help='Pretty-print results')
        parser.add_argument('--refresh-cache', action='store_true',
                            help='Force refresh of cache by making API requests to Nutanix (default: False - use cache files)')

        self.args = parser.parse_args()

    def build_cluster_inventory(self, inventory_type, auth_key, url):
        ''' Generate inventory per cluster '''

    # Get all Systems.
        try:
            systems_dump = requests.get(url + 'uom/ManagedSystem', headers={
                'Content-Type': 'application/vnd.ibm.powervm.web+xml; type=ManagedSystem', 'X-API-Session': auth_key},
                                        verify=False, timeout=300)
            all_systems = json.loads(json.dumps(xtd.parse(systems_dump.text)))['feed']['entry']
        except Exception as exception:
            print("Get Systems has failed with error: {0}".format(repr(exception)))
            raise Exception(exception)

        for system in all_systems:

            sys_id = system['id']
            systems_and_lpars = system

            lpar_dump = requests.get(url + 'uom/ManagedSystem/' + sys_id + '/LogicalPartition', headers={
                'Content-Type': 'application/vnd.ibm.powervm.web+xml; type=LogicalPartition',
                'X-API-Session': auth_key}, verify=False, timeout=120)
            if lpar_dump.text != '':  # Some systems have no LPARs and return nothing
                all_lpars = json.loads(json.dumps(xtd.parse(lpar_dump.text)))  # Load into a dict

                systems_and_lpars['lpars'] = {}   
                
                for lpar in all_lpars['feed']['entry']:
                    # Collect each LPAR's data under a branch of that system.
                    if 'PartitionProfiles' not in lpar['content']['LogicalPartition:LogicalPartition'] or 'link' not in \
                            lpar['content']['LogicalPartition:LogicalPartition']['PartitionProfiles']:
                        continue
                    systems_and_lpars['lpars'][lpar['id']] = lpar

                    lpar_name = lpar['content']['LogicalPartition:LogicalPartition']['PartitionName']['#text']
                    # Collect each LPAR PROFILE's data under a branch of THAT branch.
                    systems_and_lpars['lpars'][lpar['id']]['lpar_profiles'] = {}
                    
                    self.inventory['_meta']['hostvars'].update({lpar_name: {}})

                    try:
                        ip_lpar = {'ansible_host': lpar['content']['LogicalPartition:LogicalPartition'][
                            'ResourceMonitoringIPAddress']['#text']}
                        self.inventory['_meta']['hostvars'][lpar_name].update(ip_lpar)
                        self.inventory['lpars']['hosts'] += [lpar_name]

                    except: 
                        ip_lpar = {'ansible_host': lpar_name}
                        self.inventory['_meta']['hostvars'][lpar_name].update(ip_lpar)
                        self.inventory['lpars']['hosts'] += [lpar_name]
                        continue

                   
         
        print(json.dumps(self.inventory))
        return self.inventory

    def hmc_inventory(self, inventory_type): # passing 'all' to inventory_type
        ''' Generate inventory from one or more configured clusters '''

        try:
            try:
                self.hmc_address = os.environ.get('hmchostname')
            except KeyError:
                print('An address must be configured for cluster.')
                sys.exit(1)
            # API port defaults to 443 unless specified otherwise
            if os.environ.get('hmc_port'):
                self.hmc_port = os.environ.get('hmc_port')
            else:
                self.hmc_port = 443
            # Get cluster username
            try:
                self.hmc_username = os.environ.get('hmcuser')
            except KeyError:
                print('A username must be configured for cluster.')
                sys.exit(1)
            # Get cluster password
            try:
                self.hmc_password = os.environ.get('hmcpassword')
            except KeyError:
                print('A password must be configured for cluster.')
                sys.exit(1)
            # SSL verification defaults to True unless specified otherwise
            if os.environ.get('hmc_verify'):
                self.verify_ssl = True
            else:
                self.verify_ssl = False
        except TypeError:
            print('No credentials found')
            sys.exit(1)
        url = "https://" + self.hmc_address + "/rest/api/"
        auth_key, url = self.get_auth_key(url, self.hmc_username, self.hmc_password, self.verify_ssl)
        return auth_key, url

HMCInventory()
