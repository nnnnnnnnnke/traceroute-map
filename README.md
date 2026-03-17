# Traceroute Map

Traceroute the route to a domain or IP address and visualize the path on a world map with geolocation data.

## Features

- Run traceroute to any domain or IP
- Geolocate each hop using ip-api.com
- Visualize the route on an interactive Leaflet.js map
- Show city, country, ISP, and RTT for each hop
- Click hops to focus on the map

## Setup

```bash
sudo apt-get update && sudo apt-get install -y python3-venv traceroute
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Access at `http://<server-ip>:3000`

## Tech Stack

- **Backend**: Python / Flask
- **Frontend**: Leaflet.js + OpenStreetMap
- **GeoIP**: ip-api.com (free batch API)
