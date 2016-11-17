from _nodes_shared import *

bash_script = os.environ.get('RD_EXEC_COMMAND', '')

if len(bash_script) == 0:
    raise Exception( "Can't run, command is empty!" )

# todo: is container running?

# bash_script = bash_script.strip().encode("string_escape").replace('"', '\\\"')

node_id = "1i19139"

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

api_url = "{}/containers/{}?action=execute".format(api_base_url, node_id)
api_res = requests.post(api_url, auth=HTTPBasicAuth(api_access_key, api_secret_key), json=api_data)
api_res_json = api_res.json()

if api_res.status_code != 200:
    raise Exception("Rancher API error, code \"{} ({})\"!".format(api_res_json['code'], api_res_json['status']))

ws_url = "{}?token={}".format(api_res_json['url'], api_res_json['token'])
ws = websocket.create_connection(ws_url)
ws_res = ws.recv()

print(base64.b64decode(ws_res).strip())
