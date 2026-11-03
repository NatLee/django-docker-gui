#!/bin/bash
set -e
python manage.py migrate
# WhiteNoise serves these when DEBUG is off.
python manage.py collectstatic --noinput --verbosity 0
exec /usr/local/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
