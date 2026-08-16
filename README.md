# TRAM THU PHI VETC - ALPR SYSTEM
**Hệ thống Nhận diện Biển số Tự động (ALPR) cho Trạm Thu Phí với Kiến trúc Zero-Crash và 100% LAN HTTP**

---

## 1. TỔNG QUAN DỰ ÁN
Dự án **Trạm Thu Phí VETC** là một giải pháp nhận diện biển số xe thông minh và an toàn, được thiết kế đặc biệt với:
- **Kiến trúc Zero-Crash (Chống sập barie):** Thuật toán bảo vệ kép "Double Check", đảm bảo tuyệt đối cổng không đóng khi vẫn còn xe ở dưới, loại bỏ hoàn toàn hiện tượng nhiễu cảm biến gây tai nạn.
- **Xử lý Offline 100%:** Sử dụng mô hình nhận diện EasyOCR chạy hoàn toàn nội bộ trên máy chủ Python, không phụ thuộc vào Internet hay Cloud API (Bỏ Gemini).
- **Mạng LAN HTTP Tốc độ cao:** Loại bỏ hoàn toàn độ trễ của MQTT/ThingsBoard. ESP32 kết nối trực tiếp với Python Server qua các HTTP Request cục bộ, cho độ trễ < 50ms.
- **Camera Chuyên dụng (ESP32-CAM):** Thay thế Smartphone bằng module ESP32-CAM (OV2640) với cấu hình phân giải cao nhất (UXGA 1600x1200) được tinh chỉnh phần cứng để nhận diện biển số sắc nét.

---

## 2. KIẾN TRÚC HỆ THỐNG
Hệ thống gồm 3 module phần cứng và 1 phần mềm trung tâm, liên kết với nhau qua mạng LAN (WiFi `NONNET`):

### 2.1. Module Điều Khiển Vật Lý (Mạch 1 - ESP32 Master)
*Thư mục: `IOT_`*
- **Chức năng:** Trực tiếp điều khiển Động cơ Servo (Cổng barie), Còi cảnh báo (Buzzer), Nút bấm khẩn cấp và đọc dữ liệu từ 2 cảm biến siêu âm (HC-SR04).
- **Logic:** Chịu trách nhiệm hoàn toàn về tính năng **Zero-Crash**. Gửi dữ liệu trạng thái xe sang Mạch 2 qua đường truyền Serial (UART).

### 2.2. Module Giao Tiếp Mạng (Mạch 2 - ESP32 Slave)
*Thư mục: `IOT_2`*
- **Chức năng:** Đóng vai trò làm cầu nối (Bridge) giữa phần cứng và máy chủ. Nhận dữ liệu UART từ Mạch 1 và bắn tín hiệu HTTP (`/trigger_capture`) lên Python Server. 
- **Điều khiển ngược:** Mở cổng Web Server cục bộ (Port 80) tại IP tĩnh `192.168.137.199` để nhận lệnh mở/đóng cổng khẩn cấp từ giao diện Web.
- **Hiển thị:** Quản lý màn hình LCD I2C hiển thị thông báo.

### 2.3. Module Thu Ảnh (ESP32-CAM)
*Thư mục: `ESP32_CAM`*
- **Chức năng:** Camera độc lập với IP tĩnh `192.168.137.233`. Chạy web server cung cấp luồng ảnh `/photo.jpg` chất lượng cao với cấu hình chống lóa, khử nhiễu tự động.

### 2.4. Máy Chủ Trí Tuệ Nhân Tạo (Python Server)
*Thư mục: `Python_ALPR`*
- **Chức năng:** Trái tim của hệ thống. Chạy ứng dụng Web Flask. Khi nhận lệnh từ Mạch 2, máy chủ sẽ tải ảnh từ ESP32-CAM và chạy AI (EasyOCR) để nhận diện biển số. 
- **Dashboard:** Cung cấp giao diện trực quan cho nhân viên kiểm soát. 
- **Cloudflare Tunnel:** Tự động tạo đường hầm để truy cập Dashboard từ bất kỳ đâu trên Internet mà không cần mở Port rườm rà.

---

## 3. SƠ ĐỒ ĐẤU NỐI (WIRING DIAGRAM)

### 3.1. Mạch 1 (ESP32 Master)
- **Cảm biến 1 (Lối vào):** TRIG `GPIO 13` | ECHO `GPIO 12`
- **Cảm biến 2 (Lối ra):** TRIG `GPIO 5`  | ECHO `GPIO 18`
- **Servo (Barie):** PWM `GPIO 4`
- **Còi (Buzzer):** `GPIO 14`
- **Nút bấm thủ công:** `GPIO 26` (Nối với GND)
- **UART (Sang Mạch 2):** TX `GPIO 17` | RX `GPIO 16` (Nhớ nối chung GND)

### 3.2. Mạch 2 (ESP32 Slave)
- **UART (Từ Mạch 1):** TX `GPIO 17` | RX `GPIO 16`
- **Màn hình LCD I2C:** SDA `GPIO 21` | SCL `GPIO 22`

---

## 4. WORKFLOW VẬN HÀNH

1. **Khởi động:** Python Server tải model AI (EasyOCR) vào RAM (mất ~30s-1p). Mạch 1 chạy Calibration đo khoảng cách nền (Tường đối diện).
2. **Xe tiến vào:** Cảm biến 1 phát hiện có xe. Mạch 1 tự động mở cổng (Servo quay), kêu tít tít. 
3. **Chụp ảnh:** Mạch 1 truyền UART báo Mạch 2. Mạch 2 bắn HTTP Get tới Python Server (`/trigger_capture`). Python Server gọi IP của ESP32-CAM tải ảnh.
4. **Xử lý AI:** Python Server đưa ảnh vào EasyOCR, trả về chuỗi Biển số và cập nhật Dashboard.
5. **Xe đi qua cổng:** Xe chạm Cảm biến 2. Mạch 1 ghi nhận trạng thái `carAtGate = true`.
6. **Đóng cổng an toàn:** Khi xe đi khỏi Cảm biến 2, mạch 1 chờ thêm 3 giây, kiểm tra lại Cảm biến 2 một lần nữa (Double Check) để chắc chắn vùng không gian đã trống, sau đó mới hạ barie.

---

## 5. HƯỚNG DẪN KHỞI ĐỘNG (QUICK START)
1. Bật mạng WiFi trên Laptop/Router với tên: `NONNET` - Pass: `abcd1234`. Đặt IP máy tính tĩnh thành `192.168.137.1`.
2. Cấp nguồn cho cả 3 vi điều khiển (Mạch 1, Mạch 2, ESP32-CAM).
3. Mở Terminal vào thư mục `Python_ALPR`:
   ```bash
   venv\Scripts\activate
   python server.py
   ```
4. Giao diện quản lý nội bộ sẽ mở tại `http://localhost:5000`. Một đường link Cloudflare công khai (Vd: `https://abcd-xyz.trycloudflare.com`) cũng sẽ được in ra console để xem từ xa.

