#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>

const char* WIFI_SSID     = "NONNET";
const char* WIFI_PASSWORD = "abcd1234";

// Cấu hình IP Tĩnh: 192.168.137.233
IPAddress local_IP(192, 168, 137, 233);
IPAddress gateway(192, 168, 137, 1);
IPAddress subnet(255, 255, 255, 0);
IPAddress primaryDNS(8, 8, 8, 8);

WebServer server(80);

// ==========================================
// CẤU HÌNH CHÂN CAMERA OV2640 (Dòng AI Thinker)
// ==========================================
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

void handlePhoto() {
  camera_fb_t * fb = NULL;
  fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println(">> Lỗi chụp ảnh!");
    server.send(500, "text/plain", "Camera capture failed");
    return;
  }

  // Trả về ảnh định dạng JPEG
  server.sendHeader("Content-Type", "image/jpeg");
  server.sendHeader("Content-Disposition", "inline; filename=capture.jpg");
  server.sendHeader("Access-Control-Allow-Origin", "*"); // Cho phép CORS
  server.sendContent((const char *)fb->buf, fb->len);
  
  esp_camera_fb_return(fb); // Giải phóng bộ nhớ
  Serial.println(">> Đã chụp và gửi 1 ảnh về Python!");
}

void setup() {
  Serial.begin(115200);
  Serial.println();

  // Khởi tạo Camera
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
  config.pixel_format = PIXFORMAT_JPEG; // Đảm bảo output luôn là JPEG
  
  // Cấu hình chất lượng ảnh để đọc rõ biển số
  config.frame_size = FRAMESIZE_VGA; // 640x480 (Rất nét cho biển số, nhẹ)
  config.jpeg_quality = 10; // 10-63 (Càng thấp càng nét, 10 là cực nét)
  config.fb_count = 1;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Khởi tạo Camera LỖI: 0x%x\n", err);
    return;
  }
  
  // Tăng cường một số setting phần cứng của OV2640 nếu cần
  sensor_t * s = esp_camera_sensor_get();
  s->set_vflip(s, 0); // Lật ảnh dọc nếu cần (0 hoặc 1)
  s->set_hmirror(s, 0); // Lật ảnh ngang nếu cần (0 hoặc 1)
  
  // Kết nối WiFi với IP Tĩnh
  if (!WiFi.config(local_IP, gateway, subnet, primaryDNS, primaryDNS)) {
    Serial.println("Lỗi cấu hình IP Tĩnh");
  }
  
  Serial.print("Đang kết nối WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n>> KẾT NỐI WIFI THÀNH CÔNG!");
  Serial.print(">> Địa chỉ IP Tĩnh Camera: http://");
  Serial.print(WiFi.localIP());
  Serial.println("/photo.jpg");

  // Thiết lập đường dẫn HTTP
  server.on("/photo.jpg", HTTP_GET, handlePhoto);
  server.begin();
  Serial.println(">> CAMERA SERVER KHỞI ĐỘNG XONG.");
}

void loop() {
  server.handleClient(); // Liên tục lắng nghe request từ Python
}
