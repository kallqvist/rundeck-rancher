from requests.auth import HTTPBasicAuth
import requests
import websocket
import json
import os

import os

print "Content-Type: text/plain\n\n"
for key in os.environ.keys():
    print "%30s %s \n" % (key,os.environ[key])

# todo: read from rundeck input?
bash_script = """
#!/bin/bash
pwd
echo "derp"
sleep 2
echo "more derp"
echo "\ <- backslash"
sleep 1
echo "and end with some lerp"
ls -l
uname -a
"""
bash_script = bash_script.strip().encode("string_escape").replace('"', '\\\"')

raise Exception( ":: {}".format(os.environ['RD_FILE_COPY_FILE']) )
# ${file-copy.destination} # optional

# # todo: script filename from rundeck?
# api_data = {
#     # "attachStdin": True,
#     # "attachStdout": True,
#     "command": [
#       "/bin/bash",
#       "-c",
#       "echo -e \"{}\" > test.sh".format(bash_script)
#     ],
#     # "tty": True
# }
#
# # todo: container ID?
# api_url = "{}/containers/1i18714?action=execute".format(os.environ['CATTLE_CONFIG_URL'])
# api_res = requests.post(api_url, auth=HTTPBasicAuth(os.environ['CATTLE_ACCESS_KEY'], os.environ['CATTLE_SECRET_KEY']), json=api_data).json()
#
# ws_url = "{}?token={}".format(api_res['url'], api_res['token'])
# ws = websocket.create_connection(ws_url)
# ws_res = ws.recv()
