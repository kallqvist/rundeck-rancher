from dateutil.parser import parse
import websocket
import StringIO
import requests
import hashlib
import json
import time
import os
import re

from _containers_shared import *


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


@retry()
def execute_read_history_logs():
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


@retry()
def start_container():
    api_url_start = "{}/containers/{}?action=start".format(api_base_url, node_id)
    api_res_start = requests.post(api_url_start, auth=api_auth)
    api_res_start_json = api_res_start.json()


@retry()
def wait_for_state_activated():
    ws_base_url = api_base_url.replace("https:", "wss:").replace("http:", "ws:")
    ws_url_events = "{}/projects/{}/subscribe?eventNames=resource.change".format(ws_base_url, environment_id)
    ws_events = websocket.WebSocketApp(ws_url_events,
        on_open = events_on_open,
        on_message = events_on_message,
        header = ws_auth_header
        )
    ws_events.run_forever()


@retry()
def read_logs():
    log("[ I ] Reading logs...")
    log_read_token_res = request_log_read_token()
    ws_url_logs = "{}?token={}".format(log_read_token_res['url'], log_read_token_res['token'])
    ws_logs = websocket.WebSocketApp(ws_url_logs,
        on_message = logs_on_message,
        header = ws_auth_header)
    ws_logs.run_forever()


@retry(attempts=-1)
def read_until_stopped():
    log("[ I ] Waiting until container is stopped...")
    read_logs()
    container_info_res = get_container_information()
    container_state = container_info_res["state"].lower()
    # log("[ I ] Container state: " + container_state)
    if container_state != "stopped":
        raise Exception("Container isn't in state 'stopped' yet.")
    read_logs()  # one last time when container is stopped for any leftover logs




# read last timestamp from historical logs
# todo: multiple lines in one message?
history_logs_last_timestamp = [None]
def history_logs_on_message(ws, message):
    msg_match = re.match(log_re_pattern, message)
    if not msg_match:
        raise Exception("Failed to read log history, regex does not match!")
    history_logs_last_timestamp[0] = parse(msg_match.group(2)).replace(tzinfo=None)

def events_on_open(ws):
    log("[ I ] Events stream opened")
    # trigger container start as soon as socket is open
    start_container()


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
            log(log_message)
            if is_error:
                raise Exception(log_line)





# todo: raise exception if no data is recieved at all?

log("[ I ] Reading container information")
container_info_res = get_container_information()


# check if stopped
if container_info_res['state'] != 'stopped':
    raise Exception("Invalid container state, must be set to 'stopped'!")

# todo: check if is start-once service in API resposne instead
is_start_once = (os.environ.get('RD_NODE_START_ONCE', 'false').lower() == 'true')
if not is_start_once:
    raise Exception("Can't run, isn't start-once service!")

# first we read container info (start-count) so we know if we're dealing with old events or not...
old_container_start_count = container_info_res['startCount']



execute_read_history_logs()
history_logs_last_timestamp = history_logs_last_timestamp[0]
if history_logs_last_timestamp == None:
    raise Exception("Failed to read last log timestamp!")
log("[ I ] Last historical timestamp: {}".format(history_logs_last_timestamp))

wait_for_state_activated()
read_until_stopped()
log("[ I ] Done!")
log("")

if log_handler.has_error == True:
    raise Exception(log_handler.last_error)
log_handler.clear()
