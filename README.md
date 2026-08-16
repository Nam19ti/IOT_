# HỆ THỐNG NHẬN DIỆN BIỂN SỐ TỰ ĐỘNG (ALPR) TÍCH HỢP IOT

> **Tóm tắt:** 
> Dự án này triển khai một giải pháp Trạm Thu Phí Thông minh ứng dụng Internet of Things (IoT) và Trí tuệ Nhân tạo (AI). Hệ thống sử dụng kiến trúc phân tán với 2 vi điều khiển ESP32 đảm nhiệm logic vật lý (Zero-Crash) và giao tiếp mạng cục bộ (LAN HTTP). Mô hình AI Lai (Hybrid AI) kết hợp giữa API Gemini-3.5-Flash (Cloud) và EasyOCR (Edge) đảm bảo khả năng đọc biển số tốc độ cao và tự động dự phòng khi mất mạng. Cơ sở dữ liệu và cảnh báo được đồng bộ hóa toàn diện qua MongoDB, Firebase Realtime Database và Telegram Bot.

---

## 1. ĐẶT VẤN ĐỀ VÀ MỤC TIÊU

### 1.1. Đặt vấn đề
Các hệ thống trạm thu phí truyền thống hoặc bãi giữ xe bán tự động thường gặp phải các hạn chế:
- **Lỗi cảm biến vật lý:** Barie hạ xuống khi xe chưa đi qua hết gây va chạm (Crash).
- **Độ trễ mạng IoT:** Sự phụ thuộc vào các giao thức trung gian như MQTT/ThingsBoard gây ra độ trễ lớn trong thao tác đóng mở cổng.
- **Tính liền mạch dữ liệu:** Không có cơ chế lưu trữ đệm khi hệ thống mất kết nối mạng Internet.

### 1.2. Mục tiêu giải quyết
- 🛡️ **Kiến trúc Zero-Crash:** Áp dụng thuật toán bảo vệ kép (Double Check) qua cảm biến siêu âm, ngăn chặn tuyệt đối việc barie hạ sớm.
- ⚡ **Giao tiếp LAN HTTP (Micro-latency):** Các vi điều khiển giao tiếp trực tiếp với Server thông qua HTTP RESTful API, giảm độ trễ xuống dưới 50ms.
- 🧠 **Hybrid AI & Offline Queue:** Chạy song song Cloud AI (độ chính xác cao) và Edge AI (dự phòng). Tích hợp `SyncManager` để lưu file đệm CSV (Offline Queue) tự động đồng bộ khi có mạng.

---

## 2. KIẾN TRÚC FILE CỦA TOÀN HỆ THỐNG

Dưới đây là sơ đồ kiến trúc thư mục chứa mã nguồn của toàn bộ dự án:

```text
IOT_ThangLong/
├── IOT_                 [Thư mục: Mạch 1 - ESP32 Master xử lý Vật lý]
│   └── IOT.ino          => Firmware điều khiển Servo, Còi báo, và Cảm biến siêu âm.
│
├── IOT_2                [Thư mục: Mạch 2 - ESP32 Slave xử lý Mạng]
│   └── IOT_2.ino        => Firmware chạy Web Server cục bộ & Giao tiếp Màn hình LCD I2C.
│
├── Python_ALPR          [Thư mục: Lõi xử lý Máy chủ (Backend + Web UI)]
│   ├── server.py        => Flask Web Server & API cốt lõi (Xử lý HTTP Trigger từ ESP32).
│   ├── ai.py            => AI Engine (Chạy Hybrid AI: Gemini API và EasyOCR).
│   ├── camera.py        => Bắt luồng ảnh tĩnh (Snapshot) từ IP Webcam (Smartphone).
│   ├── sync_manager.py  => Luồng nền (Background Thread) đồng bộ ảnh và dữ liệu lên Cloud.
│   ├── web_html.py      => Giao diện Bảng điều khiển người dùng (Web UI HTML/JS).
│   ├── core.py          => Quản lý trạng thái hệ thống và lưu cấu hình (Config).
│   ├── config.json      => File cấu hình tự sinh chứa các API Key và tùy chọn.
│   └── history/         => (Tự sinh) Thư mục lưu trữ ảnh và file CSV hàng đợi khi mất mạng.
│
└── README.md            => Tài liệu hướng dẫn sử dụng và mô tả hệ thống.
```

