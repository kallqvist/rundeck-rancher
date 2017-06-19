from websocket import create_connection
import websocket
import StringIO
import requests
import hashlib
import base64
import os
import re
from _containers_shared import *



@retry()
def request_execute_token():
    api_data = {
        "attachStdin": False,
        "attachStdout": True,
        "command": [
            "/bin/bash",
            "-c",
            'echo $$ > /tmp/{rundeck_job_exec_id}.pid; {{ {{ {bash_script}; }} > >( while read line; do echo 1 $(date -u +%Y-%m-%dT%H:%M:%SZ) ${{line}}; done ); }} 2> >( while read line; do echo 2 $(date -u +%Y-%m-%dT%H:%M:%SZ) ${{line}}; done ) | tee /tmp/{rundeck_job_exec_id}.out'.format(rundeck_job_exec_id=rundeck_job_exec_id, bash_script=bash_script)
        ],
        "tty": False
    }
    api_url = "{}/containers/{}?action=execute".format(api_base_url, node_id)
    api_res = requests.post(api_url, auth=api_auth, json=api_data)
    api_res_json = api_res.json()
    # log(json.dumps(api_res_json, indent=2))
    if not api_res.status_code < 300:
        raise Exception("Failed to create 'execute script' socket token: API error, code \"{} ({})\"!".format(api_res_json['code'], api_res_json['status']))
    return api_res_json


# this websocket will execute the command, we don't want to use retry here!
def execute_command():
    execute_token_res = request_execute_token()
    ws_url_execute = "{}?token={}".format(execute_token_res['url'], execute_token_res['token'])
    ws_exec = websocket.WebSocketApp(ws_url_execute,
                                     on_message=execute_on_message,
                                     header=ws_auth_header)
    ws_exec.run_forever()


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



@retry(attempts=-1, interval=30)  # -1 = try forever
def execute_pid_check():
    pid_check_token_res = request_pid_check_token()
    pid_check_result = 1
    ws_url_pid_check = "{}?token={}".format(
        pid_check_token_res['url'],
        pid_check_token_res['token']
        )
    ws = create_connection(ws_url_pid_check)
    pid_check_response = parse_websocket_response(base64.b64decode(ws.recv()))
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
                                     on_message=logs_on_message,
                                     header=ws_auth_header)
    ws_logs.run_forever()


def execute_on_message(ws, message):
    message_text = base64.b64decode(message)
    parse_logs(message_text, fail_on_parse_error=False)

log_chunks = []
seen_logs_md5 = []
def logs_on_message(ws, message):
    message_text = parse_websocket_response(base64.b64decode(message))
    log_chunks.append(message_text)


# Read rundeck values
bash_script = os.environ.get('RD_EXEC_COMMAND', '')
bash_script = bash_script.strip().encode("string_escape").replace('"', '\\\"')
if len(bash_script) == 0:
    raise Exception("Can't run, command is empty!")


# check container is running
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





log("[ I ] Executing command...")
execute_command()
log("[ I ] Log listener disconnected...")
log("[ I ] Reading PID status to check if still running...")
execute_pid_check()
log("[ I ] Command execution is done, reading remaining log output from container storage...")
execute_read_final_logs()
parse_logs(''.join(log_chunks))
log("[ I ] Done!")

if log_handler.has_error is True:
    raise Exception(log_handler.last_error)
log_handler.clear()
