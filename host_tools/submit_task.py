#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket

from smartcar.udp_protocol import encode_packet, make_packet


def main() -> None:
    p = argparse.ArgumentParser(description='Submit a delivery task to the fleet coordinator over UDP')
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=51000)
    p.add_argument('--secret', default='')
    p.add_argument('--task-id', required=True)
    p.add_argument('--recipient', required=True)
    p.add_argument('--pickup-lat', type=float, required=True)
    p.add_argument('--pickup-lon', type=float, required=True)
    p.add_argument('--dropoff-lat', type=float, required=True)
    p.add_argument('--dropoff-lon', type=float, required=True)
    p.add_argument('--priority', type=int, default=0)
    args = p.parse_args()
    packet = make_packet(
        'task_request',
        task_id=args.task_id,
        recipient_id=args.recipient,
        priority=args.priority,
        pickup={'latitude': args.pickup_lat, 'longitude': args.pickup_lon, 'altitude': 0.0},
        dropoff={'latitude': args.dropoff_lat, 'longitude': args.dropoff_lon, 'altitude': 0.0},
    )
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(encode_packet(packet, args.secret), (args.host, args.port))
    print(json.dumps(packet, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
