#include "esp_camera.h"
#include <WiFi.h>
#include <PubSubClient.h>

// =========================================================
// CẤU HÌNH WIFI VÀ MQTT
// =========================================================
const char* ssid = "NONNET";
const char* password = "abcd1234";

const char* MQTT_SERVER = "broker.hivemq.com";
const int   MQTT_PORT   = 1883;

WiFiClient espClient;
PubSubClient mqttClient(espClient);

unsigned long lastMqttAttempt = 0;

// =========================================================
// CẤU HÌNH CAMERA (AI Thinker ESP32-CAM)
// =========================================================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// Hàm chụp và bắn ảnh lên MQTT
void takeAndSendPhoto(String carId) {
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println(">> LỖI: Chụp ảnh thất bại!");
    return;
  }
  
  Serial.printf(">> Đã chụp ảnh xe ID %s! Kích thước: %u bytes.\n", carId.c_str(), fb->len);
  
  String topic = "iot_thanglong/image/" + carId;
  
  // Publish mảng byte của bức ảnh thẳng lên MQTT
  if(mqttClient.publish(topic.c_str(), fb->buf, fb->len)) {
    Serial.println(">> Đã gửi ảnh thành công qua MQTT (Siêu tốc)!");
  } else {
    Serial.println(">> LỖI: Không thể gửi ảnh. Có thể do kích thước quá lớn.");
  }
  
  esp_camera_fb_return(fb);
}

// Khi nhận được lệnh từ HiveMQ
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String topicStr = String(topic);
  
  if (topicStr == "iot_thanglong/trigger") {
    String carId = "";
    for (int i = 0; i < length; i++) {
      carId += (char)payload[i];
    }
    Serial.println("\n>> [MQTT] Nhận lệnh chụp ảnh cho xe ID: " + carId);
    
    // Tiến hành chụp và gửi
    takeAndSendPhoto(carId);
  }
}

void maintainMQTT() {
  if (mqttClient.connected()) {
    mqttClient.loop();
    return;
  }
  if (WiFi.status() != WL_CONNECTED) return;
  if (millis() - lastMqttAttempt < 5000) return;
  lastMqttAttempt = millis();

  Serial.print(">> MQTT: Ket noi HiveMQ...");
  String clientId = "ESP32_CAM_" + String(random(0xffff), HEX);
  
  if (mqttClient.connect(clientId.c_str())) {
    Serial.println(" THANH CONG!");
    mqttClient.subscribe("iot_thanglong/trigger"); // Lắng nghe lệnh chụp
    Serial.println(">> Đã subscribe topic: iot_thanglong/trigger");
  } else {
    Serial.println(" THAT BAI!");
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println();

  // Kết nối WiFi
  WiFi.begin(ssid, password);
  Serial.print("Dang ket noi WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi ket noi thanh cong!");

  // Cấu hình MQTT
  mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  
  // TĂNG KÍCH THƯỚC BỘ ĐỆM ĐỂ GỬI ẢNH (Quan trọng: Mặc định PubSubClient chỉ có 256 bytes)
  mqttClient.setBufferSize(50000); // Cho phép gửi payload lên tới 50KB

  // Cấu hình Camera
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG; 

  if(psramFound()){
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 10;
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_SVGA;
    config.jpeg_quality = 12;
    config.fb_count = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Loi khoi tao Camera: 0x%x", err);
    return;
  }
  
  Serial.println("ESP32-CAM (MQTT) da san sang.");
}

void loop() {
  maintainMQTT();
}
