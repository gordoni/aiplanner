# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

FROM aiplanner/base-deps

RUN groupadd -r syslog \
    && useradd -m -s /bin/bash -U aiplanner
    # syslog group needed by logrotate.
USER aiplanner

WORKDIR /home/aiplanner

RUN mkdir aiplanner-data
ADD --chown=aiplanner:aiplanner models.tar aiplanner-data
ADD --chown=aiplanner:aiplanner dotspia.tar ./
RUN mkdir aiplanner
ADD --chown=aiplanner:aiplanner aiplanner.tar aiplanner
ADD --chown=aiplanner:aiplanner git-rev git-rev

ENV AI_DIR /home/aiplanner/aiplanner/ai

RUN cp $AI_DIR/api/market-data.json aiplanner-data \
    && crontab $AI_DIR/crontab-example

USER root

RUN cp $AI_DIR/aiplanner.logrotate /etc/logrotate.d/aiplanner \
    && ln -s $AI_DIR/docker/deploy/start /

EXPOSE 3000

CMD ["/start"]
