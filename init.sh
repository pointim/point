#!/bin/bash

for i in core doc feed imgproc stat www xmpp; do
  git clone git@github.com:artss/point-$i.git $i
done

# TODO: remove after merge
approot=$PWD
for repo in core imgproc www xmpp; do
  cd $approot/$repo
  git checkout docker-compose
done
cd $approot

mkdir -p img
mkdir -p data/postgresql
mkdir -p data/redis/{storage,cache,sessions,queue,pubsub,imgproc}
mkdir -p ssl

openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout ./ssl/server.key -out ./ssl/server.crt

wget -c https://point.im/files/dump.sql.gz -O ./docker-entrypoint-initdb.d/dump.sql.gz

docker build --rm -t point-os -f ./Dockerfile.os .
docker build --rm -t point-db -f ./Dockerfile.db .
