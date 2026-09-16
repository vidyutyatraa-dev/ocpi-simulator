#!/usr/bin/env python
"""
Launcher script for VidyutYatraa OCPI 2.2.1 EMSP Simulator.
Automatically applies migrations and starts server on 0.0.0.0:8000.
"""
import os
import sys
import subprocess

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'simulator_project.settings')
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    print("=" * 60)
    print("⚡ VidyutYatraa OCPI 2.2.1 EMSP Simulator (Django)")
    print("=" * 60)

    # 1. Makemigrations and Migrate
    print("Running database migrations...")
    subprocess.run([sys.executable, "manage.py", "makemigrations", "ocpi_emsp"], check=False)
    subprocess.run([sys.executable, "manage.py", "migrate"], check=True)

    # 2. Display Public Base URL resolution
    import django
    django.setup()
    from ocpi_emsp.ocpi_utils import resolve_public_base_url
    from ocpi_emsp.models import SimulatorConfig

    # Seed default config if empty
    cfg = SimulatorConfig.get_config()
    detected_url = resolve_public_base_url()
    
    print("-" * 60)
    print(f"CPO Endpoint Target : {cfg.cpo_url}")
    print(f"Partner Identity    : {cfg.country_code}-{cfg.party_id}")
    print(f"Token A (Bootstrap) : {cfg.token_a}")
    print(f"Public Callback URL : {detected_url}/ocpi/emsp/2.2.1/commands/callback")
    print("-" * 60)
    print("Starting Django server on http://0.0.0.0:8000 ...")
    print("Press CTRL+C to stop.")
    print("=" * 60)

    # 3. Start server
    port = os.environ.get("PORT", "8000")
    subprocess.run([sys.executable, "manage.py", "runserver", f"0.0.0.0:{port}"])

if __name__ == '__main__':
    main()

