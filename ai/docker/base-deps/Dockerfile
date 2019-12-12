# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2019 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

FROM ubuntu:xenial
RUN apt-get update \
    && echo "postfix postfix/main_mailer_type select Internet Site" | debconf-set-selections \
    && echo "postfix postfix/mailname string aiplanner.com" | debconf-set-selections \
    && apt-get install -y \
        curl \
        build-essential \
        libreadline-gplv2-dev libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev \
        python3-pip \
        cron \
        logrotate \
        postfix \
        gnuplot-nox \
    && apt-get clean \
    && curl -O https://www.python.org/ftp/python/3.6.5/Python-3.6.5.tgz \
    && tar -zxf Python-3.6.5.tgz \
    && cd Python-3.6.5 \
    && ./configure \
    && make \
    && make install \
    && cd .. \
    && rm -r Python-3.6.5 \
    && pip3 install \
        cython==0.29.0 \
        numpy==1.15.4 \
        scipy \
        tensorflow==1.12.0 \
        gym \
        psutil \
        setproctitle \
        pyyaml
    # Need python 3.6+ because aiplanner source code uses type annotations.
    # libreadline... needed for python build otherwise pip3 ssl fails.
# RUN apt-get update \
#     && apt-get install -y \
#         wget \
#         bzip2 \
#         cmake \
#         build-essential \
#         cron \
#         logrotate \
#         postfix \
#         gnuplot-nox \
#     && apt-get clean \
#     && echo 'export PATH=/opt/conda/bin:$PATH' > /etc/profile.d/conda.sh \
#     && wget --quiet 'https://repo.continuum.io/archive/Anaconda3-5.2.0-Linux-x86_64.sh' -O /tmp/anaconda.sh \
#     && /bin/bash /tmp/anaconda.sh -b -p /opt/conda \
#     && rm /tmp/anaconda.sh \
#     && /opt/conda/bin/conda install -y \
#         libgcc \
#     && /opt/conda/bin/conda clean -y --all \
#     && /opt/conda/bin/pip install \
#         cython==0.29.0 \
#         numpy==1.15.4 \
#         scipy \
#         tensorflow==1.12.0 \
#         gym \
#         psutil \
#         setproctitle \
#         pyyaml
