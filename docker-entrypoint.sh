#!/bin/bash -e
j2 /config-templates/profile.j2 > /etc/rundeck/profile
j2 /config-templates/framework.properties.j2 > /etc/rundeck/framework.properties
j2 /config-templates/rundeck-config.properties.j2 > /etc/rundeck/rundeck-config.properties

cmd="$@"

if [ ${#cmd} -ge 1 ]; then
  exec "$@"
else
  . /etc/rundeck/profile
  ${JAVA_HOME:-/usr}/bin/java ${RDECK_JVM} -cp ${BOOTSTRAP_CP} com.dtolabs.rundeck.RunServer /var/lib/rundeck ${RDECK_HTTP_PORT}
fi
