# Eaton UPS Network-MS Scraper

This project exposes UPS telemetry from an Eaton Network-MS card (which lacks a REST API) via a lightweight Flask web server. It scrapes data from a JavaScript endpoint on the UPS and outputs structured JSON over HTTP.

---

## Features
- Sends a request to `https://UPS_IP/html/synoptic/ups_measure_11_simple.js` and parses the data to JSON.
- Optional API key protection.

---
## Installation

```bash
git clone https://github.com/simont456/eaton-ups-scraper.git
cd eaton-ups-scraper
pip install -r requirements.txt
```

## Configuration

Set the following environment variables or pass them as arguments:

| Variable         | Description                        | Required |
|------------------|------------------------------------|----------|
| `UPS_IP`         | IP address of the UPS              | True     |
| `UPS_USERNAME`   | Username for HTTP Basic Auth       | False    |
| `UPS_PASSWORD`   | Password for HTTP Basic Auth       | False    |
| `SERVER_API_KEY` | API key to secure access           | False    |

---

## Development Mode

```bash
export UPS_IP=192.168.0.100
export UPS_USERNAME=admin  # Optional
export UPS_PASSWORD=secret # Optional
export SERVER_API_KEY=mysecret # Optional, but recommended
python3 ups_scraper_server.py
```

Then send a GET-request to:
`http://localhost:5000/?format=raw&api_key=mysecret`

## Production Mode (Gunicorn)
```bash
gunicorn -b 0.0.0.0:5000 ups_scraper_server:app \
  --env UPS_IP=192.168.0.100 \
  --env UPS_USERNAME=admin \
  --env UPS_PASSWORD=secret \
  --env SERVER_API_KEY=mysecret
```

## API Key Usage
To protect access, you can pass the API key as:
- Header:
`Authorization: Bearer mysecret`
- Query param:
`?api_key=mysecret`

## HTTP Query Parameters
| Parameter | Description                                 |
|-----------|---------------------------------------------|
| `format`  | `json` (default), or `raw`                  |
| `api_key` | API key if protection is enabled            |


## Example Output (default)
```json
{
  "AC Output": {
    "Active Power": "0.2 kW",
    "Apparent Power": "0.2 kVA",
    "Current": "1.2 A",
    "Frequency": "49.8 Hz",
    "Load level": "19 %",
    "Voltage": "235 V"
  },
  "Battery": {
    "Battery load level": "100 %",
    "Life Time": "46 months",
    "Remaining backup time": "42 mn 39 s",
    "Voltage": "38 V"
  },
  "Bypass AC": {
    "Current": "unknown",
    "Voltage": "unknown"
  },
  "Normal AC": {
    "Frequency": "49.8 Hz",
    "Voltage": "235 V"
  },
  "timestamp": "2025-05-15T21:10:06.592621+00:00"
}
```
## Example Output (format=raw)
```json
{
  "AC Output": {
    "Active Power": 0.1,
    "Apparent Power": 0.2,
    "Current": 1.2,
    "Frequency": 49.9,
    "Load level": 18,
    "Voltage": 234
  },
  "Battery": {
    "Battery load level": 100,
    "Life Time": 46,
    "Remaining backup time": 2422,
    "Voltage": 38
  },
  "Bypass AC": {
    "Current": null,
    "Voltage": null
  },
  "Normal AC": {
    "Frequency": 49.9,
    "Voltage": 234
  },
  "timestamp": "2025-05-15T21:11:08.228626+00:00"
}
```

---

## 🧷 Systemd Service (Optional)

To run the scraper as a persistent background service with auto-restart:

### 📄 Create `/etc/systemd/system/eaton-ups-scraper.service`

```ini
[Unit]
Description=Eaton UPS Scraper (Gunicorn Flask Server)
After=network.target

[Service]
WorkingDirectory=/opt/eaton-ups-scraper  # Change this to the path where your script is located
ExecStart=/usr/bin/gunicorn -b 0.0.0.0:5000 ups_scraper_server:app

# Environment configuration
Environment=UPS_IP=192.168.0.100
Environment=UPS_USERNAME=admin
Environment=UPS_PASSWORD=secret
Environment=SERVER_API_KEY=mysecret

Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Enable and start the service
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now eaton-ups-scraper
sudo systemctl status eaton-ups-scraper
```