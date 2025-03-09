#!/bin/bash

#docker exec -it point_db_1 
pg_dump -h 127.0.2.1 -U point point | gzip - > "$2/pgsql-$1.sql.gz"
