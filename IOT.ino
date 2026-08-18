#include <ESP32Servo.h>

// =========================================================
// KHAI BÁO CHÂN PHẦN CỨNG
// =========================================================
const int trigPin1 = 13;  // Cảm biến siêu âm 1 (Lối vào) - Chân phát xung TRIG
const int echoPin1 = 12;  // Cảm biến siêu âm 1 (Lối vào) - Chân nhận xung ECHO
const int trigPin2 = 5;   // Cảm biến siêu âm 2 (Ngay dưới cổng/Lối ra) - Chân phát xung TRIG
const int echoPin2 = 18;  // Cảm biến siêu âm 2 (Ngay dưới cổng/Lối ra) - Chân nhận xung ECHO

const int servoPin = 4;   // Chân điều khiển Động cơ Servo đóng/mở barie
const int buzzerPin = 14; // Chân điều khiển còi báo động (Cảnh báo khi kẹt xe, khi mở/đóng)
const int buttonPin = 26; // Nút bấm cứng để đóng/mở cổng thủ công (Đổi sang 26 vì chân 4 đã dùng cho Servo)

// Khai báo chân UART2 dùng để giao tiếp với mạch ESP32 thứ 2 (IOT_2)
#define UART2_TX 17
#define UART2_RX 16

Servo gateServo; // Đối tượng điều khiển động cơ Servo

// =========================================================
// BIẾN TOÀN CỤC VÀ CẤU HÌNH
// =========================================================
float baseline1 = 0; // Lưu khoảng cách nền (khoảng cách lúc không có xe) của cảm biến 1
float baseline2 = 0; // Lưu khoảng cách nền của cảm biến 2
// Ngưỡng nhận diện xe: Nếu khoảng cách đo được thay đổi quá 20cm so với nền hoặc nhỏ hơn 20cm thì coi là có xe
const float THRESHOLD = 20.0; 
// Hằng số tính khoảng cách từ thời gian (tốc độ âm thanh 340m/s -> 0.034cm/us, đi và về nên chia đôi -> 0.017)
const float SPEED_CONST = 0.017;

bool isGateOpen = false; // Cờ lưu trạng thái hiện tại của cổng (true = đang mở, false = đang đóng)
bool isManualMode = false; // Cờ phân biệt chế độ đóng mở thủ công bằng nút/web (đòi hỏi đóng thủ công) hay tự động
bool carInside = false; // Trạng thái xác nhận xe đã bắt đầu đi vào hệ thống (đã qua cảm biến 1)
bool carAtGate = false; // Trạng thái xe đang nằm ngay dưới thanh chắn barie (đang che cảm biến 2)
unsigned long lastClearTime = 0; // Lưu thời điểm cuối cùng cảm biến 2 không bị che (dùng cho thuật toán trễ 3s đóng cổng)

// Các biến phục vụ thuật toán chống dội (debounce) cho nút bấm
volatile bool buttonPressed = false; // Cờ báo hiệu có người vừa nhấn nút (volatile vì dùng trong ngắt)
volatile unsigned long lastInterruptTime = 0; // Thời điểm xảy ra ngắt gần nhất

/*
 * HÀM NGẮT NÚT BẤM (INTERRUPT)
 * Chức năng: Kích hoạt ngay lập tức khi nhấn nút bấm.
 * Thuật toán: Dùng `millis()` để kiểm tra khoảng thời gian giữa 2 lần nhấn liên tiếp. 
 * Nếu nhỏ hơn 500ms thì bỏ qua (chống dội cơ học - debounce).
 * Chú ý: Hàm ngắt cần dùng IRAM_ATTR để lưu trên RAM, giúp thực thi nhanh nhất và tránh lỗi crash trên ESP32.
 */
void IRAM_ATTR handleButtonInterrupt() {
  unsigned long interruptTime = millis();
  if (interruptTime - lastInterruptTime > 500) { // Debounce 500ms
    buttonPressed = true; // Kích hoạt cờ nhấn nút để xử lý ở hàm loop()
    lastInterruptTime = interruptTime; // Cập nhật lại thời gian ngắt
  }
}

// Các biến ghi nhận thời gian xe ra/vào để tránh dội tín hiệu cảm biến
unsigned long lastCarInTime = 0;
unsigned long lastCarOutTime = 0;

// Biến lưu thời gian gửi báo cáo khoảng cách qua Serial/UART định kỳ
unsigned long lastDistanceReport = 0;

// Biến lưu thời điểm Cảm biến 2 (Lối ra) trống trải (không có xe)
unsigned long lastS2ClearTime = 0;

