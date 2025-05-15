#!/usr/bin/env python3

# ups_scraper_server.py
#
# This script is a lightweight Flask web server that scrapes UPS telemetry from an Eaton Network-MS card.
# Since the card does not provide a REST API, it extracts real-time measurements from a known JavaScript-based
# interface endpoint: `/html/synoptic/ups_measure_11_simple.js`.
#
# The parsed values (e.g., voltage, current, battery time) are exposed as JSON over HTTP, optionally cleaned
# of units and normalized into machine-readable types.
#
# ---------------------------
# Runtime Parameters (via environment variables or Gunicorn):
#
#   UPS_IP        - IP address of the Eaton UPS (required)
#   UPS_USERNAME  - Username for HTTP Basic Auth (optional)
#   UPS_PASSWORD  - Password for HTTP Basic Auth (optional)
#   SERVER_API_KEY - API key to restrict access (optional)
#
# These can be set via environment variables or injected by Gunicorn/systemd using `--env`.
#
# ---------------------------
# HTTP Query Parameters:
#
#   format=json   - (default) Returns structured JSON including human-readable values (with units)
#   format=raw    - Returns values with units removed and parsed into float/int
#   api_key       - Optional API key passed as query param instead of header
#
# ---------------------------
# Example usage (development mode):
#
#   $ export UPS_IP=192.168.0.100
#   $ export UPS_USERNAME=admin
#   $ export UPS_PASSWORD=secret
#   $ export SERVER_API_KEY=mysecret
#   $ python3 ups_scraper_server.py
#
# ---------------------------
# Production deployment (recommended):
#
#   Use Gunicorn and systemd for production:
#
#     gunicorn -b 0.0.0.0:5000 ups_scraper_server:app \
#         --env UPS_IP=192.168.0.100 \
#         --env UPS_USERNAME=admin \
#         --env UPS_PASSWORD=secret \
#         --env SERVER_API_KEY=mysecret
#
#   Then access via browser or API:
#     http://localhost:5000/?format=raw&api_key=mysecret
#
# ---------------------------
# Output example (format=raw):
# {
#   "timestamp": "2025-05-15T20:00:00Z",
#   "Normal AC": {
#     "Voltage": 235.0,
#     "Frequency": 49.9
#   },
#   "Battery": {
#     "Battery load level": 100.0,
#     "Remaining backup time": 2422,
#     "Voltage": 38.0,
#     "Life Time": 46.0
#   },
#   ...
# }

from flask import Flask, request, jsonify, Response, abort
import requests
from bs4 import BeautifulSoup
import re
import argparse
import urllib3
from datetime import datetime, timezone
from functools import wraps
import os

# Flask app object (used by Gunicorn and __main__)
app = Flask(__name__)

# Resolve configuration at global scope to support Gunicorn
UPS_IP = os.getenv("UPS_IP")
USERNAME = os.getenv("UPS_USERNAME")
PASSWORD = os.getenv("UPS_PASSWORD")
SERVER_API_KEY = os.getenv("SERVER_API_KEY")


def clean_value(val):
    val = val.strip().lower()
    if val in ("unknown", "-", ""):
        return None
    try:
        if "mn" in val and "s" in val:
            mins = int(re.search(r"(\d+)\s*mn", val).group(1))
            secs = int(re.search(r"(\d+)\s*s", val).group(1))
            return mins * 60 + secs
        if "%" in val:
            return float(val.replace("%", "").strip())
        return float(re.search(r"[-+]?[0-9]*\.?[0-9]+", val).group())
    except:
        return val


def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key_from_header = request.headers.get("Authorization", "").replace("Bearer ", "")
        key_from_query = request.args.get("api_key")

        if SERVER_API_KEY and (key_from_header != SERVER_API_KEY and key_from_query != SERVER_API_KEY):
            abort(401, description="Invalid or missing API key")

        return f(*args, **kwargs)
    return decorated


@app.route("/")
@require_api_key
def get_ups_data():
    fmt = request.args.get("format", "json").lower()
    ups_url = f"https://{UPS_IP}/html/synoptic/ups_measure_11_simple.js"

    request_kwargs = {"verify": False, "timeout": 5}
    if USERNAME and PASSWORD:
        request_kwargs["auth"] = (USERNAME, PASSWORD)

    try:
        response = requests.get(ups_url, **request_kwargs)
        js_content = response.text
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    tables_raw = re.findall(r"label=(<TABLE.*?</TABLE>)", js_content, re.DOTALL)

    ups_data = {}
    for table_html in tables_raw:
        soup = BeautifulSoup(table_html, "html.parser")
        section = soup.find("b").text.strip()
        data = {}
        for row in soup.find_all("tr", class_="popupData"):
            cols = row.find_all("td")
            if len(cols) == 2:
                key = cols[0].get_text(strip=True)
                value = cols[1].get_text(strip=True)
                data[key] = clean_value(value) if fmt == "raw" else value
        ups_data[section] = data

    return jsonify({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **ups_data
    })


def main():
    global UPS_IP, USERNAME, PASSWORD, SERVER_API_KEY

    parser = argparse.ArgumentParser(description="Eaton UPS Scraper Web Server")
    parser.add_argument("--ups_ip", dest="ups_ip", help="IP address of the UPS", required=False)
    parser.add_argument("--ups_username", help="UPS username (optional, or set via UPS_USERNAME)")
    parser.add_argument("--ups_password", dest="password", help="UPS password (optional, or set via UPS_PASSWORD)")
    parser.add_argument("--server_api_key", help="Optional API key to secure the scraper server")
    parser.add_argument("--server_port", type=int, default=5000, help="Port to run the server on")
    args = parser.parse_args()

    UPS_IP = args.ups_ip or UPS_IP
    USERNAME = args.ups_username or USERNAME
    PASSWORD = args.ups_password or PASSWORD
    SERVER_API_KEY = args.server_api_key or SERVER_API_KEY
    SERVER_PORT = args.server_port or int(os.getenv("SERVER_PORT", 5000))

    if not UPS_IP:
        raise RuntimeError("UPS_IP must be set via --ups_ip or environment")

    urllib3.disable_warnings()
    app.run(host="0.0.0.0", port=SERVER_PORT)


if __name__ == "__main__":
    main()
