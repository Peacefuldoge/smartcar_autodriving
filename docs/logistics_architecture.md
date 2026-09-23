# Logistics / Multi-vehicle architecture

## Vehicle-side ROS graph

```text
GPS receiver (NMEA serial) ──> gps_node ───────────────> /smartcar/gps/fix ──────┐
                                                                                │
Lower MCU voltage over RS-232 ─> battery_node ─> /smartcar/battery/* ───────────┤
                                                                                ↓
UDP host assignment ─> udp_vehicle_bridge_node ─> /smartcar/fleet/task ─> mission_manager_node
                                                                            │
                                 ┌──────────────────────────────────────────┤
                                 │                                          │
                                 ↓                                          ↓
                      gps_navigation_node                    face_recognition_node
                                 │                                          │
                    /smartcar/cmd_drive/mission               /smartcar/face/recognition
                                 │                                          │
                                 └──────────────> command_mux <──────────────┘
                                                     │
                                                     ↓
                                              vehicle_driver_node
```

The existing lane-following and object-detection pipeline remains intact. Mission navigation adds a GPS bearing correction on top of the current lane steering rather than replacing the visual lane controller.

## Low-battery behavior

1. `battery_node` parses voltage messages from the lower controller.
2. `BatteryMonitorCore` applies hysteresis so the low-battery state does not chatter around one threshold.
3. `mission_manager_node` aborts the active delivery and changes state to `RETURNING_HOME`.
4. The first valid GPS fix after startup is used as the start/home point unless a fixed home coordinate is configured.
5. `gps_navigation_node` generates `cmd_drive/mission` until the home arrival radius is reached.
6. The fleet host sees the vehicle as non-idle and will not dispatch new work to it. An aborted task is requeued for another vehicle.
7. After returning home and the battery voltage recovers past the recovery threshold, the vehicle returns to `IDLE`.

The current GPS controller is a waypoint/bearing guidance layer, **not** a global road planner or obstacle-avoidance system. Use it on a known/drivable course or replace it with a mapped planner for unrestricted outdoor navigation.

## Three-vehicle dispatch

The host maintains `car_1`, `car_2`, and `car_3` status from UDP heartbeats. A vehicle is dispatchable only when all of the following are true:

- heartbeat is fresh;
- mission state is `IDLE`;
- no current task is attached;
- battery is not low;
- battery percentage is above `min_dispatch_battery`.

Tasks are ordered by priority then FIFO time. Among currently idle/healthy vehicles, the scheduler chooses the one with the shortest GPS distance to the pickup point. Busy, returning-home, offline, or low-battery vehicles are skipped.

## Recipient verification

At the drop-off location the mission state changes to `VERIFY_RECIPIENT`. The FisherFaces node then becomes active and compares detected faces with the expected `recipient_id`. A task is completed only after the configured number of consecutive matching frames.

FisherFaces is intentionally kept because it was requested for this project, but it is a classical method and is sensitive to pose/illumination. It should be treated as a project/demo identity check rather than a high-security biometric system.
