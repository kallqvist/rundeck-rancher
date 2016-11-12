#!/bin/bash
for f in *; do
	if [[ -d $f ]]; then
		python ${f}/setup.py install
		zip -r /var/lib/rundeck/libext/${f}.zip ${f}
	fi
done
