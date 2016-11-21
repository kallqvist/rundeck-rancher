from collections import OrderedDict
from requests.auth import HTTPBasicAuth
import requests
import json
import os
import re

# todo: optional one container per service?
# todo: ignore sidekicks?

api_base_url = os.environ['CATTLE_CONFIG_URL']
api_access_key = os.environ['CATTLE_ACCESS_KEY']
api_secret_key = os.environ['CATTLE_SECRET_KEY']
api_auth = HTTPBasicAuth(api_access_key, api_secret_key)

# plugin config
environment_id = os.environ.get('RD_CONFIG_ENVIRONMENT_ID', '').lower()
stack_filter = os.environ.get('RD_CONFIG_STACK_FILTER', '').lower()
limit_one_container = os.environ.get('RD_CONFIG_LIMIT_ONE_CONTAINER', 'false') == 'true'

if len(environment_id) == 0:
    raise Exception("Environment ID is missing!")

api_url_containers = '{}/projects/{}/containers'.format(api_base_url, environment_id)
api_res_containers = requests.get(api_url_containers, auth=api_auth).json()

if not 'data' in api_res_containers:
    raise Exception("No data returned from Rancher API")

# sort containers by name
sorted_containers = sorted(api_res_containers['data'], key=lambda k: k['name'])

seen_services = []
nodes = OrderedDict()
for container in sorted_containers:
    node = OrderedDict()
    node['id'] = container['id']
    node['type'] = container['kind']
    node['state'] = container['state']
    node['environment_id'] = container['accountId']
    node['nodename'] = container['name']
    node['image'] = container['imageUuid']
    node['tty'] = bool(container['tty'])
    node['start_once'] = False
    node['hostname'] = '-'  # todo: shouldn't need this?
    # print(json.dumps(container, indent=2))

    # skip rancher network agents
    if 'io.rancher.container.system' in container['labels'] and container['labels']['io.rancher.container.system'] == 'NetworkAgent':
        continue

    # fetch additional labels
    if 'io.rancher.stack.name' in container['labels']:
        node['stack'] = container['labels']['io.rancher.stack.name']

    if 'io.rancher.stack_service.name' in container['labels']:
        node['stack_service'] = container['labels']['io.rancher.stack_service.name']
        if limit_one_container:
            if node['stack_service'] in seen_services:
                continue
            else:
                seen_services.append(node['stack_service'])

    if 'io.rancher.container.start_once' in container['labels']:
        node['start_once'] = (container['labels']['io.rancher.container.start_once'].lower() == 'true')

    if len(stack_filter) > 0:
        if 'stack' not in node or not re.search(stack_filter, node['stack'].lower()):
            continue

    nodes[node['nodename']] = node

print( json.dumps(nodes, indent=2) )
