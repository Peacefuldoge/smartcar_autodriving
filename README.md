# Autonomous Smart Car — Lane Following + Object Detection + Behavior Control

这是对当年智能车比赛代码的一次工程化整理。原项目已经具备完整的“感知—决策—控制—数据采集”闭环，但源代码以比赛现场快速迭代的形式存在：多个近似版本、硬编码路径、全局状态、临时测试脚本和硬件调用混在一起。本仓库将它重构成更适合阅读、复现和放在 GitHub 展示的项目结构。

## 项目能力

- **视觉循迹**：V4L2 摄像头采集 424×240 MJPEG 图像，基于 HSV 提取黄色车道区域，使用 **Paddle Lite** 回归模型预测转向。
- **目标/场景检测**：使用 **Paddle Mobile Tiny-YOLO** 检测赛道事件，并将输出解析为类别、置信度与目标框。
- **行为决策**：包含超车、停车线、限速/解除限速、左转、斑马线与停车等规则；对原始多帧计数逻辑进行了状态化重构。
- **车辆控制**：通过 `ctypes` 调用比赛平台提供的 `libart_driver.so`，经 `/dev/ttyUSB0` 向下位机发送油门和转向命令。
- **数据采集**：Linux 手柄 `/dev/input/js0` 控制车辆，同时保存摄像头图像与同步转向标签，用于训练循迹模型。
- **下位机控制**：Arduino 风格固件接收串口命令，将转向差值转换为左右电机差速 PWM；整理版额外加入 300 ms 通信 watchdog，避免上位机失联后车辆继续保持最后速度。

## 系统结构

```text
Camera (/dev/video2)
  ├─ HSV lane mask → Paddle Lite steering model → steering calibration ─┐
  └─ RGB frame → Tiny-YOLO detector → multi-frame behavior controller ──┼→ throttle / steering
                                                                        ↓
                                                               libart_driver.so
                                                                        ↓
                                                               serial /dev/ttyUSB0
                                                                        ↓
                                                                motor controller MCU
```

更详细的数据流见 [`docs/architecture.md`](docs/architecture.md)。

## 目录

```text
.
├── config/                     # 设备、模型、阈值与 ROS 参数
├── docs/                       # 架构、ROS1 与验证说明
├── firmware/motor_controller/  # 下位机电机控制程序
├── launch/                     # ROS1 launch 文件
├── msg/                        # ROS1 自定义消息
├── ros_nodes/                  # ROS1 节点
├── scripts/                    # 数据检查 / HSV 调试 / ROS 验证工具
├── src/smartcar/
│   ├── autonomous.py           # 自动驾驶主循环
│   ├── behavior.py             # 高层状态与赛道行为
│   ├── camera.py               # V4L2 MJPEG 摄像头
│   ├── data_collection.py      # 手柄驾驶数据采集
│   ├── hardware.py             # libart_driver.so 封装
│   ├── joystick.py             # Linux joystick 接口
│   ├── lane_following.py       # 循迹预处理、模型与舵机标定
│   └── object_detection.py     # Tiny-YOLO 推理封装
└── tests/                      # 不依赖车辆硬件的逻辑测试
```

## 原始项目中缺失的运行资产

上传的历史压缩包**不包含**以下文件，因此这个仓库目前可以完整阅读和测试纯逻辑，但不能仅凭现有文件直接在车辆上完成端到端运行：

1. `lib/libart_driver.so` — 比赛平台车辆通信动态库；
2. `models/lane/model_infer/model` 与 `params` — Paddle Lite 循迹模型；
3. `models/detector/freeze_model/` — Paddle Mobile 目标检测模型；
4. 原始 `label_list` — 本仓库根据 `user4.py` 的实际分支注释提供了 `config/labels.example.txt`，使用前请与真实训练标签核对。

建议不要把大型模型和比赛 SDK 二进制直接提交到 Git；可使用 Git LFS 或在 README 中提供获取方式。

## 安装（开发/阅读环境）

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

普通电脑只需上述依赖即可运行单元测试。目标车机还需要安装与原平台匹配的 `v4l2capture`、`paddlelite` 和 `paddlemobile`。这些旧版硬件 SDK 与具体板卡/FPGA 环境绑定，因此没有在 `requirements.txt` 中强行固定一个可能错误的版本。

## 运行

自动驾驶：

```bash
smartcar run --config config/default.json
```

数据采集：

```bash
smartcar collect \
  --output data/run_001 \
  --camera /dev/video2 \
  --joystick /dev/input/js0 \
  --serial /dev/ttyUSB0
```

采集模式中，`Y` 开始记录，`TL/TR` 停止；左摇杆 X 轴控制转向。数据以 `images/000000.jpg` + `labels.csv` 的形式保存，避免原版本通过独立 TXT/NPY 和 `num_data.txt` 维持索引带来的同步风险。

## 测试

```bash
pytest
```

测试目前覆盖了历史舵机标定、限速状态切换、停车线一次性触发和超车动作序列等硬件无关逻辑。

