FROM ubuntu:14.04
#WORKDIR /home/point/www
ADD ./core /home/point/core
#ADD . /home/point/www
RUN apt-get update && \
    apt-get install -y \
      build-essential libevent-dev libjpeg-dev libmagic-dev \
      libxml2-dev libxslt1-dev libpq-dev \
      python-dev python-imaging python-pip && \
    pip install -r /home/point/core/requirements.pip
#CMD ["python", "websocket.py"]
