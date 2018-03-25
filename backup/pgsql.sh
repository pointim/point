#!/bin/bash

pg_dump -h localhost -U point point | gzip - > "$2/pgsql-$1.sql.gz"
