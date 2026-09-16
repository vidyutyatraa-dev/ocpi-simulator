"""
WSGI config for vy-ocpi-simulator project.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simulator_project.settings')
application = get_wsgi_application()

