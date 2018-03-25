#!/bin/bash

for s in /var/run/redis/*.sock; do
  redis-cli -s $s 'SAVE'
done

tar cjf "$2/redis-$1.tar.bz2" "/var/lib/redis"
