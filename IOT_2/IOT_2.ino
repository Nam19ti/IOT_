#include <HardwareSerial.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// =========================================================
// CẤU HÌNH WIFI VÀ LAN
// =========================================================
const char* WIFI_SSID     = "NONNET";
const char* WIFI_PASSWORD = "abcd1234";

// IP của máy tính chạy Server Python
// Máy tính này sẽ chịu trách nhiệm nhận diện biển số và xử lý logic trừ tiền
const char* PYTHON_SERVER_IP = "192.168.137.1"; // <-- Thay bằng IP máy tính của bạn nếu cần
const int   PYTHON_SERVER_PORT = 5000;

// =========================================================
// CẤU HÌNH IP TĨNH CHO IOT_2 (ESP32)
// Đảm bảo ESP32 luôn nhận một IP cố định để Server Python và các thiết bị khác dễ dàng giao tiếp
// =========================================================
IPAddress local_IP(192, 168, 137, 199);
IPAddress gateway(192, 168, 137, 1);
IPAddress subnet(255, 255, 255, 0);
IPAddress primaryDNS(8, 8, 8, 8);

// Khởi tạo WebServer lắng nghe ở cổng 80 (cổng HTTP mặc định)
WebServer server(80);

// Khởi tạo đối tượng màn hình LCD I2C với địa chỉ 0x27, loại 16 cột 2 dòng
LiquidCrystal_I2C lcd(0x27, 16, 2);

// Định nghĩa các chân UART2 để giao tiếp dữ liệu với IOT_1 (Mạch 1)
#define UART2_TX 17
#define UART2_RX 16

// =========================================================
// HÀM HIỂN THỊ LCD
// =========================================================
// Hàm này có nhiệm vụ xóa màn hình và in 2 dòng văn bản mới lên màn hình LCD
// Đồng thời in log ra Serial để tiện theo dõi quá trình chạy
void printLCD(String line1, String line2) {
  lcd.clear(); // Xóa sạch dữ liệu cũ trên màn hình
  lcd.setCursor(0, 0); lcd.print(line1); // Đặt con trỏ ở đầu dòng 1 và in nội dung
  lcd.setCursor(0, 1); lcd.print(line2); // Đặt con trỏ ở đầu dòng 2 và in nội dung
  Serial.println(">> LCD: [" + line1 + "] | [" + line2 + "]"); // Ghi log ra cổng Serial
}

// =========================================================
// KẾT NỐI WIFI
// =========================================================
unsigned long lastWifiAttempt = 0; // Lưu thời điểm cuối cùng thử kết nối WiFi
bool isNetworkOffline = true;      // Cờ đánh dấu trạng thái mạng (true = mất mạng, false = có mạng)

// Hàm kiểm tra và duy trì kết nối WiFi
// Nếu mất kết nối, hệ thống sẽ tự động thử kết nối lại sau mỗi 5 giây
void checkWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    // Nếu WiFi đã kết nối và trước đó đang ở trạng thái mất mạng
    if (isNetworkOffline) {
      printLCD("He thong SS", "IP: " + WiFi.localIP().toString()); // Hiển thị IP lên LCD
      isNetworkOffline = false; // Đánh dấu là đã có mạng
    }
    return; // Thoát hàm nếu mạng vẫn ổn định
  }

  isNetworkOffline = true; // Đánh dấu trạng thái mất mạng
  // Kiểm tra nếu đã trôi qua 5 giây kể từ lần thử kết nối cuối cùng
  if (millis() - lastWifiAttempt > 5000) {
    lastWifiAttempt = millis(); // Cập nhật thời điểm thử kết nối
    printLCD("!! CANH BAO !!", "MAT MANG WIFI"); // Báo lỗi lên màn hình LCD
    Serial.println(">> Đang thử kết nối lại WiFi...");
    WiFi.disconnect(); // Ngắt kết nối hiện tại để làm mới
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD); // Yêu cầu kết nối lại với SSID và Password đã cấu hình
  }
}

// =========================================================
// LẮNG NGHE LỆNH TỪ PYTHON SERVER (Qua Mạng LAN)
// =========================================================

// Hàm xử lý khi có request GET đến endpoint /open_gate
// Python server sẽ gọi hàm này khi xe được nhận diện thành công và tài khoản đủ tiền
void handleOpenGate() {
  // URL format mong đợi: http://<IOT2_IP>/open_gate?plate=30A12345
  
  String plate = "Chua ro"; // Biến lưu biển số xe
  // Kiểm tra xem trong request có chứa tham số "plate" không
  if (server.hasArg("plate")) {
    plate = server.arg("plate"); // Lấy giá trị biển số xe từ request
  }

  printLCD(plate, "XE QUEN-MO CONG"); // Hiển thị thông báo xe hợp lệ lên LCD
  Serial2.println("OPEN"); // Gửi lệnh "OPEN" qua UART2 cho IOT_1 để điều khiển Servo mở cổng
  
  // Trả về phản hồi cho Python Server biết đã xử lý thành công
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "text/plain", "OK! Da mo cong.");
}

