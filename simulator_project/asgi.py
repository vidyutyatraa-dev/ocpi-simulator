"""
ASGI config for vy-ocpi-simulator project.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simulator_project.settings')
application = get_asgi_application()

