#include <Arduino.h>

#include "config.h"

static const int SERVO_CHANNEL = 0;
static const int SERVO_BITS = 16;
static const uint32_t SERVO_PERIOD_US = 20000;

static int angle = SWEEP_MIN_DEG;
static int direction = 1;
static uint32_t lastStepMs = 0;

static uint32_t angleToDuty(int deg) {
  const uint32_t us =
      SERVO_MIN_US + (uint32_t)(SERVO_MAX_US - SERVO_MIN_US) * deg / 180;
  return (uint32_t)((uint64_t)us * ((1u << SERVO_BITS) - 1) / SERVO_PERIOD_US);
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.printf("servo-test: MG996R sweep on GPIO%d (%d-%d us)\n", SERVO_PIN,
                SERVO_MIN_US, SERVO_MAX_US);

  ledcSetup(SERVO_CHANNEL, 50, SERVO_BITS);
  ledcAttachPin(SERVO_PIN, SERVO_CHANNEL);
  ledcWrite(SERVO_CHANNEL, angleToDuty(angle));

  lastStepMs = millis();
}

void loop() {
  const uint32_t now = millis();
  if (now - lastStepMs < SWEEP_STEP_MS) {
    return;
  }
  lastStepMs = now;

  angle += direction;
  if (angle >= SWEEP_MAX_DEG) {
    angle = SWEEP_MAX_DEG;
    direction = -1;
  } else if (angle <= SWEEP_MIN_DEG) {
    angle = SWEEP_MIN_DEG;
    direction = 1;
  }

  ledcWrite(SERVO_CHANNEL, angleToDuty(angle));

  if (angle % 15 == 0) {
    Serial.printf("angle=%d\n", angle);
  }
}
