# vy-ocpi-simulator

A standalone, database-backed **OCPI 2.2.1 EMSP (eMobility Service Provider) Simulator** built on Django. 

Designed specifically to test and validate roaming interactions with the **VidyutYatraa CPO AWS Serverless Backend** (`https://test.vidyutyatraa.co.in`), including reliable reception of asynchronous command callbacks, session telemetry pushes, and CDR financial reconciliation.

---

## Key Features

1. **Guaranteed Public Callback Delivery**: Automatically discovers the external routable IP/host (never falling back to `0.0.0.0`), ensuring AWS Lambda can always contact `response_url`.
2. **Dedicated SQLite Persistence**: Incoming `CommandResult` callbacks, live sessions, and CDRs are permanently stored and inspectable with full JSON payloads and timestamps.
3. **Interactive Control Dashboard**: Web-based interface to perform credentials handshake, fetch live charger locations/tariffs, register tokens, and trigger `START_SESSION` / `STOP_SESSION`.
4. **Live Polling Tracker**: The dashboard refreshes incoming callbacks every 3 seconds so you can watch charger responses in real-time.
5. **Turnkey AWS EC2 Deployment**: Includes `setup_ec2.sh` to handle dependencies, migrations, IP detection, and server startup in a single command.

---

## Quickstart (Local)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Migrations & Start
```bash
python run_simulator.py
```

### 3. Access Dashboard
Open your browser at:
```
http://localhost:8000
```

---

## Running on AWS EC2 (Ubuntu)

### 1. Run the Setup Script
```bash
chmod +x setup_ec2.sh
./setup_ec2.sh
```

The script will automatically:
- Query AWS EC2 instance metadata to discover your instance's Public IPv4 address.
- Install packages using `--ignore-installed --break-system-packages`.
- Run SQLite migrations.
- Save your Public IP into `SimulatorConfig` so all dispatched commands pass the correct callback URL.
- Start Django listening on `0.0.0.0:8000`.

### 2. Access the Dashboard from Any Browser
```
http://<YOUR_EC2_PUBLIC_IP>:8000
```

> **Security Group Note**: Make sure Port `8000` (Custom TCP) is open in your EC2 Security Group Inbound Rules from `0.0.0.0/0`.

---

## OCPI 2.2.1 Endpoints Exposed

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/ocpi/versions` | Version negotiation endpoint |
| `GET` | `/ocpi/emsp/2.2.1` | Module catalog and endpoint URLs |
| `POST/GET` | `/ocpi/emsp/2.2.1/credentials` | Registration & token handshake |
| `POST` | `/ocpi/emsp/2.2.1/commands/callback` | **Async CommandResult Callback Receiver** |
| `PUT` | `/ocpi/emsp/2.2.1/sessions/:cc/:party/:id` | Session start push |
| `PATCH` | `/ocpi/emsp/2.2.1/sessions/:cc/:party/:id` | Live meter readings / SoC push |
| `POST` | `/ocpi/emsp/2.2.1/cdrs` | Finalized Charge Detail Record push |