// Hàm xử lý mở cổng thủ công, không tự động đóng
void handleOpenGateManual() {
  // Mở cổng nhưng KHÔNG cho phép tự động đóng (dùng cho trường hợp khẩn cấp hoặc bảo trì)
  printLCD("Mo thu cong", "Khong tu dong");
  Serial2.println("OPEN_MANUAL"); // Gửi lệnh mở cổng thủ công sang IOT_1
  
  // Phản hồi về cho client gọi API
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "text/plain", "OK! Da mo cong thu cong.");
}

// Hàm xử lý đóng cổng thủ công
void handleCloseGate() {
  // Đóng cổng thủ công từ xa thông qua lệnh HTTP
  printLCD("Dong thu cong", "He thong SS");
  Serial2.println("CLOSE"); // Gửi lệnh đóng cổng sang IOT_1
  
  // Phản hồi trạng thái thành công
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "text/plain", "OK! Da dong cong thu cong.");
}

// Hàm xử lý từ chối mở cổng
// Python server gọi endpoint này khi xe lạ hoặc nằm trong danh sách đen
void handleDenyGate() {
  String plate = "Chua ro";
  // Trích xuất thông tin biển số xe từ request nếu có
  if (server.hasArg("plate")) {
    plate = server.arg("plate");
  }

  printLCD(plate, "XE LA/TU CHOI"); // Cảnh báo từ chối phục vụ trên màn hình LCD
  // Gửi phản hồi HTTP 200 OK để xác nhận đã nhận được lệnh
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send(200, "text/plain", "OK! Da hien thi canh bao.");
}

// =========================================================
// SETUP
// =========================================================
// Hàm setup chỉ chạy một lần duy nhất khi vi điều khiển khởi động
void setup() {
  Serial.begin(115200); // Khởi tạo UART0 để debug qua USB với baudrate 115200
  // Khởi tạo UART2 để giao tiếp nối tiếp với IOT_1. Sử dụng chuẩn 8N1, chân RX=16, TX=17
  Serial2.begin(115200, SERIAL_8N1, 16, 17); 
  
  lcd.init();       // Khởi tạo màn hình LCD
  lcd.backlight();  // Bật đèn nền LCD
  printLCD("Khoi dong", "Bai Do Xe Slave"); // Hiển thị thông báo khởi động

  // Cài đặt IP Tĩnh cho hệ thống mạng trước khi bắt đầu kết nối WiFi
  if (!WiFi.config(local_IP, gateway, subnet, primaryDNS, primaryDNS)) {
    Serial.println(">> Lỗi cấu hình IP Tĩnh!"); // Cảnh báo nếu cấu hình IP thất bại
  }

  // Khởi chạy tiến trình kết nối WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  // Gắn các đường dẫn API tương ứng với các hàm xử lý
  server.on("/open_gate", HTTP_GET, handleOpenGate);
  server.on("/open_gate_manual", HTTP_GET, handleOpenGateManual);
  server.on("/close_gate", HTTP_GET, handleCloseGate);
  server.on("/deny_gate", HTTP_GET, handleDenyGate);
  
  // Bắt đầu chạy WebServer
  server.begin();
}

