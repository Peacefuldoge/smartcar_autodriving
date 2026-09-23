#!/usr/bin/env python3
from __future__ import annotations

import json
import socket
import threading

import rospy
from std_msgs.msg import String

from smartcar.udp_protocol import decode_packet, encode_packet, make_packet
from smartcar_autonomous_driving.msg import DeliveryTask, VehicleStatus


class UDPVehicleBridgeNode:
    def __init__(self) -> None:
        cfg = rospy.get_param('/smartcar/udp', {})
        mission = rospy.get_param('/smartcar/mission', {})
        self._vehicle_id = str(rospy.get_param('~vehicle_id', mission.get('vehicle_id', 'car_1')))
        self._host = str(cfg.get('host_ip', '127.0.0.1'))
        self._host_port = int(cfg.get('host_port', 51000))
        self._bind_ip = str(cfg.get('bind_ip', '0.0.0.0'))
        self._local_port = int(rospy.get_param('~local_port', cfg.get('local_port', 52001)))
        self._secret = str(rospy.get_param('~shared_secret', cfg.get('shared_secret', '')))
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self._bind_ip, self._local_port))
        self._sock.settimeout(0.25)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._status = None
        self._seen_tasks = set()
        self._task_pub = rospy.Publisher('fleet/task', DeliveryTask, queue_size=10)
        rospy.Subscriber('fleet/status', VehicleStatus, self._on_status, queue_size=10)
        rospy.Subscriber('fleet/event', String, self._on_event, queue_size=10)
        self._thread = threading.Thread(target=self._rx_loop, name='udp-vehicle-rx', daemon=True)
        self._thread.start()
        rate = max(1.0, float(cfg.get('heartbeat_rate', 2.0)))
        self._timer = rospy.Timer(rospy.Duration(1.0 / rate), self._send_heartbeat)
        rospy.on_shutdown(self._shutdown)
        if not self._secret:
            rospy.logwarn('udp_vehicle_bridge_node: shared_secret is empty; UDP packets are not authenticated')
        rospy.loginfo('udp_vehicle_bridge_node: vehicle=%s local=%s:%d host=%s:%d',
                      self._vehicle_id, self._bind_ip, self._local_port, self._host, self._host_port)

    def _send(self, packet) -> None:
        try:
            self._sock.sendto(encode_packet(packet, self._secret), (self._host, self._host_port))
        except OSError as exc:
            rospy.logwarn_throttle(2.0, 'udp_vehicle_bridge_node send failed: %s', exc)

    def _on_status(self, msg: VehicleStatus) -> None:
        with self._lock:
            self._status = msg

    def _send_heartbeat(self, _event) -> None:
        with self._lock:
            msg = self._status
        if msg is None:
            return
        self._send(make_packet(
            'vehicle_status', self._vehicle_id,
            state=msg.state,
            task_id=msg.task_id,
            latitude=msg.latitude,
            longitude=msg.longitude,
            battery_voltage=msg.battery_voltage,
            battery_percentage=msg.battery_percentage,
            battery_low=msg.battery_low,
        ))

    def _on_event(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except Exception:
            payload = {'event': msg.data}
        task_id = str(payload.get('task_id', ''))
        if payload.get('event') in {
            'task_completed', 'task_aborted_low_battery', 'task_rejected_low_battery', 'task_rejected_busy'
        } and task_id:
            with self._lock:
                self._seen_tasks.discard(task_id)
        self._send(make_packet('vehicle_event', self._vehicle_id, **payload))

    def _rx_loop(self) -> None:
        while not self._stop.is_set() and not rospy.is_shutdown():
            try:
                data, _addr = self._sock.recvfrom(65507)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                packet = decode_packet(data, self._secret)
            except ValueError as exc:
                rospy.logwarn_throttle(2.0, 'udp_vehicle_bridge_node rejected packet: %s', exc)
                continue
            if packet.get('type') != 'task_assignment':
                continue
            if packet.get('vehicle_id') not in {'', self._vehicle_id}:
                continue
            task_id = str(packet.get('task_id', ''))
            with self._lock:
                duplicate = bool(task_id) and task_id in self._seen_tasks
            if duplicate:
                self._send(make_packet('task_ack', self._vehicle_id, task_id=task_id))
                continue
            try:
                task = DeliveryTask()
                task.header.stamp = rospy.Time.now()
                task.task_id = str(packet['task_id'])
                task.recipient_id = str(packet['recipient_id'])
                task.priority = int(packet.get('priority', 0))
                pickup = packet['pickup']
                dropoff = packet['dropoff']
                task.pickup.latitude = float(pickup['latitude'])
                task.pickup.longitude = float(pickup['longitude'])
                task.pickup.altitude = float(pickup.get('altitude', 0.0))
                task.dropoff.latitude = float(dropoff['latitude'])
                task.dropoff.longitude = float(dropoff['longitude'])
                task.dropoff.altitude = float(dropoff.get('altitude', 0.0))
            except (KeyError, TypeError, ValueError) as exc:
                rospy.logwarn('udp_vehicle_bridge_node invalid task assignment: %s', exc)
                continue
            with self._lock:
                self._seen_tasks.add(task.task_id)
            self._task_pub.publish(task)
            self._send(make_packet('task_ack', self._vehicle_id, task_id=task.task_id))

    def _shutdown(self) -> None:
        self._stop.set()
        try:
            self._sock.close()
        except OSError:
            pass
        if self._thread.is_alive():
            self._thread.join(timeout=0.5)


def main() -> None:
    rospy.init_node('udp_vehicle_bridge_node')
    UDPVehicleBridgeNode()
    rospy.spin()


if __name__ == '__main__':
    main()
