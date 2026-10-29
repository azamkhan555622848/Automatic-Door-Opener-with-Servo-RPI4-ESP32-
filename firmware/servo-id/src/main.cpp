#include <Arduino.h>

static const int PIN = 18;
static const int CH = 0;

static void pulse(uint32_t us, const char *label, uint32_t ms) {
  const uint32_t duty = (uint32_t)((uint64_t)us * 65535 / 20000);
  ledcWrite(CH, duty);
  Serial.printf("STEP %s (%lu us) for %lu ms\n", label, us, ms);
  delay(ms);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println();
  Serial.println("servo-id: 50 Hz, 16-bit, GPIO18");
  ledcSetup(CH, 50, 16);
  ledcAttachPin(PIN, CH);
  ledcWrite(CH, (uint32_t)(1500ULL * 65535 / 20000));
  delay(1000);
}

void loop() {
  Serial.println("=== cycle ===");
  pulse(1500, "centre", 6000);
  pulse(1600, "slight +", 6000);
  pulse(1500, "centre", 4000);
  pulse(1400, "slight -", 6000);
  pulse(1500, "centre", 4000);
  pulse(2000, "full +", 6000);
  pulse(1500, "centre", 4000);
  pulse(1000, "full -", 6000);
  pulse(1500, "centre", 4000);
}