// =========================================================
// LOOP
// =========================================================
// Hàm loop chạy liên tục vô hạn trong suốt quá trình hoạt động của mạch
void loop() {
  checkWiFi(); // Liên tục kiểm tra và duy trì kết nối WiFi
  server.handleClient(); // Xử lý các request HTTP gửi đến WebServer (nếu có)

  // NHẬN SỰ KIỆN TỪ MẠCH 1 (CẢM BIẾN/SERVO HUB) QUA GIAO TIẾP SERIAL2
  if (Serial2.available()) {
    // Đọc một dòng dữ liệu (kết thúc bằng ký tự '\n') từ IOT_1
    String msg = Serial2.readStringUntil('\n');
    msg.trim(); // Loại bỏ khoảng trắng hoặc ký tự xuống dòng dư thừa ở 2 đầu chuỗi
    
    // Nếu IOT_1 gửi sự kiện có xe tiến vào (cảm biến phát hiện)
    if (msg == "CAR_IN") {
      printLCD("Xe vao", "Cho nhan dien"); // Hiển thị thông báo đang chờ nhận diện
      
      // Nếu có mạng WiFi, gửi HTTP GET sang Python Server để yêu cầu chụp ảnh và nhận diện
      if (WiFi.status() == WL_CONNECTED) {
        HTTPClient http;
        // Xây dựng chuỗi URL gọi đến Python Server
        String url = "http://" + String(PYTHON_SERVER_IP) + ":" + String(PYTHON_SERVER_PORT) + "/trigger_capture";
        http.begin(url); // Khởi tạo kết nối HTTP
        int httpCode = http.GET(); // Thực hiện gọi GET request
        
        // Nếu HTTP code > 0 tức là có phản hồi từ Server
        if (httpCode > 0) {
          String payload = http.getString(); // Lấy dữ liệu phản hồi (thường là chuỗi JSON)
          Serial.printf(">> Python (Code: %d): %s\n", httpCode, payload.c_str()); // In log debug
          
          // XỬ LÝ CHUỖI JSON ĐƠN GIẢN KHÔNG DÙNG THƯ VIỆN
          // Tìm vị trí của từ khóa "plate" trong chuỗi JSON phản hồi
          int pIdx = payload.indexOf("\"plate\":\"");
          if (pIdx == -1) pIdx = payload.indexOf("\"plate\": \""); // Fallback: tìm theo format có dấu cách
          
          // Nếu tìm thấy key "plate"
          if (pIdx > 0) {
            // Xác định vị trí bắt đầu của chuỗi giá trị biển số
            int startIdx = pIdx + (payload.indexOf("\"plate\":\"") != -1 ? 9 : 10);
            // Xác định vị trí kết thúc của chuỗi giá trị (dấu ngoặc kép đóng)
            int endIdx = payload.indexOf("\"", startIdx);
            // Cắt chuỗi để lấy đúng biển số xe
            String plate = payload.substring(startIdx, endIdx);
            
            // Xử lý logic dựa trên kết quả nhận diện
            if (plate == "Khong Nhan Dien Duoc" || plate == "Khong Thay Bien" || plate == "") {
              // Lỗi nhận diện hoặc không thấy biển
              printLCD("Loi Nhan Dien", "Vui long thu lai");
            } else {
              // Nhận diện thành công, giả định xe quen và cho mở cổng
              printLCD(plate, "XE QUEN-MO CONG");
              Serial2.println("OPEN"); // Lệnh qua IOT_1 mở cổng
            }
          }
        } else {
          // Lỗi không kết nối được tới Python Server
          Serial.printf(">> LỖI KẾT NỐI PYTHON SERVER: %s\n", http.errorToString(httpCode).c_str());
          printLCD("Loi Mang LAN", "Khong thay Server");
        }
        http.end(); // Đóng kết nối HTTP để giải phóng tài nguyên
      }
    } 
    // Nếu IOT_1 báo xe đã đi qua hoàn toàn
    else if (msg == "CAR_OUT") {
      // Vì mạch 1 đã có 3s chống kẹt an toàn, ta chỉ cần xuất lệnh đóng
      Serial2.println("CLOSE"); 
    }
    // Xử lý các tin nhắn báo trạng thái từ IOT_1
    else if (msg.startsWith("STATE:")) {
      String state = msg.substring(6); // Lấy phần trạng thái đằng sau chữ "STATE:"
      if (state == "OPEN") {
        // Chỉ ghi trạng thái Cổng Mở
        printLCD("CONG MO", ""); 
      } else if (state == "CLOSED") {
        // Ghi trạng thái Cổng Đóng và Hệ thống sẵn sàng
        printLCD("CONG DONG", "He thong SS");
      } else if (state == "CALIBRATING") {
        // Hệ thống đang đo nền khởi tạo cảm biến
        printLCD("Dang do nen...", "Tranh xa CB!");
      }
    }
    // Nhận thông tin khoảng cách trực tiếp từ các cảm biến siêu âm của IOT_1
    // (Bỏ phần hiển thị khoảng cách DIST ra LCD để tránh rối mắt, chỉ giữ lại trên Serial nếu cần)
    else if (msg.startsWith("DIST:")) {
      String data = msg.substring(5); // Dữ liệu có dạng "KhoangCach1,KhoangCach2"
      int commaIndex = data.indexOf(','); // Tìm vị trí dấu phẩy phân cách
      if (commaIndex > 0) {
        // In trực tiếp ra cổng Serial để debug thời gian thực
        Serial.println(">> [LIVE] CB1: " + data.substring(0, commaIndex) + "cm | CB2: " + data.substring(commaIndex + 1) + "cm");
      }
    }
  }
}
