cmake_minimum_required(VERSION 3.0.2)
project(smartcar_autonomous_driving)

find_package(catkin REQUIRED COMPONENTS
  cv_bridge
  message_filters
  message_generation
  rospy
  sensor_msgs
  std_msgs
  std_srvs
)

add_message_files(
  FILES
  Detection.msg
  DetectionArray.msg
  DriveCommand.msg
  GeoPoint.msg
  DeliveryTask.msg
  NavigationGoal.msg
  FaceRecognition.msg
  VehicleStatus.msg
)

generate_messages(
  DEPENDENCIES
  std_msgs
)

catkin_python_setup()

catkin_package(
  CATKIN_DEPENDS cv_bridge message_filters message_runtime rospy sensor_msgs std_msgs std_srvs
)

catkin_install_python(PROGRAMS
  ros_nodes/camera_node.py
  ros_nodes/lane_following_node.py
  ros_nodes/object_detection_node.py
  ros_nodes/behavior_node.py
  ros_nodes/command_mux_node.py
  ros_nodes/vehicle_driver_node.py
  ros_nodes/joy_teleop_node.py
  ros_nodes/data_recorder_node.py
  ros_nodes/gps_node.py
  ros_nodes/battery_node.py
  ros_nodes/gps_navigation_node.py
  ros_nodes/mission_manager_node.py
  ros_nodes/face_recognition_node.py
  ros_nodes/udp_vehicle_bridge_node.py
  scripts/check_face_cascade.py
  host_tools/fleet_coordinator.py
  host_tools/submit_task.py
  test/rostest_behavior.py
  test/rostest_logistics.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY launch config
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)

if(CATKIN_ENABLE_TESTING)
  find_package(rostest REQUIRED)
  add_rostest(test/behavior_ros.test)
  add_rostest(test/logistics_ros.test)
endif()
