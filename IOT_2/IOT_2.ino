#include <HardwareSerial.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// =========================================================
// CẤU HÌNH WIFI VÀ MQTT
// =========================================================
const char* WIFI_SSID     = "NONNET";
const char* WIFI_PASSWORD = "abcd1234";

const char* HIVEMQ_SERVER = "broker.hivemq.com";
const int   HIVEMQ_PORT   = 1883;

WiFiClient   espClient;
PubSubClient mqttClient(espClient);

// LCD I2C
LiquidCrystal_I2C lcd(0x27, 16, 2);

// UART2 giao tiếp với IOT_1
#define UART2_TX 17
#define UART2_RX 16

// =========================================================
// BIẾN THỜI GIAN CHỜ (TIMERS)
// =========================================================
unsigned long carInDetectedTime = 0;
bool isWaitingToCapture = false;

unsigned long carOutDetectedTime = 0;
bool isWaitingToClose = false;

// =========================================================
// HÀM HIỂN THỊ LCD
// =========================================================
void printLCD(String line1, String line2) {
  lcd.clear();
  lcd.setCursor(0, 0); lcd.print(line1);
  lcd.setCursor(0, 1); lcd.print(line2);
  Serial.println(">> LCD: [" + line1 + "] | [" + line2 + "]");
}

// =========================================================
// KẾT NỐI WIFI VÀ MQTT
// =========================================================
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  printLCD("Dang ket noi", "WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(500); }
  printLCD("WiFi OK", WiFi.localIP().toString());
  delay(1000);
}

void maintainMQTT() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  
  if (!mqttClient.connected()) {
    printLCD("Dang ket noi", "Đám Mây MQTT...");
    String clientId = "ESP32_Slave_VETC_" + String(random(0xffff), HEX);
    if (mqttClient.connect(clientId.c_str())) {
      printLCD("MQTT San sang!", "Cho xe vao tram");
      mqttClient.subscribe("iot_thanglong/gate"); // Lắng nghe lệnh mở cổng từ Node.js
      mqttClient.subscribe("iot_thanglong/plate"); // (Optional) Nhận kết quả biển số nếu cần
    } else {
      delay(2000);
    }
  }
  mqttClient.loop();
}

// =========================================================
// XỬ LÝ LỆNH TỪ MÁY CHỦ (NODE.JS / PYTHON) TRẢ VỀ
// =========================================================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  StaticJsonDocument<256> doc;
  DeserializationError error = deserializeJson(doc, payload, length);
  if (error) return;

  if (strcmp(topic, "iot_thanglong/gate") == 0) {
    const char* action = doc["action"]; // "OPEN" hoặc "DENY"
    const char* plate = doc["plate"];
    
    if (action && strcmp(action, "OPEN") == 0) {
      printLCD("Xe: " + String(plate), "-> MO CONG (OK)");
      Serial2.println("OPEN"); // Ra lệnh cho Mạch 1 mở cổng
    } else if (action && strcmp(action, "DENY") == 0) {
      printLCD("Xe: " + String(plate), "-> TU CHOI/HET $");
      // Không mở cổng
    }
  }
}

// =========================================================
// SETUP
// =========================================================
void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, 16, 17); // Đảm bảo RX/TX chéo với Mạch 1
  
  lcd.init();
  lcd.backlight();
  printLCD("Khoi dong", "VETC Slave...");

  mqttClient.setServer(HIVEMQ_SERVER, HIVEMQ_PORT);
  mqttClient.setCallback(mqttCallback);
}

// =========================================================
// LOOP
// =========================================================
void loop() {
  maintainMQTT();

  // 1. NHẬN SỰ KIỆN TỪ MẠCH 1 (CẢM BIẾN/SERVO HUB)
  if (Serial2.available()) {
    String msg = Serial2.readStringUntil('\n');
    msg.trim();
    
    if (msg == "CAR_IN") {
      printLCD("Phat hien xe!", "Cho 5s chup...");
      carInDetectedTime = millis();
      isWaitingToCapture = true;
    } 
    else if (msg == "CAR_OUT") {
      printLCD("Xe da di qua!", "Cho 3s dong...");
      carOutDetectedTime = millis();
      isWaitingToClose = true;
    }
    else if (msg.startsWith("DIST:")) {
      // Nhận dữ liệu cảm biến: DIST:15.2,20.5
      String data = msg.substring(5);
      int commaIndex = data.indexOf(',');
      if (commaIndex > 0) {
        String d1 = data.substring(0, commaIndex);
        String d2 = data.substring(commaIndex + 1);
        
        Serial.println(">> [LIVE] CB1: " + d1 + "cm | CB2: " + d2 + "cm");
        
        // Nếu không có sự kiện gì đang chờ, hiển thị lên LCD cho trực quan
        if (!isWaitingToCapture && !isWaitingToClose) {
          lcd.setCursor(0, 1);
          lcd.print("T1:" + String(d1.toInt()) + "cm T2:" + String(d2.toInt()) + "cm  ");
        }
      }
    }
  }

  // 2. XỬ LÝ THỜI GIAN CHỜ CHỤP ẢNH (5 GIÂY)
  if (isWaitingToCapture && (millis() - carInDetectedTime >= 5000)) {
    isWaitingToCapture = false;
    printLCD("Dang chup anh...", "Gui len Python");
    
    // Đánh thức Python chụp ảnh
    if (mqttClient.connected()) {
      mqttClient.publish("iot_thanglong/trigger", "{\"action\":\"capture\"}");
    }
  }

  // 3. XỬ LÝ THỜI GIAN CHỜ ĐÓNG CỔNG (3 GIÂY)
  if (isWaitingToClose && (millis() - carOutDetectedTime >= 3000)) {
    isWaitingToClose = false;
    printLCD("Đong cong...", "He thong SS");
    
    // Ra lệnh cho Mạch 1 đóng cổng
    Serial2.println("CLOSE");
  }
}
