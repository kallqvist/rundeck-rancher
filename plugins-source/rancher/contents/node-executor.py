from _nodes_shared import *

bash_script = os.environ.get('RD_EXEC_COMMAND', '')
bash_script = bash_script.strip().encode("string_escape").replace('"', '\\\"')
# print(bash_script)

if len(bash_script) == 0:
    raise Exception( "Can't run, command is empty!" )

# check if container is running?
container_api_url = "{}/container/{}".format(api_base_url, node_id)
container_api_res = requests.get(container_api_url, auth=api_auth)
container_api_res_json = container_api_res.json()
# print(json.dumps(container_api_res_json, indent=2))

if container_api_res.status_code != 200:
    raise Exception("Rancher API error, code \"{} ({})\"!".format(api_res_json['code'], api_res_json['status']))

if container_api_res_json['state'] != 'running':
    raise Exception("Invalid container state, must be set to 'running'!")

api_data = {
    "attachStdin": False,
    "attachStdout": True,
    "command": [
      "/bin/bash",
      "-c",
      '{{ {{ {}; }} > >( while read line; do echo "1 $(date -u +%Y-%m-%dT%H:%M:%SZ) ${{line}}"; done ); }} 2> >( while read line; do echo "2 $(date -u +%Y-%m-%dT%H:%M:%SZ) ${{line}}"; done )'.format(bash_script)
    ],
    "tty": False
}
# print(json.dumps(api_data, indent=2))

api_url = "{}/containers/{}?action=execute".format(api_base_url, node_id)
api_res = requests.post(api_url, auth=api_auth, json=api_data)
api_res_json = api_res.json()
# print(json.dumps(api_res_json, indent=2))

if api_res.status_code != 200:
    raise Exception("Rancher API error, code \"{} ({})\"!".format(api_res_json['code'], api_res_json['status']))



#
# LOG LISTENER
#
ws_url_logs = "{}?token={}".format(api_res_json['url'], api_res_json['token'])

def logs_on_message(ws, message):
    msg_match = re.match(log_re_pattern, base64.b64decode(message).strip())
    if not msg_match:
        raise Exception("Failed to read log format, regex does not match!")

    is_error = (int(msg_match.group(1)) == 2)
    log_date = parse(msg_match.group(2)).replace(tzinfo=None)
    log_message = msg_match.group(3)

    if is_error:
        raise Exception(log_message)

    print(log_message)

ws_logs = websocket.WebSocketApp(ws_url_logs,
    on_message = logs_on_message,
    header = ws_auth_header)
ws_logs.run_forever()

if log_handler.has_error == True:
    raise Exception(log_handler.last_error)
log_handler.clear()
