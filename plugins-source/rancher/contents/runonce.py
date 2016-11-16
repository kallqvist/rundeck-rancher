from requests.auth import HTTPBasicAuth
from dateutil.parser import parse
import websocket
import requests
import logging
import base64
import json
import os
import re


# todo: abstract away as shared code
class ErrorLogger(logging.StreamHandler):
    last_error = ''
    def clear(self):
        self.last_error = None

    def emit(self, record):
        msg = self.format(record)
        self.last_error = msg
        raise Exception (msg)
    pass

log_handler = ErrorLogger()
logger = logging.getLogger('websocket')
logger.setLevel(logging.ERROR)
logger.addHandler(log_handler)

# todo: remove this when rundeck bug is resolved
cattle_config = json.load(open("/rancher-auth-workaround.json"))
api_base_url = cattle_config['host'] # os.environ['CATTLE_CONFIG_URL']
api_access_key = cattle_config['access_key'] #  os.environ['CATTLE_ACCESS_KEY']
api_secret_key = cattle_config['secret_key'] #  os.environ['CATTLE_SECRET_KEY']

node_id = os.environ.get('RD_NODE_ID', '')
if len(node_id) == 0:
    raise Exception("Can't run, node ID is not set!")

# todo: is run-once service?
# todo: is tty disabled?
# todo: environment ID?

# tell the service to start before attaching log listener
# api_url_start = "{}/containers/{}?action=start".format(api_base_url, node_id)
# api_res_start = requests.post(api_url_start, auth=HTTPBasicAuth(api_access_key, api_secret_key), json=api_data)
# api_res_start_json = api_res_start.json()
# print(api_res_start_json)
#
# print("---------------------------------------------------------------------")

# if api_res_start.status_code != 200:
#     raise Exception("Can't start service, code \"{} ({})\"!".format(api_res_start_json['code'], api_res_start_json['status']))


log_re_pattern = '^(\d*) (.*?Z) (.*)$'

# setup websocket for reading log output
api_data_logs = {
    "follow": True,
    "lines": 100
}
api_url_logs = "{}/containers/{}?action=logs".format(api_base_url, node_id)
api_res_logs = requests.post(api_url_logs, auth=HTTPBasicAuth(api_access_key, api_secret_key), json=api_data_logs)
api_res_logs_json = api_res_logs.json()
# print(api_res_logs_json)

if api_res_logs.status_code != 200:
    raise Exception("Can't create log listener, code \"{} ({})\"!".format(api_res_logs_json['code'], api_res_logs_json['status']))

ws_url_logs = "{}?token={}".format(api_res_logs_json['url'], api_res_logs_json['token'])
ws_auth_header = {'Authorization': "Basic {}".format(base64.b64encode("{}:{}".format(api_access_key, api_secret_key)))}





#
# HISTORY LOGS
#

# read last timestamp from historical logs
history_logs_last_timestamp = [None]
def history_logs_on_message(ws, message):
    msg_match = re.match(log_re_pattern, message)
    if not msg_match:
        raise Exception("Failed to read log history, regex does not match!")
    history_logs_last_timestamp[0] = parse(msg_match.group(2)).replace(tzinfo=None)

history_logs_ws = websocket.WebSocketApp(ws_url_logs,
    on_message = history_logs_on_message,
    header = ws_auth_header)
history_logs_ws.run_forever()
history_logs_last_timestamp = history_logs_last_timestamp[0]

if history_logs_last_timestamp == None:
    raise Exception("Failed to read last log timestamp!")

# todo: handle error?
log_handler.clear()

# todo: start service




#
# EVENT LISTENER
#
def events_on_error(ws, error):
    print("### events stream error ###")
    print error

def events_on_close(ws):
    print("### events stream closed ###")

def events_on_open(ws):
    print("### events stream opened ###")

def events_on_message(ws, message):
    json_message = json.loads(message)
    if "resourceId" not in json_message or json_message["resourceId"] != node_id:
        return
    node_state = json_message["data"]["resource"]["state"]
    print("Container state: {}".format(node_state))
    # todo: timing issues with short lived containers (already stopped)?
    if node_state in ["running"]:
        ws.close()

# todo: http?
ws_base_url = api_base_url.replace("https", "wss")

ws_url_events = "{}/projects/1a81/subscribe?eventNames=resource.change".format(ws_base_url)
ws_events = websocket.WebSocketApp(ws_url_events,
    on_open = events_on_open,
    on_message = events_on_message,
    on_error = events_on_error,
    on_close = events_on_close,
    header = ws_auth_header)
ws_events.run_forever()

# todo: check for errors
log_handler.clear()




# todo: class?

#
# LOG LISTENER
#
def logs_on_error(ws, error):
    print("### logs stream error ###")
    print(error)

def logs_on_close(ws):
    print "### logs stream closed ###"

def logs_on_open(ws):
    print("### logs stream opened ###")

def logs_on_message(ws, message):
    msg_match = re.match(log_re_pattern, message)
    if not msg_match:
        raise Exception("Failed to read log format, regex does not match!")

    is_error = (int(msg_match.group(1)) == 2)
    log_date = parse(msg_match.group(2)).replace(tzinfo=None)
    log_message = msg_match.group(3)
    # print("{} - {}".format(log_date, log_message))

    if log_date > history_logs_last_timestamp:
        if is_error:
            raise Exception("{} - {}".format(log_date, log_message))

        print("{} - {}".format(log_date, log_message))

ws_logs = websocket.WebSocketApp(ws_url_logs,
    on_open = logs_on_open,
    on_message = logs_on_message,
    on_error = logs_on_error,
    on_close = logs_on_close,
    header = ws_auth_header)
ws_logs.run_forever()

# todo: raise exception if no data is recieved at all?

if len(log_handler.last_error) > 0:
    raise Exception(log_handler.last_error)

print("=== DONE ===")
