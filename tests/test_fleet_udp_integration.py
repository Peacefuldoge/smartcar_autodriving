import json
import os
import socket
import select
import subprocess
import sys
import time
from pathlib import Path

from smartcar.udp_protocol import decode_packet, encode_packet, make_packet


ROOT = Path(__file__).resolve().parents[1]


def _free_udp_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_three_vehicle_udp_coordinator_assigns_nearest_idle(tmp_path):
    host_port = _free_udp_port()
    cfg = {
        'bind_ip': '127.0.0.1',
        'port': host_port,
        'vehicle_ids': ['car_1', 'car_2', 'car_3'],
        'heartbeat_timeout': 3.0,
        'min_dispatch_battery': 0.25,
        'ack_timeout': 0.2,
        'max_retries': 3,
        'shared_secret': 'test-secret',
    }
    cfg_path = tmp_path / 'fleet.json'
    cfg_path.write_text(json.dumps(cfg), encoding='utf-8')
    env = dict(os.environ)
    env['PYTHONPATH'] = str(ROOT / 'src') + os.pathsep + env.get('PYTHONPATH', '')
    env['PYTHONUNBUFFERED'] = '1'
    proc = subprocess.Popen(
        [sys.executable, '-u', str(ROOT / 'host_tools/fleet_coordinator.py'), '--config', str(cfg_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    sockets = []
    try:
        ready, _, _ = select.select([proc.stdout], [], [], 3.0)
        assert ready, 'fleet coordinator did not become ready'
        line = proc.stdout.readline()
        assert 'Fleet coordinator listening' in line
        positions = {
            'car_1': (3.0000, 101.0000),
            'car_2': (3.0200, 101.0200),
            'car_3': (3.0002, 101.0002),
        }
        for vehicle_id in ('car_1', 'car_2', 'car_3'):
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('127.0.0.1', 0))
            sock.settimeout(1.5)
            sockets.append((vehicle_id, sock))
        # Send more than one heartbeat so the test is insensitive to process startup timing.
        for _ in range(2):
            for vehicle_id, sock in sockets:
                lat, lon = positions[vehicle_id]
                pkt = make_packet('vehicle_status', vehicle_id,
                                  state='IDLE', task_id='', latitude=lat, longitude=lon,
                                  battery_voltage=12.1, battery_percentage=0.8, battery_low=False)
                sock.sendto(encode_packet(pkt, 'test-secret'), ('127.0.0.1', host_port))
            time.sleep(0.10)

        submitter = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        task = make_packet(
            'task_request',
            task_id='T-UDP-1', recipient_id='alice', priority=1,
            pickup={'latitude': 3.00025, 'longitude': 101.00025, 'altitude': 0.0},
            dropoff={'latitude': 3.01, 'longitude': 101.01, 'altitude': 0.0},
        )
        submitter.sendto(encode_packet(task, 'test-secret'), ('127.0.0.1', host_port))
        submitter.close()

        received_by = None
        assignment = None
        deadline = time.time() + 2.0
        while time.time() < deadline and received_by is None:
            for vehicle_id, sock in sockets:
                sock.settimeout(0.05)
                try:
                    data, _ = sock.recvfrom(65507)
                except socket.timeout:
                    continue
                packet = decode_packet(data, 'test-secret')
                if packet.get('type') == 'task_assignment':
                    received_by = vehicle_id
                    assignment = packet
                    ack = make_packet('task_ack', vehicle_id, task_id=packet['task_id'])
                    sock.sendto(encode_packet(ack, 'test-secret'), ('127.0.0.1', host_port))
                    break
        assert received_by == 'car_3'
        assert assignment['task_id'] == 'T-UDP-1'
    finally:
        for _, sock in sockets:
            sock.close()
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            proc.kill()
