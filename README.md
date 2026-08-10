<<<<<<< HEAD
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
=======
# Hệ thống đo tốc độ với ESP32 và Cảm biến siêu âm

Dự án này sử dụng ESP32 cùng 2 cảm biến siêu âm (HC-SR04) để tính toán tốc độ của phương tiện, hiển thị lên màn hình LCD I2C và truyền thông tin vận tốc qua chuẩn giao tiếp I2C cho một ESP32 khác.

## Sơ đồ đấu nối

Dưới đây là sơ đồ đấu nối giữa ESP32 (Master) và các linh kiện ngoại vi:

```mermaid
graph LR
    subgraph ESP32_Master
        ESP32[ESP32 Board - Master]
    end

    subgraph Cảm biến
        CB1[Cảm biến Siêu âm 1<br/>Bên trái]
        CB2[Cảm biến Siêu âm 2<br/>Bên phải]
    end

    subgraph Hiển thị & Giao tiếp
        LCD[Màn hình LCD I2C<br/>16x2]
        BTN_START[Nút nhấn Bắt đầu]
        ESP32_Slave[ESP32 Board - Slave<br/>Địa chỉ: 0x08]
    end

    %% Kết nối CB1
    ESP32 -- GPIO 15 -->|Trig| CB1
    CB1 -- Echo -->|GPIO 4| ESP32

    %% Kết nối CB2
    ESP32 -- GPIO 18 -->|Trig| CB2
    CB2 -- Echo -->|GPIO 19| ESP32

    %% Kết nối LCD & Slave qua I2C
    ESP32 -- GPIO 22 -->|SCL| LCD
    ESP32 -- GPIO 21 -->|SDA| LCD
    ESP32 -- GPIO 22 -->|SCL| ESP32_Slave
    ESP32 -- GPIO 21 -->|SDA| ESP32_Slave
    
    %% Kết nối Nút bấm
    BTN_START -- Nhấn kéo GND -->|GPIO 26| ESP32
```

### Bảng tóm tắt các chân GPIO

| Linh kiện | Chân trên Linh kiện | Chân trên ESP32 | Ghi chú |
| :--- | :--- | :--- | :--- |
| **Cảm biến 1** | TRIG | `GPIO 15` | Phát xung siêu âm |
| | ECHO | `GPIO 4` | Nhận tín hiệu phản hồi |
| **Cảm biến 2** | TRIG | `GPIO 18` | Phát xung siêu âm |
| | ECHO | `GPIO 19` | Nhận tín hiệu phản hồi |
| **LCD I2C 16x2**| SDA | `GPIO 21` | I2C Data mặc định của ESP32 |
| | SCL | `GPIO 22` | I2C Clock mặc định của ESP32 |
| **ESP32 Slave**| SDA | `GPIO 21` | Chung bus I2C để nhận dữ liệu (Đ/c: `0x08`) |
| | SCL | `GPIO 22` | Chung bus I2C để nhận dữ liệu |
| **Nút nhấn** | Bắt đầu / Dừng đo | `GPIO 26` | Kéo GND khi nhấn (Sử dụng INPUT_PULLUP) |

*Lưu ý: Bạn phải nối chung chân GND giữa 2 mạch ESP32 nếu chúng dùng các nguồn điện khác nhau để bus I2C có thể hoạt động chính xác.*
>>>>>>> 0fe4cd981f049234ff1086e4dde977460c4ddbb5
