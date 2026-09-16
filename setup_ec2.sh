#!/bin/bash
# ==============================================================================
# VidyutYatraa OCPI 2.2.1 EMSP Simulator - EC2 Setup & Launch Script
# ==============================================================================
set -e

echo "=================================================="
echo "⚡ Setting up vy-ocpi-simulator on Ubuntu EC2..."
echo "=================================================="

# 1. Detect EC2 Public IPv4
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null || true)
if [ -n "$TOKEN" ]; then
    PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)
fi

if [ -z "$PUBLIC_IP" ]; then
    PUBLIC_IP=$(curl -s https://api.ipify.org 2>/dev/null || echo "127.0.0.1")
fi

echo "Detected EC2 Public IP: $PUBLIC_IP"
export PUBLIC_BASE_URL="http://${PUBLIC_IP}:8000"

# 2. Install dependencies (with PEP 668 bypass & ignore-installed)
echo "Installing Python dependencies..."
sudo python3 -m pip install -r requirements.txt --ignore-installed --break-system-packages

# 3. Run migrations
echo "Applying database migrations..."
python3 manage.py makemigrations ocpi_emsp
python3 manage.py migrate

# 4. Save public_base_url in database
python3 -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simulator_project.settings')
django.setup()
from ocpi_emsp.models import SimulatorConfig
cfg = SimulatorConfig.get_config()
cfg.public_base_url = 'http://${PUBLIC_IP}:8000'
cfg.save()
print('Configured callback URL in database: ' + cfg.public_base_url + '/ocpi/emsp/2.2.1/commands/callback')
"

# 5. Start simulator on 0.0.0.0:8000
echo "=================================================="
echo "🚀 Starting OCPI Simulator Dashboard at:"
echo "   http://${PUBLIC_IP}:8000"
echo "=================================================="
exec python3 manage.py runserver 0.0.0.0:8000

