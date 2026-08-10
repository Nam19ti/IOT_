# Hệ Thống IoT Đo Tốc Độ và Nhận Diện Biển Số Xe Bằng AI

Hệ thống IoT thông minh giúp phát hiện xe, đo tốc độ di chuyển và tự động chụp ảnh nhận diện biển số (ALPR) bằng Điện thoại (Smartphone). Dữ liệu được thu thập và đồng bộ lên nền tảng ThingsBoard thông qua giao thức MQTT siêu tốc.

---

## 🏗️ Kiến Trúc Hệ Thống

Hệ thống sử dụng cảm biến siêu âm để đo tốc độ, truyền dữ liệu qua UART và MQTT. Hình ảnh được xử lý nét căng bằng Smartphone và gửi lên PC chạy AI.

1. **Master ESP32 (`IOT.ino`)**: 
   - Đo tốc độ từ 2 cảm biến siêu âm.
   - Gắn ID định danh cho mỗi lượt xe và gửi qua UART cho Slave.
   
2. **Slave ESP32 (`IOT_2.ino`)**: 
   - Đóng vai trò là "MQTT Router".
   - Nhận Tốc độ + ID từ UART và bắn ngay lập tức lên MQTT (HiveMQ).

3. **Smartphone Camera (IP Webcam / DroidCam)**:
   - Dùng làm Camera chụp ảnh sắc nét (Full HD) kết nối trực tiếp với Máy tính thông qua cáp USB (Tethering).

4. **Python Server (`alpr_server.py`)**:
   - Lắng nghe Tốc độ từ HiveMQ.
   - Nhận được tốc độ -> Kích hoạt Smartphone chụp ảnh -> Chạy AI (EasyOCR) nhận diện biển số.
   - Đẩy dữ liệu hoàn chỉnh lên ThingsBoard.

---

## 🔌 Sơ Đồ Đấu Nối Phần Cứng

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
        ESP32_Slave[ESP32 Board - Slave]
    end

    %% Kết nối CB1
    ESP32 -- GPIO 15 -->|Trig| CB1
    CB1 -- Echo -->|GPIO 4| ESP32

    %% Kết nối CB2
    ESP32 -- GPIO 18 -->|Trig| CB2
    CB2 -- Echo -->|GPIO 19| ESP32

    %% Kết nối LCD qua I2C
    ESP32 -- GPIO 22 -->|SCL| LCD
    ESP32 -- GPIO 21 -->|SDA| LCD
    
    %% Kết nối Giao tiếp UART (Master -> Slave)
    ESP32 -- GPIO 17 -->|TX2 sang RX2| ESP32_Slave
    
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
| **LCD I2C 16x2**| SDA | `GPIO 21` | I2C Data mặc định của ESP32 Master |
| | SCL | `GPIO 22` | I2C Clock mặc định của ESP32 Master |
| **ESP32 Slave** | RX2 | `GPIO 16` | Nối vào chân TX2 (17) của Master để nhận tốc độ |
| **Nút nhấn** | Bắt đầu / Dừng đo | `GPIO 26` | Kéo GND khi nhấn (Sử dụng INPUT_PULLUP) |

*Lưu ý: Bạn phải nối chung chân GND giữa mạch Master và mạch Slave.*

---

## 🚀 Hướng Dẫn Chạy Hệ Thống

### Bước 1: Nạp Code cho 2 mạch ESP
- Mở Arduino IDE.
- Nạp `IOT.ino` cho mạch Master.
- Điền WiFi của bạn vào `IOT_2.ino` và nạp cho mạch Slave.

### Bước 2: Thiết Lập Camera Điện Thoại
- Dùng dây USB cắm điện thoại vào máy tính, bật "Chia sẻ mạng qua USB (Tethering)".
- Mở App **IP Webcam** trên điện thoại, ấn **Start Server**. Ghi nhớ đường link IP hiện ra (VD: `http://192.168.42.129:8080`).

### Bước 3: Cấu Hình Python Server
Mở file `alpr_server.py` trong thư mục `Python_ALPR`:
- Cập nhật dòng `IP_WEBCAM_URL = "http://192.168.42.129:8080/photo.jpg"` bằng link của bạn.
- Đảm bảo `TB_TOKEN` đã đúng.

Chạy lệnh để cài đặt thư viện:
```bash
pip install opencv-python numpy easyocr paho-mqtt requests
```

Khởi động Server:
```bash
python alpr_server.py
```

### Bước 4: Vận Hành
Quẹt tay qua 2 cảm biến siêu âm. Mạch Master sẽ tính tốc độ -> truyền cho Slave -> Slave báo qua WiFi về Python -> Python tự động lấy ảnh nét từ điện thoại -> Nhận diện chữ -> Cập nhật lên web!

---

## 📁 Cấu Trúc Thư Mục
- `/IOT_/` : Chứa code của Master ESP32.
- `/IOT_2/`: Chứa code của Slave ESP32 MQTT Router.
- `/Python_ALPR/`: Chứa file mã nguồn chạy AI (`alpr_server.py`).
- `/archive/`: Thư mục lưu trữ mớ hỗn độn ESP32-CAM cũ.
