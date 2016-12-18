from dateutil.parser import parse
import websocket
import StringIO
import requests
import hashlib
import json
import time
import os
import re

from _nodes_shared import *

# todo: raise exception if no data is recieved at all?

# check if is start-once service
is_start_once = (os.environ.get('RD_NODE_START_ONCE', 'false').lower() == 'true')
if not is_start_once:
    raise Exception("Can't run, isn't start-once service!")


# todo: is container stopped?


# setup websocket for reading log output

@retry()
def request_log_read_token():
    api_data = {
        "follow": True,
        "lines": 1
    }
    api_url = "{}/containers/{}?action=logs".format(api_base_url, node_id)
    api_res = requests.post(api_url, auth=api_auth, json=api_data)
    api_res_json = api_res.json()
    # log(api_res_logs_json)
    if not api_res.status_code < 300:
        raise Exception("Can't create log listener, code \"{} ({})\"!".format(api_res_json['code'], api_res_json['status']))
    return api_res_json


#
# HISTORY LOGS
#

# read last timestamp from historical logs
# todo: multiple lines in one message?
history_logs_last_timestamp = [None]
def history_logs_on_message(ws, message):
    msg_match = re.match(log_re_pattern, message)
    if not msg_match:
        raise Exception("Failed to read log history, regex does not match!")
    history_logs_last_timestamp[0] = parse(msg_match.group(2)).replace(tzinfo=None)


@retry()
def read_history_logs():
    log_read_token_res = request_log_read_token()
    ws_url_logs = "{}?token={}".format(log_read_token_res['url'], log_read_token_res['token'])
    history_logs_ws = websocket.WebSocketApp(ws_url_logs,
        on_message = history_logs_on_message,
        header = ws_auth_header)
    history_logs_ws.run_forever()
    if log_handler.has_error == True:
        e = Exception(log_handler.last_error)
        log_handler.clear()
        raise e
    # todo: can logs be empty if service is new? (set to some minutes ago)
    if history_logs_last_timestamp[0] == None:
        raise Exception("Failed to read last log timestamp!")

read_history_logs()
history_logs_last_timestamp = history_logs_last_timestamp[0]
if history_logs_last_timestamp == None:
    raise Exception("Failed to read last log timestamp!")
log("[ I ] Last historical timestamp: {}".format(history_logs_last_timestamp))



#
# EVENT LISTENER
#

# first we read container info (start-count) so we know if we're dealing with old events or not...
reconnect_attempts = 0
while True:
    api_url_info = "{}/containers/{}".format(api_base_url, node_id)
    api_res_info = requests.get(api_url_info, auth=api_auth)
    api_res_info_json = api_res_info.json()
    # log(json.dumps(api_res_info_json, indent=2))

    if not api_res_info.status_code < 300:
        reconnect_attempts += 1
        if reconnect_attempts > reconnect_attempts_limit:
            raise Exception("Can't read container information, code \"{} ({})\"!".format(api_res_info_json['code'], api_res_info_json['status']))
        else:
            log("[ W ] Failed to read container information. Retrying attempt {}/{} in {} seconds...".format(reconnect_attempts, reconnect_attempts_limit, reconnect_timeout))
            time.sleep(reconnect_timeout)
            continue

    # all is good
    old_container_start_count = api_res_info_json['startCount']
    break



def events_on_open(ws):
    log("[ I ] Events stream opened")
    # tell the service to start before attaching log listener
    reconnect_attempts = 0
    while True:
        api_url_start = "{}/containers/{}?action=start".format(api_base_url, node_id)
        api_res_start = requests.post(api_url_start, auth=api_auth)
        api_res_start_json = api_res_start.json()

        if not api_res_start.status_code < 300:
            reconnect_attempts += 1
            if reconnect_attempts > reconnect_attempts_limit:
                raise Exception("Can't start service, code \"{} ({})\"!".format(api_res_start_json['code'], api_res_start_json['status']))
            else:
                log("[ W ] Failed to start service. Retrying attempt {}/{} in {} seconds...".format(reconnect_attempts, reconnect_attempts_limit, reconnect_timeout))
                time.sleep(reconnect_timeout)
                continue

        # all is good
        break


