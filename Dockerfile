FROM ubuntu

ENV DEBIAN_FRONTEND noninteractive

ADD content/ /

RUN echo "deb http://ftp.debian.org/debian jessie-backports main" >> /etc/apt/sources.list && apt-get -qq update && apt-get -qqy upgrade && apt-get -qqy install --no-install-recommends bash openjdk-8-jre-headless procps sudo openssh-client mysql-client curl git && apt-get clean
RUN curl -Lo /tmp/rundeck.deb http://dl.bintray.com/rundeck/rundeck-deb/rundeck-2.6.9-1-GA.deb
RUN curl -Lo /tmp/rundeck-cli.deb https://github.com/rundeck/rundeck-cli/releases/download/v0.1.19/rundeck-cli_0.1.19-1_all.deb
RUN dpkg -i /tmp/rundeck*.deb && rm /tmp/rundeck*.deb
RUN chown rundeck:rundeck /tmp/rundeck
RUN mkdir -p /var/lib/rundeck/.ssh
RUN chown rundeck:rundeck /var/lib/rundeck/.ssh

# Remove default plugins
RUN rm -R /var/lib/rundeck/libext/*
RUN rm -R /var/lib/rundeck/exp/webapp/WEB-INF/rundeck/plugins/*

# Slack plugin
RUN curl -Lo /var/lib/rundeck/libext/rundeck-slack-incoming-webhook-plugin-0.6.jar https://github.com/higanworks/rundeck-slack-incoming-webhook-plugin/releases/download/v0.6.dev/rundeck-slack-incoming-webhook-plugin-0.6.jar

# Build/install bundled plugins
RUN apt-get update && apt-get install -y python zip
ADD plugins-source /build
WORKDIR /build
RUN ./build-all.sh && rm -R /build
WORKDIR /

ADD ./docker-entrypoint.sh /docker-entrypoint.sh

EXPOSE 4440

# VOLUME  ["/etc/rundeck", "/var/rundeck", "/var/lib/rundeck", "/var/lib/mysql", "/var/log/rundeck", "/opt/rundeck-plugins", "/var/lib/rundeck/logs", "/var/lib/rundeck/var/storage"]
ENTRYPOINT ["/docker-entrypoint.sh"]

# check docker-entrypoint.sh, we keep this empty to allow command overrides at runtime
CMD [""]
