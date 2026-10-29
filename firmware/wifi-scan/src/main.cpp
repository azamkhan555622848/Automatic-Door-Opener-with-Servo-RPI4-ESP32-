#include <Arduino.h>
#include <WiFi.h>

static const char *authName(wifi_auth_mode_t m) {
  switch (m) {
    case WIFI_AUTH_OPEN: return "OPEN";
    case WIFI_AUTH_WEP: return "WEP";
    case WIFI_AUTH_WPA_PSK: return "WPA";
    case WIFI_AUTH_WPA2_PSK: return "WPA2";
    case WIFI_AUTH_WPA_WPA2_PSK: return "WPA/WPA2";
    case WIFI_AUTH_WPA2_ENTERPRISE: return "WPA2-ENT";
    default: return "?";
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println("wifi-scan: 2.4 GHz only");
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(200);
}

void loop() {
  Serial.println("scan...");
  const int n = WiFi.scanNetworks(false, true);
  Serial.printf("found %d\n", n);
  for (int i = 0; i < n; i++) {
    Serial.printf("%2d  ch=%2d  rssi=%4d  %-9s  %s\n", i + 1,
                  WiFi.channel(i), WiFi.RSSI(i),
                  authName(WiFi.encryptionType(i)),
                  WiFi.SSID(i).c_str());
  }
  Serial.println("---");
  delay(5000);
}
