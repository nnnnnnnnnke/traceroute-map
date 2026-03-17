#!/usr/bin/env python3
"""Traceroute Map - Visualize network routes on a world map."""

import json
import re
import subprocess
import asyncio
import aiohttp
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


def run_traceroute(target: str, method: str = 'tcp') -> list[dict]:
    """Run traceroute and parse hops."""
    # Validate target (prevent command injection)
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
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError("Traceroute timed out")

    hops = []
    for line in result.stdout.strip().split('\n')[1:]:  # Skip header
        match = re.match(r'\s*(\d+)\s+(.+)', line)
        if not match:
            continue
        hop_num = int(match.group(1))
        rest = match.group(2)

        # Extract first responding IP
        ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', rest)
        if ip_match:
            ip = ip_match.group(1)
            # Extract RTT
            rtt_match = re.search(r'([\d.]+)\s*ms', rest)
            rtt = float(rtt_match.group(1)) if rtt_match else None
            hops.append({'hop': hop_num, 'ip': ip, 'rtt': rtt})
        else:
            hops.append({'hop': hop_num, 'ip': '*', 'rtt': None})

    return hops


async def geolocate_ips(ips: list[str]) -> dict:
    """Batch geolocate IPs using ip-api.com (max 100 per request)."""
    # Filter out private/reserved IPs and wildcards
    valid_ips = [ip for ip in ips if ip != '*' and not _is_private(ip)]
    if not valid_ips:
        return {}

    results = {}
    async with aiohttp.ClientSession() as session:
        # ip-api.com batch endpoint (free, no key needed)
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
    """Check if an IP is private/reserved."""
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
    if not target:
        return jsonify({'error': 'Target is required'}), 400

    try:
        hops = run_traceroute(target, method)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except TimeoutError as e:
        return jsonify({'error': str(e)}), 504

    # Geolocate all IPs
    ips = [h['ip'] for h in hops if h['ip'] != '*']
    geo_data = asyncio.run(geolocate_ips(ips))

    # Merge geo data into hops
    for hop in hops:
        if hop['ip'] in geo_data:
            hop['geo'] = geo_data[hop['ip']]

    return jsonify({'target': target, 'hops': hops})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
