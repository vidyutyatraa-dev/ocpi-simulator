"""
Root URL configuration for vy-ocpi-simulator project.
"""
from django.urls import path, include

urlpatterns = [
    path('', include('ocpi_emsp.urls')),
]

