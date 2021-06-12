# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2019-2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

FROM aiplanner-base-deps

RUN groupadd -r syslog \
    && groupadd -g 1000 aiplanner \
    && useradd -u 1000 -g aiplanner -m -s /bin/bash aiplanner
    # syslog group needed by logrotate.
    # aiplanner uid and gid chosen to map to ubuntu:ubuntu so can write to shared ~/aiplanner-data directory.
USER aiplanner

WORKDIR /home/aiplanner

ADD dotspia.tar ./
RUN mkdir -p aiplanner-data.docker/models
ADD models.tgz aiplanner-data.docker/models
RUN mkdir -p aiplanner-data.docker/webroot
ADD webroot.tgz aiplanner-data.docker/webroot
ADD --chown=aiplanner:aiplanner aiplanner aiplanner/
ADD --chown=aiplanner:aiplanner git-rev git-rev

ENV API_DIR /home/aiplanner/aiplanner/ai/docker/apiserver

RUN cp $API_DIR/LICENSE . \
    && crontab $API_DIR/aiplanner.crontab

USER root

RUN cp $API_DIR/LICENSE / \
    && cp $API_DIR/aiplanner.logrotate /etc/logrotate.d/aiplanner \
    && ln -s $API_DIR/start /

EXPOSE 3000

CMD ["/start"]