// =========================================================
// CÁC HÀM CƠ BẢN
// =========================================================

/*
 * HÀM BÁO CÒI TÍT TÍT (Bình thường)
 * Chức năng: Phát ra một tiếng kêu ngắn (100ms) để báo hiệu thao tác mở/đóng cổng diễn ra.
 */
void beepBuzzer() {
  digitalWrite(buzzerPin, HIGH); // Bật còi
  delay(100);                    // Kêu 100ms
  digitalWrite(buzzerPin, LOW);  // Tắt còi
}

/*
 * HÀM BÁO ĐỘNG KHI KẸT (Hú liên tục dồn dập)
 * Chức năng: Hú còi liên tục 10 lần khi phát hiện có lệnh đóng nhưng xe đang nằm dưới cổng (cảnh báo nguy hiểm).
 */
void alarmBuzzer() {
  for (int i = 0; i < 10; i++) {
    digitalWrite(buzzerPin, HIGH); // Bật còi
    delay(50);                     // Kêu 50ms
    digitalWrite(buzzerPin, LOW);  // Tắt còi
    delay(50);                     // Nghỉ 50ms (tạo nhịp dồn dập)
  }
}

/*
 * HÀM MỞ CỔNG SERVO
 * Chức năng: Xoay servo lên 90 độ, bật còi báo, cập nhật cờ trạng thái, và gửi tín hiệu cho IOT_2.
 */
void openGate() {
  if (!isGateOpen) { // Chỉ xử lý thao tác nếu cổng đang đóng
    Serial.println(">> MO CONG");
    gateServo.write(90); // Xoay Servo sang góc 90 độ (Mở barie)
    beepBuzzer();        // Kêu bíp báo hiệu
    isGateOpen = true;   // Cập nhật trạng thái cổng đang mở
    Serial2.println("STATE:OPEN"); // Báo trạng thái qua UART2 cho IOT_2 hiển thị LCD
  }
}

/*
 * THUẬT TOÁN ĐO SIÊU ÂM CHỐNG NHIỄU (KIỂM TRA CÓ XE DƯỚI CỔNG)
 * Chức năng: Quét cảm biến 2 (ngay dưới cổng) 3 lần. Lấy giá trị nhỏ nhất để loại trừ nhiễu loạn sóng ngẫu nhiên.
 * Thuật toán bổ sung: Nếu kính xe chéo làm phản xạ sóng ra ngoài (không về lại chân echo), 
 * thời gian đo pulseIn sẽ bị timeout, sinh ra giá trị đo cực lớn (>=990).
 * Nếu cả 3 lần đo đều bị timeout, hàm sẽ khẳng định là có vật cản lớn (xe) đang che khuất.
 */
bool isCarUnderGate() {
  float min_d = 999.0;
  int lost_ground = 0; // Bộ đếm số lần đo bị mất sóng nền
  for (int i = 0; i < 3; i++) { // Quét liên tiếp 3 lần
    float d2 = getDistance(trigPin2, echoPin2);
    if (d2 < min_d) min_d = d2; // Lấy khoảng cách ngắn nhất trong 3 lần
    if (d2 >= 990.0) lost_ground++; // Nếu >= 990.0 tức là bị timeout do sóng bị hắt đi mất
    delay(15); // Nghỉ 15ms giữa các lần đo
  }
  // Nếu cả 3 lần đo đều bị timeout (mất sóng nền do kính xe hắt đi), thì chắc chắn có vật cản che khuất
  if (lost_ground == 3) return true;
  
  // Trả về true (có xe) nếu khoảng cách nhỏ (<20) hoặc giảm đột ngột quá ngưỡng (THRESHOLD) so với nền
  return (min_d < 20.0) || (baseline2 - min_d > THRESHOLD);
}

/*
 * HÀM ĐÓNG CỔNG SERVO VÀ THUẬT TOÁN CHỐNG KẸT
 * Chức năng: Xoay barie xuống 0 độ, nhưng bắt buộc đi qua lớp bảo vệ an toàn kép.
 * Thuật toán: Trước khi hạ barie, kiểm tra xem có xe dưới cổng không.
 * Nếu phát hiện có vật/xe, từ chối thực thi lệnh đóng và hú còi cảnh báo. Tuyệt đối không hạ barie đập vào xe.
 */
