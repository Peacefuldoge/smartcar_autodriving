#define FORWARD 0x09
#define BACKWARD 0x06
#define STOP 0x00
#define PWM_FROM_PERCENT(x) ((unsigned int)((x) * 2.55))

const int MOTOR_PINS[6] = {22, 23, 24, 25, 4, 5};
const int COMMAND_BAUD = 38400;
const int DEBUG_BAUD = 115200;
const int NEUTRAL = 1500;
const int MIN_THROTTLE = 1400;
const int MAX_THROTTLE = 1600;
const unsigned long COMMAND_TIMEOUT_MS = 300;

// The original firmware reconstructed 16-bit fields with a base of 255 rather
// than the conventional 256. Keep this value for compatibility with the
// competition-provided libart_driver.so. Verify both sides before changing it.
const int PROTOCOL_BYTE_BASE = 255;

unsigned char recv_buffer[7] = {0};
unsigned char byte_in = 0;
int recv_count = 0;
unsigned long last_command_ms = 0;

void setMotorMode(int mode);
void setMotorSpeed(int left, int right);

void setup() {
  for (int i = 0; i < 6; ++i) {
    pinMode(MOTOR_PINS[i], OUTPUT);
    digitalWrite(MOTOR_PINS[i], LOW);
  }
  setMotorMode(FORWARD);
  Serial3.begin(COMMAND_BAUD);
  Serial2.begin(DEBUG_BAUD);
}

void loop() {
  if (millis() - last_command_ms > COMMAND_TIMEOUT_MS) {
    setMotorSpeed(0, 0);
  }

  if (Serial3.available() <= 0) {
    return;
  }

  byte_in = Serial3.read();
  if (byte_in == 0xAA) {
    memset(recv_buffer, 0, sizeof(recv_buffer));
    recv_count = 1;
    return;
  }

  if (recv_count > 0 && recv_count < 6) {
    recv_buffer[recv_count++] = byte_in;
  }

  if (recv_count != 6) {
    return;
  }

  recv_count = 0;
  last_command_ms = millis();
  long throttle = (unsigned int)recv_buffer[1] + (unsigned int)recv_buffer[2] * PROTOCOL_BYTE_BASE;
  long steering = (unsigned int)recv_buffer[3] + (unsigned int)recv_buffer[4] * PROTOCOL_BYTE_BASE;

  throttle = constrain(throttle, MIN_THROTTLE, MAX_THROTTLE);
  const long throttle_delta = throttle - NEUTRAL;
  const long steering_delta = steering - NEUTRAL;

  if (throttle_delta == 0) {
    setMotorSpeed(0, 0);
  } else {
    setMotorSpeed(
      throttle_delta - steering_delta * 0.2,
      throttle_delta + steering_delta * 0.2
    );
  }
}

void setMotorSpeed(int left, int right) {
  left = constrain(left, -100, 100);
  right = constrain(right, -100, 100);

  digitalWrite(MOTOR_PINS[0], left >= 0 ? HIGH : LOW);
  digitalWrite(MOTOR_PINS[1], left >= 0 ? LOW : HIGH);
  digitalWrite(MOTOR_PINS[2], right >= 0 ? LOW : HIGH);
  digitalWrite(MOTOR_PINS[3], right >= 0 ? HIGH : LOW);

  analogWrite(MOTOR_PINS[4], PWM_FROM_PERCENT(abs(left)));
  analogWrite(MOTOR_PINS[5], PWM_FROM_PERCENT(abs(right)));
}

void setMotorMode(int mode) {
  for (int i = 0; i < 4; ++i) {
    digitalWrite(MOTOR_PINS[i], (mode >> i) & 0x01);
  }
}
