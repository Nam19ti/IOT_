#include <Wire.h>
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 2); 

// KHAI BÁO CHÂN CẢM BIẾN
const int trigPin1 = 26;  
const int echoPin1 = 27; 
const int trigPin2 = 18;  
const int echoPin2 = 19; 

// KHAI BÁO CHÂN NÚT BẤM
const int MODE_BUTTON_PIN = 0;   
const int START_BUTTON_PIN = 5;  

// =========================================================
// TÙY CHỈNH KHOẢNG CÁCH TẠI ĐÂY (DỄ DÀNG THAY ĐỔI)
// =========================================================

// 1. KHOẢNG CÁCH GIỮA 2 CẢM BIẾN (Dùng để tính tốc độ)
// Đơn vị: Mét (m). Ví dụ: 10cm = 0.100, 20cm = 0.200, 1 mét = 1.000
const float SENSOR_DISTANCE_M = 0.100; 

// 2. KHOẢNG CÁCH QUÉT TỐI ĐA CỦA 3 CHẾ ĐỘ 
// Đơn vị: Centimet (cm). 
const float MODE_1_MAX_CM = 200.0; // Chế độ 1: Nhìn xa tối đa 2 mét (200cm)
const float MODE_2_MAX_CM = 100.0; // Chế độ 2: Nhìn xa tối đa 1 mét (100cm)
const float MODE_3_MAX_CM = 15.0;  // Chế độ 3: Nhìn xa tối đa 15 cm

// 3. ĐỘ NHẠY CẮT NỀN (Auto-Background Offset)
// Cứ có vật cản làm khoảng cách thụt giảm lớn hơn số này thì nhận là xe
const float OFFSET_CM = 2.0; 

// =========================================================
// HẾT PHẦN TÙY CHỈNH - LOGIC HỆ THỐNG BÊN DƯỚI
// =========================================================

const unsigned long TIMEOUT_US = 3000000; // 3 Giây chờ xe qua
const float SPEED_CONST = 0.017; 

volatile int currentMode = 3; 
volatile bool modeChanged = false; 
volatile unsigned long lastModePress = 0;

bool isArmed = false; 
unsigned long lastSerialPrint = 0; 
unsigned long lastStartBtnPress = 0; 

unsigned long PULSE_TIMEOUT_US; 

float activeThres1 = 0;
float activeThres2 = 0;
float currentMaxDist = 0;

void waitMillis(unsigned long ms) {
  unsigned long start = millis();
  while (millis() - start < ms) { yield(); }
}

void waitMicros(unsigned long us) {
  unsigned long start = micros();
  while (micros() - start < us); 
}

void IRAM_ATTR modeISR() {
  unsigned long currentTime = millis();
  if (currentTime - lastModePress > 300) { 
    currentMode++;
    if (currentMode > 3) currentMode = 1; 
    modeChanged = true; 
    lastModePress = currentTime; 
  }
}

inline float quickPing(int trig, int echo, unsigned long timeout) {
  digitalWrite(trig, LOW); 
  waitMicros(2);  
  
  digitalWrite(trig, HIGH); 
  waitMicros(10); 
  
  digitalWrite(trig, LOW);
  
  long duration = pulseIn(echo, HIGH, timeout); 
  if (duration == 0) return 999.0;
  
  float dist = duration * SPEED_CONST; 
  if (dist < 2.0 || dist > 400.0) return 999.0; 
  return dist; 
}

float getMedianPing(int trig, int echo, int samples = 3, unsigned long customTimeout = 0) {
  float arr[5]; 
  if (samples > 5) samples = 5;
  unsigned long timeoutToUse = (customTimeout > 0) ? customTimeout : PULSE_TIMEOUT_US;

  for (int i = 0; i < samples; i++) {
    yield(); 
    arr[i] = quickPing(trig, echo, timeoutToUse); 
    waitMillis(15); 
  }
  
  for (int i = 0; i < samples - 1; i++) {
    for (int j = i + 1; j < samples; j++) {
      if (arr[i] > arr[j]) { 
        float temp = arr[i]; arr[i] = arr[j]; arr[j] = temp; 
      }
    }
  }
  return arr[samples / 2]; 
}

void printIdleScreen() {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Mode:"); lcd.print(currentMode); 
  lcd.print(" T1:"); lcd.print((int)activeThres1);
  lcd.setCursor(0, 1); 
  lcd.print("Bam N5 de DO");
  lcd.setCursor(11, 1);
  lcd.print("T2:"); lcd.print((int)activeThres2);
}

