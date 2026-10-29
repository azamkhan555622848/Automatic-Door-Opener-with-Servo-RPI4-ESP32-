#pragma once

#define SERVO_PIN 18
#define SERVO_MIN_US 1000
#define SERVO_MAX_US 2000

// 1 = USB/serial link (Pi <-> ESP32 cable), 0 = Wi-Fi TCP link
#define LINK_SERIAL 1

#define SERVO_STOP_US 1500
// offset from stop (us) while moving: bigger = faster = more degrees per MOVE_MS
#define SERVO_SPEED_US 300
#define SERVO_OPEN_US (SERVO_STOP_US + SERVO_SPEED_US)
#define SERVO_CLOSE_US (SERVO_STOP_US - SERVO_SPEED_US)
#define MOVE_MS 2739
// pause at the far end before turning back to zero
#define RETURN_PAUSE_MS 3000

#define PI_HOST "doorlock-pi.local"
#define PI_FALLBACK_IP "192.168.50.140"
#define PI_PORT 5000

#define LINK_TIMEOUT_MS 30000
#define WIFI_TIMEOUT_MS 20000
#define BACKOFF_MIN_MS 1000
#define BACKOFF_MAX_MS 15000
