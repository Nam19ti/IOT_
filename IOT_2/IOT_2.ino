#include <HardwareSerial.h>
#include <WiFi.h>
#include <PubSubClient.h>

// =========================================================
// CẤU HÌNH WIFI VÀ MQTT (HIVEMQ)
// =========================================================
const char* WIFI_SSID     = "NONNET";
const char* WIFI_PASSWORD = "abcd1234";

// Dùng Broker công cộng miễn phí siêu nhanh
const char* MQTT_SERVER   = "broker.hivemq.com";
const int   MQTT_PORT     = 1883;

WiFiClient   espClient;
PubSubClient mqttClient(espClient);

unsigned long lastMqttAttempt = 0;
const unsigned long MQTT_RETRY_MS = 5000;

// =========================================================
// BUFFER UART
// =========================================================
#define LINE_BUF_SIZE 128
char lineBuf[LINE_BUF_SIZE];
int  linePos = 0;

// =========================================================
// KẾT NỐI WIFI
// =========================================================
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.print(">> WiFi: Dang ket noi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 10000) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(" OK! IP: " + WiFi.localIP().toString());
  } else {
    Serial.println(" THAT BAI.");
  }
}

// =========================================================
// DUY TRÌ MQTT
// =========================================================
void maintainMQTT() {
  if (mqttClient.connected()) {
    mqttClient.loop();
    return;
  }
  if (WiFi.status() != WL_CONNECTED) return;
  if (millis() - lastMqttAttempt < MQTT_RETRY_MS) return;
  lastMqttAttempt = millis();

  espClient.setTimeout(3000);
  Serial.print(">> MQTT: Ket noi " + String(MQTT_SERVER) + "...");
  
  // Tạo Client ID ngẫu nhiên để không trùng lặp trên HiveMQ
  String clientId = "ESP32_Slave_" + String(random(0xffff), HEX);
  
  if (mqttClient.connect(clientId.c_str())) {
    Serial.println(" THANH CONG!");
  } else {
    Serial.println(" THAT BAI!");
  }
}

// =========================================================
// XỬ LÝ KHI NHẬN ĐƯỢC DỮ LIỆU TỪ UART MASTER
// =========================================================
void processLine(char* raw) {
  int len = strlen(raw);
  while (len > 0 && (raw[len-1] == '\r' || raw[len-1] == ' ')) raw[--len] = '\0';
  if (len == 0) return;

  String msg = String(raw);
  int distIdx = msg.indexOf("DIST:");
  int speedIdx = msg.indexOf("SPEED:");

  if (distIdx >= 0) {
    int i1 = msg.indexOf("CB1=", distIdx) + 4;
    int ic = msg.indexOf(",CB2=", distIdx);
    int i2 = ic + 5;
    if (i1 < 4 || ic < 0) return;
    Serial.println(">> [DIST] CB1=" + msg.substring(i1, ic) + "cm  CB2=" + msg.substring(i2) + "cm");

  } else if (speedIdx >= 0) {
    // "SPEED:25.3,DIR:Trai->Phai,ID:1"
    int iSpeed = speedIdx + 6;
    int iComma = msg.indexOf(",DIR:", speedIdx);
    int iDir   = iComma + 5;
    int iIdTag = msg.indexOf(",ID:", iDir);
    int iId    = iIdTag + 4;

    if (iComma < 0 || iIdTag < 0) return; 

    String speedStr = msg.substring(iSpeed, iComma);
    String dir      = msg.substring(iDir, iIdTag);
    String idStr    = msg.substring(iId);
    
    Serial.println(">> [TOC DO] " + speedStr + " km/h | " + dir + " | ID: " + idStr);

    if (mqttClient.connected()) {
      // 1. Publish tốc độ cho Python Server
      String payload = "{\"id\":\"" + idStr + "\",\"speed\":" + speedStr + ",\"direction\":\"" + dir + "\"}";
      mqttClient.publish("iot_thanglong/speed", payload.c_str());
      
      // 2. Publish lệnh chụp ảnh (Trigger) cho ESP32-CAM
      mqttClient.publish("iot_thanglong/trigger", idStr.c_str());
      
      Serial.println(">> Đã đẩy lệnh chụp ảnh (ID: " + idStr + ") lên HiveMQ siêu tốc!");
    } else {
      Serial.println(">> LỖI: Chưa kết nối MQTT, không thể ra lệnh chụp ảnh.");
    }
  }
}

// =========================================================
// SETUP
// =========================================================
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial2.begin(115200, SERIAL_8N1, 16, 17);

  connectWiFi();
  
  mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
  mqttClient.setKeepAlive(60);

  Serial.println(">> Slave (MQTT Router) da san sang. Lang nghe UART...");
}

// =========================================================
// LOOP
// =========================================================
void loop() {
  maintainMQTT();

  // ĐỌC UART
  int bytesReadThisLoop = 0;
  while (Serial2.available() && bytesReadThisLoop < 256) {
    char c = (char)Serial2.read();
    bytesReadThisLoop++;
    
    if (c == '\n') {
      lineBuf[linePos] = '\0';
      processLine(lineBuf);
      linePos = 0;
    } else if (c != '\r') {
      if (linePos < LINE_BUF_SIZE - 1) lineBuf[linePos++] = c;
      else linePos = 0; // Tràn -> Xóa rác
    }
  }
}
