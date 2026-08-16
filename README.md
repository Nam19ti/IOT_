# MẠCH 1: ESP32 MASTER (ĐIỀU KHIỂN CỔNG VÀ CẢM BIẾN)

Dự án Trạm Thu Phí VETC - Mạch ESP32 Master chịu trách nhiệm đọc tín hiệu từ 2 cảm biến siêu âm (HC-SR04) để phát hiện xe, tự động mở cổng bằng Servo và đảm bảo tính năng **Zero-Crash** (chống sập barie vào xe).

## Chức Năng Chính
- **Đo khoảng cách nền tự động:** Khi mới khởi động, mạch sẽ quét khoảng cách tới bức tường/vật cản đối diện để lấy mốc (baseline). Bất kỳ vật gì đi ngang qua làm giảm khoảng cách sẽ được coi là xe.
- **Bảo vệ chống kẹp xe (Zero-Crash):** Sử dụng cờ trạng thái kép `carAtGate` và đọc lại cảm biến trước khi đóng cổng để tuyệt đối không sập cần barie vào kính xe.
- **Còi báo động:** Tít tít khi mở cổng và hú còi khi có lỗi.
- **Giao tiếp:** Gửi dữ liệu sự kiện (Xe vào, Lỗi...) sang Mạch 2 qua UART.

## Sơ đồ đấu nối

| Linh kiện | Chân trên Linh kiện | Chân trên ESP32 | Ghi chú |
| :--- | :--- | :--- | :--- |
| **Cảm biến 1 (Lối Vào)** | TRIG | `GPIO 13` | Phát xung |
| | ECHO | `GPIO 12` | Nhận xung |
| **Cảm biến 2 (Lối Ra)** | TRIG | `GPIO 5` | Phát xung |
| | ECHO | `GPIO 18` | Nhận xung |
| **Động Cơ Servo** | PWM | `GPIO 4` | Điều khiển Barie |
| **Còi (Buzzer)** | VCC/IN | `GPIO 14` | Còi chip |
| **Nút Nhấn Mở Cổng** | PIN | `GPIO 26` | Kéo GND khi nhấn (PULLUP) |
| **Mạch 2 (IOT_2)** | RX2 | `GPIO 17 (TX2)` | Truyền UART |
| | TX2 | `GPIO 16 (RX2)` | Nhận UART |

*Lưu ý: Mạch 1 và Mạch 2 phải được nối chung chân GND.*
