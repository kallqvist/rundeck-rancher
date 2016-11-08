#!/bin/bash

# todo: iterate folders
python rancher/setup.py install
zip -r /var/lib/rundeck/libext/rancher.zip rancher
