#include <HardwareSerial.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <PubSubClient.h>

// =========================================================
// CẤU HÌNH WIFI VÀ LAN
// =========================================================
const char* WIFI_SSID     = "NONNET";
const char* WIFI_PASSWORD = "abcd1234";

// IP của máy tính chạy Server Python
const char* PYTHON_SERVER_IP = "192.168.137.1"; // <-- Thay bằng IP máy tính của bạn nếu cần
const int   PYTHON_SERVER_PORT = 5000;

// =========================================================
// CẤU HÌNH IP TĨNH CHO IOT_2 (ESP32)
// =========================================================
IPAddress local_IP(192, 168, 137, 199);
IPAddress gateway(192, 168, 137, 1);
IPAddress subnet(255, 255, 255, 0);
IPAddress primaryDNS(8, 8, 8, 8);

WebServer server(80);

// LCD I2C
LiquidCrystal_I2C lcd(0x27, 16, 2);

// UART2 giao tiếp với IOT_1
#define UART2_TX 17
#define UART2_RX 16

// =========================================================
// CẤU HÌNH THINGSBOARD MQTT
// =========================================================
const char* TB_SERVER = "thingsboard.cloud";
const int TB_PORT = 1883;
const char* TB_TOKEN = "GkUmbnN2vDPBljtNCKfo";

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

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
unsigned long lastWifiAttempt = 0;
unsigned long lastMqttAttempt = 0;
bool isNetworkOffline = true;

void checkNetwork() {
  if (WiFi.status() != WL_CONNECTED) {
    isNetworkOffline = true;
    if (millis() - lastWifiAttempt > 5000) {
      lastWifiAttempt = millis();
      printLCD("!! CANH BAO !!", "MAT MANG WIFI");
      Serial.println(">> Đang thử kết nối lại WiFi...");
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }
    return; // Nếu mất WiFi thì không check MQTT
  } else {
    if (isNetworkOffline) {
      printLCD("He thong SS", "IP: " + WiFi.localIP().toString());
      isNetworkOffline = false;
    }
  }

  if (!mqttClient.connected()) {
    if (millis() - lastMqttAttempt > 5000) {
      lastMqttAttempt = millis();
      Serial.println(">> Đang kết nối tới ThingsBoard MQTT...");
      if (mqttClient.connect("IOT2_Client", TB_TOKEN, NULL)) {
        Serial.println(">> Đã kết nối ThingsBoard MQTT!");
        // Subscribe nhận lệnh RPC từ Dashboard
        mqttClient.subscribe("v1/devices/me/rpc/request/+");
      } else {
        Serial.print(">> Lỗi kết nối MQTT, rc=");
        Serial.println(mqttClient.state());
      }
    }
  } else {
    mqttClient.loop(); // Duy trì kết nối MQTT
  }
}

// =========================================================
// XỬ LÝ LỆNH RPC TỪ THINGSBOARD
// =========================================================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  
  Serial.print(">> Nhan RPC [");
  Serial.print(topic);
  Serial.print("]: ");
  Serial.println(message);

  // Ví dụ JSON: {"method":"OPEN","params":{}}
  // Lấy request_id từ topic: v1/devices/me/rpc/request/$request_id
  String topicStr = String(topic);
  String requestId = topicStr.substring(topicStr.lastIndexOf("/") + 1);

  // Phân tích chuỗi cơ bản để lấy method (Tránh dùng thư viện Json nặng)
  String method = "";
  if (message.indexOf("\"method\":\"OPEN\"") > 0) method = "OPEN";
  else if (message.indexOf("\"method\":\"OPEN_MANUAL\"") > 0) method = "OPEN_MANUAL";
  else if (message.indexOf("\"method\":\"CLOSE\"") > 0) method = "CLOSE";

  if (method != "") {
    Serial.println(">> Thuc thi RPC method: " + method);
    Serial2.println(method);
    printLCD("Dieu khien TX", method);
  } else {
    Serial.println(">> Khong xac dinh method!");
  }

  // Gửi response phản hồi lại ThingsBoard
  String responseTopic = "v1/devices/me/rpc/response/" + requestId;
  mqttClient.publish(responseTopic.c_str(), "{\"status\":\"ok\"}");
}

