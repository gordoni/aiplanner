# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

FROM aiplanner-base-deps

RUN groupadd -r syslog \
    && useradd -m -s /bin/bash -U aiplanner
    # syslog group needed by logrotate.
USER aiplanner

WORKDIR /home/aiplanner

ADD dotspia.tar ./
RUN mkdir -p aiplanner-data/models
ADD models.tar aiplanner-data/models
ADD --chown=aiplanner:aiplanner aiplanner aiplanner/
ADD --chown=aiplanner:aiplanner git-rev git-rev

ENV API_DIR /home/aiplanner/aiplanner/ai/docker/apiserver

RUN cp $API_DIR/LICENSE . \
    && cp $API_DIR/market-data.json aiplanner-data \
    && crontab $API_DIR/aiplanner.crontab

USER root

RUN cp $API_DIR/LICENSE / \
    && cp aiplanner/ai/aiplanner-example.yaml /aiplanner.yaml \
    && cp $API_DIR/aiplanner.logrotate /etc/logrotate.d/aiplanner \
    && ln -s $API_DIR/start /

EXPOSE 3000

CMD ["/start"]
