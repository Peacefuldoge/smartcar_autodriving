#!/usr/bin/env python3
from __future__ import annotations

import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image

from smartcar.camera import CameraConfig, V4L2MJPEGCamera


def main() -> None:
    rospy.init_node("camera_node")
    cfg = rospy.get_param("/smartcar/camera", {})
    rate_hz = float(rospy.get_param("~rate", 30.0))
    frame_id = rospy.get_param("~frame_id", "smartcar_camera")

    camera_cfg = CameraConfig(
        device=cfg.get("device", "/dev/video2"),
        width=int(cfg.get("width", 424)),
        height=int(cfg.get("height", 240)),
        fourcc=cfg.get("fourcc", "MJPG"),
    )
    publisher = rospy.Publisher("camera/image_raw", Image, queue_size=1)
    bridge = CvBridge()
    rate = rospy.Rate(rate_hz)

    camera = V4L2MJPEGCamera(camera_cfg)
    rospy.loginfo("camera_node: opened %s at %dx%d", camera_cfg.device, camera_cfg.width, camera_cfg.height)
    try:
        while not rospy.is_shutdown():
            frame = camera.read()
            msg = bridge.cv2_to_imgmsg(frame, encoding="bgr8")
            msg.header.stamp = rospy.Time.now()
            msg.header.frame_id = frame_id
            publisher.publish(msg)
            rate.sleep()
    finally:
        camera.close()


if __name__ == "__main__":
    main()