---

## 3. SƠ ĐỒ WORKFLOW TOÀN BỘ HỆ THỐNG

### 3.1. Workflow: Khi có xe tiến vào cổng (Quét Biển Số)
```text
[1. THIẾT BỊ VẬT LÝ]
   Cảm biến siêu âm 1 (Lối vào) đo thấy khoảng cách giảm mạnh so với nền.
         ↓
[2. MẠCH MASTER (IOT.ino)]
   Xác nhận có xe vào. Gửi tín hiệu UART "CAR_IN" sang Mạch Slave.
         ↓
[3. MẠCH SLAVE (IOT_2.ino)]
   Nhận tín hiệu UART. Ngay lập tức gọi API HTTP GET '/trigger_capture' tới Server.
         ↓
[4. MÁY CHỦ PYTHON (server.py + camera.py)]
   Server nhận HTTP request. Gọi 'CameraClient' lấy 1 khung hình sắc nét nhất từ Smartphone.
         ↓
[5. TRÍ TUỆ NHÂN TẠO (ai.py)]
   Chạy HybridOCR. Thử gọi Google Gemini (Cloud). 
   (Nếu rớt mạng, lập tức chuyển qua dùng EasyOCR Offline). Trích xuất ra biển số.
         ↓
[6. ĐỒNG BỘ ĐÁM MÂY (sync_manager.py)]
   Server gửi lệnh mở cổng về Mạch Slave.
   Song song đó, đưa biển số và ảnh vào Hàng Đợi (Queue). 
   Truy vấn MongoDB -> Lưu log lên Firebase -> Gửi thông báo Telegram cho người dùng.
         ↓
[7. THỰC THI (IOT.ino)]
   Mạch Slave nhận lệnh, ra lệnh qua UART cho Master nâng Barie (Mở cổng).
```

### 3.2. Workflow: Zero-Crash (Khi xe đi qua cổng)
```text
[1] Xe đang nằm ngang dưới cổng. Cảm biến 2 (Lối ra) bị che khuất.
[2] Mạch Master khóa chặt lệnh ĐÓNG CỔNG (Ngay cả khi người dùng cố tình bấm nút). Hú còi cảnh báo nếu có lệnh đóng.
[3] Xe vượt qua barie hoàn toàn. Cảm biến 2 báo trống.
[4] Master bắt đầu đếm ngược thời gian chờ an toàn: 3 GIÂY.
   - Nếu trong 3 giây này, xe lùi lại -> Hủy đếm ngược, khóa cổng tiếp!
[5] Hết 3 giây không có vật cản -> Master tự động hạ Barie.
[6] Master gửi tín hiệu "CAR_OUT" báo cho toàn hệ thống biết chu trình đã kết thúc.
```

---

## 4. SƠ ĐỒ ĐẤU NỐI PHẦN CỨNG (WIRING DIAGRAM)

Yêu cầu cấp nguồn 5V ổn định cho cả hai mạch. Khuyến nghị nối chung Ground (GND) giữa Mạch 1 và Mạch 2 để giao tiếp UART ổn định.

### 4.1. Mạch 1 (ESP32 Master - Vật lý)
| Linh kiện | Chân trên Linh kiện | Chân trên ESP32 |
| :--- | :--- | :--- |
| **Cảm biến 1 (Lối vào)** | TRIG | `GPIO 13` |
| | ECHO | `GPIO 12` |
| **Cảm biến 2 (Lối ra)** | TRIG | `GPIO 5` |
| | ECHO | `GPIO 18` |
| **Servo (Cổng Barie)** | PWM (Tín hiệu) | `GPIO 4` |
| **Buzzer (Còi)** | Tín hiệu | `GPIO 14` |
| **Nút bấm thủ công** | Một đầu | `GPIO 26` |
| | Đầu kia | `GND` |
| **Giao tiếp Mạch 2** | TX (Gửi) | `GPIO 17` |
| | RX (Nhận) | `GPIO 16` |

