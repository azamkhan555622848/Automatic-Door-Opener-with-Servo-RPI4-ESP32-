#include <Arduino.h>

#include "config.h"

#if !LINK_SERIAL
#include <ESPmDNS.h>
#include <WiFi.h>
#include <WiFiClient.h>

#include "secrets.h"
#endif

static const int SERVO_CHANNEL = 0;
static const int SERVO_BITS = 16;
static const uint32_t SERVO_PERIOD_US = 20000;

static char rxbuf[96];
static size_t rxlen = 0;

static uint32_t lastRxMs = 0;
static bool linkReady = false;

#if !LINK_SERIAL
static WiFiClient client;
static uint32_t lastAttemptMs = 0;
static uint32_t backoffMs = BACKOFF_MIN_MS;
static uint8_t connFails = 0;
#endif

enum Phase { PH_IDLE, PH_OUT, PH_PAUSE, PH_BACK, PH_HOME };
static Phase phase = PH_IDLE;
static uint32_t phaseUntil = 0;
static int8_t phaseDir = 1;
static int8_t pendingDir = 0;
static uint32_t moveMs = MOVE_MS;
static uint32_t speedUs = SERVO_SPEED_US;
static uint32_t pauseMs = RETURN_PAUSE_MS;

static void servoUs(uint32_t us) {
  ledcWrite(SERVO_CHANNEL, (uint32_t)((uint64_t)us * ((1u << SERVO_BITS) - 1) / SERVO_PERIOD_US));
}

static void startCycle(int8_t dir) {
  if (phase != PH_IDLE) {
    pendingDir = dir;
    Serial.println("busy, queued");
    return;
  }
  phaseDir = dir;
  phase = PH_OUT;
  phaseUntil = millis() + moveMs;
  servoUs(dir > 0 ? SERVO_STOP_US + speedUs : SERVO_STOP_US - speedUs);
  Serial.printf("turn %s: %lu ms out, then back\n", dir > 0 ? "unlock" : "lock", (unsigned long)moveMs);
}

static void tickServo() {
  if (phase == PH_IDLE || (int32_t)(millis() - phaseUntil) < 0) {
    return;
  }
  switch (phase) {
    case PH_OUT:
      servoUs(SERVO_STOP_US);
      phase = PH_PAUSE;
      phaseUntil = millis() + pauseMs;
      Serial.println("out");
      break;
    case PH_PAUSE:
      servoUs(phaseDir > 0 ? SERVO_STOP_US - speedUs : SERVO_STOP_US + speedUs);
      phase = PH_BACK;
      phaseUntil = millis() + moveMs;
      Serial.println("returning");
      break;
    case PH_BACK:
      servoUs(SERVO_STOP_US);
      phase = PH_IDLE;
      Serial.println("at zero");
      if (pendingDir) {
        const int8_t d = pendingDir;
        pendingDir = 0;
        startCycle(d);
      }
      break;
    case PH_HOME:
      servoUs(SERVO_STOP_US);
      phase = PH_IDLE;
      Serial.println("homed");
      break;
    default:
      break;
  }
}

static void requestUnlock() { startCycle(1); }

static void requestLock() { startCycle(-1); }

static void handleLine(const char *line) {
  lastRxMs = millis();
  linkReady = true;

  if (strcmp(line, "PERSON 1") == 0) {
    requestUnlock();
  } else if (strcmp(line, "PERSON 0") == 0) {
    // person left: no motion, the arm is already back at zero
    Serial.println("person cleared");
  } else if (strcmp(line, "PING") == 0) {
    Serial.printf("PONG %lu", (unsigned long)millis());
    Serial.println();
    Serial.printf("STATUS phase=%d move_ms=%lu speed_us=%lu", (int)phase, (unsigned long)moveMs, (unsigned long)speedUs);
    Serial.println();
  } else if (strncmp(line, "MOVE ", 5) == 0) {
    const long v = atol(line + 5);
    if (v >= 50 && v <= 5000) {
      moveMs = (uint32_t)v;
      Serial.printf("move_ms=%lu\n", (unsigned long)moveMs);
    } else {
      Serial.println("move_ms: out of range 50..5000");
    }
  } else if (strncmp(line, "SPEED ", 6) == 0) {
    const long v = atol(line + 6);
    if (v >= 50 && v <= 500) {
      speedUs = (uint32_t)v;
      Serial.printf("speed_us=%lu\n", (unsigned long)speedUs);
    } else {
      Serial.println("speed_us: out of range 50..500");
    }
  } else if (strncmp(line, "PAUSE ", 6) == 0) {
    const long v = atol(line + 6);
    if (v >= 0 && v <= 20000) {
      pauseMs = (uint32_t)v;
      Serial.printf("pause_ms=%lu", (unsigned long)pauseMs);
      Serial.println();
    } else {
      Serial.println("pause_ms: out of range 0..20000");
    }
  } else if (strncmp(line, "HOME", 4) == 0) {
    // drive into the lock-side end stop, then treat that as zero
    const long v = atol(line + 4);
    const uint32_t t = (v >= 100 && v <= 10000) ? (uint32_t)v : 3000;
    if (phase == PH_IDLE) {
      phase = PH_HOME;
      phaseUntil = millis() + t;
      servoUs(SERVO_STOP_US - speedUs);
      Serial.printf("homing: %lu ms to lock stop\n", (unsigned long)t);
    }
  } else if (strcmp(line, "ZERO") == 0) {
    phase = PH_IDLE;
    servoUs(SERVO_STOP_US);
    Serial.println("zero: stopped");
  } else {
    Serial.printf("rx: %s\n", line);
  }
}

