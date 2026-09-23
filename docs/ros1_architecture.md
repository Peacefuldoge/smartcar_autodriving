# ROS1 architecture

The ROS layer intentionally wraps the refactored `smartcar` Python core instead of moving
model/control logic into callbacks.  This keeps the algorithms independently testable and
allows both the historical stand-alone CLI and ROS1 front-end to coexist.

## Nodes and topics

```text
                         /smartcar/camera/image_raw (sensor_msgs/Image)
                                      │
                 ┌────────────────────┴────────────────────┐
                 │                                         │
        lane_following_node                      object_detection_node
                 │                                         │
 /smartcar/lane/steering (Int32)      /smartcar/detector/detections
                 │                            (DetectionArray)
                 └────────────────────┬────────────────────┘
                                      │
                               behavior_node
                                      │
                   /smartcar/cmd_drive/autonomous
                                      │
                                      ├──────────────┐
                                      │              │
 /smartcar/joy -> joy_teleop_node -> /smartcar/cmd_drive/manual
                                      │              │
                                      └──────┬───────┘
                                             │
                                      command_mux_node
                                             │
                               /smartcar/cmd_drive
                                             │
                                      vehicle_driver_node
                                             │
                              libart_driver.so / serial MCU

         camera/image_raw + cmd_drive -> data_recorder_node -> images + labels.csv
```

`/smartcar/control_mode` (`std_msgs/String`) selects `autonomous` or `manual` in the mux.
Both the mux and hardware driver contain command timeouts.  If the selected source stops
publishing, the output becomes neutral instead of holding the last throttle value.

## Why maneuvers are non-blocking

The historical overtaking/stop sequences used `time.sleep()`.  Blocking inside a ROS
callback would prevent timely message handling.  `TimedManeuverExecutor` therefore turns
the same sequence into a monotonic-time state machine.  A timer publishes the currently
active step while ROS continues processing subscriptions and shutdown events.

## Custom messages

- `DriveCommand.msg`: header + throttle + steering.
- `Detection.msg`: class id, confidence and normalized/absolute bounding-box fields as
  produced by the historical Paddle Mobile model.
- `DetectionArray.msg`: timestamped list of detections.

## Safety layers

1. `command_mux_node`: selected source must remain fresh (`command_timeout`, default 0.3 s).
2. `vehicle_driver_node`: if final commands disappear (`watchdog_timeout`, default 0.3 s),
   a neutral command is sent.
3. The microcontroller firmware retains its own serial watchdog from the previous refactor.

This deliberately gives the project an independent fail-safe at each control boundary.

## ROS data collection

`data_recorder_node` synchronizes `camera/image_raw` and the **final** `cmd_drive` message
with `message_filters.ApproximateTimeSynchronizer`. Recording is toggled with:

```bash
rosservice call /smartcar/data_recorder/set_recording "data: true"
rosservice call /smartcar/data_recorder/set_recording "data: false"
```

This replaces the old monolithic joystick/camera/serial collection loop while preserving the
same image + steering-label workflow.
