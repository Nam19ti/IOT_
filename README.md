# HỆ THỐNG NHẬN DIỆN BIỂN SỐ TỰ ĐỘNG (ALPR) TÍCH HỢP IOT

> **Tóm tắt:** 
> Dự án này triển khai một giải pháp Trạm Thu Phí Thông minh ứng dụng Internet of Things (IoT) và Trí tuệ Nhân tạo (AI). Hệ thống sử dụng kiến trúc phân tán với 2 vi điều khiển ESP32 đảm nhiệm logic vật lý (Zero-Crash) và giao tiếp mạng cục bộ (LAN HTTP). Mô hình AI Lai (Hybrid AI) kết hợp giữa API Gemini-3.5-Flash (Cloud via SDK google-genai) và EasyOCR (Edge) đảm bảo khả năng đọc biển số tốc độ cao và tự động dự phòng khi mất mạng. Hệ thống trang bị màn hình đăng nhập bảo mật, Bảng điều khiển Web UI mượt mà hỗ trợ chỉnh vùng ROI (Drag/Resize), Dashboard tách biệt Lịch sử Cloud & Hàng đợi Offline, cùng khả năng đồng bộ hóa qua MongoDB, Firebase Realtime Database và Telegram Bot.

---

## 1. ĐẶT VẤN ĐỀ VÀ MỤC TIÊU

### 1.1. Đặt vấn đề
Các hệ thống trạm thu phí truyền thống hoặc bãi giữ xe bán tự động thường gặp phải các hạn chế:
- **Lỗi cảm biến vật lý:** Barie hạ xuống khi xe chưa đi qua hết gây va chạm (Crash).
- **Độ trễ mạng IoT:** Sự phụ thuộc vào các giao thức trung gian như MQTT/ThingsBoard gây ra độ trễ lớn trong thao tác đóng mở cổng.
- **Tính liền mạch dữ liệu:** Không có cơ chế lưu trữ đệm khi hệ thống mất kết nối mạng Internet.

### 1.2. Mục tiêu giải quyết
- 🛡️ **Kiến trúc Zero-Crash:** Áp dụng thuật toán bảo vệ kép (Double Check) qua cảm biến siêu âm, ngăn chặn tuyệt đối việc barie hạ sớm khi phương tiện đang dừng/di chuyển qua cổng.
- ⚡ **Giao tiếp LAN HTTP (Micro-latency):** Các vi điều khiển giao tiếp trực tiếp với Server thông qua HTTP RESTful API, giảm độ trễ xuống dưới 50ms.
- 🧠 **Hybrid AI (Google GenAI & EasyOCR):** Chạy song song Cloud AI (Gemini 3.5 Flash / 2.5 Flash qua SDK `google-genai` mới nhất) và Edge AI (EasyOCR). Tích hợp `SyncManager` tự động lưu bản ghi vào `history` MongoDB và lưu file đệm CSV (`pending_sync.csv`) khi rớt mạng.
- 🔒 **Bảo mật & Trải nghiệm Web UI:** Trang đăng nhập Session Admin, tùy chỉnh vùng nhận diện ROI (Kéo di chuyển & Thu phóng trực tiếp với núm đỏ), Dashboard phân 4 Tab dữ liệu chuẩn xác, xử lý xe lạ xóa hàng loạt tức thì trên DOM.
- 🌐 **Cloudflare Tunnel & Remote Control:** Tự động mở luồng truy cập Public qua Cloudflare và gửi link truy cập từ xa trực tiếp về Telegram Admin.

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
│   ├── server.py        => Flask Web Server & API cốt lõi (Xử lý Trigger từ ESP32, Login, Tunnel).
│   ├── ai.py            => AI Engine (Hybrid AI: Google GenAI SDK & EasyOCR Offline).
│   ├── camera.py        => Bắt luồng ảnh tĩnh (Snapshot) từ IP Webcam (Smartphone).
│   ├── sync_manager.py  => Luồng nền (Background Worker) đồng bộ dữ liệu MongoDB, Firebase, Telegram.
│   ├── web_html.py      => Giao diện Bảng điều khiển người dùng (Web UI HTML/JS + Session Login).
│   ├── core.py          => Quản lý trạng thái hệ thống và lưu cấu hình (Config).
│   ├── cloud.py         => Module kết nối Firebase Realtime Database.
│   ├── config.json      => File cấu hình tự sinh chứa các API Key, Token và Tùy chỉnh.
│   └── history/         => Thư mục đệm chứa nhật ký, ảnh vi phạm và file đệm CSV pending_sync.
│
└── README.md            => Tài liệu hướng dẫn sử dụng và mô tả hệ thống chi tiết.
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
pip install flask opencv-python easyocr google-genai google-generativeai requests pymongo
```

### Bước 4: Khởi động hệ thống
```bash
# Khởi chạy lõi xử lý
python server.py
```
- Truy cập vào **Bảng điều khiển Web (Dashboard)** tại địa chỉ: `http://localhost:5000` (hoặc `http://192.168.137.1:5000`).

