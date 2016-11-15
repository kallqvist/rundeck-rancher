from requests.auth import HTTPBasicAuth
import requests
import json
import os

api_base_url = os.environ['CATTLE_CONFIG_URL']
api_access_key = os.environ['CATTLE_ACCESS_KEY']
api_secret_key = os.environ['CATTLE_SECRET_KEY']
api_auth = HTTPBasicAuth(api_access_key, api_secret_key)

# api_url_environment = '{}/environment'.format(api_base_url)
# api_res_environment = requests.get(api_url_environment, auth=api_auth).json()
# print(json.dumps(api_res_environment, indent=2))

api_url_containers = '{}/containers'.format(api_base_url)
api_res_containers = requests.get(api_url_containers, auth=api_auth).json()

if not 'data' in api_res_containers:
    raise Exception("No data returned from Rancher API")

nodes = {}

# plugin config
stack_filter = os.environ.get('RD_CONFIG_STACK_NAME', '').lower()

for container in api_res_containers['data']:
    # todo: environment ID?
    node = {
        'id': container['id'],
        # 'type': container['kind'],
        'image': container['imageUuid'],
        'state': container['state'],
        'nodename': container['name'],
        'hostname': '-', # todo: shouldn't need this?
        'tty': bool(container['tty']),
    }

    # print(json.dumps(container, indent=2))

    # skip rancher network agents
    if 'io.rancher.container.system' in container['labels'] and container['labels']['io.rancher.container.system'] == 'NetworkAgent':
        continue

    # fetch additional labels
    if 'io.rancher.stack.name' in container['labels']:
        node['stack'] = container['labels']['io.rancher.stack.name']

    if 'io.rancher.stack_service.name' in container['labels']:
        node['stack_service'] = container['labels']['io.rancher.stack_service.name']

    if 'io.rancher.container.start_once' in container['labels']:
        node['start_once'] = container['labels']['io.rancher.container.start_once']

    if len(stack_filter) > 0:
        if not 'stack' in node or node['stack'].lower() != stack_filter:
            continue

    nodes[node['nodename']] = node

print( json.dumps(nodes, indent=2) )
