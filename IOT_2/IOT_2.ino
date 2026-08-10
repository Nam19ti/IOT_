#include <HardwareSerial.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h> // Cần cài đặt thư viện ArduinoJson trong Library Manager

// =========================================================
// CẤU HÌNH WIFI VÀ MQTT
// =========================================================
const char* WIFI_SSID     = "NONNET";
const char* WIFI_PASSWORD = "abcd1234";

// 1. HiveMQ (Dùng để giao tiếp siêu tốc với Python)
const char* HIVEMQ_SERVER = "broker.hivemq.com";
const int   HIVEMQ_PORT   = 1883;

// 2. ThingsBoard (Dùng để báo cáo lên Đám mây)
const char* TB_SERVER     = "mqtt.thingsboard.cloud";
const int   TB_PORT       = 1883;
const char* TB_TOKEN      = "GkUmbnN2vDPBljtNCKfo"; 

// Bắt buộc phải tạo 2 WiFiClient riêng biệt cho 2 kết nối MQTT
WiFiClient   espClient_Hive;
PubSubClient hiveClient(espClient_Hive);

WiFiClient   espClient_TB;
PubSubClient tbClient(espClient_TB);

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
// HÀM XỬ LÝ KHI NHẬN ĐƯỢC KẾT QUẢ AI TỪ PYTHON (QUA HIVEMQ)
// =========================================================
void hiveCallback(char* topic, byte* payload, unsigned int length) {
  if (strcmp(topic, "iot_thanglong/plate") == 0) {
    // Parse JSON
    StaticJsonDocument<256> doc;
    DeserializationError error = deserializeJson(doc, payload, length);

    if (error) {
      Serial.print(F("deserializeJson() failed: "));
      Serial.println(error.f_str());
      return;
    }

    const char* idStr = doc["id"];
    float speed = doc["speed"];
    const char* dir = doc["direction"];
    const char* plate = doc["plate"];

    Serial.println("=========================================");
    Serial.println(">> NHẬN KẾT QUẢ AI TỪ PYTHON:");
    Serial.printf("   ID: %s | Tốc độ: %.1f | Biển số: %s\n", idStr, speed, plate);
    
    // 1. TRUYỀN NGƯỢC VỀ MẠCH MASTER ĐỂ HIỂN THỊ LCD (QUA UART)
    // Định dạng: "RESULT:ID=1,V=25.3,P=30A-12345\n"
    Serial2.print("RESULT:ID=");
    Serial2.print(idStr);
    Serial2.print(",V=");
    Serial2.print(speed, 1);
    Serial2.print(",P=");
    Serial2.println(plate);

    // 2. GỬI BÁO CÁO LÊN THINGSBOARD
    if (tbClient.connected()) {
      StaticJsonDocument<200> tbDoc;
      tbDoc["speed"] = speed;
      tbDoc["direction"] = dir;
      tbDoc["license_plate"] = plate;
      
      char tbPayload[200];
      serializeJson(tbDoc, tbPayload);
      
      tbClient.publish("v1/devices/me/telemetry", tbPayload);
      Serial.println(">> ĐÃ BÁO CÁO LÊN THINGSBOARD THÀNH CÔNG!");
    } else {
      Serial.println("!!! KHÔNG THỂ BÁO CÁO THINGSBOARD (MẤT KẾT NỐI) !!!");
    }
    Serial.println("=========================================");
  }
}

// =========================================================
// DUY TRÌ 2 KẾT NỐI MQTT
// =========================================================
void maintainMQTT() {
  bool hiveConnected = hiveClient.connected();
  bool tbConnected = tbClient.connected();
  
  if (hiveConnected) hiveClient.loop();
  if (tbConnected) tbClient.loop();
  
  if (hiveConnected && tbConnected) return; // Cả 2 đều OK
  if (WiFi.status() != WL_CONNECTED) return;
  if (millis() - lastMqttAttempt < MQTT_RETRY_MS) return;
  lastMqttAttempt = millis();

  // 1. Kết nối HiveMQ
  if (!hiveConnected) {
    Serial.print(">> KET NOI HIVEMQ...");
    String clientId = "ESP32_Slave_Hive_" + String(random(0xffff), HEX);
    if (hiveClient.connect(clientId.c_str())) {
      Serial.println(" OK!");
      hiveClient.subscribe("iot_thanglong/plate"); // Lắng nghe biển số từ Python
    } else {
      Serial.println(" THAT BAI!");
    }
  }

  // 2. Kết nối ThingsBoard
  if (!tbConnected) {
    Serial.print(">> KET NOI THINGSBOARD...");
    String clientId = "ESP32_Slave_TB_" + String(random(0xffff), HEX);
    if (tbClient.connect(clientId.c_str(), TB_TOKEN, NULL)) {
      Serial.println(" OK!");
    } else {
      Serial.println(" THAT BAI!");
    }
  }
}

// =========================================================
// XỬ LÝ KHI NHẬN ĐƯỢC DỮ LIỆU TỪ UART MASTER (BẮN LÊN HIVEMQ)
// =========================================================
void processLine(char* raw) {
  int len = strlen(raw);
  while (len > 0 && (raw[len-1] == '\r' || raw[len-1] == ' ')) raw[--len] = '\0';
  if (len == 0) return;

  String msg = String(raw);
  int speedIdx = msg.indexOf("SPEED:");

  if (speedIdx >= 0) {
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
    
    Serial.println(">> ĐÃ NHẬN TỐC ĐỘ TỪ MASTER: " + speedStr + " km/h | ID: " + idStr);

    if (hiveClient.connected()) {
      // Bắn thẳng lên Python thông qua HiveMQ
      String payload = "{\"id\":\"" + idStr + "\",\"speed\":" + speedStr + ",\"direction\":\"" + dir + "\"}";
      hiveClient.publish("iot_thanglong/speed", payload.c_str());
      Serial.println("   -> Đã bắn lên HiveMQ, chờ Python chụp ảnh...");
    } else {
      Serial.println("   -> LỖI: Mất mạng HiveMQ, không thể gọi Python!");
    }
  }
}

// =========================================================
// SETUP
// =========================================================
void setup() {
  Serial.begin(115200);
  delay(1000);

  // Mở UART2: RX = 16, TX = 17
  Serial2.begin(115200, SERIAL_8N1, 16, 17);

  connectWiFi();
  
  hiveClient.setServer(HIVEMQ_SERVER, HIVEMQ_PORT);
  hiveClient.setCallback(hiveCallback);
  
  tbClient.setServer(TB_SERVER, TB_PORT);
  
  // Tăng buffer size cho PubSubClient (Tránh lỗi payload JSON dài)
  hiveClient.setBufferSize(512);
  tbClient.setBufferSize(512);

  Serial.println(">> SLAVE HUB (DUAL MQTT) ĐÃ SẴN SÀNG.");
}

// =========================================================
// LOOP
// =========================================================
void loop() {
  maintainMQTT();

  // ĐỌC UART TỪ MASTER
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
      else linePos = 0; 
    }
  }
}
