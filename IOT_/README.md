# BÁO CÁO NGHIÊN CỨU: HỆ THỐNG NHẬN DIỆN BIỂN SỐ VÀ QUẢN LÝ BÃI ĐỖ XE TỰ ĐỘNG (ALPR SMART PARKING)

## 1. Vấn đề nghiên cứu (Problem Statement)
+ Tại các bãi đỗ xe truyền thống, việc quản lý ra vào hiện tại đòi hỏi nhiều nhân lực, dễ xảy ra sai sót khi ghi chép thủ công và thường xuyên gây ùn tắc tại cổng vào các giờ cao điểm.
+ Các hệ thống nhận diện biển số (ALPR) chuyên dụng trên thị trường có chi phí đầu tư ban đầu quá cao (bao gồm camera chuyên dụng, máy chủ xử lý AI cấu hình khủng, và bản quyền phần mềm).
+ Nhu cầu cấp thiết là xây dựng một hệ thống đỗ xe thông minh, tự động hóa đóng/mở cổng, với chi phí siêu rẻ bằng cách tận dụng sức mạnh xử lý đám mây (Cloud AI), camera từ điện thoại cũ và vi điều khiển ESP32.

## 2. Đối tượng nghiên cứu (Research Objects)
+ Hệ thống Vi điều khiển (Microcontrollers): ESP32 được sử dụng làm lõi xử lý phần cứng, giao tiếp cảm biến và điều khiển cơ cấu chấp hành (Servo).
+ Công nghệ Thị giác Máy tính đám mây (Cloud Computer Vision): Ứng dụng mô hình ngôn ngữ lớn và thị giác (Google Gemini Vision Pro API) để trích xuất biển số xe từ hình ảnh tĩnh mà không cần GPU cục bộ.
+ Giao thức Mạng (Network Protocols): Giao tiếp không dây qua HTTP GET/POST trong mạng LAN, cấp phát IP động (DHCP), truyền dữ liệu siêu tốc bằng `urllib` và luồng video IP Webcam.
+ Giao thức Giao tiếp Nối tiếp (Serial Communication): Truyền tải dữ liệu bất đồng bộ UART giữa các vi điều khiển để phân tán tác vụ xử lý.

## 3. Cách thức thực hiện (Methodology)
Dự án được phân chia thành 2 hệ thống cốt lõi: Mạng lưới Phần cứng (Hardware Node) và Máy chủ Xử lý Trung tâm (Central Server).

- Phân tán phần cứng (Hardware Decentralization): 
  - Thay vì gộp chung, dự án sử dụng 2 mạch ESP32 riêng biệt nhằm đảm bảo hiệu năng. Mạch 1 chuyên trách xử lý ngắt cảm biến và động cơ (tránh giật lag). Mạch 2 chuyên trách duy trì kết nối WiFi và xử lý các luồng gọi API HTTP. Hai mạch giao tiếp qua giao thức UART2.
- Kiến trúc Máy chủ và AI (Server & AI Architecture):
  - Một máy tính (hoặc Raspberry Pi) đóng vai trò làm Server cục bộ (chạy Python/Flask). 
  - Điện thoại thông minh Android (cài IP Webcam) đóng vai trò như một IP Camera không dây giám sát cổng.
  - Khi có sự kiện xe vào, Server sẽ yêu cầu Camera chụp ảnh (tối ưu hóa bỏ qua Header để đạt tốc độ <0.1s), sau đó gửi ảnh lên Google Gemini API.
  - Dữ liệu kết quả được lọc nhiễu bằng Regular Expression (Regex), lưu vào Cơ sở dữ liệu SQLite và cập nhật thời gian thực lên giao diện Web điều khiển.

## 4. Tiến độ dự án / Dự án làm được đến đâu (Current Achievements)
+ Hoàn thiện phần cứng phần cơ điện: Đọc tín hiệu cảm biến siêu âm chính xác, điều khiển Servo mượt mà, thiết lập nút bấm cứng và còi báo hiệu chống kẹt xe.
+ Tối ưu hóa Mạng & Camera: 
  - Khắc phục hoàn toàn lỗi rớt mạng và đứt kết nối HTTP.
  - Chuyển đổi thành công Mạch ESP32 kết nối mạng sang chế độ IP Động (DHCP), tăng tính linh hoạt khi triển khai ở các mạng WiFi khác nhau.
  - Tối ưu hóa giao thức lấy ảnh (bỏ cơ chế giả lập trình duyệt, dùng gói tin thô) giúp giảm độ trễ chụp từ 2.5s xuống mức Tức thì.
+ Tích hợp AI thành công: Server Python đã giao tiếp ổn định với Gemini, trích xuất chính xác chuỗi ký tự biển số ngay cả khi ảnh bị lóa hoặc xe di chuyển.
+ Giao diện Quản trị (Web UI): Cung cấp bảng điều khiển (Dashboard) cho phép bảo vệ xem lịch sử ra vào, xem ảnh chụp xe, và có nút ấn Mở/Đóng cổng khẩn cấp qua giao diện web.

