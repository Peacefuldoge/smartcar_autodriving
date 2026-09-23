#!/usr/bin/env python3
from __future__ import annotations

import rospy
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Bool

from smartcar.battery import BatteryMonitorCore, parse_voltage_line


class BatteryNode:
    def __init__(self) -> None:
        cfg = rospy.get_param('/smartcar/battery', {})
        self._core = BatteryMonitorCore(
            low_voltage=float(cfg.get('low_voltage', 10.8)),
            recovery_voltage=float(cfg.get('recovery_voltage', 11.2)),
            empty_voltage=float(cfg.get('empty_voltage', 10.0)),
            full_voltage=float(cfg.get('full_voltage', 12.6)),
        )
        self._state_pub = rospy.Publisher('battery/state', BatteryState, queue_size=10, latch=True)
        self._low_pub = rospy.Publisher('battery/low', Bool, queue_size=1, latch=True)
        self._mock_voltage = rospy.get_param('~mock_voltage', None)
        self._serial = None

        if self._mock_voltage is not None:
            rate = max(0.5, float(cfg.get('publish_rate', 2.0)))
            self._timer = rospy.Timer(rospy.Duration(1.0 / rate), self._poll_mock)
            rospy.logwarn('battery_node: MOCK voltage=%s V', self._mock_voltage)
        else:
            try:
                import serial
            except ImportError as exc:
                raise RuntimeError('battery_node requires pyserial') from exc
            self._serial = serial.Serial(
                str(cfg.get('serial_device', '/dev/ttyUSB2')),
                int(cfg.get('baudrate', 9600)),
                timeout=float(cfg.get('timeout', 0.1)),
            )
            rate = max(1.0, float(cfg.get('poll_rate', 10.0)))
            self._timer = rospy.Timer(rospy.Duration(1.0 / rate), self._poll_serial)
            rospy.loginfo('battery_node: RS-232 serial=%s', self._serial.port)

    def _publish_voltage(self, voltage: float) -> None:
        reading = self._core.update(voltage)
        msg = BatteryState()
        msg.header.stamp = rospy.Time.now()
        msg.voltage = reading.voltage
        msg.percentage = reading.percentage
        msg.present = True
        msg.power_supply_status = BatteryState.POWER_SUPPLY_STATUS_DISCHARGING
        msg.power_supply_health = BatteryState.POWER_SUPPLY_HEALTH_GOOD
        self._state_pub.publish(msg)
        self._low_pub.publish(Bool(data=reading.low))
        if reading.low:
            rospy.logwarn_throttle(5.0, 'battery_node: LOW BATTERY %.2f V (%.0f%%)',
                                   reading.voltage, reading.percentage * 100.0)

    def _poll_serial(self, _event) -> None:
        try:
            line = self._serial.readline().decode('ascii', errors='ignore')
        except Exception as exc:
            rospy.logwarn_throttle(2.0, 'battery_node serial read failed: %s', exc)
            return
        voltage = parse_voltage_line(line)
        if voltage is not None:
            self._publish_voltage(voltage)

    def _poll_mock(self, _event) -> None:
        self._publish_voltage(float(rospy.get_param('~mock_voltage', self._mock_voltage)))


def main() -> None:
    rospy.init_node('battery_node')
    BatteryNode()
    rospy.spin()


if __name__ == '__main__':
    main()
