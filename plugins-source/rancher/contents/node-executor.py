from websocket import create_connection
import websocket
import StringIO
import requests
import hashlib
import base64
import os
import re
from _nodes_shared import *

bash_script = os.environ.get('RD_EXEC_COMMAND', '')
bash_script = bash_script.strip().encode("string_escape").replace('"', '\\\"')
# log(bash_script)

if len(bash_script) == 0:
    raise Exception("Can't run, command is empty!")


@retry()
def get_container_information():
    api_url = "{}/container/{}".format(api_base_url, node_id)
    api_res = requests.get(api_url, auth=api_auth)
    api_res_json = api_res.json()
    # log(json.dumps(api_res_json, indent=2))
    if not api_res.status_code < 300:
        raise Exception("Failed to read container information: API error, code \"{} ({})\"!".format(api_res_json['code'], api_res_json['status']))
    return api_res_json


# todo: check container is running
container_info_res = get_container_information()
if container_info_res['state'] != 'running':
    raise Exception("Invalid container state, must be set to 'running'!")



# create an unique ID for this job execution
rundeck_project = os.environ.get('RD_RUNDECK_PROJECT', '')
rundeck_exec_id = os.environ.get('RD_JOB_EXECID', '')
rundeck_retry_attempt = os.environ.get('RD_JOB_RETRYATTEMPT', '')
if len(rundeck_project) == 0 or len(rundeck_exec_id) == 0:
    raise Exception("Can't create run ID, RD_RUNDECK_PROJECT, RD_JOB_EXECID or RD_JOB_RETRYATTEMPT is not getting set by rundeck!")
m = hashlib.md5()
m.update(bash_script)
bash_script_md5 = m.hexdigest()
rundeck_job_exec_id = "{}_{}_{}_{}".format(rundeck_project, rundeck_exec_id, rundeck_retry_attempt, bash_script_md5)
log("[ I ] Rundeck job execution ID: {}".format(rundeck_job_exec_id))

exec_api_data = {
    "attachStdin": False,
    "attachStdout": True,
    "command": [
      "/bin/bash",
      "-c",
      'echo $$ > /tmp/{rundeck_job_exec_id}.pid; {{ {{ {bash_script}; }} > >( while read line; do echo 1 $(date -u +%Y-%m-%dT%H:%M:%SZ) ${{line}}; done ); }} 2> >( while read line; do echo 2 $(date -u +%Y-%m-%dT%H:%M:%SZ) ${{line}}; done ) | tee /tmp/{rundeck_job_exec_id}.out'.format(rundeck_job_exec_id=rundeck_job_exec_id, bash_script=bash_script)
    ],
    "tty": False
}
# log(json.dumps(exec_api_data, indent=2))


@retry()
def request_execute_token():
    api_url = "{}/containers/{}?action=execute".format(api_base_url, node_id)
    api_res = requests.post(api_url, auth=api_auth, json=exec_api_data)
    api_res_json = api_res.json()
    # log(json.dumps(api_res_json, indent=2))
    if not api_res.status_code < 300:
        raise Exception("Failed to create 'execute script' socket token: API error, code \"{} ({})\"!".format(api_res_json['code'], api_res_json['status']))
    return api_res_json



#
# Execute command and read output
#

seen_logs_md5 = []


def logs_on_message(ws, message):
    message_text = base64.b64decode(message).strip()
    # sometimes we get single lines, sometimes we get all the logs at once...
    string_buf = StringIO.StringIO(message_text)
    for log_line in string_buf:
        if len(log_line.strip()) == 0:
            continue
        msg_match = re.match(log_re_pattern, log_line, re.MULTILINE | re.DOTALL)
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
        # parse log format
        is_error = (int(msg_match.group(1)) == 2)
        # log_date = parse(msg_match.group(2)).replace(tzinfo=None)
        log_message = msg_match.group(3)
        if is_error:
            raise Exception(log_message)
        log(log_message)







@retry()
def request_pid_check_token():
    api_data = {
        "attachStdin": False,
        "attachStdout": True,
        "command": [
          "/bin/sh",
          "-c",
          'if ps -p $(cat /tmp/{rundeck_job_exec_id}.pid) > /dev/null; then echo 1; else echo 0; fi'.format(rundeck_job_exec_id=rundeck_job_exec_id)
        ],
        "tty": False
    }
    api_url = "{}/containers/{}?action=execute".format(api_base_url, node_id)
    api_res = requests.post(api_url, auth=api_auth, json=api_data)
    api_res_json = api_res.json()
    if not api_res.status_code < 300:
        raise Exception("Can't create 'PID state' socket token, code \"{} ({})\"!".format(api_res_json['code'], api_res_json['status']))
    return api_res_json


log("[ I ] Reconnecting to see if command is done executing and logs are remaining...")


@retry(attempts=-1, interval=30)  # -1 = try forever
def execute_pid_check():
    pid_check_token_res = request_pid_check_token()
    pid_check_result = 1
    ws_url_pid_check = "{}?token={}".format(
        pid_check_token_res['url'],
        pid_check_token_res['token']
        )
    ws = create_connection(ws_url_pid_check)
    pid_check_response = base64.b64decode(ws.recv())
    ws.close()
    try:
        pid_check_result = int(pid_check_response)
    except ValueError:
        log("[ W ] Failed to read PID state: '{}'".format(pid_check_response.strip()))
        pid_check_result = -1
    if not pid_check_result == 0:
        raise Exception(
            "Process have not yet stopped "
            "in container (PID state {})".format(pid_check_result))


@retry()
def request_log_read_token():
    api_data = {
        "attachStdin": False,
        "attachStdout": True,
        "command": [
            "/bin/sh",
            "-c",
            'cat /tmp/{rundeck_job_exec_id}.out'.format(rundeck_job_exec_id=rundeck_job_exec_id)
        ],
        "tty": False
    }
    api_url = "{}/containers/{}?action=execute".format(api_base_url, node_id)
    api_res = requests.post(api_url, auth=api_auth, json=api_data)
    api_res_json = api_res.json()
    if not api_res.status_code < 300:
        raise Exception("Can't read container logs, code \"{} ({})\"!".format(api_res_json['code'], api_res_json['status']))
    return api_res_json


@retry()
def execute_read_final_logs():
    final_logs_token = request_log_read_token()
    ws_url_final_logs = "{}?token={}".format(final_logs_token['url'], final_logs_token['token'])
    ws_logs = websocket.WebSocketApp(ws_url_final_logs,
        on_message = logs_on_message,
        header = ws_auth_header)
    ws_logs.run_forever()



# this websocket will execute the command, we don't want to use retry here!
log("[ I ] Executing command...")
execute_token_res = request_execute_token()
ws_url_execute = "{}?token={}".format(execute_token_res['url'], execute_token_res['token'])
ws_exec = websocket.WebSocketApp(ws_url_execute,
                                 on_message=logs_on_message,
                                 header=ws_auth_header)
ws_exec.run_forever()
log("[ I ] Log listener disconnected...")
log("[ I ] Reading PID status to check if still running...")
execute_pid_check()
log("[ I ] Command execution is done, reading remaining log output from container storage...")
# Finally, when we're sure the command isn't running anymore we connect one last time to read all logs from disk
execute_read_final_logs()

if log_handler.has_error is True:
    raise Exception(log_handler.last_error)
log_handler.clear()
