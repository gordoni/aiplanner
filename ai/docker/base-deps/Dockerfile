# AIPlanner - Deep Learning Financial Planner
# Copyright (C) 2019-2021 Gordon Irlam
#
# All rights reserved. This program may not be used, copied, modified,
# or redistributed without permission.
#
# This program is distributed WITHOUT ANY WARRANTY; without even the
# implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
# PURPOSE.

FROM ubuntu:20.04
# libgl1-mesa-dev required by Ray which does "import cv2" for opencv python bindings.
RUN apt-get update \
    && apt-get upgrade -y \
    && echo "postfix postfix/main_mailer_type select Internet Site" | debconf-set-selections \
    && echo "postfix postfix/mailname string aiplanner.com" | debconf-set-selections \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y \
        curl \
        less \
        nano \
        python3-pip \
        cron \
        logrotate \
        postfix \
        cython3 \
        python3-setproctitle \
        gnuplot-nox \
        python3-reportlab \
        libgl1-mesa-dev \
    && apt-get clean \
    && apt-get install -y cmake \
    && pip3 install \
        torch \
        'ray[rllib]==1.1.0' \
        pyyaml \
        svglib \
    && rm -rf /root/.cache/pip
    # RLlib depends on atari-py which requires cmake and used to require bazel which requires unzip to install
    #&& apt-get install -y unzip \
    #&& curl -s -L -R -o install-bazel.sh https://github.com/bazelbuild/bazel/releases/download/1.1.0/bazel-1.1.0-installer-linux-x86_64.sh \
    #&& bash ./install-bazel.sh \
    # Bazel version based on: ray/ci/travis/install-bazel.sh
