#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import time
from pathlib import Path

from smartcar.fleet import DeliveryTask, FleetCoordinatorCore, VehicleSnapshot
from smartcar.navigation import GeoPoint
from smartcar.udp_protocol import decode_packet, encode_packet, make_packet


def point_from(obj):
    return GeoPoint(float(obj['latitude']), float(obj['longitude']), float(obj.get('altitude', 0.0)))


def task_packet(task: DeliveryTask, vehicle_id: str):
    def p(point):
        return {'latitude': point.latitude, 'longitude': point.longitude, 'altitude': point.altitude}
    return make_packet(
        'task_assignment', vehicle_id,
        task_id=task.task_id,
        recipient_id=task.recipient_id,
        priority=task.priority,
        pickup=p(task.pickup),
        dropoff=p(task.dropoff),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description='UDP fleet coordinator for three smart cars')
    parser.add_argument('--config', default='config/fleet_host.json')
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
    vehicle_ids = cfg.get('vehicle_ids', ['car_1', 'car_2', 'car_3'])
    core = FleetCoordinatorCore(
        vehicle_ids,
        heartbeat_timeout=float(cfg.get('heartbeat_timeout', 3.0)),
        min_dispatch_battery=float(cfg.get('min_dispatch_battery', 0.25)),
    )
    secret = str(cfg.get('shared_secret', ''))
    ack_timeout = float(cfg.get('ack_timeout', 0.5))
    max_retries = int(cfg.get('max_retries', 5))
    pending_ack = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((str(cfg.get('bind_ip', '0.0.0.0')), int(cfg.get('port', 51000))))
    sock.settimeout(0.25)
    print(f"Fleet coordinator listening on {sock.getsockname()} for {vehicle_ids}", flush=True)
    if not secret:
        print('WARNING: shared_secret is empty; UDP packets are not authenticated', flush=True)

    while True:
        now = time.time()
        try:
            data, addr = sock.recvfrom(65507)
        except socket.timeout:
            data = None
            addr = None
        except KeyboardInterrupt:
            break

        if data:
            try:
                packet = decode_packet(data, secret)
            except ValueError as exc:
                print(f'rejected packet from {addr}: {exc}')
                continue
            typ = packet.get('type')
            if typ == 'vehicle_status':
                vehicle_id = str(packet.get('vehicle_id', ''))
                if vehicle_id in core.vehicles:
                    lat = float(packet.get('latitude', 0.0))
                    lon = float(packet.get('longitude', 0.0))
                    position = None if (lat == 0.0 and lon == 0.0) else GeoPoint(lat, lon)
                    status_task_id = str(packet.get('task_id', ''))
                    core.update_vehicle(VehicleSnapshot(
                        vehicle_id=vehicle_id,
                        state=str(packet.get('state', 'OFFLINE')),
                        position=position,
                        battery_percentage=float(packet.get('battery_percentage', 0.0)),
                        battery_low=bool(packet.get('battery_low', False)),
                        task_id=status_task_id,
                        last_seen=now,
                        endpoint=addr,
                    ))
                    if status_task_id and status_task_id in pending_ack:
                        pending_ack.pop(status_task_id, None)
                        print(f'implicit ack for {status_task_id} from vehicle status')
            elif typ == 'task_request':
                try:
                    task = DeliveryTask(
                        task_id=str(packet['task_id']),
                        recipient_id=str(packet['recipient_id']),
                        pickup=point_from(packet['pickup']),
                        dropoff=point_from(packet['dropoff']),
                        priority=int(packet.get('priority', 0)),
                        created_at=now,
                    )
                    core.submit(task)
                    print(f'queued task {task.task_id}')
                except (KeyError, ValueError, TypeError) as exc:
                    print(f'invalid task request: {exc}')
            elif typ == 'task_ack':
                task_id = str(packet.get('task_id', ''))
                if task_id in pending_ack:
                    pending_ack.pop(task_id, None)
                    print(f'acknowledged task {task_id} by {packet.get("vehicle_id", "")}')
            elif typ == 'vehicle_event':
                event = str(packet.get('event', ''))
                task_id = str(packet.get('task_id', ''))
                vehicle_id = str(packet.get('vehicle_id', ''))
                if event == 'task_completed' and task_id:
                    pending_ack.pop(task_id, None)
                    core.complete(task_id)
                    print(f'completed task {task_id} by {vehicle_id}')
                elif event in {'task_aborted_low_battery', 'task_rejected_low_battery', 'task_rejected_busy'} and task_id:
                    pending_ack.pop(task_id, None)
                    core.abort(task_id, requeue=True)
                    if vehicle_id in core.vehicles:
                        core.vehicles[vehicle_id].task_id = ''
                    print(f'requeued task {task_id}: {vehicle_id} event={event}')

        for vehicle_id in core.mark_offline(now):
            for task_id, task in list(core.active.items()):
                if task.assigned_vehicle == vehicle_id:
                    pending_ack.pop(task_id, None)
                    core.abort(task_id, requeue=True)
                    print(f'requeued task {task_id}: {vehicle_id} offline')

        # Retransmit unacknowledged UDP assignments. task_id makes delivery idempotent.
        for task_id, entry in list(pending_ack.items()):
            if now - entry['sent_at'] < ack_timeout:
                continue
            if entry['retries'] >= max_retries:
                vehicle_id = entry['vehicle_id']
                pending_ack.pop(task_id, None)
                core.abort(task_id, requeue=True)
                if vehicle_id in core.vehicles:
                    core.vehicles[vehicle_id].state = 'OFFLINE'
                    core.vehicles[vehicle_id].task_id = ''
                print(f'assignment {task_id} failed after {max_retries} retries; requeued')
                continue
            sock.sendto(entry['payload'], entry['endpoint'])
            entry['sent_at'] = now
            entry['retries'] += 1

        for vehicle, task in core.assign_pending(now):
            if vehicle.endpoint is None:
                core.abort(task.task_id, requeue=True)
                continue
            payload = encode_packet(task_packet(task, vehicle.vehicle_id), secret)
            sock.sendto(payload, vehicle.endpoint)
            pending_ack[task.task_id] = {
                'vehicle_id': vehicle.vehicle_id,
                'endpoint': vehicle.endpoint,
                'payload': payload,
                'sent_at': now,
                'retries': 0,
            }
            print(f'assigned {task.task_id} -> {vehicle.vehicle_id}')


if __name__ == '__main__':
    main()
