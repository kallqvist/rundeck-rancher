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

for e in os.environ:
    print(e)

# todo: container ID?
api_url = "{}/containers/1i18714?action=execute".format(os.environ['CATTLE_CONFIG_URL'])
api_res = requests.post(api_url, auth=HTTPBasicAuth(os.environ['CATTLE_ACCESS_KEY'], os.environ['CATTLE_SECRET_KEY']), json=api_data).json()

ws_url = "{}?token={}".format(api_res['url'], api_res['token'])
ws = websocket.create_connection(ws_url)
ws_res = ws.recv()

print(base64.b64decode(ws_res).strip())