### 4.2. Mạch 2 (ESP32 Slave - Mạng & Hiển thị)
| Linh kiện | Chân trên Linh kiện | Chân trên ESP32 |
| :--- | :--- | :--- |
| **Giao tiếp Mạch 1** | TX (Gửi) | `GPIO 17` (Nối RX Mạch 1)|
| | RX (Nhận) | `GPIO 16` (Nối TX Mạch 1)|
| **Màn hình LCD I2C** | SDA | `GPIO 21` |
| | SCL | `GPIO 22` |
| | VCC | `5V` (Hoặc 3V3 tùy module) |

---

## 5. CÀI ĐẶT VÀ TRIỂN KHAI

### Bước 1: Mạng và Phần cứng
1. Phát WiFi từ Router hoặc Laptop với cấu hình bắt buộc:
   - Tên WiFi (SSID): `NONNET`
   - Mật khẩu: `abcd1234`
2. Cài đặt IP Tĩnh cho Laptop (Máy chủ) là: `192.168.137.1`.
3. Bật ứng dụng **IP Webcam** trên điện thoại Android, nhấn "Start server". (Ví dụ IP thu được là `http://192.168.137.233:8080`).

### Bước 2: Nạp Code ESP32
1. Mở Arduino IDE.
2. Cài đặt các thư viện cần thiết: `LiquidCrystal_I2C`, `ESP32Servo`.
3. Mở thư mục `IOT_`, nạp file `IOT.ino` vào Mạch 1.
4. Mở thư mục `IOT_2`, nạp file `IOT_2.ino` vào Mạch 2.

### Bước 3: Cài đặt Python Server
Yêu cầu: Môi trường Python 3.9+
```bash
# Di chuyển vào thư mục Server
cd Python_ALPR

# Tạo môi trường ảo (Khuyến nghị)
python -m venv venv
venv\Scripts\activate

# Cài đặt thư viện
pip install flask opencv-python easyocr google-generativeai requests pymongo
```

### Bước 4: Khởi động hệ thống
```bash
# Khởi chạy lõi xử lý
python server.py
```
- Truy cập vào **Bảng điều khiển Web (Dashboard)** tại địa chỉ: `http://localhost:5000` (hoặc `http://192.168.137.1:5000`).

---

## 6. HƯỚNG DẪN SỬ DỤNG

### Cấu hình Hệ thống trên Web
Giao diện điều khiển cung cấp một bảng cấu hình toàn diện. Lần đầu sử dụng, bạn cần nhập:
1. **URL Camera:** Link IP Webcam từ điện thoại (vd: `http://192.168.137.233:8080/video`).
2. **Mô hình AI:** Chọn `Hybrid (Gemini + EasyOCR)` (Yêu cầu điền Gemini API Key) hoặc `Offline (EasyOCR)`.
3. **Dịch vụ Đám mây:** 
   - Điền Telegram Bot Token.
   - Điền Chuỗi kết nối MongoDB (URI).
   - Điền Firebase URL (Dạng `https://xyz.firebaseio.com/`).
   *(Hệ thống hỗ trợ gạt Tắt/Bật từng dịch vụ độc lập).*

### Vận hành
- **Tự động:** Đưa phương tiện đi ngang qua cảm biến 1. Hệ thống sẽ tự động chụp ảnh, phân tích, đẩy dữ liệu lên đám mây, mở cổng và tự đóng cổng.
- **Thủ công:** Trên giao diện Web có nút **"Chụp & Nhận Diện"** để test riêng hệ thống AI, hoặc các nút **"Mở Cổng" / "Đóng Cổng"** để can thiệp vật lý trực tiếp xuống ESP32.

> **Lưu ý Căn chỉnh:** Lần đầu cắm điện, mạch Master sẽ nháy đèn và chạy đo đạc không gian xung quanh làm mẫu nền khoảng 2 giây. Xin vui lòng không đứng che cảm biến trong lúc này. Màn hình LCD sẽ báo `He thong SS` khi quá trình hoàn tất.
