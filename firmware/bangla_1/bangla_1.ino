#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <ArduinoJson.h>
#include "secrets.h"   // WIFI_SSID, WIFI_PASSWORD, MQTT_SERVER (not committed to git)

// ====== Display settings ======
#define USE_SH1106 1        // 0 = SSD1306, 1 = SH1106 (1.3 inch screens)
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64    // use 32 for thin screens
// ==============================

#if USE_SH1106
  #include <Adafruit_SH110X.h>
  Adafruit_SH1106G display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
  #define COLOR_ON SH110X_WHITE
#else
  #include <Adafruit_SSD1306.h>
  Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
  #define COLOR_ON SSD1306_WHITE
#endif

const char* ssid = WIFI_SSID;
const char* password = WIFI_PASSWORD;
const char* mqtt_server = MQTT_SERVER;

#define LED_PIN 25
#define BUTTON_PIN 4

WiFiClient espClient;
PubSubClient client(espClient);

bool lastButtonState = HIGH;

bool oledBegin() {
#if USE_SH1106
  return display.begin(0x3C, true);
#else
  return display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
#endif
}

void showText(const char* line1, const char* line2 = "") {
  display.clearDisplay();
  display.setTextColor(COLOR_ON);
  display.setTextSize(2);
  display.setCursor(0, 0);
  display.println(line1);
  display.setCursor(0, 24);
  display.println(line2);
  display.display();
}

void setup_wifi() {
  delay(10);
  Serial.print("Connecting to WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" Connected!");
  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());
}

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived on topic: ");
  Serial.println(topic);

  StaticJsonDocument<200> doc;
  DeserializationError error = deserializeJson(doc, payload, length);
  if (error) {
    Serial.println("JSON Parse Error!");
    showText("JSON", "ERROR");
    return;
  }

  int idx = doc["idx"];
  bool ok = doc["ok"];
  Serial.print("Parsed ID: "); Serial.println(idx);
  Serial.print("ok = "); Serial.println(ok);

  char idLine[20];
  snprintf(idLine, sizeof(idLine), "id=%d", idx);

  if (ok) {
    digitalWrite(LED_PIN, HIGH);
    if (idx == 11)      showText("KA", idLine);
    else if (idx == 12) showText("KHA", idLine);
    else                showText("UNKNOWN", idLine);
    delay(1500);               // keep LED on briefly
    digitalWrite(LED_PIN, LOW);
  } else {
    showText("RETAKE!", idLine);
  }
  Serial.println("display() called");
}

void setup() {
  Serial.begin(115200);

  pinMode(LED_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  digitalWrite(LED_PIN, LOW);

  Wire.begin(21, 22);

  if (!oledBegin()) {
    Serial.println("OLED Failed");
    for (;;);
  }
  Serial.println("OLED begin OK");

  // Boot test
  display.clearDisplay();
  display.drawRect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_ON);
  display.setTextColor(COLOR_ON);
  display.setTextSize(2);
  display.setCursor(10, 10);
  display.println("OLED OK");
  display.display();
  delay(2000);

  showText("WiFi...", "");
  setup_wifi();
  showText("WiFi OK", "MQTT...");

  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (client.connect("ESP32_Device")) {
      Serial.println("connected");
      client.subscribe("bangla/result");
      showText("READY", "waiting");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      showText("MQTT fail", "retry...");
      delay(5000);
    }
  }
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  bool currentButtonState = digitalRead(BUTTON_PIN);
  if (lastButtonState == HIGH && currentButtonState == LOW) {
    client.publish("bangla/capture", "click");
    Serial.println("Button Clicked! Sent MQTT msg.");
    delay(200);
  }
  lastButtonState = currentButtonState;
}
