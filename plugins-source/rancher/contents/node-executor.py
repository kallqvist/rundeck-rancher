from _nodes_shared import *

pid_check_timeout = 10

bash_script = os.environ.get('RD_EXEC_COMMAND', '')
bash_script = bash_script.strip().encode("string_escape").replace('"', '\\\"')
# log(bash_script)

if len(bash_script) == 0:
    raise Exception( "Can't run, command is empty!" )

reconnect_attempts = 0
while True:
    container_api_url = "{}/container/{}".format(api_base_url, node_id)
    container_api_res = requests.get(container_api_url, auth=api_auth)
    container_api_res_json = container_api_res.json()
    # log(json.dumps(container_api_res_json, indent=2))

    if not container_api_res.status_code < 300:
        reconnect_attempts += 1
        if reconnect_attempts > reconnect_attempts_limit:
            raise Exception("Failed to read container information: API error, code \"{} ({})\"!".format(container_api_res_json['code'], container_api_res_json['status']))
        else:
            log("[ W ] Failed to read container information. Retrying attempt {}/{} in {} seconds...".format(reconnect_attempts, reconnect_attempts_limit, reconnect_timeout))
            time.sleep(reconnect_timeout)
            continue

    # all is good
    if container_api_res_json['state'] != 'running':
        raise Exception("Invalid container state, must be set to 'running'!")
    break



# create an ID for this job session to use for future reconnection attempts
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
      'echo $$ > /tmp/{rundeck_job_exec_id}.pid; {{ {{ {bash_script}; }} > >( while read line; do echo 1 $(date -u +%Y-%m-%dT%H:%M:%S.%6NZ) ${{line}}; done ); }} 2> >( while read line; do echo 2 $(date -u +%Y-%m-%dT%H:%M:%S.%6NZ) ${{line}}; done ) | tee /tmp/{rundeck_job_exec_id}.out'.format(rundeck_job_exec_id=rundeck_job_exec_id, bash_script=bash_script)
    ],
    "tty": False
}
# log(json.dumps(exec_api_data, indent=2))

reconnect_attempts = 0
while True:
    api_url = "{}/containers/{}?action=execute".format(api_base_url, node_id)
    api_res = requests.post(api_url, auth=api_auth, json=exec_api_data)
    api_res_json = api_res.json()
    # log(json.dumps(api_res_json, indent=2))

    if not api_res.status_code < 300:
        reconnect_attempts += 1
        if reconnect_attempts > reconnect_attempts_limit:
            raise Exception("Failed to create 'execute script' socket token: API error, code \"{} ({})\"!".format(api_res_json['code'], api_res_json['status']))
        else:
            log("[ W ] Failed to create 'execute script' token. Retrying attempt {}/{} in {} seconds...".format(reconnect_attempts, reconnect_attempts_limit, reconnect_timeout))
            time.sleep(reconnect_timeout)
            continue

    # all is good
    break







#
# Execute command and read output
#

# todo: retry? (can't without executing comand again...)
# we need to open the socket to trigger the command but we wait with reading logs until everything is done
ws_url_execute = "{}?token={}".format(api_res_json['url'], api_res_json['token'])
log("[ I ] Executing command...")
# ws_exec = create_connection(ws_url_execute)
# # result =  ws.recv()
# # print "Received '%s'" % result
# ws_exec.close()



seen_logs_md5 = []
def logs_on_message(ws, message):
    message_text = base64.b64decode(message).strip()

    # sometimes we get single lines, sometimes we get all the logs at once...
    string_buf = StringIO.StringIO(message_text)
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

        # parse log format
        is_error = (int(msg_match.group(1)) == 2)
        log_date = parse(msg_match.group(2)).replace(tzinfo=None)
        log_message = msg_match.group(3)

        if is_error:
            raise Exception(log_message)

        log(log_message)

ws_logs = websocket.WebSocketApp(ws_url_execute,
    on_message = logs_on_message,
    header = ws_auth_header)
ws_logs.run_forever()
log("[ I ] Log listener disconnected...")

if log_handler.has_error == True:
    raise Exception(log_handler.last_error)
log_handler.clear()



# check if pid is still alive and sleep for a while if it is
pid_check_api_data = {
    "attachStdin": False,
    "attachStdout": True,
    "command": [
      "/bin/sh",
      "-c",
      'if ps -p $(cat /tmp/{rundeck_job_exec_id}.pid) > /dev/null; then echo 1; else echo 0; fi'.format(rundeck_job_exec_id=rundeck_job_exec_id)
    ],
    "tty": False
}
# log(json.dumps(pid_check_api_data, indent=2))