void applyMode(int mode) {
  switch(mode) {
    case 1: currentMaxDist = MODE_1_MAX_CM; break;
    case 2: currentMaxDist = MODE_2_MAX_CM; break;
    case 3: currentMaxDist = MODE_3_MAX_CM; break;
  }
  
  // Tự động tính thời gian ép xung siêu âm dựa trên cấu hình khoảng cách
  PULSE_TIMEOUT_US = (unsigned long)(currentMaxDist / SPEED_CONST) + 2000;
  
  lcd.clear(); lcd.setCursor(0, 0); lcd.print("Mode "); lcd.print(mode); lcd.print(" setup..");
  lcd.setCursor(0, 1); lcd.print("Dang do nen...");
  
  Serial.print("\n=== AUTO LAY NEN MODE "); Serial.print(mode); Serial.println(" ===");
  
  float bg1 = getMedianPing(trigPin1, echoPin1, 5, 25000);
  float bg2 = getMedianPing(trigPin2, echoPin2, 5, 25000);

  if (bg1 != 999.0) activeThres1 = min((float)(bg1 - OFFSET_CM), currentMaxDist);
  else activeThres1 = currentMaxDist;

  if (bg2 != 999.0) activeThres2 = min((float)(bg2 - OFFSET_CM), currentMaxDist);
  else activeThres2 = currentMaxDist;

  if (activeThres1 < 3.0) activeThres1 = 3.0;
  if (activeThres2 < 3.0) activeThres2 = 3.0;

  waitMillis(800); 
  printIdleScreen();
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
    if (modeChanged) return; 
    
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
  Serial.begin(115200); 
  
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("He Thong Do");
  lcd.setCursor(0, 1);
  lcd.print("Toc Do - ESP32");
  
  waitMillis(2000); 
  
  pinMode(MODE_BUTTON_PIN, INPUT_PULLUP); 
  attachInterrupt(digitalPinToInterrupt(MODE_BUTTON_PIN), modeISR, FALLING);
  pinMode(START_BUTTON_PIN, INPUT_PULLUP); 

  pinMode(trigPin1, OUTPUT); pinMode(echoPin1, INPUT);
  pinMode(trigPin2, OUTPUT); pinMode(echoPin2, INPUT);
  
  applyMode(currentMode);
}

void loop() {
  if (modeChanged) {
    applyMode(currentMode);
    isArmed = false; 
    modeChanged = false;
  }

  bool currentBtnState = digitalRead(START_BUTTON_PIN);
  static bool lastBtnState = HIGH;
  bool isBtnPressed = false;
  
  if (currentBtnState == LOW && lastBtnState == HIGH && (millis() - lastStartBtnPress > 300)) {
    isBtnPressed = true;
    lastStartBtnPress = millis();
  }
  lastBtnState = currentBtnState;

  // =========================================================
  // TRẠNG THÁI CHỜ
  // =========================================================
  if (!isArmed) {
    if (millis() - lastSerialPrint >= 500) {
      float d1_idle = getMedianPing(trigPin1, echoPin1, 3);
      float d2_idle = getMedianPing(trigPin2, echoPin2, 3);
      
      Serial.print("[Giam Sat] CB1: ");
      if (d1_idle == 999.0 || d1_idle > activeThres1) Serial.print("TRONG"); 
      else { Serial.print(d1_idle); Serial.print(" cm"); }
      
      Serial.print("   |   CB2: ");
      if (d2_idle == 999.0 || d2_idle > activeThres2) Serial.println("TRONG"); 
      else { Serial.print(d2_idle); Serial.println(" cm"); }
      
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
  
  // 1. QUÉT XE ĐI TỪ TRÁI SANG PHẢI (CB1 -> CB2)
  float d1 = quickPing(trigPin1, echoPin1, PULSE_TIMEOUT_US);
  
  if (d1 < activeThres1) {
    unsigned long timeS1 = micros(); 
    
    lcd.clear(); lcd.setCursor(0, 0); lcd.print("Dang tinh toan..");
    lcd.setCursor(0, 1); lcd.print("Xe qua CB1 >>");

    unsigned long fastTimeout2 = (unsigned long)(activeThres2 / SPEED_CONST) + 500;
    unsigned long timeS2 = 0;
    
    while (micros() - timeS1 < TIMEOUT_US) {
      yield(); 
      if (modeChanged) return; 

      float d2 = quickPing(trigPin2, echoPin2, fastTimeout2);
      if (d2 < activeThres2) {
        timeS2 = micros(); 
        break; 
      }
    }
    
    if (timeS2 > 0) calculateSpeed(timeS1, timeS2, "Trai -> Phai");
    else printError("Het thoi gian!", "CB2 khong nhan");
    resetSystem(3000); 
    return;
  }
  
  // 2. QUÉT XE ĐI TỪ PHẢI SANG TRÁI (CB2 -> CB1)
  float d2 = quickPing(trigPin2, echoPin2, PULSE_TIMEOUT_US);
  
  if (d2 < activeThres2) {
    unsigned long timeS2 = micros(); 
    
    lcd.clear(); lcd.setCursor(0, 0); lcd.print("Dang tinh toan..");
    lcd.setCursor(0, 1); lcd.print("<< Xe qua CB2");

    unsigned long fastTimeout1 = (unsigned long)(activeThres1 / SPEED_CONST) + 500;
    unsigned long timeS1 = 0;
    
    while (micros() - timeS2 < TIMEOUT_US) {
      yield(); 
      if (modeChanged) return; 

      float d1 = quickPing(trigPin1, echoPin1, fastTimeout1);
      if (d1 < activeThres1) {
        timeS1 = micros(); 
        break;
      }
    }
    
    if (timeS1 > 0) calculateSpeed(timeS2, timeS1, "Phai -> Trai");
    else printError("Het thoi gian!", "CB1 khong nhan");
    resetSystem(3000);
    return;
  }
}