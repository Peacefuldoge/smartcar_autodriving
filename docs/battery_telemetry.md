# Battery voltage telemetry

The lower-controller firmware now keeps the original motor command channel on `Serial3 @ 38400` and uses `Serial2 @ 9600` as a dedicated battery telemetry channel.

Every 500 ms it sends one ASCII line:

```text
VOLTAGE:12.34
```

`battery_node.py` accepts this format as well as `VBAT=12.34`, `V=12.34` or a bare `12.34V` line.

## ADC / divider calibration

The example firmware assumes an Arduino-Mega-like 5 V ADC and a 3:1 resistor divider:

```cpp
const float ADC_REFERENCE_V = 5.0f;
const float BATTERY_DIVIDER_RATIO = 3.0f;
```

Do **not** treat these values as universal. Measure the real battery with a multimeter and adjust `ADC_REFERENCE_V` / `BATTERY_DIVIDER_RATIO` so the serial value matches the measured voltage. Also verify the maximum divided voltage never exceeds the MCU ADC input limit.

For a real RS-232 electrical interface, MCU UART pins need a proper level shifter/transceiver such as a MAX3232. A USB-TTL adapter is not electrically the same thing as true RS-232.

The default ROS thresholds (`10.0 / 10.8 / 11.2 / 12.6 V`) are only an example consistent with a common 3-cell Li-ion/LiPo pack. Change them to match the chemistry, cell count, load sag and safe cutoff of the actual vehicle battery.
