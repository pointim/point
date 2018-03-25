#!/bin/bash

d=`date +%Y-%m-%d-%H-%M-%S`
rotate=14

cd `dirname $0`

backup_dir="./$1/"

mkdir -p $backup_dir

. "./$1.sh" $d $backup_dir

find $backup_dir -type f -mtime +$rotate -exec rm '{}' \;

. "./.credentials"

i=0
cnt=${#host[*]}
while [ $i -lt $cnt ]; do
  if [[ ${host[$i]} == '-u'* ]]; then
    lftp -e "mirror -R -e $backup_dir $1; bye;" ${host[$i]}
  else
    rsync -a --delete $backup_dir "${host[$i]}/$1"
  fi

  let "i = $i + 1"
done
