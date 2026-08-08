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