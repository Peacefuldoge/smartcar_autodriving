#!/usr/bin/env python3
from __future__ import annotations

import math

import rospy
from sensor_msgs.msg import NavSatFix, NavSatStatus

from smartcar.gps import parse_nmea


class GPSNode:
    def __init__(self) -> None:
        cfg = rospy.get_param('/smartcar/gps', {})
        self._frame_id = str(cfg.get('frame_id', 'gps'))
        self._verify_checksum = bool(cfg.get('verify_checksum', True))
        self._mock = bool(rospy.get_param('~mock', False))
        self._publisher = rospy.Publisher('gps/fix', NavSatFix, queue_size=10)
        self._serial = None

        if self._mock:
            self._mock_lat = float(rospy.get_param('~mock_latitude', cfg.get('mock_latitude', 0.0)))
            self._mock_lon = float(rospy.get_param('~mock_longitude', cfg.get('mock_longitude', 0.0)))
            self._mock_alt = float(rospy.get_param('~mock_altitude', cfg.get('mock_altitude', 0.0)))
            rate = max(0.2, float(cfg.get('publish_rate', 5.0)))
            self._timer = rospy.Timer(rospy.Duration(1.0 / rate), self._publish_mock)
            rospy.logwarn('gps_node: MOCK mode enabled')
        else:
            try:
                import serial
            except ImportError as exc:
                raise RuntimeError('gps_node requires pyserial') from exc
            self._serial = serial.Serial(
                str(cfg.get('serial_device', '/dev/ttyUSB1')),
                int(cfg.get('baudrate', 9600)),
                timeout=float(cfg.get('timeout', 0.1)),
            )
            rate = max(1.0, float(cfg.get('poll_rate', 20.0)))
            self._timer = rospy.Timer(rospy.Duration(1.0 / rate), self._poll)
            rospy.loginfo('gps_node: serial=%s', self._serial.port)

    def _make_msg(self, latitude: float, longitude: float, altitude: float,
                  valid: bool, hdop: float = 0.0) -> NavSatFix:
        msg = NavSatFix()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = self._frame_id
        msg.status.status = NavSatStatus.STATUS_FIX if valid else NavSatStatus.STATUS_NO_FIX
        msg.status.service = NavSatStatus.SERVICE_GPS
        msg.latitude = latitude
        msg.longitude = longitude
        msg.altitude = altitude
        if hdop > 0.0:
            sigma = max(0.5, hdop * 2.5)
            msg.position_covariance = [sigma * sigma, 0.0, 0.0,
                                       0.0, sigma * sigma, 0.0,
                                       0.0, 0.0, (sigma * 2.0) ** 2]
            msg.position_covariance_type = NavSatFix.COVARIANCE_TYPE_APPROXIMATED
        else:
            msg.position_covariance_type = NavSatFix.COVARIANCE_TYPE_UNKNOWN
        return msg

    def _poll(self, _event) -> None:
        try:
            raw = self._serial.readline().decode('ascii', errors='ignore').strip()
        except Exception as exc:
            rospy.logwarn_throttle(2.0, 'gps_node serial read failed: %s', exc)
            return
        fix = parse_nmea(raw, verify_checksum=self._verify_checksum)
        if fix is not None:
            self._publisher.publish(self._make_msg(
                fix.latitude, fix.longitude, fix.altitude, fix.valid, fix.hdop))

    def _publish_mock(self, _event) -> None:
        self._publisher.publish(self._make_msg(
            self._mock_lat, self._mock_lon, self._mock_alt, True, 1.0))


def main() -> None:
    rospy.init_node('gps_node')
    GPSNode()
    rospy.spin()


if __name__ == '__main__':
    main()
