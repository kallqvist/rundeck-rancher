from _nodes_shared import *

pid_check_timeout = 10
reconnect_timeout = 1

bash_script = os.environ.get('RD_EXEC_COMMAND', '')
bash_script = bash_script.strip().encode("string_escape").replace('"', '\\\"')
# print(bash_script)

if len(bash_script) == 0:
    raise Exception( "Can't run, command is empty!" )

# todo: check if container is running?
container_api_url = "{}/container/{}".format(api_base_url, node_id)
container_api_res = requests.get(container_api_url, auth=api_auth)
container_api_res_json = container_api_res.json()
# print(json.dumps(container_api_res_json, indent=2))

# create an ID for this job session to use for future reconnection attempts
rundeck_project = os.environ.get('RD_RUNDECK_PROJECT', '')
rundeck_exec_id = os.environ.get('RD_JOB_EXECID', '')
if len(rundeck_project) == 0 or len(rundeck_exec_id) == 0:
    raise Exception("Can't create run ID, RD_RUNDECK_PROJECT or RD_JOB_EXECID is not getting set by rundeck!")

m = hashlib.md5()
m.update(bash_script)
bash_script_md5 = m.hexdigest()
rundeck_job_exec_id = "{}_{}_{}".format(rundeck_project, rundeck_exec_id, bash_script_md5)
print("[ I ] Rundeck job execution ID: {}".format(rundeck_job_exec_id))

if container_api_res.status_code != 200:
    raise Exception("Rancher API error, code \"{} ({})\"!".format(container_api_res_json['code'], container_api_res_json['status']))

if container_api_res_json['state'] != 'running':
    raise Exception("Invalid container state, must be set to 'running'!")

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
# print(json.dumps(exec_api_data, indent=2))

api_url = "{}/containers/{}?action=execute".format(api_base_url, node_id)
api_res = requests.post(api_url, auth=api_auth, json=exec_api_data)
api_res_json = api_res.json()
# print(json.dumps(api_res_json, indent=2))

if api_res.status_code != 200:
    raise Exception("Rancher API error, code \"{} ({})\"!".format(api_res_json['code'], api_res_json['status']))



#
# Execute command and read output
#
ws_url_logs = "{}?token={}".format(api_res_json['url'], api_res_json['token'])

# we need to open the socket to trigger the command but we wait with reading logs until everything is done
print("[ I ] Executing command...")
ws_exec = create_connection(ws_url_logs)
# result =  ws.recv()
# print "Received '%s'" % result
ws_exec.close()



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
            print("[ E ] PARSE_ERROR: " + log_line + " ::")
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

        print(log_message)

# ws_logs = websocket.WebSocketApp(ws_url_logs,
#     # on_message = logs_on_message,
#     header = ws_auth_header)
# ws_logs.run_forever()
# print("[ I ] Log listener disconnected...")
#
# if log_handler.has_error == True:
#     raise Exception(log_handler.last_error)
# log_handler.clear()



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
# print(json.dumps(pid_check_api_data, indent=2))

pid_check_api_url = "{}/containers/{}?action=execute".format(api_base_url, node_id)
pid_check_api_res = requests.post(pid_check_api_url, auth=api_auth, json=pid_check_api_data)
pid_check_api_res_json = pid_check_api_res.json()

time.sleep(reconnect_timeout)

# tailing logs while waiting for process to finish
log_tail_api_data = {
    "attachStdin": False,
    "attachStdout": True,
    "command": [
      "/bin/sh",
      "-c",
      'tail /tmp/{rundeck_job_exec_id}.out'.format(rundeck_job_exec_id=rundeck_job_exec_id)
    ],
    "tty": False
}

# log_tail_api_url = "{}/containers/{}?action=execute".format(api_base_url, node_id)
# log_tail_api_res = requests.post(log_tail_api_url, auth=api_auth, json=log_tail_api_data)
# log_tail_api_res_json = log_tail_api_res.json()
#
# time.sleep(reconnect_timeout)


print("[ I ] Reconnecting to see if command is done executing and logs are remaining...")
pid_check_result = 1
while pid_check_result == 1:
    ws_url_pid_check = "{}?token={}".format(pid_check_api_res_json['url'], pid_check_api_res_json['token'])
    ws = create_connection(ws_url_pid_check)
    pid_check_result =  int(base64.b64decode(ws.recv()))
    ws.close()
    if pid_check_result == 0:
        print("[ I ] Process have exited, safe to read logs now...")
        break
    print("[ W ] Process is still running in container, waiting for {} seconds and trying again.".format(pid_check_timeout))
    time.sleep(pid_check_timeout)

    # todo: tail current log progress? don't know if we can or if rundeck buffer all output until script is done?
    # ws_url_log_tail = "{}?token={}".format(pid_check_api_res_json['url'], pid_check_api_res_json['token'])

time.sleep(reconnect_timeout)

print("""

Command execution is done, reading complete log output from container storage...
""")

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
# print(json.dumps(pid_check_api_data, indent=2))

final_log_read_api_url = "{}/containers/{}?action=execute".format(api_base_url, node_id)
final_log_read_api_res = requests.post(final_log_read_api_url, auth=api_auth, json=final_log_read_api_data)
final_log_read_api_res_json = final_log_read_api_res.json()

ws_logs = websocket.WebSocketApp(ws_url_logs,
    on_message = logs_on_message,
    header = ws_auth_header)
ws_logs.run_forever()

if log_handler.has_error == True:
    raise Exception(log_handler.last_error)
log_handler.clear()