void closeGate() {
  if (isGateOpen) {
    // KIỂM TRA KÉP BẢO VỆ CHỐNG KẸT: 
    // - carAtGate: Biến cờ ở vòng loop chính đã ghi nhận xe đang tiến vào dưới cổng.
    // - isCarUnderGate(): Đo quét lại thực tế bằng sóng âm ngay tại thời điểm gọi lệnh đóng.
    // Nếu 1 trong 2 điều kiện này là đúng, lập tức hủy thao tác đóng cổng.
    if (carAtGate || isCarUnderGate()) {
      Serial.println(">> [CANH BAO] CO XE DUOI CONG! TU CHOI DONG CONG!");
      alarmBuzzer(); // Hú còi liên tục
      return; // Thoát ra, TUYỆT ĐỐI không đóng cổng
    }
    
    // Nếu qua được vòng kiểm tra an toàn, tiến hành đóng
    Serial.println(">> DONG CONG");
    gateServo.write(0); // Trả barie về 0 độ (Đóng)
    beepBuzzer();       // Kêu bíp
    delay(100);
    beepBuzzer();       // Kêu bíp thứ 2 báo hiệu cổng đã hạ
    isGateOpen = false; // Cập nhật trạng thái
    Serial2.println("STATE:CLOSED"); // Báo trạng thái cho IOT_2
  }
}

/*
 * HÀM ĐỌC CẢM BIẾN SIÊU ÂM (HC-SR04 / JSN-SR04T)
 * Chức năng: Phát 1 xung kích qua chân TRIG (10us), sau đó đo thời gian chân ECHO lên mức CAO.
 * Đầu ra: Khoảng cách tính bằng cm.
 */
float getDistance(int trig, int echo) {
  // Tạo xung kích TRIG
  digitalWrite(trig, LOW);
  delayMicroseconds(2);
  digitalWrite(trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig, LOW);
  
  // Hàm pulseIn chờ ECHO lên HIGH. Timeout 30000 micro-giây (30ms), tương đương quãng đường đo < 5 mét.
  long duration = pulseIn(echo, HIGH, 30000); 
  if (duration == 0) return 999.0; // Bằng 0 nghĩa là quá thời gian chờ (timeout)
  
  // Khoảng cách = Thời gian x Tốc độ âm thanh
  return duration * SPEED_CONST;
}

/*
 * HÀM LẤY MẪU NỀN (CALIBRATION)
 * Chức năng: Đo tự động khoảng cách tới mặt đường lúc không có xe khi hệ thống vừa bật nguồn.
 * Thuật toán: Cho người dùng 2s để tránh đường. Đo 10 lần liên tiếp, lấy trung bình cộng để ra "Khoảng cách nền".
 * Dùng khoảng cách nền này làm mốc chuẩn. Khi xe xuất hiện, khoảng cách đo được sẽ hụt đi rõ rệt so với nền.
 */
void calibrateBackground() {
  Serial.println(">> Dang lay mau nen...");
  Serial2.println("STATE:CALIBRATING"); // Báo cho IOT_2 hiển thị chữ CALIBRATING lên LCD
  
  // Đợi 2 giây để người dùng tránh xa vùng cảm biến, tránh đo nhầm người
  delay(2000);
  
  float sum1 = 0, sum2 = 0;
  int valid1 = 0, valid2 = 0;
  
  // Quét lấy mẫu 10 vòng
  for (int i = 0; i < 10; i++) {
    float d1 = getDistance(trigPin1, echoPin1);
    float d2 = getDistance(trigPin2, echoPin2);
    
    // Bỏ qua các giá trị rác > 4m (400cm). Chỉ tính tổng các giá trị hợp lệ.
    if (d1 < 400) { sum1 += d1; valid1++; }
    if (d2 < 400) { sum2 += d2; valid2++; }
    delay(50);
  }
  
  // Tính trung bình. Nếu bị lỗi không lấy được giá trị nào thì gán mặc định là 200cm
  if (valid1 > 0) baseline1 = sum1 / valid1; else baseline1 = 200;
  if (valid2 > 0) baseline2 = sum2 / valid2; else baseline2 = 200;
  
  Serial.printf(">> NEN 1: %.1f cm | NEN 2: %.1f cm\n", baseline1, baseline2);
  Serial2.println("STATE:CLOSED"); // Khôi phục LCD trên IOT_2 về bình thường
}