---

## 6. HƯỚNG DẪN SỬ DỤNG

### Cấu hình và Tính năng trên Bảng Điều Khiển Web (Dashboard)
Giao diện điều khiển cung cấp một bảng quản trị toàn diện, bảo mật bằng mật khẩu:
1. **Đăng nhập Bảo mật (Login):** Yêu cầu xác thực tài khoản Admin trước khi truy cập hệ thống (Mật khẩu mặc định trong `admin_password` của `config.json`).
2. **Tùy chỉnh vùng nhận diện ROI (Drag & Resize):**
   - Nắm kéo vùng màu xanh để di chuyển (Drag).
   - Nắm kéo **núm đỏ** ở góc dưới bên phải để thu nhỏ / phóng to vùng cắt ảnh (Resize).
3. **Cấu hình Hệ thống (`[Cài Đặt]`):** Nhấp nút `[Cài Đặt]` để mở bảng điều chỉnh URL IP Webcam, Gemini API Key, MongoDB URI, Firebase URL, Telegram Bot Token.
4. **Hệ thống 4 Tab Quản lý:**
   - **Trạm Thu Phí:** Theo dõi camera trực tiếp, kết quả OCR và bảng điều khiển cổng LAN.
   - **Xe Khách Lạ:** Hiển thị danh sách xe lạ. Tích chọn ô vuông (Checkbox) để **Xóa Đã Chọn** hàng loạt hoặc Duyệt/Cảnh báo (Cập nhật DOM mượt 100% không reload trang).
   - **Lịch Sử Nhận Diện:** Truy vấn 50 lượt xe đi qua mới nhất từ Cloud MongoDB, có nhãn màu phân loại (🟢 Xe Quen / 🟡 Xe Lạ / 🔴 CẢNH BÁO).
   - **Hàng Đợi CSV:** Quản lý các bản ghi đệm khi rớt mạng (`pending_sync.csv`). Các lượt xe đẩy lên Cloud thành công sẽ tự động biến mất khỏi danh sách này.

### Vận hành & Đóng Mở Cổng
- **Tự động:** Đưa phương tiện đi ngang qua cảm biến 1. Hệ thống tự động chụp ảnh, phân tích biển số, đẩy dữ liệu lên đám mây, mở cổng và đếm ngược 3s tự đóng.
- **Thủ công từ Web UI:**
  - **Mở (Tự Động Đóng Sau 3s):** Server chạy luồng nền Background Thread đếm lùi 3 giây rồi phát lệnh đóng cổng an toàn.
  - **Mở Mãi Mãi (Không Tự Đóng):** Giữ cổng mở liên tục cho đến khi có lệnh đóng mới.
  - **Đóng Cổng Khẩn Cấp:** Hạ thanh chắn ngay lập tức.

---

## 7. XỬ LÝ SỰ CỐ THƯỜNG GẶP (TROUBLESHOOTING)

### 7.1. Chạy trên Raspberry Pi 5 hoặc Mạng Hotspot ĐTDĐ
- 📷 **Không chụp được ảnh:** 
  1. Đảm bảo app IP Webcam trên điện thoại đã bấm **Start server**.
  2. Địa chỉ IP khi dùng Hotspot thường thay đổi (ví dụ: `http://192.168.43.1:8080/shot.jpg`). Hãy cập nhật đúng IP mới trong mục `[Cài Đặt]` trên Web UI.
- 📲 **Không gửi được thông báo Telegram:**
  1. Đảm bảo ĐTDĐ phát Hotspot có bật **4G/5G (Dữ liệu di động)** để Raspberry Pi 5 truy cập được Internet (`api.telegram.org`).
  2. Đã nhập đúng **Telegram Bot Token** và **Admin Telegram ID** trong mục `[Cài Đặt]`.
- 🌐 **Không thấy gửi link kết nối Cloudflare về Telegram khi bật Server:**
  - Kiểm tra xem ô `telegram_token` trong `config.json` đã có dữ liệu chưa. Nhập Token trên Web UI và bấm **Lưu Cài Đặt** để lưu cố định.
  - Chạy lệnh `pip install pycloudflared` trên Pi 5 nếu chưa cài đặt thư viện Cloudflare.

> **Lưu ý Căn chỉnh Cảm biến:** Lần đầu cắm điện, mạch Master sẽ nháy đèn và chạy đo đạc không gian xung quanh làm mẫu nền khoảng 2 giây. Xin vui lòng không đứng che cảm biến trong lúc này. Màn hình LCD sẽ báo `He thong SS` khi quá trình hoàn tất.
