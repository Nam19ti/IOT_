# BÁO CÁO TỔNG KẾT DỰ ÁN KỸ THUẬT

**Tên đề tài:** Hệ Thống Cảnh Báo Tốc Độ và Nhận Diện Biển Số Xe Tự Động (ALPR) sử dụng Kiến trúc IoT Phân tán và Cloud AI.

---

## TÓM TẮT (Abstract)

Dự án tập trung vào việc thiết kế và phát triển một hệ thống giám sát giao thông IoT với khả năng đo tốc độ phương tiện và tự động trích xuất biển số xe vi phạm. Bằng việc áp dụng kiến trúc phần cứng phân tán (Master-Slave ESP32) để đảm bảo tính thời gian thực (Real-time) của cảm biến, kết hợp với sức mạnh xử lý ảnh tiên tiến từ Cloud AI (Gemini 3.5 Flash), hệ thống mang lại độ chính xác nhận diện cực cao với tốc độ xử lý nhanh. Mọi dữ liệu vi phạm được đồng bộ tự động lên nền tảng đám mây ThingsBoard (IoT) và Node.js/MongoDB Atlas (Quản trị).

---

## 1. ĐẶT VẤN ĐỀ (Introduction)

Việc giám sát tốc độ và phạt nguội tự động hiện đang là nhu cầu thiết yếu trong quản lý giao thông đô thị thông minh. Tuy nhiên, các hệ thống camera chuyên dụng thường có giá thành rất cao và yêu cầu đường truyền cáp quang phức tạp. Đề tài này giải quyết bài toán trên bằng cách tận dụng sức mạnh camera từ Smartphone thông thường, kết hợp với vi máy tính (Raspberry Pi/PC) và Cloud AI để tạo ra một hệ thống chi phí thấp, hoạt động ổn định 24/7 và có cấu trúc Lean (Tối giản hóa) giúp loại bỏ tình trạng giật lag, treo máy tính.

---

## 2. KIẾN TRÚC HỆ THỐNG (System Architecture)

Hệ thống được chia làm 4 module chính giao tiếp với nhau qua giao thức MQTT siêu tốc:

1. **Module Cảm biến (Master ESP32):**
   - Đọc dữ liệu từ 2 cảm biến siêu âm HC-SR04.
   - Tính toán vận tốc (V), hướng đi và gán ID định danh duy nhất cho mỗi phương tiện.
   - Hiển thị kết quả tạm thời lên màn hình LCD I2C.
   - Gửi dữ liệu UART sang Slave ESP32.

2. **Module IoT Gateway (Slave ESP32):**
   - Đóng vai trò là "MQTT Router" kết nối Internet qua WiFi.
   - Nhận dữ liệu từ Master qua UART và phát sóng (Publish) lên HiveMQ Broker (Topic: `iot_thanglong/speed`).

3. **Module Xử lý Trí tuệ Nhân tạo (Python AI Server):**
   - Hoạt động theo kiến trúc "Tối giản" (Lean Architecture) 100% dựa vào Cloud AI.
   - Lắng nghe tín hiệu tốc độ từ MQTT để kích hoạt chớp lấy ảnh ngay lập tức.
   - Chụp liên tiếp 3 frame từ IP Webcam.
   - Lọc ảnh thông minh bằng thuật toán Laplacian Variance (phân tích phương sai) để chọn ra bức ảnh nét nhất.
   - Phân tích biển số bằng Gemini 3.5 Flash API.
   - Đẩy kết quả lên ThingsBoard và Node.js.

4. **Module Quản trị Đám mây (ThingsBoard & Node.js):**
   - **ThingsBoard:** Dashboard giám sát trực quan thời gian thực (Hiển thị Vận tốc, Biển số và Ảnh tự động ép dung lượng).
   - **Node.js + MongoDB Atlas:** Cổng duyệt phạt nguội cho Cảnh sát Giao thông, cho phép sửa biển số bị mờ và tự động gửi Email hóa đơn phạt cho chủ xe.

---

## 3. PHƯƠNG PHÁP NGHIÊN CỨU & CÔNG NGHỆ ÁP DỤNG