// =========================================================
// HÀM SETUP (CHẠY 1 LẦN DUY NHẤT KHI KHỞI ĐỘNG)
// =========================================================
void setup() {
  Serial.begin(115200); // Mở cổng Serial Monitor (Để debug với máy tính)
  Serial2.begin(115200, SERIAL_8N1, UART2_RX, UART2_TX); // Mở UART2 giao tiếp với bo IOT_2
  
  // Thiết lập chiều in/out cho các chân Cảm biến siêu âm
  pinMode(trigPin1, OUTPUT); pinMode(echoPin1, INPUT);
  pinMode(trigPin2, OUTPUT); pinMode(echoPin2, INPUT);
  
  pinMode(buzzerPin, OUTPUT); // Chân xuất còi
  pinMode(buttonPin, INPUT_PULLUP); // Nút bấm dùng điện trở kéo lên, mặc định mức HIGH. Nhấn xuống mức LOW.
  
  // Gắn ngắt cho nút bấm. Kích hoạt ở sườn xuống (FALLING)
  attachInterrupt(digitalPinToInterrupt(buttonPin), handleButtonInterrupt, FALLING);
  
  // Khởi tạo thông số chuẩn cho Động cơ Servo
  gateServo.setPeriodHertz(50); // Tần số 50Hz cho Servo chuẩn
  gateServo.attach(servoPin, 500, 2400); // Gắn chân điều khiển, độ rộng xung 500us - 2400us
  
  closeGate(); // Mặc định khi khởi động thì cổng phải ở trạng thái đóng để an toàn
  
  delay(1000);
  calibrateBackground(); // Tiến hành đo nền không gian môi trường
  Serial.println(">> IOT MASTER SAN SANG!");
}

