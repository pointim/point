FROM ubuntu:14.04
COPY ./core/requirements.pip /home/point/requirements.pip
VOLUME ["/home/point/core", "/home/point/img"]
RUN apt-get update && \
    apt-get install -y \
      build-essential libevent-dev libjpeg-dev libmagic-dev \
      libxml2-dev libxslt1-dev libpq-dev \
      python-dev python-imaging python-pip && \
    pip install -r /home/point/requirements.pip
