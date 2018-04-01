#!/bin/bash

redis_dir="../data/redis"

for s in $(ls -1 $redis_dir); do
  echo $s SAVE
  docker exec -it "point_redis-${s}_1" redis-cli 'SAVE'
done

tar cjf "$2/redis-$1.tar.bz2" $redis_dir
