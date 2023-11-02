"""
WSGI config for backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
import socketio
import eventlet
import eventlet.wsgi

from xterm.views import sio

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

application = get_wsgi_application()

application = socketio.Middleware(sio, application)

eventlet.wsgi.server(eventlet.listen(('', 8000)), application)

