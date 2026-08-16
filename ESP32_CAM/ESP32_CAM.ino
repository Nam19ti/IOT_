#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>

const char* WIFI_SSID     = "NONNET";
const char* WIFI_PASSWORD = "abcd1234";

// Cau hinh IP Tinh: 192.168.137.233
IPAddress local_IP(192, 168, 137, 233);
IPAddress gateway(192, 168, 137, 1);
IPAddress subnet(255, 255, 255, 0);
IPAddress primaryDNS(8, 8, 8, 8);

WebServer server(80);

// ==========================================
// CAU HINH CHAN CAMERA OV2640 (AI Thinker)
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

// ==========================================
// XU LY YEU CAU CHUP ANH
// ==========================================
void handlePhoto() {
  camera_fb_t * fb = NULL;

  // Xa bo frame cu trong bo dem de lay frame moi nhat (tranh anh bi mo/lag)
  fb = esp_camera_fb_get();
  if (fb) esp_camera_fb_return(fb);
  fb = esp_camera_fb_get();

  if (!fb) {
    Serial.println(">> Loi chup anh!");
    server.send(500, "text/plain", "Camera capture failed");
    return;
  }

  server.sendHeader("Content-Type", "image/jpeg");
  server.sendHeader("Content-Disposition", "inline; filename=capture.jpg");
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.setContentLength(fb->len);
  server.send(200, "image/jpeg", "");
  server.sendContent((const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb);
  Serial.printf(">> Da chup va gui anh (Size: %d bytes)\n", fb->len);
}

void setup() {
  Serial.begin(115200);
  Serial.println();

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM; config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM; config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM; config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM; config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // ==================================================
  // CAU HINH CHAT LUONG ANH CAO NHAT CO THE
  // UXGA = 1600x1200 - Do phan giai lon nhat cua OV2640
  // jpeg_quality: 0-63, cang THAP cang NET (4 = cuc cao)
  // fb_count = 2: Bo dem kep, tranh bi mo do lag bo dem
  // ==================================================
  config.frame_size   = FRAMESIZE_UXGA;
  config.jpeg_quality = 4;
  config.fb_count     = 2;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf(">> LOI khoi tao Camera: 0x%x\n", err);
    return;
  }

  // ==================================================
  // TINH CHINH CAM BIEN OV2640 - ANH NET NHAT
  // ==================================================
  sensor_t * s = esp_camera_sensor_get();

  s->set_framesize(s, FRAMESIZE_UXGA);
  s->set_quality(s, 4);

  // Anh sang, tuong phan, do net
  s->set_brightness(s, 1);              // Tang sang nhe (+1)
  s->set_contrast(s, 1);               // Tang tuong phan (bien so ro hon)
  s->set_saturation(s, 0);             // Mau sac trung tinh
  s->set_sharpness(s, 2);              // Do net cao nhat OV2640 ho tro

  // Auto White Balance
  s->set_whitebal(s, 1);
  s->set_awb_gain(s, 1);
  s->set_wb_mode(s, 0);                // Tu dong

  // Auto Exposure
  s->set_exposure_ctrl(s, 1);
  s->set_aec2(s, 1);                   // AEC2 giam rung anh sang
  s->set_ae_level(s, 0);
  s->set_aec_value(s, 300);

  // Auto Gain - gioi han de tranh nhieu hat
  s->set_gain_ctrl(s, 1);
  s->set_agc_gain(s, 0);
  s->set_gainceiling(s, (gainceiling_t)2); // Gioi han gain x4

  // Xu ly anh va khu nhieu
  s->set_bpc(s, 1);                    // Black Pixel Correction
  s->set_wpc(s, 1);                    // White Pixel Correction
  s->set_raw_gma(s, 1);               // Gamma correction
  s->set_lenc(s, 1);                  // Lens Correction (giam mo canh)
  s->set_dcw(s, 1);

  // Lat anh (chinh theo huong lap dat thuc te)
  s->set_vflip(s, 0);
  s->set_hmirror(s, 0);

  // Cho cam bien on dinh sau khi cai dat
  delay(500);
  Serial.println(">> Camera OV2640: CHE DO CHAT LUONG CAO NHAT - UXGA 1600x1200 | Quality=4");

  // Ket noi WiFi voi IP Tinh
  if (!WiFi.config(local_IP, gateway, subnet, primaryDNS, primaryDNS)) {
    Serial.println(">> Loi cau hinh IP Tinh");
  }
  Serial.print(">> Dang ket noi WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.println("\n>> KET NOI WIFI THANH CONG!");
  Serial.printf(">> Camera Server: http://%s/photo.jpg\n", WiFi.localIP().toString().c_str());

  server.on("/photo.jpg", HTTP_GET, handlePhoto);
  server.begin();
  Serial.println(">> CAMERA SERVER KHOI DONG XONG.");
}

void loop() {
  server.handleClient();
}
