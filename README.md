# Traceroute Map

Traceroute to any domain or IP address and visualize the network path on a world map with geolocation data.

## Features

- **Global Probe**: Run traceroute from 3,800+ probes across 114 countries via [Globalping API](https://globalping.io/) (no API key required)
- **Local Traceroute**: Run traceroute directly from the server (TCP / UDP / ICMP)
- Geolocate each hop (city, country, ISP, ASN) using ip-api.com
- Visualize the route on an interactive Leaflet.js / OpenStreetMap map
- Click hops in the sidebar to focus on the map
- Probe location displayed as starting point marker

## Screenshot

```
[Global Probe / Local] [target input] [From: Japan ▾] [Trace]

    ┌─────────────────────────┬──────────────────────┐
    │                         │ Probe: Tokyo, JP     │
    │    World Map            │  1  45.8.112.1       │
    │    with route lines     │  2  91.200.240.64    │
    │    and hop markers      │  ...                 │
    │                         │  9  103.117.168.0    │
    │                         │     American Samoa   │
    └─────────────────────────┴──────────────────────┘
```

## Setup

```bash
sudo apt-get update && sudo apt-get install -y python3-venv traceroute
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Access at `http://<server-ip>:3000`

### Production (systemd + gunicorn)

```bash
pip install -r requirements.txt
gunicorn --bind 0.0.0.0:3000 --workers 2 --timeout 120 app:app
```

## Tech Stack

- **Backend**: Python / Flask
- **Global Traceroute**: [Globalping API](https://globalping.io/) (free, no auth, 250 req/hr)
- **Frontend**: Leaflet.js + OpenStreetMap
- **GeoIP**: ip-api.com (free batch API)

## Probe Locations

Japan, USA, Germany, UK, Singapore, Australia, Brazil, India, France, Korea, Netherlands, Canada

## API

### `POST /api/traceroute`

**Global Probe mode:**
```json
{
  "target": "example.com",
  "source": "globalping",
  "location": "JP"
}
```

**Local mode:**
```json
{
  "target": "example.com",
  "source": "local",
  "method": "tcp"
}
```

**Response:**
```json
{
  "target": "example.com",
  "probe": { "city": "Tokyo", "country": "JP", "network": "xTom", "asn": 3258 },
  "hops": [
    {
      "hop": 1,
      "ip": "45.8.112.1",
      "rtt": 0.372,
      "hostname": "_gateway",
      "geo": { "lat": 35.69, "lon": 139.69, "city": "Tokyo", "country": "Japan", "isp": "..." }
    }
  ]
}
```