## 5. Sơ đồ đấu nối (Wiring Diagram)

- Mạch 1 (ESP32 - Master Hardware Logic):
  - Chân 13 (Trig), 12 (Echo) --> Cảm biến siêu âm 1 (Nhận diện xe đi vào vùng cổng)
  - Chân 5 (Trig), 18 (Echo) --> Cảm biến siêu âm 2 (Nhận diện xe đã qua barie để đóng cổng an toàn)
  - Chân 4 --> Chân tín hiệu Động cơ Servo (Điều khiển thanh chắn Barie)
  - Chân 14 --> Còi chip (Buzzer - Phát tín hiệu tít tít khi đóng/mở)
  - Chân 26 --> Nút bấm cơ học (Mở/đóng cổng thủ công từ bốt bảo vệ)
  - Chân 16 (RX2), 17 (TX2) --> Giao tiếp UART chéo sang Mạch 2

- Mạch 2 (ESP32 - WiFi & LAN Slave):
  - Chân 16 (RX2), 17 (TX2) --> Nối chéo (TX-RX, RX-TX) sang Mạch 1 để truyền/nhận lệnh.
  - Nguồn cấp 5V & GND nối chung với hệ thống điện của Mạch 1.

## 6. Sơ đồ hoạt động (Operation Flow)
- Xe tiến vào vùng cổng --> Cảm biến siêu âm 1 bị che.
- Mạch 1 phát hiện, gửi tín hiệu UART sang Mạch 2.
- (Hoạt động song song) Mạch 2 báo trạng thái lên Server / Server tự động yêu cầu Camera điện thoại chụp 1 khung hình (Snapshot).
- Server Python gửi bức ảnh này qua API lên Google Gemini Vision.
- AI phản hồi chuỗi ký tự biển số xe (VD: 29A-12345).
- Server Python lưu biển số, thời gian và file ảnh vào Database (SQLite).
- Server Python gửi API HTTP GET (ví dụ: `/open_gate`) tới địa chỉ IP của Mạch 2.
- Mạch 2 nhận được lệnh HTTP, gửi lệnh UART sang Mạch 1.
- Mạch 1 nhận lệnh UART --> Kích hoạt Servo mở góc 90 độ, đồng thời nhại còi báo hiệu.
- Xe di chuyển qua barie, che Cảm biến siêu âm 2.
- Khi xe đi khỏi Cảm biến siêu âm 2 (an toàn) --> Mạch 1 chờ 3 giây rồi tự động kích hoạt Servo hạ barie xuống.
- Kết thúc một chu trình ra/vào.

## 7. Cấu trúc chi tiết của file (Detailed File Structure)
+ `IOT.ino`
  - File nạp cho Mạch 1 (ESP32).
  - Khởi tạo thư viện `ESP32Servo`, các chân GPIO.
  - Chứa thuật toán chống dội nút bấm (Debounce), thuật toán tránh kẹt xe dùng cảm biến siêu âm, logic điều khiển Barie.
+ `IOT_2.ino`
  - File nạp cho Mạch 2 (ESP32).
  - Khởi tạo thư viện `WiFi`, `WebServer`.
  - Quản lý kết nối DHCP, tạo máy chủ tại cổng 80, chứa các hàm Endpoint như `handleOpenGate()`, `handleCloseGate()`.
+ `server.py`
  - File chạy chính của Server Backend (sử dụng framework Flask).
  - Quản lý các Route API của Web UI, render file HTML, liên kết các module Camera, AI, DB lại với nhau.
+ `camera.py`
  - Module phụ trách luồng Camera.
  - Sử dụng `urllib` để gửi gói tin cực nhẹ đến địa chỉ IP Webcam Android, trích xuất ma trận điểm ảnh (NumPy array) và giao cho OpenCV.
+ `ai.py`
  - Module tích hợp Trí tuệ nhân tạo.
  - Khởi tạo Gemini model, tiền xử lý hình ảnh (có thể cắt xén ROI - Vùng quan tâm), đóng gói request và xử lý chuỗi JSON trả về.
+ `db.py`
  - Module Cơ sở dữ liệu SQLite cục bộ.
  - Khởi tạo bảng `history`, thêm mới các bản ghi (Thời gian, Biển số, Đường dẫn ảnh).
+ `core.py`
  - Chứa các hàm tiện ích chung dùng cho toàn hệ thống như hàm `p()` để log ra màn hình Console giúp dễ dàng Debug.
+ `cloud.py` (Tùy chọn)
  - File hỗ trợ đồng bộ dữ liệu song song lên Firebase Realtime Database nếu dự án cần quản lý từ xa qua Internet.
+ `templates/` & `static/`
  - Thư mục chứa giao diện Front-End của Web UI (Mã HTML, CSS, JavaScript).
  - Giao diện được thiết kế tương thích với bảo vệ thao tác trên máy tính bảng hoặc laptop.
