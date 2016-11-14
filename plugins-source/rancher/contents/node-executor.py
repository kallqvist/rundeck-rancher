from requests.auth import HTTPBasicAuth
import requests
import websocket
import json
import os
import base64

bash_script = os.environ.get('RD_EXEC_COMMAND', '')

if len(bash_script) == 0:
    raise Exception( "Can't run, command is empty!" )

# bash_script = bash_script.strip().encode("string_escape").replace('"', '\\\"')

# todo: remove this when rundeck bug is resolved
cattle_config = json.load(open("/rancher-auth-workaround.json"))
api_base_url = cattle_config['host'] # os.environ['CATTLE_CONFIG_URL']
api_access_key = cattle_config['access_key'] #  os.environ['CATTLE_ACCESS_KEY']
api_secret_key = cattle_config['secret_key'] #  os.environ['CATTLE_SECRET_KEY']

api_data = {
    # "attachStdin": True,
    "attachStdout": True,
    "command": [
      "/bin/bash",
      "-c",
      bash_script
    ],
    # "tty": True
}

# for e in os.environ:
#     print(e)

node_id = os.environ.get('RD_NODE_ID', '')
if len(node_id) == 0:
    raise Exception("Can't run, node ID is not set!")

# todo: is container running?

api_url = "{}/containers/{}?action=execute".format(api_base_url, node_id)
api_res = requests.post(api_url, auth=HTTPBasicAuth(api_access_key, api_secret_key), json=api_data)
api_res_json = api_res.json()

if api_res.status_code != 200:
    raise Exception("Rancher API error, code \"{} ({})\"!".format(api_res_json['code'], api_res_json['status']))

ws_url = "{}?token={}".format(api_res_json['url'], api_res_json['token'])
ws = websocket.create_connection(ws_url)
ws_res = ws.recv()

print(base64.b64decode(ws_res).strip())
