from requests.auth import HTTPBasicAuth
from dateutil.parser import parse
import websocket
import requests
import logging
import base64
import json
import sys
import os
import re

# hiding traceback
sys.tracebacklimit = 0

class ErrorLogger(logging.StreamHandler):
    has_error = False
    last_error = None
    def clear(self):
        self.has_error = False
        self.last_error = None

    def emit(self, record):
        msg = self.format(record)
        self.has_error = True
        self.last_error = msg
        raise Exception (msg)
    pass

log_handler = ErrorLogger()
logger = logging.getLogger('websocket')
logger.setLevel(logging.ERROR)
logger.addHandler(log_handler)
log_re_pattern = '^(\d*) (.*?Z) (.*)$'

# todo: remove this when rundeck bug is resolved
cattle_config = json.load(open("/rancher-auth-workaround.json"))
api_base_url = cattle_config['host'] # os.environ['CATTLE_CONFIG_URL']
api_access_key = cattle_config['access_key'] #  os.environ['CATTLE_ACCESS_KEY']
api_secret_key = cattle_config['secret_key'] #  os.environ['CATTLE_SECRET_KEY']
ws_auth_header = {'Authorization': "Basic {}".format(base64.b64encode("{}:{}".format(api_access_key, api_secret_key)))}

environment_id = os.environ.get('RD_NODE_ENVIRONMENT_ID', '')
if len(environment_id) == 0:
    raise Exception("Can't run, environment ID is not set!")

node_id = os.environ.get('RD_NODE_ID', '')
if len(node_id) == 0:
    raise Exception("Can't run, node ID is not set!")

node_tty = (os.environ.get('RD_NODE_TTY', 'true').lower() == 'true')
if node_tty == True:
    raise Exception("Can't run, TTY must be disabled in rancher settings")
