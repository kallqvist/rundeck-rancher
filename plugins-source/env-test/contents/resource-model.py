import os

if not 'myvar' in os.environ:
    raise Exception( 'myvar is not available' )

print('{ "node1": { "nodename": "node1", "hostname": "node1", "myvar": "' + os.environ['myvar'] + '"} }')
