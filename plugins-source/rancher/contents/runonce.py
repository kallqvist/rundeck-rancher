from requests.auth import HTTPBasicAuth
import requests
import websocket
import time
import json
import os
import base64

# todo: remove this when rundeck bug is resolved
cattle_config = json.load(open("/rancher-auth-workaround.json"))
api_base_url = cattle_config['host'] # os.environ['CATTLE_CONFIG_URL']
api_access_key = cattle_config['access_key'] #  os.environ['CATTLE_ACCESS_KEY']
api_secret_key = cattle_config['secret_key'] #  os.environ['CATTLE_SECRET_KEY']

api_data = {
    "follow": True,
    "lines": 100
}

node_id = os.environ.get('RD_NODE_ID', '')
if len(node_id) == 0:
    raise Exception("Can't run, node ID is not set!")

# todo: is run-once service?

# tell the service to start before attaching log listener
# api_url_start = "{}/containers/{}?action=start".format(api_base_url, node_id)
# api_res_start = requests.post(api_url_start, auth=HTTPBasicAuth(api_access_key, api_secret_key), json=api_data)
# api_res_start_json = api_res_start.json()
# print(api_res_start_json)
#
# print("---------------------------------------------------------------------")

# if api_res_start.status_code != 200:
#     raise Exception("Can't start service, code \"{} ({})\"!".format(api_res_start_json['code'], api_res_start_json['status']))

print("===============================================")

def on_error(ws, error):
    print("### err ###")
    print error

def on_close(ws):
    print "### closed ###"

def on_open(ws):
    print("### opened ###")

def on_message(ws, message):
    json_message = json.loads(message)
    if "resourceId" not in json_message or json_message["resourceId"] != node_id:
        return
    node_state = json_message["data"]["resource"]["state"]
    print(node_state)
    if node_state == "running":
        ws.close()
    # print(json.dumps(json_message, indent=2))

print("Listening...")



ws_base_url = api_base_url.replace("https", "wss")

# todo: environment ID?
ws_url = "{}/projects/1a81/subscribe?eventNames=resource.change".format(ws_base_url)
ws = websocket.WebSocketApp(ws_url,
    on_open = on_open,
    on_message = on_message,
    on_error = on_error,
    on_close = on_close,
    header = {'Authorization': "Basic " + base64.b64encode("{}:{}".format(api_access_key, api_secret_key))})
ws.run_forever()

print("#######################################################################")


# setup websocket for reading log output
api_url_logs = "{}/containers/{}?action=logs".format(api_base_url, node_id)
api_res_logs = requests.post(api_url_logs, auth=HTTPBasicAuth(api_access_key, api_secret_key), json=api_data)
api_res_logs_json = api_res_logs.json()
# print(api_res_logs_json)
#
if api_res_logs.status_code != 200:
    raise Exception("Can't create log listener, code \"{} ({})\"!".format(api_res_logs_json['code'], api_res_logs_json['status']))

# attach to log listener websocket
ws_url = "{}?token={}".format(api_res_logs_json['url'], api_res_logs_json['token'])
ws = websocket.create_connection(ws_url)
ws_res = ws.recv()

print(ws_res)
# print(base64.b64decode(ws_res).strip())
