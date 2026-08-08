# Hệ thống đo tốc độ với ESP32 và Cảm biến siêu âm

Dự án này sử dụng ESP32 cùng 2 cảm biến siêu âm (HC-SR04) để tính toán tốc độ của phương tiện, hiển thị lên màn hình LCD I2C và gửi dữ liệu lên ThingsBoard qua MQTT.

## Sơ đồ đấu nối

Dưới đây là sơ đồ đấu nối giữa ESP32 và các linh kiện ngoại vi theo cấu hình trong mã nguồn:

```mermaid
graph LR
    subgraph Controller
        ESP32[ESP32 Board]
    end

    subgraph Cảm biến
        CB1[Cảm biến Siêu âm 1<br/>Bên trái]
        CB2[Cảm biến Siêu âm 2<br/>Bên phải]
    end

    subgraph Hiển thị & Điều khiển
        LCD[Màn hình LCD I2C<br/>16x2]
        BTN_START[Nút nhấn Bắt đầu]
        BTN_MODE[Nút nhấn Mode]
    end

    %% Kết nối CB1
    ESP32 -- GPIO 15 -->|Trig| CB1
    CB1 -- Echo -->|GPIO 4| ESP32

    %% Kết nối CB2
    ESP32 -- GPIO 18 -->|Trig| CB2
    CB2 -- Echo -->|GPIO 19| ESP32

    %% Kết nối LCD (I2C)
    ESP32 -- GPIO 22 -->|SCL| LCD
    ESP32 -- GPIO 21 -->|SDA| LCD
    
    %% Kết nối Nút bấm
    BTN_START -- Nhấn kéo GND -->|GPIO 26| ESP32
    BTN_MODE -- Nhấn kéo GND -->|GPIO 25| ESP32
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
| **Nút nhấn** | Bắt đầu / Dừng đo | `GPIO 26` | Kéo GND khi nhấn (Sử dụng INPUT_PULLUP) |
| | Chuyển chế độ (Mode)| `GPIO 25` | Kéo GND khi nhấn |