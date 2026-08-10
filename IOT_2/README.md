# IOT_2 - Bộ nhận dữ liệu (I2C Slave)

Đây là chương trình dành cho mạch ESP32 thứ 2 đóng vai trò là I2C Slave. Mạch này có nhiệm vụ nhận dữ liệu vận tốc từ mạch ESP32 Master đo được và in ra Serial Monitor (hoặc dùng để phát triển thêm các tính năng khác).

## Sơ đồ đấu nối cho mạch Slave

Bạn chỉ cần kết nối 3 dây cơ bản giữa mạch ESP32 Master (Mạch đo tốc độ) và mạch ESP32 Slave (Mạch nhận):

```mermaid
graph LR
    subgraph Mạch đo tốc độ (Master)
        Master[ESP32 Master]
    end

    subgraph Mạch nhận (Slave)
        Slave[ESP32 Slave<br>Địa chỉ I2C: 0x08]
    end

    %% Kết nối 2 mạch
    Master -- SDA (GPIO 21) --> Slave
    Master -- SCL (GPIO 22) --> Slave
    Master -- GND chung --> Slave
```

### Bảng cấu hình chân I2C (Mặc định của ESP32)

| Tín hiệu | Chân trên Slave | Nối với Master | Ý nghĩa |
| :--- | :--- | :--- | :--- |
| **SDA** (Dữ liệu) | `GPIO 21` | `GPIO 21` (Master) | Đường truyền dữ liệu I2C |
| **SCL** (Xung nhịp) | `GPIO 22` | `GPIO 22` (Master) | Đường đồng bộ xung nhịp I2C |
| **GND** (Mass chung) | `GND` | `GND` (Master) | **Bắt buộc** phải nối chung GND nếu 2 mạch dùng 2 nguồn cấp điện khác nhau |

*Lưu ý: Bạn có thể cắm trực tiếp cáp USB từ ESP32 Slave vào máy tính, mở Serial Monitor ở baudrate `115200` để xem kết quả khi Master gửi sang.*
