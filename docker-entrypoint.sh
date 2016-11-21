#!/bin/bash -e
j2 /config-templates/profile.j2 > /etc/rundeck/profile
j2 /config-templates/realm.properties.j2 > /etc/rundeck/realm.properties
j2 /config-templates/framework.properties.j2 > /etc/rundeck/framework.properties
j2 /config-templates/rundeck-config.properties.j2 > /etc/rundeck/rundeck-config.properties

# workaround for rundeck environment variable bug
j2 /config-templates/rancher-auth-workaround.json.j2 > /rancher-auth-workaround.json

cmd="$@"

if [ ${#cmd} -ge 1 ]; then
  exec "$@"
else
  . /etc/rundeck/profile
  ${JAVA_HOME:-/usr}/bin/java ${RDECK_JVM} -cp ${BOOTSTRAP_CP} com.dtolabs.rundeck.RunServer /var/lib/rundeck ${RDECK_HTTP_PORT}
fi
