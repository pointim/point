FROM ubuntu:14.04
COPY ./core/requirements.pip /home/point/requirements.pip
VOLUME ["/home/point/core", "/home/point/img"]
RUN apt-get update && \
    apt-get install -y \
      build-essential \
      libevent-dev \
      libfreetype6-dev \
      libjpeg-dev \
      libjpeg8-dev \
      libmagic-dev \
      libpq-dev \
      libxml2-dev \
      libxslt1-dev \
      python-dateutil \
      python-dev \
      python-dnspython \
      python-imaging \
      python-levenshtein \
      python-lxml \
      python-meld3 \
      python-pil \
      python-pip \
      python-redis \
      python-requests \
      python-setproctitle \
      python-six \
      python-tz \
      python-unidecode \
      python-urllib3 \
      zlib1g-dev \
    && \
    pip install -r /home/point/requirements.pip
