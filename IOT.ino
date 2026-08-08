#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <WiFi.h>
#include <PubSubClient.h>

// =========================================================
// KHỞI TẠO WIFI VÀ THINGSBOARD (MQTT)
// =========================================================
const char* WIFI_SSID     = "Dar";
const char* WIFI_PASSWORD = "12345678";
const char* MQTT_SERVER   = "demo.thingsboard.io";
const int   MQTT_PORT     = 1883;
const char* TOKEN         = "GkUmbnN2vDPBljtNCKfo";

WiFiClient espClient;
PubSubClient client(espClient);

// =========================================================
// KHỞI TẠO MÀN HÌNH LCD (địa chỉ I2C: 0x27, kích thước: 16 cột x 2 hàng)
// =========================================================
LiquidCrystal_I2C lcd(0x27, 16, 2);

// =========================================================
// KHAI BÁO CHÂN CẢM BIẾN SIÊU ÂM
// CB1: Cảm biến thứ nhất (bên trái)
// CB2: Cảm biến thứ hai  (bên phải)
// =========================================================
const int trigPin1 = 15;  // Chân TRIG của cảm biến 1 - CB1 (phát xung siêu âm)
const int echoPin1 =  4;  // Chân ECHO của cảm biến 1 - CB1 (nhận tín hiệu phản hồi)
const int trigPin2 = 18;  // Chân TRIG của cảm biến 2 - CB2 (phát xung siêu âm)
const int echoPin2 = 19;  // Chân ECHO của cảm biến 2 - CB2 (nhận tín hiệu phản hồi)

// =========================================================
// KHAI BÁO CHÂN NÚT BẤM
// =========================================================
// CÁC CHÂN NÊN TRÁNH TRÊN ESP32:
//   - GPIO 0, 2, 12 : Strapping pins -> kéo HIGH lúc boot gây crash
//   - GPIO 12,13,14,15 : JTAG pins   -> có thể nhiễu trên một số board
//   - GPIO 34,35,36,39 : Chỉ INPUT  -> không dùng được cho interrupt
// CHÂN AN TOÀN: 25, 26, 27, 32, 33 (đa năng, interrupt, không xung đột)
const int MODE_BUTTON_PIN  = 25;  // GPIO 25 - Nút CHUYỂN CHẾ ĐỘ (nhấn để đổi Mode 1/2/3) | An toàn, hỗ trợ interrupt
const int START_BUTTON_PIN = 26;  // GPIO 26 - Nút BẮN TỐC ĐỘ   (nhấn để bắt đầu/dừng đo)   | An toàn, đọc trong loop

// =========================================================
// TÙY CHỈNH KHOẢNG CÁCH TẠI ĐÂY (DỄ DÀNG THAY ĐỔI)
// =========================================================

// 1. KHOẢNG CÁCH GIỮA 2 CẢM BIẾN (Dùng để tính tốc độ)
// Đơn vị: Mét (m). Ví dụ: 10.5cm = 0.105
const float SENSOR_DISTANCE_M = 0.105;

// 2. KHOẢNG CÁCH QUÉT TỐI ĐA (Duy nhất 1 chế độ)
// Siêu chuẩn, không nhiễu - Đo xe < 80 km/h
const float MAX_DISTANCE_CM = 15.0;

// 3. ĐỘ NHẠY CẮT NỀN (Background Offset)
// Khi vật cản làm khoảng cách giảm nhiều hơn giá trị này so với nền -> nhận là xe
const float OFFSET_CM = 2.0;

// =========================================================
// HẾT PHẦN TÙY CHỈNH - LOGIC HỆ THỐNG BÊN DƯỚI
// =========================================================

const unsigned long TIMEOUT_US = 3000000; // Thời gian tối đa chờ xe đi qua cảm biến thứ 2: 3 giây
const float SPEED_CONST = 0.017;          // Hệ số tính khoảng cách từ thời gian: dist(cm) = duration(us) * 0.017

