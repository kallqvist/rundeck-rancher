import os

if not 'myvar' in os.environ:
    raise Exception( 'myvar is not available' )
