#!/usr/bin/env python3
"""Traceroute Map - Visualize network routes on a world map."""

import re
import subprocess
import asyncio
import time
import aiohttp
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

GLOBALPING_API = "https://api.globalping.io/v1"


def run_traceroute(target: str, method: str = 'tcp') -> list[dict]:
    """Run traceroute locally and parse hops."""
    if not re.match(r'^[a-zA-Z0-9.\-:]+$', target):
        raise ValueError("Invalid target")
    if method not in ('tcp', 'udp', 'icmp'):
        method = 'tcp'

    cmd = ['sudo', 'traceroute', '-n', '-m', '30', '-w', '2']
    if method == 'tcp':
        cmd.append('-T')
    elif method == 'icmp':
        cmd.append('-I')
    cmd.append(target)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise TimeoutError("Traceroute timed out")

    hops = []
    for line in result.stdout.strip().split('\n')[1:]:
        match = re.match(r'\s*(\d+)\s+(.+)', line)
        if not match:
            continue
        hop_num = int(match.group(1))
        rest = match.group(2)

        ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', rest)
        if ip_match:
            ip = ip_match.group(1)
            rtt_match = re.search(r'([\d.]+)\s*ms', rest)
            rtt = float(rtt_match.group(1)) if rtt_match else None
            hops.append({'hop': hop_num, 'ip': ip, 'rtt': rtt})
        else:
            hops.append({'hop': hop_num, 'ip': '*', 'rtt': None})

    return hops


def run_globalping_traceroute(target: str, location: str) -> list[dict]:
    """Run traceroute via Globalping API from a specified location."""
    if not re.match(r'^[a-zA-Z0-9.\-:]+$', target):
        raise ValueError("Invalid target")

    # Parse location: "JP", "US", "DE", etc.
    loc_filter = {"country": location.upper()} if len(location) == 2 else {"city": location}

    # Step 1: Create measurement
    resp = requests.post(f"{GLOBALPING_API}/measurements", json={
        "target": target,
        "type": "traceroute",
        "limit": 1,
        "locations": [loc_filter],
    }, timeout=10)

    if resp.status_code == 422:
        raise ValueError(f"No probes available for location: {location}")
    resp.raise_for_status()
    measurement_id = resp.json()["id"]

    # Step 2: Poll for results
    for _ in range(30):
        time.sleep(1)
        r = requests.get(f"{GLOBALPING_API}/measurements/{measurement_id}", timeout=10)
        data = r.json()
        if data["status"] == "finished":
            break
    else:
        raise TimeoutError("Globalping measurement timed out")

    result = data["results"][0]
    probe = result["probe"]
    gp_hops = result["result"].get("hops", [])

    hops = []
    for i, hop in enumerate(gp_hops, 1):
        ip = hop.get("resolvedAddress") or "*"
        timings = hop.get("timings", [])
        rtt = timings[0]["rtt"] if timings else None
        hostname = hop.get("resolvedHostname", "")
        hops.append({
            'hop': i,
            'ip': ip if ip else '*',
            'rtt': rtt,
            'hostname': hostname or '',
        })

    probe_info = {
        'city': probe.get('city', ''),
        'country': probe.get('country', ''),
        'asn': probe.get('asn'),
        'network': probe.get('network', ''),
        'lat': probe.get('latitude'),
        'lon': probe.get('longitude'),
    }

    return hops, probe_info


async def geolocate_ips(ips: list[str]) -> dict:
    """Batch geolocate IPs using ip-api.com."""
    valid_ips = [ip for ip in ips if ip != '*' and not _is_private(ip)]
    if not valid_ips:
        return {}

    results = {}
    async with aiohttp.ClientSession() as session:
        batch = [{'query': ip} for ip in valid_ips[:100]]
        try:
            async with session.post(
                'http://ip-api.com/batch?fields=status,query,lat,lon,city,regionName,country,isp,as',
                json=batch, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    for item in data:
                        if item.get('status') == 'success':
                            results[item['query']] = {
                                'lat': item['lat'],
                                'lon': item['lon'],
                                'city': item.get('city', ''),
                                'region': item.get('regionName', ''),
                                'country': item.get('country', ''),
                                'isp': item.get('isp', ''),
                                'as': item.get('as', ''),
                            }
        except Exception:
            pass

    return results


def _is_private(ip: str) -> bool:
    parts = ip.split('.')
    if len(parts) != 4:
        return True
    try:
        a, b = int(parts[0]), int(parts[1])
    except ValueError:
        return True
    return (
        a == 10 or
        (a == 172 and 16 <= b <= 31) or
        (a == 192 and b == 168) or
        a == 127 or
        a == 0 or
        a >= 224
    )


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/traceroute', methods=['POST'])
def api_traceroute():
    data = request.get_json()
    target = data.get('target', '').strip()
    method = data.get('method', 'tcp')
    source = data.get('source', 'local')
    location = data.get('location', 'JP')

    if not target:
        return jsonify({'error': 'Target is required'}), 400

    try:
        if source == 'globalping':
            hops, probe_info = run_globalping_traceroute(target, location)
        else:
            hops = run_traceroute(target, method)
            probe_info = None
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except TimeoutError as e:
        return jsonify({'error': str(e)}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    # Geolocate all IPs
    ips = [h['ip'] for h in hops if h['ip'] != '*']
    geo_data = asyncio.run(geolocate_ips(ips))

    for hop in hops:
        if hop['ip'] in geo_data:
            hop['geo'] = geo_data[hop['ip']]

    result = {'target': target, 'hops': hops}
    if probe_info:
        result['probe'] = probe_info
    return jsonify(result)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
