#!/usr/bin/env python3
from __future__ import annotations

import time
import unittest

import rospy
import rostest
from sensor_msgs.msg import NavSatFix, NavSatStatus
from std_msgs.msg import Bool, String

from smartcar_autonomous_driving.msg import DeliveryTask, NavigationGoal


class LogisticsRosTest(unittest.TestCase):
    def setUp(self):
        self.state = ''
        self.goal = None
        self.state_sub = rospy.Subscriber('/smartcar/mission/state', String, self._on_state, queue_size=10)
        self.goal_sub = rospy.Subscriber('/smartcar/mission/navigation_goal', NavigationGoal, self._on_goal, queue_size=10)
        self.gps_pub = rospy.Publisher('/smartcar/gps/fix', NavSatFix, queue_size=10)
        self.task_pub = rospy.Publisher('/smartcar/fleet/task', DeliveryTask, queue_size=10)
        self.low_pub = rospy.Publisher('/smartcar/battery/low', Bool, queue_size=10)
        self._wait_for_connections()

    def _on_state(self, msg):
        self.state = msg.data

    def _on_goal(self, msg):
        self.goal = msg

    def _wait_for_connections(self):
        deadline = time.time() + 5.0
        while time.time() < deadline and not rospy.is_shutdown():
            if self.gps_pub.get_num_connections() and self.task_pub.get_num_connections() and self.low_pub.get_num_connections():
                return
            rospy.sleep(0.05)
        self.fail('mission manager subscribers did not connect')

    def _wait_state(self, expected, timeout=3.0):
        deadline = time.time() + timeout
        while time.time() < deadline and not rospy.is_shutdown():
            if self.state == expected:
                return
            rospy.sleep(0.05)
        self.fail('expected state %s, got %s' % (expected, self.state))

    def test_low_battery_aborts_delivery_and_returns_home(self):
        fix = NavSatFix()
        fix.header.stamp = rospy.Time.now()
        fix.status.status = NavSatStatus.STATUS_FIX
        fix.status.service = NavSatStatus.SERVICE_GPS
        fix.latitude = 3.1390
        fix.longitude = 101.6869
        fix.altitude = 10.0
        self.gps_pub.publish(fix)
        rospy.sleep(0.2)

        task = DeliveryTask()
        task.header.stamp = rospy.Time.now()
        task.task_id = 'ros-logistics-1'
        task.recipient_id = 'alice'
        task.priority = 1
        task.pickup.latitude = 3.1400
        task.pickup.longitude = 101.6870
        task.dropoff.latitude = 3.1410
        task.dropoff.longitude = 101.6880
        self.task_pub.publish(task)
        self._wait_state('TO_PICKUP')

        self.low_pub.publish(Bool(data=True))
        self._wait_state('RETURNING_HOME')

        deadline = time.time() + 3.0
        while time.time() < deadline and not rospy.is_shutdown():
            goal = self.goal
            if goal is not None and goal.goal_type == 'home':
                self.assertAlmostEqual(goal.target.latitude, 3.1390, places=5)
                self.assertAlmostEqual(goal.target.longitude, 101.6869, places=5)
                return
            rospy.sleep(0.05)
        self.fail('home navigation goal was not published')


if __name__ == '__main__':
    rospy.init_node('rostest_logistics')
    rostest.rosrun('smartcar_autonomous_driving', 'rostest_logistics', LogisticsRosTest)