// =========================================================
// HÀM LOOP (CHẠY LẶP LẠI LIÊN TỤC CHU KỲ CHÍNH)
// =========================================================
void loop() {
  // ---------------------------------------------------------
  // 1. Kiểm tra và Xử lý Nút bấm thủ công (Kích hoạt từ ngắt)
  // ---------------------------------------------------------
  if (buttonPressed) {
    buttonPressed = false; // Xóa cờ ngay lập tức để nhận lần bấm sau
    
    if (isGateOpen) { // Cổng đang mở -> Bấm nút là ra lệnh ĐÓNG
      // Quét xem dưới cổng có xe không trước khi thực sự quyết định
      bool hadCar = carAtGate || isCarUnderGate();
      if (hadCar) {
        Serial.println(">> [NUT BAM] CO XE DUOI CONG - KHONG DONG!");
        alarmBuzzer(); // Có xe -> Hú cảnh báo, không đóng!
        // isManualMode KHONG thay doi, giu nguyen trang thai để đóng sau
      } else {
        closeGate(); // An toàn -> Thực hiện đóng cổng
        isManualMode = false; // Reset chế độ thủ công, quay lại trạng thái tự động
      }
    } else { // Cổng đang đóng -> Bấm nút là ra lệnh MỞ
      openGate(); // Mở cổng
      isManualMode = true; // Bật cờ thủ công (mở tay thì sẽ không tự đóng lại khi xe qua)
    }
  }

  // ---------------------------------------------------------
  // 2. Nhận lệnh điều khiển từ IOT_2 qua giao tiếp UART
  // ---------------------------------------------------------
  if (Serial2.available()) {
    String msg = Serial2.readStringUntil('\n'); // Đọc từng dòng lệnh gửi sang
    msg.trim(); // Cắt bỏ các ký tự trống, xuống dòng
    
    if (msg == "OPEN") {
      Serial.println(">> [UART] Nhan lenh MO CONG (Tu Dong Dong)");
      openGate();
      isManualMode = false; // Lệnh mở chuẩn, sẽ tự động đóng khi xe qua cổng
    } else if (msg == "OPEN_MANUAL") {
      Serial.println(">> [UART] Nhan lenh MO CONG (Khong Tu Dong Dong)");
      openGate();
      isManualMode = true; // Lệnh mở thủ công từ xa (VD: Bảo vệ bấm trên app web), cấm tự động đóng
    } else if (msg == "CLOSE") {
      Serial.println(">> [UART] Nhan lenh DONG CONG");
      closeGate();
      isManualMode = false; // Reset lại chế độ tự động bình thường
    }
  }

  // ---------------------------------------------------------
  // 3. Quét Cảm biến Siêu âm theo dõi hành trình xe
  // ---------------------------------------------------------
  float d1 = getDistance(trigPin1, echoPin1); // Đo cảm biến ngoài
  delay(20); // Tạo trễ 20ms tránh hiện tượng nhiễu chéo (sóng cảm biến này lọt vào cảm biến kia)
  float d2 = getDistance(trigPin2, echoPin2); // Đo cảm biến trong
  
  // Gửi số liệu khoảng cách trực tiếp định kỳ mỗi 2.5 giây cho màn hình LCD
  if (millis() - lastDistanceReport >= 2500) {
    lastDistanceReport = millis();
    Serial.printf(">> [LIVE] CB1: %.1f cm | CB2: %.1f cm\n", d1, d2);
    // Gửi qua UART để Mạch IOT_2 bắt và hiển thị
    Serial2.printf("DIST:%.1f,%.1f\n", d1, d2);
  }
  
  // --- Logic xe đi RA / NẰM DƯỚI CỔNG (Qua Cảm biến 2) ---
  bool trigger2 = (d2 < 20.0) || (baseline2 - d2 > THRESHOLD);
  
  // Cập nhật liên tục mốc thời gian nếu S2 đang có xe
  if (trigger2) {
    lastS2ClearTime = millis();
  }

  // --- Logic xe đi VÀO (Qua Cảm biến 1) ---
  // trigger1 là cờ báo có xe khi khoảng cách nhỏ hơn 20cm, HOẶC sụt giảm > ngưỡng 20cm so với nền
  bool trigger1 = (d1 < 20.0) || (baseline1 - d1 > THRESHOLD);
  
  // Điều kiện: 
  // 1. Có xe che (trigger1)
  // 2. Hệ thống chưa có xe trong trạm (!carInside)
  // 3. Xe trước đó đã vào quá 5 giây (chống nhiễu nhấp nháy)
  // 4. (MỚI) Cảm biến 2 đã hoàn toàn TRỐNG trải ít nhất 3.3 giây (Chống chụp ảnh khi xe trước chưa qua hẳn)
  if (trigger1 && !carInside && (millis() - lastCarInTime > 5000) && (millis() - lastS2ClearTime > 3300)) {
    carInside = true; // Xác nhận có xe đang đi vào
    lastCarInTime = millis();
    Serial.println(">> [SENS] XE VAO TRAM!");
    Serial2.println("CAR_IN"); // Báo qua UART cho IOT_2 để xử lý logic (như quẹt thẻ, đếm xe)
  }
  
  // Phần xử lý đóng cổng với Cảm biến 2
  if (trigger2 && carInside) {
    // Xe bắt đầu tiến sâu vào và chắn ngang Cảm biến 2 (Đang nằm ngay dưới thanh chắn Barie)
    if (!carAtGate) {
      carAtGate = true; // Bật cờ cảnh báo xe đang kẹt dưới cổng (rất quan trọng để khóa lệnh đóng cổng)
      Serial.println(">> [SENS] XE DANG NAM DUOI CONG...");
    }
    // LƯU Ý THUẬT TOÁN: Chừng nào xe vẫn đang che cảm biến 2, ta liên tục reset đồng hồ lastClearTime về hiện tại!
    lastClearTime = millis();
  } 
  else if (!trigger2 && carAtGate) {
    // TRƯỜNG HỢP: Khoảng cách d2 đã trở về nền bình thường (Cảm biến 2 báo trống, xe vừa thoát khỏi cổng)
    
    // THUẬT TOÁN ĐÓNG CỔNG TRỄ: Phải chờ ĐỦ 3 giây liên tục cảm biến trống thì mới được đóng!
    // Nếu trong vòng 3 giây này, thùng xe lùi lại che cảm biến, lastClearTime lập tức bị reset ở khối if bên trên.
    if (millis() - lastClearTime > 3000) { 
      carAtGate = false; // Xóa cờ kẹt cổng
      carInside = false; // Reset toàn bộ chu trình, sẵn sàng đón xe mới
      
      if (!isManualMode) { // Chỉ thực thi tự động nếu hệ thống không bị khóa bởi mở thủ công
        Serial.println(">> [SENS] XE DA QUA HOAN TOAN 3 GIAY! ĐONG CONG.");
        Serial2.println("CAR_OUT"); // Báo cho IOT_2 biết xe đã an toàn đi qua (để IOT_2 ra lệnh đóng hoặc cập nhật web)
      } else {
        // Nếu cổng bị mở bằng tay (nút/web), phải đợi người dùng đóng bằng tay, bỏ qua việc báo tự động đóng
        Serial.println(">> [SENS] XE DA QUA, NHUNG DANG MO THU CONG -> KHONG DONG TU DONG!");
      }
    }
  }
  
  delay(50); // Trễ một chút trong vòng lặp chính để giảm tải cho vi điều khiển ESP32
}