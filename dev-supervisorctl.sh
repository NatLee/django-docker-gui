#!/bin/bash
docker exec -it d-docker-web supervisorctl -c /etc/supervisor/conf.d/supervisord.conf