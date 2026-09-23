# UDP host protocol

Cross-machine communication does not rely on a multi-host ROS master. Each vehicle runs its own local ROS graph and communicates with the fleet host using UDP JSON datagrams.

Default ports:

- host coordinator: UDP `51000`;
- `car_1`: UDP `52001`;
- `car_2`: UDP `52002`;
- `car_3`: UDP `52003`.

A packet contains `v`, `type`, `vehicle_id`, `ts`, the message payload and, when a shared secret is configured, an HMAC-SHA256 `auth` field.

Main packet types:

| Type | Direction | Purpose |
|---|---|---|
| `vehicle_status` | car -> host | GPS, voltage, percentage, low flag, mission state and task ID |
| `vehicle_event` | car -> host | task completion, low-battery abort, rejection, etc. |
| `task_request` | client -> host | enqueue a delivery job |
| `task_assignment` | host -> car | assign pickup/drop-off/recipient information |
| `task_ack` | car -> host | acknowledge assignment receipt |

Because UDP itself is unreliable, `task_assignment` is idempotent by `task_id`. The host retries an assignment until it receives either `task_ack` or a heartbeat that already reports the assigned task ID. After the configured retry limit the task is put back into the queue.

For a real network set the same non-empty `shared_secret` in `config/fleet_host.json` and `config/ros1.yaml`. HMAC provides packet authentication/integrity but does **not** encrypt location or identity data; use a trusted LAN/VPN if confidentiality matters.
