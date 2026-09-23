#!/usr/bin/env python3
from __future__ import annotations

import threading
import unittest

import rospy
import rostest
from std_msgs.msg import Int32

from smartcar_autonomous_driving.msg import Detection, DetectionArray, DriveCommand


class BehaviorRosTest(unittest.TestCase):
    def setUp(self):
        self._last = None
        self._event = threading.Event()
        self._steering_pub = rospy.Publisher("lane/steering", Int32, queue_size=1)
        self._detections_pub = rospy.Publisher("detector/detections", DetectionArray, queue_size=1)
        self._command_sub = rospy.Subscriber("cmd_drive/autonomous", DriveCommand, self._on_command, queue_size=1)
        deadline = rospy.Time.now() + rospy.Duration(3.0)
        while not rospy.is_shutdown() and rospy.Time.now() < deadline:
            if self._steering_pub.get_num_connections() and self._detections_pub.get_num_connections():
                break
            rospy.sleep(0.05)
        self.assertGreater(self._steering_pub.get_num_connections(), 0, "steering publisher not connected")
        self.assertGreater(self._detections_pub.get_num_connections(), 0, "detection publisher not connected")

    def _on_command(self, msg):
        self._last = msg
        self._event.set()

    def _wait_command(self, timeout=2.0):
        self._event.clear()
        self.assertTrue(self._event.wait(timeout), "timed out waiting for autonomous drive command")
        return self._last

    def _publish_detection(self, label_id, score=0.99):
        msg = DetectionArray()
        msg.header.stamp = rospy.Time.now()
        d = Detection()
        d.label_id = label_id
        d.score = score
        msg.detections = [d]
        self._detections_pub.publish(msg)

    def test_lane_command_and_speed_limit_state(self):
        self._steering_pub.publish(Int32(data=1420))
        rospy.sleep(0.15)
        cmd = self._wait_command()
        self.assertEqual(cmd.steering, 1420)
        self.assertEqual(cmd.throttle, 1600)

        self._publish_detection(2)  # speed limit
        rospy.sleep(0.15)
        cmd = self._wait_command()
        self.assertEqual(cmd.throttle, 1530)

        self._publish_detection(3)  # speed limit end
        rospy.sleep(0.15)
        cmd = self._wait_command()
        self.assertEqual(cmd.throttle, 1600)


if __name__ == "__main__":
    rospy.init_node("behavior_ros_test")
    rostest.rosrun("smartcar_autonomous_driving", "behavior_ros", BehaviorRosTest)
