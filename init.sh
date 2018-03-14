#!/bin/bash

for i in core doc feed imgproc stat www xmpp; do
  git clone git@github.com:artss/point-$i.git $i
done

mkdir -p img
mkdir -p postgresql
mkdir -p redis/{storage,cache,sessions,queue,pubsub}

docker build --rm -t point-os -f ./Dockerfile.os .
docker build --rm -t point-db -f ./Dockerfile.db .
