# common code
from _nodes_shared import *

# todo: is run-once service?
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

def history_logs_on_error(ws, error):
    print("### history logs error ###")
    raise Exception(error)

history_logs_ws = websocket.WebSocketApp(ws_url_logs,
    on_message = history_logs_on_message,
    header = ws_auth_header)
history_logs_ws.run_forever()
history_logs_last_timestamp = history_logs_last_timestamp[0]

if history_logs_last_timestamp == None:
    raise Exception("Failed to read last log timestamp!")

print("Last historical timestamp: {}".format(history_logs_last_timestamp))

if log_handler.has_error == True:
    raise Exception(log_handler.last_error)
log_handler.clear()

# todo: start service




#
# EVENT LISTENER
#

def events_on_error(ws, error):
    print("### events error ###")
    raise Exception(error)

def events_on_close(ws):
    print("### events closed ###")

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

if log_handler.has_error == True:
    raise Exception(log_handler.last_error)
log_handler.clear()




# todo: class?

#
# LOG LISTENER
#
def logs_on_error(ws, error):
    print("### logs error ###")
    raise Exception(error)

def logs_on_close(ws):
    print "### logs closed ###"

def logs_on_open(ws):
    print("### logs opened ###")

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

if log_handler.has_error == True:
    raise Exception(log_handler.last_error)
log_handler.clear()

print("=== DONE ===")
