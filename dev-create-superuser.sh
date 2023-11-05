#!/bin/bash
docker exec -it d-docker-web bash -c 'DJANGO_SUPERUSER_PASSWORD=1234 python manage.py createsuperuser --noinput --username admin --email admin@admin.com'
