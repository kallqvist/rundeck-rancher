#!/bin/bash -e
cmd="$@"

if [ ${#cmd} -ge 1 ]; then
  exec "$@"
else
  . /etc/rundeck/profile
  ${JAVA_HOME:-/usr}/bin/java ${RDECK_JVM} -cp ${BOOTSTRAP_CP} com.dtolabs.rundeck.RunServer /var/lib/rundeck ${RDECK_HTTP_PORT}
fi
