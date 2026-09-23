# ROS Multi-Vehicle Autonomous Delivery System

基于 **ROS** 的智能车，由原智能车项目整理而来，集成视觉感知、GPS 导航、电池管理、UDP 通信、多车任务调度及人脸检测功能。

## Features

* **Lane Following**：基于 OpenCV + 深度学习模型进行车道检测与转向控制
* **Object Detection**：识别道路交通标志并执行停车、限速、超车等行为
* **GPS Navigation**：解析 NMEA GPS 数据，提供车辆位置与任务目标导航
* **Battery Monitoring**：通过 RS-232 接收下位机电池电压
* **Low-Battery Return**：低电量时停止接单并自动返回起点
* **UDP Communication**：车辆与主机之间通过 UDP Socket 通信
* **Multi-Vehicle Coordination**：支持 3 辆智能车协同配送
* **Task Scheduling**：优先向在线、空闲、电量正常且距离较近的车辆派单
* **Face Detection**：使用 OpenCV Haar Cascade 检测收货现场人脸
* **Manual / Autonomous Mode**：支持手柄控制与自动驾驶模式切换
* **Safety Watchdog**：通信或控制指令超时自动停车

## System Architecture

```text
                    Host / Fleet Coordinator
                              │
                         UDP Socket
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
        Car 1               Car 2               Car 3
          │
     UDP Bridge
          │
 ┌────────┼───────────┐
 │        │           │
GPS    Battery     Delivery Task
 │        │           │
 └────────┼───────────┘
          │
    Mission Manager
          │
 ┌────────┴─────────┐
 │                  │
GPS Navigation   Face Detection
 │                  │
 └────────┬─────────┘
          │
    Command Mux
          │
   Vehicle Driver
          │
      MCU / Motor
```

## ROS Nodes

| Node                      | Function                                          |
| ------------------------- | ------------------------------------------------- |
| `camera_node`             | Camera acquisition                                |
| `lane_following_node`     | Lane following and steering prediction            |
| `object_detection_node`   | Traffic / scene object detection                  |
| `behavior_node`           | Driving behavior state machine                    |
| `gps_node`                | GPS NMEA parsing                                  |
| `battery_node`            | Battery voltage monitoring                        |
| `mission_manager_node`    | Delivery mission management                       |
| `gps_navigation_node`     | GPS target navigation                             |
| `face_verification_node`  | Haar Cascade face detection                       |
| `udp_vehicle_bridge_node` | Vehicle-host UDP communication                    |
| `command_mux_node`        | Manual / autonomous / mission command arbitration |
| `vehicle_driver_node`     | Vehicle hardware control                          |
| `data_recorder_node`      | Driving data collection                           |

The host runs:

```text
fleet_coordinator.py
```

for vehicle monitoring and delivery-task scheduling.

## Environment

Recommended:

```text
Ubuntu 20.04
ROS1 Noetic
Python 3
OpenCV
PySerial
```

Install ROS dependencies:

```bash
sudo bash scripts/install_ros1_noetic_focal.sh
```

Build:

```bash
bash scripts/build_and_test_ros1.sh
```

Or manually:

```bash
mkdir -p ~/catkin_ws/src
cd ~/catkin_ws/src

ln -s /path/to/project smartcar_autonomous_driving

cd ~/catkin_ws
catkin_make
source devel/setup.bash
```

## Run

### Autonomous Driving

```bash
roslaunch smartcar_autonomous_driving autonomous.launch
```

### Logistics Vehicle

```bash
roslaunch smartcar_autonomous_driving logistics_vehicle.launch \
    vehicle_id:=car_1
```

Run the other vehicles with:

```text
car_2
car_3
```

### Fleet Coordinator

```bash
python3 scripts/fleet_coordinator.py
```

## Multi-Vehicle Scheduling

The coordinator maintains the status of all vehicles:

```text
IDLE
TO_PICKUP
TO_DROPOFF
VERIFY_RECIPIENT
RETURNING_HOME
OFFLINE
```

Only vehicles that are:

```text
Online
+ Idle
+ Battery OK
```

can receive new tasks.

When multiple vehicles are available, the coordinator prefers the vehicle closest to the pickup location.

If battery voltage drops below the configured threshold:

```text
Current Mission Cancelled
        ↓
RETURNING_HOME
        ↓
Navigate to Home GPS Position
```

The vehicle becomes available again only after battery recovery.

## Face Detection

Delivery verification uses OpenCV:

```python
cv2.CascadeClassifier
```

with the default Haar frontal-face detector.

```text
haarcascade_frontalface_default.xml
```

Multiple consecutive detections are required before confirming that a person is present.

> The default Haar Cascade performs **face detection**, not personal identity recognition.

## Communication

Vehicle ↔ Host communication uses **UDP Socket + JSON**.

Supported messages include:

```text
heartbeat
vehicle_status
task_request
task_assignment
task_ack
task_status
task_complete
task_abort
```

Task assignment supports ACK, retry and task-ID based duplicate protection.

## Validation

Current automated tests cover:

```text
Lane control
Behavior state machine
GPS parsing
Battery monitoring
Low-battery return
UDP communication
Three-vehicle scheduling
Task management
GPS navigation
Cascade face detection
Command arbitration
```

Test result:

```text
34 tests passed
```

Run:

```bash
pytest
```

## Project Structure

```text
.
├── config/
├── docs/
├── firmware/
├── launch/
├── msg/
├── scripts/
├── src/
│   └── smartcar/
├── test/
├── CMakeLists.txt
├── package.xml
└── README.md
```

## License

This project is intended for research, education and intelligent-vehicle development.