// Biến trạng thái hệ thống
bool isArmed = false;              // true = đang trong chế độ ĐO TỐC ĐỘ, false = đang chờ
unsigned long lastSerialPrint  = 0; // Thời điểm in Serial lần cuối (ms) - tránh in liên tục
unsigned long lastStartBtnPress = 0; // Thời điểm nhấn nút BẮT ĐẦU lần cuối (ms) - chống rung

unsigned long PULSE_TIMEOUT_US; // Thời gian timeout pulseIn (us)

float activeThres1   = 0;  // Ngưỡng phát hiện xe CB1 = dynamicBg1 - currentOffset
float activeThres2   = 0;  // Ngưỡng phát hiện xe CB2 = dynamicBg2 - currentOffset
float currentMaxDist = MAX_DISTANCE_CM;  
float currentOffset  = OFFSET_CM;

// =========================================================
// NỀN ĐỘNG (DYNAMIC BACKGROUND)
// Thay vì lấy nền 1 lần rồi cố định, hệ thống liên tục cập nhật
// nền theo thuật toán EMA (Exponential Moving Average).
// Khi môi trường thay đổi đột ngột >= OFFSET_CM -> nhận diện là xe.
// =========================================================
float dynamicBg1 = 0; // Nền động CB1 - tự thích nghi theo môi trường
float dynamicBg2 = 0; // Nền động CB2 - tự thích nghi theo môi trường

// Tốc độ thích nghi nền (EMA alpha):
// - Nhỏ (0.02-0.05): thích nghi chậm, ổn định, ít bị nhiễu nhất thời
// - Lớn (0.1-0.2) : thích nghi nhanh hơn khi môi trường thay đổi nhiều
const float BG_ALPHA = 0.03f;

// Hàm chờ (ms) không chặn watchdog - thay thế cho delay()
void waitMillis(unsigned long ms) {
  unsigned long start = millis();
  while (millis() - start < ms) { yield(); }
}

// Hàm chờ chính xác theo micro-giây (us) - dùng khi cần timing siêu âm
void waitMicros(unsigned long us) {
  unsigned long start = micros();
  while (micros() - start < us);
}

// =========================================================
// CẬP NHẬT NỀN ĐỘNG (EMA - Exponential Moving Average)
// Công thức: bg_mới = bg_cũ * (1 - alpha) + đo_mới * alpha
// Chỉ cập nhật khi: không có xe (reading >= activeThres)
//                   và giá trị đo hợp lệ (2cm - 400cm)
// =========================================================
void updateDynamicBg(float reading, float &bg) {
  if (reading >= 2.0 && reading < 400.0) {
    if (bg <= 0) {
      bg = reading; // Khởi tạo lần đầu: gán thẳng giá trị đo được
    } else {
      bg = bg * (1.0f - BG_ALPHA) + reading * BG_ALPHA; // EMA: cập nhật chậm và mượt
    }
  }
  // Nếu reading = 999 (không hợp lệ/ngoài tầm) -> giữ nguyên nền cũ, không cập nhật
}

// Đo khoảng cách nhanh bằng cảm biến siêu âm (1 lần đo duy nhất)
// Trả về khoảng cách (cm), hoặc 999.0 nếu không hợp lệ / ngoài tầm
inline float quickPing(int trig, int echo, unsigned long timeout) {
  // Tạo xung TRIG: kéo LOW 2us -> HIGH 10us -> LOW
  digitalWrite(trig, LOW);
  waitMicros(2);
  digitalWrite(trig, HIGH);
  waitMicros(10);
  digitalWrite(trig, LOW);

  // Đo thời gian xung ECHO HIGH (us)
  long duration = pulseIn(echo, HIGH, timeout);
  if (duration == 0) return 999.0; // Timeout: không có vật cản hoặc quá xa

  float dist = duration * SPEED_CONST; // Quy đổi thời gian -> khoảng cách (cm)
  if (dist < 2.0 || dist > 400.0) return 999.0; // Loại bỏ giá trị ngoài dải hợp lệ (2-400 cm)
  return dist;
}

