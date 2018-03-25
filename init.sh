#!/bin/bash

mkdir -p img
mkdir -p data/postgresql
mkdir -p data/redis/{storage,cache,sessions,queue,pubsub,imgproc}
mkdir -p ssl

openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout ./ssl/server.key -out ./ssl/server.crt

wget -c https://point.im/files/dump.sql.gz -O ./docker-entrypoint-initdb.d/dump.sql.gz

docker build --rm -t point-os -f ./Dockerfile.os .
docker build --rm -t point-db -f ./Dockerfile.db .
