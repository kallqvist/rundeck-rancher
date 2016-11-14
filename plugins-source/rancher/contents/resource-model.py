from requests.auth import HTTPBasicAuth
import requests
import json
import os

# todo: environment id?

api_url = '{}/containers'.format(os.environ['CATTLE_CONFIG_URL'])
api_res = requests.get(api_url, auth=HTTPBasicAuth(os.environ['CATTLE_ACCESS_KEY'], os.environ['CATTLE_SECRET_KEY'])).json()

if not 'data' in api_res:
    raise Exception("No data returned from Rancher API")

nodes = {}

# plugin config
stack_filter = os.environ.get('RD_CONFIG_STACK_NAME', '').lower()

for container in api_res['data']:
    node = {
        'id': container['id'],
        # 'type': container['kind'],
        'image': container['imageUuid'],
        'state': container['state'],
        'nodename': container['name'],
        'hostname': container['name'],
    }

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
