#include <ESP32Servo.h>

// =========================================================
// KHAI BÁO CHÂN PHẦN CỨNG
// =========================================================
const int trigPin1 = 13;  // Cảm biến 1 (Vào) - TRIG
const int echoPin1 = 12;  // Cảm biến 1 (Vào) - ECHO
const int trigPin2 = 5;   // Cảm biến 2 (Ra)  - TRIG
const int echoPin2 = 18;  // Cảm biến 2 (Ra)  - ECHO

const int servoPin = 4;   // Động cơ Servo đóng/mở cổng
const int buzzerPin = 14; // Còi báo động
const int buttonPin = 26; // Nút bấm đóng/mở thủ công (Đổi sang 26 vì chân 4 đã dùng cho Servo)

// UART2 giao tiếp với IOT_2
#define UART2_TX 17
#define UART2_RX 16

Servo gateServo;

// =========================================================
// BIẾN TOÀN CỤC VÀ CẤU HÌNH
// =========================================================
float baseline1 = 0; // Khoảng cách nền CB1
float baseline2 = 0; // Khoảng cách nền CB2
const float THRESHOLD = 20.0; // Xe được nhận diện khi khoảng cách thay đổi 20cm so với nền, hoặc cách < 20cm
const float SPEED_CONST = 0.017;

bool isGateOpen = false;
bool carInside = false; // Trạng thái xe đang trong vùng quét

// Chống dội nút bấm
unsigned long lastBtnPress = 0;
bool lastBtnState = HIGH;

// Chống dội cảm biến
unsigned long lastCarInTime = 0;
unsigned long lastCarOutTime = 0;

// Báo cáo định kỳ
unsigned long lastDistanceReport = 0;

// =========================================================
// CÁC HÀM CƠ BẢN
// =========================================================

// Phát tiếng còi tít tít ngắn
void beepBuzzer() {
  digitalWrite(buzzerPin, HIGH);
  delay(100);
  digitalWrite(buzzerPin, LOW);
}

// Mở cổng
void openGate() {
  if (!isGateOpen) {
    Serial.println(">> MO CONG");
    gateServo.write(90); // Xoay 90 độ để mở
    beepBuzzer();
    isGateOpen = true;
  }
}

// Đóng cổng
void closeGate() {
  if (isGateOpen) {
    Serial.println(">> DONG CONG");
    gateServo.write(0); // Trở về 0 độ để đóng
    beepBuzzer();
    delay(100);
    beepBuzzer();
    isGateOpen = false;
  }
}

// Đo khoảng cách
float getDistance(int trig, int echo) {
  digitalWrite(trig, LOW);
  delayMicroseconds(2);
  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);
  
  long duration = pulseIn(echo, HIGH, 30000); // Timeout 30ms (~5m)
  if (duration == 0) return 999.0;
  return duration * SPEED_CONST;
}

// Lấy mẫu nền
void calibrateBackground() {
  Serial.println(">> Dang lay mau nen...");
  float sum1 = 0, sum2 = 0;
  int valid1 = 0, valid2 = 0;
  
  for (int i = 0; i < 10; i++) {
    float d1 = getDistance(trigPin1, echoPin1);
    float d2 = getDistance(trigPin2, echoPin2);
    
    if (d1 < 400) { sum1 += d1; valid1++; }
    if (d2 < 400) { sum2 += d2; valid2++; }
    delay(50);
  }
  
  if (valid1 > 0) baseline1 = sum1 / valid1; else baseline1 = 200;
  if (valid2 > 0) baseline2 = sum2 / valid2; else baseline2 = 200;
  
  Serial.printf(">> NEN 1: %.1f cm | NEN 2: %.1f cm\n", baseline1, baseline2);
}

// =========================================================
// SETUP & LOOP
// =========================================================
void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, UART2_RX, UART2_TX);
  
  pinMode(trigPin1, OUTPUT); pinMode(echoPin1, INPUT);
  pinMode(trigPin2, OUTPUT); pinMode(echoPin2, INPUT);
  
  pinMode(buzzerPin, OUTPUT);
  pinMode(buttonPin, INPUT_PULLUP);
  
  gateServo.setPeriodHertz(50); // Tần số 50Hz cho Servo chuẩn
  gateServo.attach(servoPin, 500, 2400); 
  
  closeGate(); // Mặc định cổng đóng
  
  delay(1000);
  calibrateBackground();
  Serial.println(">> IOT MASTER SAN SANG!");
}

void loop() {
  // 1. Kiểm tra Nút bấm thủ công
  bool currentBtnState = digitalRead(buttonPin);
  if (currentBtnState == LOW && lastBtnState == HIGH && millis() - lastBtnPress > 500) {
    lastBtnPress = millis();
    if (isGateOpen) closeGate();
    else openGate();
  }
  lastBtnState = currentBtnState;

  // 2. Nhận lệnh từ IOT_2 (Qua UART)
  if (Serial2.available()) {
    String msg = Serial2.readStringUntil('\n');
    msg.trim();
    if (msg == "OPEN") {
      openGate();
    } else if (msg == "CLOSE") {
      closeGate();
    }
  }

  // 3. Quét Cảm biến
  float d1 = getDistance(trigPin1, echoPin1);
  delay(20); // Tránh nhiễu chéo
  float d2 = getDistance(trigPin2, echoPin2);
  
  // Hiển thị và gửi dữ liệu cảm biến mỗi 2.5 giây
  if (millis() - lastDistanceReport >= 2500) {
    lastDistanceReport = millis();
    Serial.printf(">> [LIVE] CB1: %.1f cm | CB2: %.1f cm\n", d1, d2);
    // Gửi qua UART để Mạch 2 hiển thị
    Serial2.printf("DIST:%.1f,%.1f\n", d1, d2);
  }
  
  // Logic xe đi VÀO (CB1)
  bool trigger1 = (d1 < 20.0) || (baseline1 - d1 > THRESHOLD);
  if (trigger1 && !carInside && millis() - lastCarInTime > 5000) {
    carInside = true;
    lastCarInTime = millis();
    Serial.println(">> [SENS] XE VAO TRAM!");
    Serial2.println("CAR_IN"); // Báo cho IOT_2
  }
  
  // Logic xe đi RA (CB2)
  bool trigger2 = (d2 < 20.0) || (baseline2 - d2 > THRESHOLD);
  if (trigger2 && carInside && millis() - lastCarOutTime > 5000) {
    carInside = false; // Reset trạng thái
    lastCarOutTime = millis();
    Serial.println(">> [SENS] XE DA QUA CONG!");
    Serial2.println("CAR_OUT"); // Báo cho IOT_2
  }
  
  delay(50);
}