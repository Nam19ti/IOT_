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
bool isManualMode = false; // Cờ theo dõi chế độ đóng mở thủ công
bool carInside = false; // Trạng thái xe đang trong vùng quét (Đã qua CB1)
bool carAtGate = false; // Trạng thái xe đang nằm ngay dưới cổng (Đang chắn CB2)
unsigned long lastClearTime = 0; // Thời điểm cuối cùng cảm biến 2 bị che

// Chống dội nút bấm
volatile bool buttonPressed = false;
volatile unsigned long lastInterruptTime = 0;

void IRAM_ATTR handleButtonInterrupt() {
  unsigned long interruptTime = millis();
  if (interruptTime - lastInterruptTime > 500) { // Debounce 500ms
    buttonPressed = true;
    lastInterruptTime = interruptTime;
  }
}

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

// Còi hú báo động (kêu dồn dập)
void alarmBuzzer() {
  for (int i = 0; i < 10; i++) {
    digitalWrite(buzzerPin, HIGH);
    delay(50);
    digitalWrite(buzzerPin, LOW);
    delay(50);
  }
}

// Mở cổng
void openGate() {
  if (!isGateOpen) {
    Serial.println(">> MO CONG");
    gateServo.write(90); // Xoay 90 độ để mở
    beepBuzzer();
    isGateOpen = true;
    Serial2.println("STATE:OPEN"); // Báo trạng thái cho IOT_2
  }
}

// Kiểm tra xem có xe đang nằm dưới cổng (CB2) không (Đo 3 lần lấy giá trị nhỏ nhất để chống nhiễu)
bool isCarUnderGate() {
  float min_d = 999.0;
  int lost_ground = 0;
  for (int i = 0; i < 3; i++) {
    float d2 = getDistance(trigPin2, echoPin2);
    if (d2 < min_d) min_d = d2;
    if (d2 >= 990.0) lost_ground++;
    delay(15);
  }
  // Nếu cả 3 lần đo đều bị timeout (mất sóng nền do kính xe hắt đi), thì chắc chắn có vật cản che khuất
  if (lost_ground == 3) return true;
  
  // Nếu khoảng cách d2 nhỏ (<20) hoặc giảm đột ngột so với nền
  return (min_d < 20.0) || (baseline2 - min_d > THRESHOLD);
}

// Đóng cổng
void closeGate() {
  if (isGateOpen) {
    if (isCarUnderGate()) {
      Serial.println(">> [CANH BAO] CO XE DUOI CONG! TU CHOI DONG CONG DE AN TOAN!");
      alarmBuzzer(); // Còi hú báo động liên tục
      return;
    }
    Serial.println(">> DONG CONG");
    gateServo.write(0); // Trở về 0 độ để đóng
    beepBuzzer();
    delay(100);
    beepBuzzer();
    isGateOpen = false;
    Serial2.println("STATE:CLOSED"); // Báo trạng thái cho IOT_2
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
  Serial2.println("STATE:CALIBRATING"); // Báo cho IOT_2 hiển thị LCD
  
  // Đợi 2 giây để người dùng tránh xa vùng cảm biến
  delay(2000);
  
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
  Serial2.println("STATE:CLOSED"); // Khôi phục LCD
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
  attachInterrupt(digitalPinToInterrupt(buttonPin), handleButtonInterrupt, FALLING);
  
  gateServo.setPeriodHertz(50); // Tần số 50Hz cho Servo chuẩn
  gateServo.attach(servoPin, 500, 2400); 
  
  closeGate(); // Mặc định cổng đóng
  
  delay(1000);
  calibrateBackground();
  Serial.println(">> IOT MASTER SAN SANG!");
}

void loop() {
  // 1. Kiểm tra Nút bấm thủ công (Xử lý ngay lập tức nhờ Ngắt phần cứng)
  if (buttonPressed) {
    buttonPressed = false;
    if (isGateOpen) {
      closeGate();
      isManualMode = false; // Tắt chế độ thủ công khi đã đóng cổng
    } else {
      openGate();
      isManualMode = true; // Bật chế độ thủ công: KHÔNG đóng cổng tự động
    }
  }

  // 2. Nhận lệnh từ IOT_2 (Qua UART)
  if (Serial2.available()) {
    String msg = Serial2.readStringUntil('\n');
    msg.trim();
    if (msg == "OPEN") {
      Serial.println(">> [UART] Nhan lenh MO CONG (Tu Dong Dong)");
      openGate();
      isManualMode = false; // Mở tự động, sẽ đóng tự động
    } else if (msg == "OPEN_MANUAL") {
      Serial.println(">> [UART] Nhan lenh MO CONG (Khong Tu Dong Dong)");
      openGate();
      isManualMode = true; // Mở thủ công, KHÔNG đóng tự động
    } else if (msg == "CLOSE") {
      Serial.println(">> [UART] Nhan lenh DONG CONG");
      closeGate();
      isManualMode = false; // Reset chế độ
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
  // Tính luôn trường hợp d2 >= 990.0 (Timeout) là có xe chắn ngang làm mất dội sóng
  bool trigger2 = (d2 < 20.0) || (baseline2 - d2 > THRESHOLD) || (d2 >= 990.0);
  
  if (trigger2 && carInside) {
    // Xe bắt đầu tiến vào và chắn ngang Cảm biến 2 (Đang nằm dưới Barie)
    if (!carAtGate) {
      carAtGate = true;
      Serial.println(">> [SENS] XE DANG NAM DUOI CONG...");
    }
    // LƯU Ý: Nếu xe vẫn đang chắn, liên tục reset đồng hồ đếm 3 giây!
    lastClearTime = millis();
  } 
  else if (!trigger2 && carAtGate) {
    // Khoảng cách d2 đã trở về nền bình thường (Xe không còn che cảm biến)
    // Phải chờ ĐỦ 3 giây liên tục không bị che thì mới đóng cổng!
    if (millis() - lastClearTime > 3000) { 
      carAtGate = false;
      carInside = false; // Reset chu trình
      
      if (!isManualMode) {
        Serial.println(">> [SENS] XE DA QUA HOAN TOAN 3 GIAY! ĐONG CONG.");
        Serial2.println("CAR_OUT"); // Báo cho IOT_2 biết đã an toàn tuyệt đối
      } else {
        Serial.println(">> [SENS] XE DA QUA, NHUNG DANG MO THU CONG -> KHONG DONG TU DONG!");
      }
    }
  }
  
  delay(50);
}