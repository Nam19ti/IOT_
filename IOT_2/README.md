# MẠCH 2: ESP32 SLAVE (GIAO TIẾP MẠNG LAN)

Dự án Trạm Thu Phí VETC - Mạch ESP32 Slave đóng vai trò làm Router / Cầu nối Mạng. Nó cung cấp giao diện Web nội bộ để Python Server hoặc trình duyệt có thể ra lệnh đóng mở cổng khẩn cấp, đồng thời gửi tín hiệu ngược lên máy chủ khi Mạch 1 phát hiện có xe.

## Chức Năng Chính
- **Mạng LAN WiFi:** Kết nối tới WiFi cục bộ (`NONNET`) với địa chỉ IP tĩnh là `192.168.137.199`.
- **Máy Chủ Web Nhúng:** Mở cổng 80 để lắng nghe các API:
  - `/open_gate`: Mở tự động (Đóng sau 3s nếu xe qua)
  - `/open_gate_manual`: Mở giữ mãi mãi
  - `/close_gate`: Đóng khẩn cấp
- **Bắn HTTP GET:** Khi nhận được tín hiệu "Có Xe" qua UART từ Mạch 1, Mạch 2 lập tức gửi HTTP GET tới `http://192.168.137.1:5000/trigger_capture` để yêu cầu máy tính chạy AI nhận diện biển số.
- **Màn Hình LCD I2C:** Hiển thị trực tiếp thông báo hệ thống và IP mạng đang kết nối.

## Sơ đồ đấu nối

| Linh kiện | Chân trên Linh kiện | Chân trên ESP32 | Ghi chú |
| :--- | :--- | :--- | :--- |
| **Mạch 1 (IOT_)** | TX2 | `GPIO 16 (RX2)` | Nhận dữ liệu UART |
| | RX2 | `GPIO 17 (TX2)` | Truyền lệnh điều khiển (Chưa dùng tới) |
| **Màn Hình LCD 16x2** | SDA | `GPIO 21` | Bus I2C |
| | SCL | `GPIO 22` | Bus I2C |
| | VCC | `5V / VIN` | Cấp nguồn cho LCD |

*Lưu ý: Mạch 1 và Mạch 2 phải được nối chung chân GND.*