// Đo khoảng cách lấy trung vị từ nhiều mẫu - giảm nhiễu và giá trị lạ
// samples: số lần đo (tối đa 5), customTimeout: override timeout nếu cần
float getMedianPing(int trig, int echo, int samples = 3, unsigned long customTimeout = 0) {
  float arr[5];
  if (samples > 5) samples = 5;
  unsigned long timeoutToUse = (customTimeout > 0) ? customTimeout : PULSE_TIMEOUT_US;

  // Đo nhiều lần, mỗi lần cách nhau 15ms để cảm biến ổn định
  for (int i = 0; i < samples; i++) {
    yield();                                      // Nhường CPU cho hệ thống ESP32
    arr[i] = quickPing(trig, echo, timeoutToUse);
    waitMillis(15);
  }

  // Sắp xếp mảng tăng dần (bubble sort đơn giản)
  for (int i = 0; i < samples - 1; i++) {
    for (int j = i + 1; j < samples; j++) {
      if (arr[i] > arr[j]) {
        float temp = arr[i]; arr[i] = arr[j]; arr[j] = temp;
      }
    }
  }
  return arr[samples / 2]; // Trả về giá trị ở giữa (trung vị)
}

void printIdleScreen() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("He thong SS! T1:");
  lcd.print((int)activeThres1);
  lcd.setCursor(0, 1);
  lcd.print("Bam nut de doT2:"); 
  lcd.print((int)activeThres2);
}

void calibrateBackground() {
  PULSE_TIMEOUT_US = (unsigned long)(currentMaxDist / SPEED_CONST) + 2000;
  
  lcd.clear(); lcd.setCursor(0, 0); lcd.print("He thong setup..");
  lcd.setCursor(0, 1); lcd.print("Dang do nen...");
  
  Serial.print("\n=== AUTO LAY NEN ===");
  
  float bg1 = getMedianPing(trigPin1, echoPin1, 5, 25000);
  float bg2 = getMedianPing(trigPin2, echoPin2, 5, 25000);

  if (bg1 != 999.0) dynamicBg1 = bg1;
  else              dynamicBg1 = currentMaxDist;

  if (bg2 != 999.0) dynamicBg2 = bg2;
  else              dynamicBg2 = currentMaxDist;

  activeThres1 = min(dynamicBg1 - currentOffset, currentMaxDist);
  activeThres2 = min(dynamicBg2 - currentOffset, currentMaxDist);
  if (activeThres1 < 3.0) activeThres1 = 3.0;
  if (activeThres2 < 3.0) activeThres2 = 3.0;

  Serial.println(" -> OK!");
  waitMillis(800);
  printIdleScreen();
}

void sendTelemetryMQTT(float speed_kmph, String direction) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println(">> MQTT: Khong co WiFi, bo qua gui.");
    return;
  }
  
  lcd.clear(); lcd.setCursor(0, 0); lcd.print("Dang gui MQTT...");
  Serial.print(">> MQTT: Ket noi den ThingsBoard... ");
  
  unsigned long startConnect = millis();
  // Thử kết nối MQTT (chờ tối đa 2 giây để không làm treo máy lâu)
  while (!client.connected() && (millis() - startConnect < 2000)) {
    if (client.connect("ESP32_Speed_Client", TOKEN, NULL)) {
      Serial.println("OK");
    } else {
      waitMillis(500);
    }
  }

  if (client.connected()) {
    // Đóng gói JSON
    String payload = "{\"speed\":";
    payload += speed_kmph;
    payload += ", \"direction\":\"";
    payload += direction;
    payload += "\"}";
    
    // Gửi dữ liệu
    if (client.publish("v1/devices/me/telemetry", payload.c_str())) {
      Serial.println(">> MQTT: Da gui " + payload);
      lcd.setCursor(0, 1); lcd.print("Gui THANH CONG!");
    } else {
      Serial.println(">> MQTT: Loi khi gui.");
      lcd.setCursor(0, 1); lcd.print("Gui THAT BAI!");
    }
    
    // Đọc data dọn bộ đệm MQTT một lần rồi ngắt
    client.loop(); 
    waitMillis(1000); // Hiện chữ thông báo 1s
  } else {
    Serial.println("THAT BAI (Timeout).");
    lcd.setCursor(0, 1); lcd.print("Loi ket noi MQTT");
    waitMillis(1000);
  }
}

