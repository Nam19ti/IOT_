# Hệ Thống IoT Đo Tốc Độ và Nhận Diện Biển Số Xe Bằng AI

Hệ thống IoT thông minh giúp phát hiện xe, đo tốc độ di chuyển và tự động chụp ảnh nhận diện biển số (ALPR). Dữ liệu được thu thập và đồng bộ lên nền tảng ThingsBoard thông qua giao thức MQTT siêu tốc.

---

## 🏗️ Kiến Trúc Hệ Thống (Giao thức 100% MQTT)

Hệ thống được chia làm 4 thành phần độc lập, kết nối với nhau hoàn toàn bằng giao thức MQTT (thông qua broker công cộng siêu nhanh `broker.hivemq.com`), giúp giải quyết triệt để vấn đề độ trễ và tránh xung đột khi có nhiều xe đi qua cùng lúc.

1. **Master ESP32 (`IOT.ino`)**: 
   - Đảm nhiệm việc giao tiếp với các cảm biến siêu âm.
   - Tính toán tốc độ, hướng di chuyển.
   - Gắn ID định danh cho mỗi lượt xe và gửi qua UART cho Slave.
   
2. **Slave ESP32 (`IOT_2.ino`)**: 
   - Đóng vai trò là "MQTT Router" siêu nhẹ.
   - Nhận Tốc độ + ID từ UART và bắn ngay lập tức lên MQTT (HiveMQ) cho Python.
   - Bắn lệnh Trigger (Chụp ảnh) lên MQTT để kích hoạt Camera.

3. **ESP32-CAM (`ESP32_CAM.ino`)**:
   - Lắng nghe lệnh Trigger từ MQTT.
   - Nhận lệnh -> Chụp ảnh -> Gửi nguyên bức ảnh (Raw Bytes) lên MQTT để Python xử lý.

4. **Python Server (`alpr_server.py`)**:
   - Là "Não bộ" trung tâm của hệ thống.
   - Đăng ký nhận (Subscribe) Tốc độ và Ảnh từ HiveMQ.
   - Chạy AI (EasyOCR) để trích xuất biển số từ ảnh.
   - Ghép biển số với tốc độ dựa trên ID, sau đó đẩy dữ liệu hoàn chỉnh lên ThingsBoard.

---

## 🔌 Hướng Dẫn Đấu Nối Phần Cứng

**1. Mạch Master ESP32:**
- Cảm biến 1 (CB1): TRIG = `15`, ECHO = `4`
- Cảm biến 2 (CB2): TRIG = `18`, ECHO = `19`
- Màn hình LCD I2C: SDA = `21`, SCL = `22`
- Nút bấm (Start/Stop): `26` (Nối với GND qua điện trở Pull-up hoặc dùng Internal Pull-up).
- Dây truyền dữ liệu sang Slave (UART2 TX): Chân `17` (Nối vào chân `16` của Slave).

**2. Mạch Slave ESP32:**
- Nhận dữ liệu (UART2 RX): Chân `16` (Nối vào chân `17` của Master).
- *Lưu ý:* Phải nối chung chân GND giữa mạch Master và mạch Slave.

**3. Mạch ESP32-CAM:**
- Chỉ cần cắm nguồn 5V và GND. Không cần đấu nối thêm dây tín hiệu nào với các mạch khác (kết nối hoàn toàn qua WiFi/MQTT).

---

## 🚀 Hướng Dẫn Chạy Hệ Thống

### Bước 1: Nạp Code cho các mạch ESP
- Mở Arduino IDE, cài đặt đầy đủ các thư viện: `LiquidCrystal_I2C`, `PubSubClient`, `esp32_camera`.
- Mở file `IOT_2.ino` và `ESP32_CAM.ino`, điền thông tin WiFi của bạn (`WIFI_SSID` và `WIFI_PASSWORD`).
- Nạp code vào 3 bo mạch tương ứng.

### Bước 2: Cấu Hình Python Server
Máy tính của bạn cần cài đặt Python. Mở Command Prompt (CMD) và chạy lệnh sau để tải các thư viện AI:
```bash
pip install flask opencv-python numpy easyocr paho-mqtt requests
```

Mở file `alpr_server.py` trong thư mục `Python_ALPR`, tìm đến dòng `TB_TOKEN` và thay bằng Token thiết bị của bạn trên ThingsBoard:
```python
TB_TOKEN = "GkUmbnN2vDPBljtNCKfo"
```

### Bước 3: Vận Hành
- Cấp điện cho 3 mạch ESP32.
- Trên máy tính, di chuyển vào thư mục `Python_ALPR` và chạy lệnh khởi động server:
  ```bash
  python alpr_server.py
  ```
- Khi màn hình CMD báo **"Đã kết nối HiveMQ và đang trực ban lắng nghe MQTT..."**, bạn quẹt tay qua 2 cảm biến siêu âm.
- Hệ thống sẽ tự động bắt đầu quy trình: Đo tốc độ -> Báo Slave -> Kích hoạt CAM -> Python nhận ảnh -> OCR ra biển số -> Publish lên ThingsBoard.

---

## 📁 Cấu Trúc Thư Mục
- `/IOT_/` : Chứa code của Master ESP32 (`IOT.ino`).
- `/IOT_2/`: Chứa code của Slave ESP32 MQTT Router (`IOT_2.ino`).
- `/ESP32_CAM/`: Chứa code của Camera (`ESP32_CAM.ino`).
- `/Python_ALPR/`: Chứa file mã nguồn chạy AI (`alpr_server.py`).
