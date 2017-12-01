FROM ubuntu:14.04
MAINTAINER arts <arts@point.im>

ENV HOME /root
ENV DEBIAN_FRONTEND noninteractive
ENV SETUP_DIR /root/setup
ENV POINT_DIR /home/point
ENV POINT_DOMAIN point.local
ENV YOUR_USER arts

ARG timezone

RUN locale-gen en_US.UTF-8 && \
    update-locale LANG=en_US.UTF-8 && \
    echo ${timezone} >> /etc/timezone && \
    ntpdate -s ntp.ubuntu.com && \
    apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common && \
    add-apt-repository -y ppa:nginx/stable && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        gettext \
        git-core \
        nginx \
        pwgen \
        python2.7 \
        python2.7-dev \
        supervisor \
        wget && \
    apt-get clean && \
    mkdir -p /usr/local/etc/supervisor.d/

ADD setup ${SETUP_DIR}

RUN chmod +x ${SETUP_DIR}/start.sh

VOLUME [ "${POINT_DIR}" ]
EXPOSE 80 443 5222 5223

CMD [ "/root/setup/start.sh" ]