void calculateSpeed(unsigned long t_start, unsigned long t_end, String direction) {
  unsigned long timeDiff_us = t_end - t_start;
  float timeDiff_s = timeDiff_us / 1000000.0; 
  if (timeDiff_s <= 0.0) timeDiff_s = 0.000001; 

  float speed_mps = SENSOR_DISTANCE_M / timeDiff_s;
  float speed_kmph = speed_mps * 3.6;
  
  lcd.clear(); lcd.setCursor(0, 0); lcd.print(direction); 
  lcd.setCursor(0, 1); lcd.print("V:"); lcd.print(speed_kmph, 1); lcd.print(" km/h");
  Serial.print(">> KET QUA: "); Serial.print(speed_kmph); Serial.println(" km/h");
  
  waitMillis(2000); // Cho người dùng đọc kết quả trước
  sendTelemetryMQTT(speed_kmph, direction);
}

void printError(String dong1, String dong2) {
  lcd.clear(); lcd.setCursor(0, 0); lcd.print(dong1);
  lcd.setCursor(0, 1); lcd.print(dong2);
  Serial.print(">> LOI: "); Serial.println(dong2);
}

void resetSystem(unsigned long waitTimeMs = 2500) {
  isArmed = false;
  unsigned long startWait = millis();
  
  while (millis() - startWait < waitTimeMs) {
    if (digitalRead(START_BUTTON_PIN) == LOW) {
      lastStartBtnPress = millis(); 
      while (digitalRead(START_BUTTON_PIN) == LOW) yield(); 
      break; 
    }
    yield(); 
  } 
  
  Serial.println("\n--- He thong da Reset, tiep tuc giam sat ---");
  printIdleScreen(); 
}

void setup() {
  Serial.begin(115200); // Khởi tạo Serial Monitor ở baudrate 115200

  // Khởi tạo LCD và hiển thị màn hình chào
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("He Thong Do");
  lcd.setCursor(0, 1);
  lcd.print("Toc Do - ESP32");

  // Kết nối WiFi chạy nền (không block)
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  client.setServer(MQTT_SERVER, MQTT_PORT);

  waitMillis(2000); // Giữ màn hình chào 2 giây

  // Cấu hình nút BẮN TỐC ĐỘ (GPIO 26) - dùng điện trở nội PULL-UP
  // Nút nối GND: khi nhấn = LOW, khi thả = HIGH (đọc thủ công trong loop)
  pinMode(START_BUTTON_PIN, INPUT_PULLUP);

  // Cấu hình chân cảm biến siêu âm
  pinMode(trigPin1, OUTPUT); // TRIG CB1: phát xung (OUTPUT)
  pinMode(echoPin1, INPUT);  // ECHO CB1: nhận tín hiệu (INPUT)
  pinMode(trigPin2, OUTPUT); // TRIG CB2: phát xung (OUTPUT)
  pinMode(echoPin2, INPUT);  // ECHO CB2: nhận tín hiệu (INPUT)

  // Lấy nền lần đầu
  calibrateBackground();
}

