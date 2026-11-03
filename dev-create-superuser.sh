#!/bin/bash
# Create a Django superuser in the running container: ./dev-create-superuser.sh [username] [password]
# Defaults: admin / 1234 (change the password for anything but a local try-out).
USERNAME=${1:-admin}
PASSWORD=${2:-1234}
docker exec -e DJANGO_SUPERUSER_PASSWORD="$PASSWORD" d-docker-web \
  python manage.py createsuperuser --noinput --username "$USERNAME" --email "$USERNAME@admin.com"