### 3.1. Kỹ thuật Lấy Mẫu Tức Thì (Instant Burst Capture)

Hệ thống loại bỏ hoàn toàn các thuật toán quay video nền (Background Subtraction / MOG2) vốn gây ngốn CPU và treo máy. Thay vào đó, ngay tại khoảnh khắc nhận được tín hiệu có xe vi phạm từ mạch ESP32 thông qua MQTT, hệ thống Python lập tức **chụp chớp nhoáng 3 bức ảnh** (với độ trễ chỉ 0.05 giây mỗi ảnh) từ Camera. 

### 3.2. Đánh Giá Độ Nét Tự Động (Laplacian Variance Sharpness)

Để tiết kiệm thời gian xử lý và chi phí API, hệ thống không gửi toàn bộ ảnh lên AI. Thay vào đó, OpenCV được sử dụng để quét ma trận điểm ảnh của 3 bức ảnh vừa chụp bằng thuật toán **Laplacian Variance**.
Bức ảnh có điểm phương sai cao nhất (ít bị nhòe chuyển động nhất, nét nhất) sẽ được đẩy lên top đầu để ưu tiên gửi đi phân tích.

### 3.3. Sử dụng Cloud AI Mới Nhất (Gemini 3.5 Flash)

Dự án đã loại bỏ hoàn toàn thuật toán OCR truyền thống (EasyOCR) vốn yêu cầu cấu hình máy tính mạnh và mất nhiều phút khởi động. 
Hệ thống sử dụng **100% Gemini 3.5 Flash** (Model mới nhất của Google dành cho xử lý hình ảnh nhanh).
- **Tốc độ khởi động:** 0 giây.
- **Tốc độ nhận diện:** ~1-2 giây qua mạng.
- **Khả năng siêu phàm:** Có thể tự động nội suy và đọc được biển số bị xoay góc, nghiêng 45 độ, bị mờ sương, lóa sáng mà không cần ta phải lập trình các hàm xoay ảnh phức tạp.

### 3.4. Định Dạng Chuẩn Hóa (VN Pattern Validation)

Sau khi Gemini đọc xong chữ trên biển, hệ thống sử dụng Biểu thức chính quy (Regex: `^[0-9]{2,3}[A-Z]{1,2}[0-9]{4,5}$`) kết hợp với từ điển sửa lỗi (Ví dụ: số `0` bị đọc nhầm thành chữ `O`) để ép kết quả về đúng chuẩn format biển số Việt Nam (`XX-XXXXX`).

### 3.5. Xử Lý Ép Dung Lượng (Payload Compression)

ThingsBoard Cloud có giới hạn nghiêm ngặt về dung lượng truyền tải dữ liệu (max 32KB cho 1 chuỗi). Do đó, trước khi đẩy ảnh lên ThingsBoard, thuật toán tại `cloud.py` sẽ tự động:
- Giảm độ phân giải chiều rộng xuống 320px.
- Giảm chất lượng ảnh JPEG xuống 50%.
- Mã hóa Base64 và nối tiền tố `data:image/jpeg;base64,` để Dashboard ThingsBoard có thể hiển thị mượt mà mà không bị "chém" mất dữ liệu do quá tải.

### 3.6. Phân quyền và Bảo mật thư tín (Single Sign-On OAuth2)

Để đảm bảo tính pháp lý và bảo mật cho việc gửi thông báo phạt nguội:
- **Đăng nhập nhân viên (SSO):** Cảnh sát/Nhân viên phải đăng nhập bằng tài khoản Google (Gmail) của chính họ qua *Google Identity Services*.
- **Tự động tra cứu CSDL (Auto-Lookup):** Khi ấn "Gửi Phạt", Node.js Server tự động tra cứu biển số xe trong Cơ Sở Dữ Liệu để tìm ra Tên và Địa chỉ Email của chủ xe.
- **Gửi Email mượn danh (OAuth2 Nodemailer):** Hệ thống sử dụng Access Token của nhân viên để gửi biên lai phạt trực tiếp từ hòm thư của chính nhân viên đó tới người vi phạm.

---

## 4. HƯỚNG DẪN CÀI ĐẶT 1-CLICK (ONE-CLICK SETUP)

