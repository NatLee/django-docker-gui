#!/bin/bash
python manage.py migrate && python manage.py makemigrations
/usr/local/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