static void feedRx(char c) {
  if (c == '\n') {
    rxbuf[rxlen] = '\0';
    if (rxlen > 0 && rxbuf[rxlen - 1] == '\r') {
      rxbuf[rxlen - 1] = '\0';
    }
    if (rxlen > 0) {
      handleLine(rxbuf);
    }
    rxlen = 0;
  } else if (rxlen < sizeof(rxbuf) - 1) {
    rxbuf[rxlen++] = c;
  } else {
    rxlen = 0;
  }
}

#if LINK_SERIAL

static void pollSerial() {
  while (Serial.available()) {
    feedRx((char)Serial.read());
  }
}

#else

static bool connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  const uint32_t start = millis();
  uint32_t lastPrint = 0;
  while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_TIMEOUT_MS) {
    delay(200);
    if (millis() - lastPrint > 2000) {
      lastPrint = millis();
      Serial.printf("[wifi status=%d rssi=%d]\n", (int)WiFi.status(), WiFi.RSSI());
    }
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("wifi: connect timeout");
    return false;
  }
  Serial.print("wifi: connected, ip=");
  Serial.println(WiFi.localIP());
  return true;
}

static IPAddress resolvePi() {
  IPAddress ip;
  if (MDNS.begin("lock1")) {
    ip = MDNS.queryHost(PI_HOST, 2000);
  }
  if (ip == IPAddress(0, 0, 0, 0)) {
    if (!ip.fromString(PI_FALLBACK_IP)) {
      Serial.println("resolve: fallback IP invalid");
      return ip;
    }
    Serial.printf("resolve: mDNS failed, using %s\n", PI_FALLBACK_IP);
  } else {
    Serial.printf("resolve: %s -> %s\n", PI_HOST, ip.toString().c_str());
  }
  return ip;
}

static bool connectPi() {
  if (!connectWifi()) {
    return false;
  }

  const IPAddress ip = resolvePi();
  if (ip == IPAddress(0, 0, 0, 0)) {
    return false;
  }

  client.setTimeout(2000);
  if (!client.connect(ip, PI_PORT)) {
    Serial.printf("tcp: connect to %s:%d failed\n", ip.toString().c_str(), PI_PORT);
    return false;
  }

  client.print("HELLO lock1\n");
  rxlen = 0;
  lastRxMs = millis();
  linkReady = true;
  backoffMs = BACKOFF_MIN_MS;
  connFails = 0;
  servoUs(SERVO_STOP_US);
  Serial.println("tcp: connected, sent HELLO");
  return true;
}

static void pollClient() {
  while (client.available()) {
    feedRx((char)client.read());
  }
}

#endif

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
#if LINK_SERIAL
  Serial.println("lock-node: serial link servo");
#else
  Serial.println("lock-node: wifi tcp servo");
#endif

  ledcSetup(SERVO_CHANNEL, 50, SERVO_BITS);
  ledcAttachPin(SERVO_PIN, SERVO_CHANNEL);
  servoUs(SERVO_STOP_US);

#if LINK_SERIAL
  Serial.println("HELLO lock1");
  lastRxMs = millis();
  linkReady = true;
#else
  connectPi();
#endif
}

void loop() {
  tickServo();

#if LINK_SERIAL
  pollSerial();
  if (linkReady && millis() - lastRxMs > LINK_TIMEOUT_MS) {
    Serial.println("link timeout, stopping");
    linkReady = false;
    phase = PH_IDLE;
    servoUs(SERVO_STOP_US);
  }
  delay(10);
#else
  if (WiFi.status() != WL_CONNECTED) {
    if (client.connected()) {
      client.stop();
    }
    linkReady = false;
    requestLock();
    if (millis() - lastAttemptMs > backoffMs) {
      lastAttemptMs = millis();
      connectWifi();
    }
    return;
  }

  if (!client.connected()) {
    linkReady = false;
    requestLock();
    if (millis() - lastAttemptMs > backoffMs) {
      lastAttemptMs = millis();
      if (!connectPi()) {
        Serial.printf("retry in %lu ms\n", backoffMs);
        backoffMs = min(backoffMs * 2, (uint32_t)BACKOFF_MAX_MS);
        if (++connFails >= 2) {
          Serial.println("forcing wifi reconnect");
          connFails = 0;
          WiFi.disconnect(true);
          delay(200);
          WiFi.begin(WIFI_SSID, WIFI_PASS);
        }
      }
    }
    return;
  }

  pollClient();

  if (linkReady && millis() - lastRxMs > LINK_TIMEOUT_MS) {
    Serial.println("link timeout, locking");
    linkReady = false;
    requestLock();
    client.stop();
    lastAttemptMs = millis();
    return;
  }

  delay(10);
#endif
}