void loop() {
  bool currentBtnState = digitalRead(START_BUTTON_PIN);
  static bool lastBtnState = HIGH;
  bool isBtnPressed = false;
  
  if (currentBtnState == LOW && lastBtnState == HIGH && (millis() - lastStartBtnPress > 300)) {
    isBtnPressed = true;
    lastStartBtnPress = millis();
  }
  lastBtnState = currentBtnState;

  // =========================================================
  // TRẠNG THÁI CHỜ - CẬP NHẬT NỀN ĐỘNG
  // Mỗi 500ms: đo khoảng cách, nếu KHÔNG có xe thì cập nhật nền EMA
  // Nếu CÓ xe -> giữ nguyên nền, không cập nhật (tránh học sai)
  // =========================================================
  if (!isArmed) {
    if (millis() - lastSerialPrint >= 500) {
      float d1_idle = getMedianPing(trigPin1, echoPin1, 3);
      float d2_idle = getMedianPing(trigPin2, echoPin2, 3);

      // --- Cập nhật nền động CB1 ---
      bool xe1 = (d1_idle < activeThres1); // true = có vật cản/xe tại CB1
      if (!xe1) {
        updateDynamicBg(d1_idle, dynamicBg1); // Không có xe -> cập nhật nền
        activeThres1 = min(dynamicBg1 - currentOffset, currentMaxDist);
        if (activeThres1 < 3.0) activeThres1 = 3.0;
      }

      // --- Cập nhật nền động CB2 ---
      bool xe2 = (d2_idle < activeThres2); // true = có vật cản/xe tại CB2
      if (!xe2) {
        updateDynamicBg(d2_idle, dynamicBg2); // Không có xe -> cập nhật nền
        activeThres2 = min(dynamicBg2 - currentOffset, currentMaxDist);
        if (activeThres2 < 3.0) activeThres2 = 3.0;
      }

      // --- In trạng thái ra Serial Monitor ---
      Serial.print("[Giam Sat] CB1: ");
      if (d1_idle == 999.0)  Serial.print("NGOAI TAM");
      else if (xe1)          { Serial.print(d1_idle); Serial.print("cm [XE!]"); }
      else                   { Serial.print(d1_idle); Serial.print("cm (nen="); Serial.print(dynamicBg1, 1); Serial.print(")"); }

      Serial.print("   |   CB2: ");
      if (d2_idle == 999.0)  Serial.println("NGOAI TAM");
      else if (xe2)          { Serial.print(d2_idle); Serial.println("cm [XE!]"); }
      else                   { Serial.print(d2_idle); Serial.print("cm (nen="); Serial.print(dynamicBg2, 1); Serial.println(")"); }

      lastSerialPrint = millis();
    }

    if (isBtnPressed) {
      isArmed = true;
      lcd.clear(); lcd.setCursor(0, 0); lcd.print("Dang quet xe...");
      lcd.setCursor(0, 1); lcd.print("T1:"); lcd.print((int)activeThres1);
      lcd.setCursor(8, 1); lcd.print("T2:"); lcd.print((int)activeThres2);
    }
    return;
  }

  // =========================================================
  // TRẠNG THÁI ĐANG QUÉT XE LIÊN TỤC
  // =========================================================
  
  if ((millis() / 500) % 2 == 0) { lcd.setCursor(15, 0); lcd.print("*"); } 
  else { lcd.setCursor(15, 0); lcd.print(" "); }

  if (isBtnPressed) {
    lcd.clear(); lcd.setCursor(0, 0); lcd.print("Da huy do...");
    resetSystem(500);
    return;
  }
  
  // =========================================================
  // TIMEOUT CHO VÒNG LẶP QUÉT BAN ĐẦU:
  //   Dùng PULSE_TIMEOUT_US (đã tính đủ cho tầm tối đa + buffer 2000us)
  //   KHÔNG dùng timeout ngắn hơn ở đây vì HC-SR04 cần ~600us xử lý nội bộ
  //   trước khi ECHO lên HIGH. Timeout quá ngắn = cắt echo giữa chừng = miss xe!
  //
  // TIMEOUT CHO VÒNG LẶP CHỜ CẢM BIẾN THỨ 2 (sau khi đã bắt được cảm biến 1):
  //   = thời gian echo tại ngưỡng + 900us (600us sensor delay + 300us buffer)
  //   Ngắn hơn PULSE_TIMEOUT_US giúp poll CB thứ 2 nhanh hơn, ít miss hơn.
  // =========================================================
  unsigned long waitTimeout1 = (unsigned long)(activeThres1 / SPEED_CONST) + 900;
  unsigned long waitTimeout2 = (unsigned long)(activeThres2 / SPEED_CONST) + 900;

  // 1. QUÉT XE ĐI TỪ TRÁI SANG PHẢI (CB1 -> CB2)
  // Ghi timestamp TRƯỚC khi phát xung để tránh độ trễ của quickPing()
  unsigned long tBefore1 = micros();
  float d1 = quickPing(trigPin1, echoPin1, PULSE_TIMEOUT_US); // PULSE_TIMEOUT_US: an toàn cho mọi mode
  
  if (d1 < activeThres1) {
    unsigned long timeS1 = tBefore1;
    unsigned long timeS2 = 0;

    // === TỐI ƯU HÓA KHẮC PHỤC SAI SỐ TẦN SỐ QUÉT ===
    // CB1 đã thấy xe ở khoảng cách d1. Mặc định CB2 phải quét ra tận background.
    // Giờ ta ép CB2 chỉ quét tới độ sâu của d1 (cộng thêm 25cm bù trừ xe đi chéo).
    // Giúp Mode 1 và 2 chớp mắt nhanh y hệt như Mode 3!
    unsigned long fastPoll2 = (unsigned long)((d1 + 25.0) / SPEED_CONST) + 900;
    unsigned long currentWait2 = min(waitTimeout2, fastPoll2);
    
    while (micros() - timeS1 < TIMEOUT_US) {
      yield(); // Bắt buộc! Không có yield() -> WDT reset ESP32 sau ~3 giây

      unsigned long tBefore2 = micros();
      float d2 = quickPing(trigPin2, echoPin2, currentWait2); // Quét siêu tốc
      if (d2 < activeThres2) {
        timeS2 = tBefore2;
        break; 
      }
    }
    
    // Cập nhật LCD SAU khi đã đo xong
    if (timeS2 > 0) calculateSpeed(timeS1, timeS2, "Trai -> Phai");
    else {
      lcd.clear(); lcd.setCursor(0, 0); lcd.print("Het thoi gian!");
      lcd.setCursor(0, 1); lcd.print("CB2 khong nhan");
      Serial.println(">> LOI: CB2 khong nhan");
    }
    resetSystem(3000); 
    return;
  }
  
  // 2. QUÉT XE ĐI TỪ PHẢI SANG TRÁI (CB2 -> CB1)
  // Ghi timestamp TRƯỚC khi phát xung để tránh độ trễ của quickPing()
  unsigned long tBefore2 = micros();
  float d2 = quickPing(trigPin2, echoPin2, PULSE_TIMEOUT_US); // PULSE_TIMEOUT_US: an toàn cho mọi mode
  
  if (d2 < activeThres2) {
    unsigned long timeS2 = tBefore2;
    unsigned long timeS1 = 0;

    // === TỐI ƯU HÓA KHẮC PHỤC SAI SỐ TẦN SỐ QUÉT ===
    unsigned long fastPoll1 = (unsigned long)((d2 + 25.0) / SPEED_CONST) + 900;
    unsigned long currentWait1 = min(waitTimeout1, fastPoll1);
    
    while (micros() - timeS2 < TIMEOUT_US) {
      yield(); // Bắt buộc! Không có yield() -> WDT reset ESP32 sau ~3 giây

      unsigned long tBeforeCB1 = micros();
      float d1 = quickPing(trigPin1, echoPin1, currentWait1); // Quét siêu tốc
      if (d1 < activeThres1) {
        timeS1 = tBeforeCB1;
        break;
      }
    }
    
    // Cập nhật LCD SAU khi đã đo xong
    if (timeS1 > 0) calculateSpeed(timeS2, timeS1, "Phai -> Trai");
    else {
      lcd.clear(); lcd.setCursor(0, 0); lcd.print("Het thoi gian!");
      lcd.setCursor(0, 1); lcd.print("CB1 khong nhan");
      Serial.println(">> LOI: CB1 khong nhan");
    }
    resetSystem(3000);
    return;
  }
}