def events_on_message(ws, message):
    json_message = json.loads(message)
    if "resourceId" not in json_message or json_message["resourceId"] != node_id:
        return
    # is this an old event?
    new_container_start_count = json_message["data"]["resource"]["startCount"]
    if new_container_start_count <= old_container_start_count:
        return
    node_state = json_message["data"]["resource"]["state"]
    log("Container state: {}".format(node_state))
    if node_state in ["running", "stopping", "stopped"]:
        ws.close()

ws_base_url = api_base_url.replace("https:", "wss:").replace("http:", "ws:")


reconnect_attempts = 0
while True:
    ws_url_events = "{}/projects/{}/subscribe?eventNames=resource.change".format(ws_base_url, environment_id)
    ws_events = websocket.WebSocketApp(ws_url_events,
        on_open = events_on_open,
        on_message = events_on_message,
        header = ws_auth_header
        )
    ws_events.run_forever()

    if log_handler.has_error == True:
        reconnect_attempts += 1
        if reconnect_attempts > reconnect_attempts_limit:
            raise Exception(log_handler.last_error)
        else:
            log("[ W ] Error returned from events socket. Retrying attempt {}/{} in {} seconds...".format(reconnect_attempts, reconnect_attempts_limit, reconnect_timeout))
            log(log_handler.last_error)
            time.sleep(reconnect_timeout)
            log_handler.clear()
            continue

    log_handler.clear()

    # all is good
    break



#
# LOG LISTENER
#

seen_logs_md5 = []
def logs_on_message(ws, message):
    # if we would happen to get more than one line of logs per message
    string_buf = StringIO.StringIO(message)
    for log_line in string_buf:
        if len(log_line.strip()) == 0:
            continue

        msg_match = re.match(log_re_pattern, log_line)
        if not msg_match:
            log("[ E ] PARSE_ERROR: " + log_line + " ::")
            raise Exception("Failed to read log format, regex does not match!")

        # keep track of log line hashes so we can ignore already read lines if we need to reconnect and fetch logs
        m = hashlib.md5()
        m.update(log_line)
        message_text_md5 = m.hexdigest()
        if message_text_md5 in seen_logs_md5:
            return
        seen_logs_md5.append(message_text_md5)

        is_error = (int(msg_match.group(1)) == 2)
        log_date = parse(msg_match.group(2)).replace(tzinfo=None)
        log_message = msg_match.group(3)
        # log("{} - {}".format(log_date, log_message))

        if log_date > history_logs_last_timestamp:
            if is_error:
                raise Exception(log_line)
            log(log_message)

# todo: retry?
log_read_token_res = request_log_read_token()
ws_url_logs = "{}?token={}".format(log_read_token_res['url'], log_read_token_res['token'])
ws_logs = websocket.WebSocketApp(ws_url_logs,
    on_message = logs_on_message,
    header = ws_auth_header)
ws_logs.run_forever()


# reconnect to read any remaining logs when we're sure container is stopped
log("[ I ] Waiting until container is stopped...")
container_state = "running"
while container_state != "stopped":
    reconnect_attempts = 0
    while True:
        container_state_api_url = "{}/container/{}".format(api_base_url, node_id)
        container_state_api_res = requests.get(container_state_api_url, auth=api_auth)
        container_state_api_res_json = container_state_api_res.json()

        if not container_state_api_res.status_code < 300:
            reconnect_attempts += 1
            if reconnect_attempts > reconnect_attempts_limit:
                raise Exception("Can't read container state, code \"{} ({})\"!".format(container_state_api_res['code'], container_state_api_res['status']))
            else:
                log("[ W ] Failed to read container state. Retrying attempt {}/{} in {} seconds...".format(reconnect_attempts, reconnect_attempts_limit, reconnect_timeout))
                time.sleep(reconnect_timeout)
                continue

        # all is good
        container_state = container_state_api_res_json["state"].lower()
        log("[ I ] Container state: " + container_state)
        break

# read any remaining logs
log("[ I ] Reconnecting to check if any unread logs are found...")
# todo: retry?
# todo: renew token
ws_logs = websocket.WebSocketApp(ws_url_logs,
    on_message = logs_on_message,
    header = ws_auth_header)
ws_logs.run_forever()

if log_handler.has_error == True:
    raise Exception(log_handler.last_error)
log_handler.clear()

log("[ I ] Done!")