// =========================================================
// LẮNG NGHE LỆNH TỪ PYTHON SERVER (Qua Mạng LAN)
// =========================================================
void handleOpenGate() {
  // Python gọi vào đường dẫn này khi xe đủ tiền
  // URL format: http://<IOT2_IP>/open_gate?plate=30A12345
  
  String plate = "Chua ro";
  if (server.hasArg("plate")) {
    plate = server.arg("plate");
  }

  printLCD(plate, "Da thu phi");
  Serial2.println("OPEN"); // Ra lệnh cho Mạch 1 mở cổng
  
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "text/plain", "OK! Da mo cong.");
}

void handleOpenGateManual() {
  // Mở cổng nhưng KHÔNG cho phép tự động đóng
  printLCD("Mo thu cong", "Khong tu dong");
  Serial2.println("OPEN_MANUAL");
  
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "text/plain", "OK! Da mo cong thu cong.");
}

void handleCloseGate() {
  // Đóng cổng thủ công
  printLCD("Dong thu cong", "He thong SS");
  Serial2.println("CLOSE");
  
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "text/plain", "OK! Da dong cong thu cong.");
}

void handleDenyGate() {
  // Python gọi vào đường dẫn này khi xe KHÔNG đủ tiền
  String plate = "Chua ro";
  if (server.hasArg("plate")) {
    plate = server.arg("plate");
  }

  printLCD(plate, "HET TIEN/TU CHOI");
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "text/plain", "OK! Da hien thi canh bao.");
}

// =========================================================
// SETUP
// =========================================================
void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, 16, 17); // RX/TX chéo với Mạch 1
  
  lcd.init();
  lcd.backlight();
  printLCD("Khoi dong", "VETC LAN Slave");

  // Cài đặt IP Tĩnh trước khi kết nối WiFi
  if (!WiFi.config(local_IP, gateway, subnet, primaryDNS, primaryDNS)) {
    Serial.println(">> Lỗi cấu hình IP Tĩnh!");
  }

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  // Cài đặt MQTT
  mqttClient.setServer(TB_SERVER, TB_PORT);
  mqttClient.setCallback(mqttCallback);

  server.on("/open_gate", HTTP_GET, handleOpenGate);
  server.on("/open_gate_manual", HTTP_GET, handleOpenGateManual);
  server.on("/close_gate", HTTP_GET, handleCloseGate);
  server.on("/deny_gate", HTTP_GET, handleDenyGate);
  server.begin();
}

// =========================================================
// LOOP
// =========================================================
void loop() {
  checkNetwork();
  server.handleClient(); // Xử lý API LAN

  // NHẬN SỰ KIỆN TỪ MẠCH 1 (CẢM BIẾN/SERVO HUB)
  if (Serial2.available()) {
    String msg = Serial2.readStringUntil('\n');
    msg.trim();
    
    if (msg == "CAR_IN") {
      printLCD("Xe vao", "Cho nhan dien");
      
      // Gọi HTTP GET thẳng sang Python Server
      if (WiFi.status() == WL_CONNECTED) {
        HTTPClient http;
        String url = "http://" + String(PYTHON_SERVER_IP) + ":" + String(PYTHON_SERVER_PORT) + "/trigger_capture";
        http.begin(url);
        int httpCode = http.GET();
        if (httpCode > 0) {
          Serial.printf(">> Đã gửi lệnh chụp ảnh tới Python (Code: %d)\n", httpCode);
        } else {
          Serial.printf(">> LỖI KẾT NỐI PYTHON SERVER: %s\n", http.errorToString(httpCode).c_str());
          printLCD("Loi Mang LAN", "Khong thay Server");
        }
        http.end();
      }
    } 
    else if (msg == "CAR_OUT") {
      // Vì mạch 1 đã có 3s chống kẹt, ta chỉ cần xuất lệnh đóng
      Serial2.println("CLOSE"); 
    }
    else if (msg.startsWith("STATE:")) {
      String state = msg.substring(6);
      if (state == "OPEN") {
        // Chỉ ghi cổng đóng/mở theo yêu cầu
        printLCD("CONG MO", ""); 
      } else if (state == "CLOSED") {
        printLCD("CONG DONG", "He thong SS");
      } else if (state == "CALIBRATING") {
        printLCD("Dang do nen...", "Tranh xa CB!");
      }
    }
    // (Bỏ phần hiển thị khoảng cách DIST ra LCD để tránh rối mắt, chỉ giữ lại trên Serial nếu cần)
    else if (msg.startsWith("DIST:")) {
      String data = msg.substring(5);
      int commaIndex = data.indexOf(',');
      if (commaIndex > 0) {
        Serial.println(">> [LIVE] CB1: " + data.substring(0, commaIndex) + "cm | CB2: " + data.substring(commaIndex + 1) + "cm");
      }
    }
  }
}