## 对历史代码的关键修正

原代码最值得保留的是整体系统思路，但有一些现场迭代造成的问题：`user4.py` 中 `used` 未定义；`limited` 状态会被后面的速度分支覆盖；不同类别共用一个 `number` 计数器；同一目标在一个循环里会多次调用 `send_cmd`；主循环每帧还有大量调试打印/图片写盘。现在这些问题都被拆成明确的模型、状态和硬件接口。

完整删改映射与兼容性说明见 [`docs/refactor_notes.md`](docs/refactor_notes.md)。

## 历史模型兼容性说明

循迹预处理里有一个值得注意的历史行为：原代码先生成 NHWC 数组，再直接 `reshape(1, 3, 128, 128)`，而不是标准 `transpose`。这在常规深度学习代码里很反常，但模型可能已经按这一数据布局被训练/部署。因此默认配置保留了该行为：

```json
"legacy_memory_layout": true
```

只有在重新训练并验证模型后，才建议切换成标准 CHW 转置。


## ROS1（Noetic）集成

当前版本在原有纯 Python 核心之上增加了 ROS1 通信层，核心算法仍保留在
`src/smartcar/`，因此不依赖 ROS 也能进行单元测试；ROS 节点只负责消息传递、
模块编排和硬件接口。

ROS 计算图：

```text
camera_node
  └─ /smartcar/camera/image_raw
       ├─ lane_following_node ── /smartcar/lane/steering ─┐
       └─ object_detection_node ─ /smartcar/detector/detections ─┤
                                                               ↓
                                                        behavior_node
                                                               ↓
                                              /smartcar/cmd_drive/autonomous
                                                               ↓
joy_node → joy_teleop_node → /smartcar/cmd_drive/manual → command_mux_node
                                                               ↓
                                                    /smartcar/cmd_drive
                                                               ↓
                                                     vehicle_driver_node
```

相比历史版本，超车、停车等动作不再通过 `time.sleep()` 阻塞整个控制循环，而是由
`TimedManeuverExecutor` 按时间状态非阻塞执行；自动驾驶/手动控制由 `command_mux_node`
仲裁，并在命令超时后自动回到中位值。详细设计见
[`docs/ros1_architecture.md`](docs/ros1_architecture.md)。

### ROS1 依赖

推荐 Ubuntu 20.04 + ROS Noetic：

```bash
sudo apt install \
  ros-noetic-ros-base \
  ros-noetic-cv-bridge \
  ros-noetic-message-filters \
  ros-noetic-std-srvs \
  ros-noetic-joy \
  ros-noetic-rostest \
  python3-catkin-tools
```

目标车机仍需另外安装与原硬件匹配的 Paddle Lite、Paddle Mobile、`v4l2capture`
以及比赛平台 `libart_driver.so`。

### Catkin 构建

```bash
mkdir -p ~/catkin_ws/src
cd ~/catkin_ws/src
ln -s /path/to/smartcar-autonomous-driving smartcar_autonomous_driving
cd ..
catkin_make
source devel/setup.bash
```

或使用 `catkin build`。

### ROS1 启动

先用不连接实车的 dry-run 模式：

```bash
roslaunch smartcar_autonomous_driving autonomous.launch dry_run:=true
```

由于历史压缩包没有包含两个 Paddle 模型，完整自动驾驶启动前仍需将权重放入
`models/` 对应目录。若只想检查 ROS 控制链，不加载摄像头和模型：

```bash
roslaunch smartcar_autonomous_driving logic_only.launch
```

手柄控制并启用 ROS 数据采集节点：

```bash
roslaunch smartcar_autonomous_driving manual.launch dry_run:=true
rosservice call /smartcar/data_recorder/set_recording "data: true"
# 停止记录
rosservice call /smartcar/data_recorder/set_recording "data: false"
```

记录内容仍为 `images/*.jpg + labels.csv`，但现在图像和最终底盘命令通过
`message_filters` 做近似时间同步。

模式也可以运行时切换：

```bash
rostopic pub -1 /smartcar/control_mode std_msgs/String "data: 'manual'"
rostopic pub -1 /smartcar/control_mode std_msgs/String "data: 'autonomous'"
```

### ROS 测试

纯 Python 测试：

```bash
pytest -q
```

ROS 环境中构建后还可以运行：

```bash
rostest smartcar_autonomous_driving behavior_ros.test
```

该 ROS 集成测试会通过 Topic 发送转向和限速检测消息，并检查
`/smartcar/cmd_drive/autonomous` 是否正确从巡航速度切换到限速速度，再恢复巡航。
当前整理环境的实际验证记录见 [`docs/validation.md`](docs/validation.md)。

## License

历史代码中包含 PaddlePaddle 相关片段，但当前上传内容无法确定整个项目当年的统一许可证与全部第三方授权来源。因此本整理版**暂不替你指定开源许可证**。正式公开前，建议确认比赛 SDK、模型权重和第三方代码的授权，再选择 MIT / Apache-2.0 等合适许可证。