Để đơn giản hóa quá trình triển khai, dự án đã được đóng gói kèm các script tự động cài đặt.

### BƯỚC 1: Phần Cứng ESP32
1. Mở Arduino IDE. Nạp `IOT_/IOT_.ino` cho mạch Master.
2. Sửa thông tin WiFi trong `IOT_2/IOT_2.ino` và nạp cho mạch Slave.
3. Đấu nối dây UART giữa 2 mạch:
   - `TX2 (GPIO 17)` của Master nối với `RX2 (GPIO 16)` của Slave
   - Nối chung dây **GND** (bắt buộc)

### BƯỚC 2: Backend Node.js (Trung Tâm Phạt Nguội)
Yêu cầu: Máy tính đã cài sẵn Node.js.
1. Truy cập thư mục `Node_Backend`.
2. Nhấp đúp chuột vào file **`setup_node.bat`**. 
   - Script sẽ tự động tải `node_modules` và tạo 2 dữ liệu chủ xe mẫu (Seed) vào MongoDB.
3. Chạy Server bằng lệnh: `node server.js`
4. Mở Dashboard tại `http://localhost:3000`.

### BƯỚC 3: Python AI Server (Máy Trạm Phân Tích)
Yêu cầu: Máy tính đã cài sẵn Python 3.9+.
1. Bật app **IP Webcam** trên điện thoại Android. Ghi lại địa chỉ IP (ví dụ: `http://192.168.1.100:8080`).
2. Vào thư mục `Python_ALPR`. Nhấp đúp chuột vào file **`setup.bat`**.
   - Script sẽ tự động tạo môi trường ảo (VENV) cách ly và tải OpenCV, Flask, Google GenAI...
3. Khởi động AI Server:
   - Mở Terminal/PowerShell gõ:
     ```powershell
     venv\Scripts\activate
     python server.py
     ```
4. Mở trình duyệt vào trang cấu hình nội bộ: `http://localhost:5000/`
5. Nhập Cấu hình:
   - **IP Camera:** Link hiện trên điện thoại (Ví dụ: `http://192.168.1.100:8080/photo.jpg`)
   - **Gemini API Key:** Lấy miễn phí từ Google AI Studio (Dùng Model Gemini 3.5 Flash)
   - **ThingsBoard Token:** Lấy từ thiết bị trên trang thingsboard.cloud
6. Bấm "Lưu Cấu Hình". Hệ thống đã sẵn sàng 100%!

---

## 5. CẤU TRÚC FILE DỰ ÁN

```
IOT_ThangLong/
│
├── IOT_/                      # Firmware Master ESP32
│   ├── IOT_.ino               # Code đo tốc độ, LCD, UART
│   └── README.md
│
├── IOT_2/                     # Firmware Slave ESP32
│   ├── IOT_2.ino              # Code WiFi, MQTT, UART
│   └── README.md
│
├── Node_Backend/              # Backend Node.js + Web Dashboard
│   ├── server.js              # API REST, MongoDB, OAuth2
│   ├── setup_node.bat         # Script cài đặt tự động & Seeding
│   ├── public/
│   │   └── index.html         # Giao diện duyệt phạt (SSO Login)
│   ├── .env                   # Config bảo mật
│   └── package.json
│
├── Python_ALPR/               # AI Server (Kiến trúc Lean)
│   ├── setup.bat              # Script tạo VENV và tải thư viện tự động
│   ├── server.py              # File chạy chính, Web UI
│   ├── core.py                # Quản lý luồng, Camera, Tín hiệu MQTT
│   ├── camera.py              # CameraClient HTTP Polling
│   ├── ai.py                  # Module Laplacian Variance & Gemini API
│   ├── cloud.py               # Ép dung lượng ảnh & đẩy Node.js / ThingsBoard
│   ├── mqtt_service.py        # Paho MQTT lắng nghe ESP32
│   ├── config.json            # Cấu hình lưu tự động
│   ├── requirements.txt       # Danh sách thư viện
│   └── violations/            # Thư mục lưu ảnh gốc siêu nét
│
└── README.md                  # Báo cáo dự án (file này)
```