reconnect_attempts = 0
while True:
    pid_check_api_url = "{}/containers/{}?action=execute".format(api_base_url, node_id)
    pid_check_api_res = requests.post(pid_check_api_url, auth=api_auth, json=pid_check_api_data)
    pid_check_api_res_json = pid_check_api_res.json()

    if not pid_check_api_res.status_code < 300:
        reconnect_attempts += 1
        if reconnect_attempts > reconnect_attempts_limit:
            raise Exception("Can't create 'PID state' socket token, code \"{} ({})\"!".format(api_res_info_json['code'], api_res_info_json['status']))
        else:
            log("[ W ] Failed to create 'PID state' socket token. Retrying attempt {}/{} in {} seconds...".format(reconnect_attempts, reconnect_attempts_limit, reconnect_timeout))
            time.sleep(reconnect_timeout)
            continue

    # all is good
    break


# time.sleep(timeout_between_stages)

# tailing logs while waiting for process to finish
# log_tail_api_data = {
#     "attachStdin": False,
#     "attachStdout": True,
#     "command": [
#       "/bin/sh",
#       "-c",
#       'tail /tmp/{rundeck_job_exec_id}.out'.format(rundeck_job_exec_id=rundeck_job_exec_id)
#     ],
#     "tty": False
# }

# todo: retry?
# log_tail_api_url = "{}/containers/{}?action=execute".format(api_base_url, node_id)
# log_tail_api_res = requests.post(log_tail_api_url, auth=api_auth, json=log_tail_api_data)
# log_tail_api_res_json = log_tail_api_res.json()
#
# time.sleep(timeout_between_stages)


log("[ I ] Reconnecting to see if command is done executing and logs are remaining...")
pid_check_result = 1
while True:
    ws_url_pid_check = "{}?token={}".format(pid_check_api_res_json['url'], pid_check_api_res_json['token'])
    ws = create_connection(ws_url_pid_check)
    pid_check_response = base64.b64decode(ws.recv())
    ws.close()

    try:
        pid_check_result =  int(pid_check_response)
    except ValueError:
        log("[ W ] Failed to read PID state: '{}'".format(pid_check_response))
        pid_check_result = -1

    if not pid_check_result == 0:
        log("[ W ] Process have not yet stopped in container (PID {}), waiting for {} seconds and trying again.".format(pid_check_result, pid_check_timeout))
        time.sleep(pid_check_timeout)
        continue

    # all good
    log("[ I ] Process have exited")
    break

    # todo: tail current log progress? don't know if we can or if rundeck buffer all output until script is done?
    # ws_url_log_tail = "{}?token={}".format(pid_check_api_res_json['url'], pid_check_api_res_json['token'])

# time.sleep(timeout_between_stages)

log("[ I ] Command execution is done, reading remaining log output from container storage...\n")

# Finally, when we're sure the command isn't running anymore we connect one last time to read all logs from disk
final_log_read_api_data = {
    "attachStdin": False,
    "attachStdout": True,
    "command": [
      "/bin/sh",
      "-c",
      'cat /tmp/{rundeck_job_exec_id}.out'.format(rundeck_job_exec_id=rundeck_job_exec_id)
    ],
    "tty": False
}
# log(json.dumps(pid_check_api_data, indent=2))

reconnect_attempts = 0
while True:
    final_log_read_api_url = "{}/containers/{}?action=execute".format(api_base_url, node_id)
    final_log_read_api_res = requests.post(final_log_read_api_url, auth=api_auth, json=final_log_read_api_data)
    final_log_read_api_res_json = final_log_read_api_res.json()

    if not final_log_read_api_res.status_code < 300:
        reconnect_attempts += 1
        if reconnect_attempts > reconnect_attempts_limit:
            raise Exception("Can't read container logs, code \"{} ({})\"!".format(api_res_info_json['code'], api_res_info_json['status']))
        else:
            log("[ W ] Failed to read container logs. Retrying attempt {}/{} in {} seconds...".format(reconnect_attempts, reconnect_attempts_limit, reconnect_timeout))
            time.sleep(reconnect_timeout)
            continue

    # all is good
    ws_url_final_logs = "{}?token={}".format(final_log_read_api_res_json['url'], final_log_read_api_res_json['token'])
    break


# todo: retry?
ws_logs = websocket.WebSocketApp(ws_url_final_logs,
    on_message = logs_on_message,
    header = ws_auth_header)
ws_logs.run_forever()

if log_handler.has_error == True:
    raise Exception(log_handler.last_error)
log_handler.clear()
