# DỰ ÁN: HỆ THỐNG NHẬN DIỆN BIỂN SỐ VÀ QUẢN LÝ BÃI ĐỖ XE TỰ ĐỘNG (ALPR SMART PARKING)

## 1. Vấn đề của dự án (Problem Statement)
+ Thực trạng hiện nay: Tại các khu dân cư, cơ quan hay bãi đỗ xe truyền thống, việc kiểm soát xe ra vào vẫn chủ yếu dựa vào sức người (bảo vệ ghi vé giấy, quẹt thẻ thủ công). Phương pháp này bộc lộ nhiều hạn chế như: tốn kém chi phí thuê nhân sự trực 24/24, dễ xảy ra sai sót hoặc gian lận, làm mất vé xe, và đặc biệt là gây ùn tắc giao thông cục bộ tại khu vực cổng vào những khung giờ cao điểm (giờ đi làm, giờ tan tầm).
+ Rào cản công nghệ: Mặc dù các hệ thống nhận diện biển số tự động (ALPR - Automated License Plate Recognition) đã có mặt trên thị trường để giải quyết bài toán trên, nhưng chúng lại gặp một rào cản rất lớn về mặt chi phí. Một hệ thống ALPR tiêu chuẩn yêu cầu phải có Camera IP chuyên dụng đắt tiền (vài triệu đến hàng chục triệu đồng), một Máy chủ (Server) cục bộ tích hợp Card đồ họa (GPU) cấu hình cực mạnh để chạy các mô hình AI nặng nề, cùng với chi phí bảo trì và bản quyền phần mềm đắt đỏ.
+ Giải pháp đề xuất: Từ những bất cập trên, dự án này được ra đời nhằm mục đích "bình dân hóa" công nghệ bãi đỗ xe thông minh. Thay vì sử dụng thiết bị đắt tiền, dự án sử dụng Camera từ những chiếc Điện thoại thông minh (Smartphone) Android cũ đã qua sử dụng, kết hợp với các vi điều khiển giá siêu rẻ ESP32 (chỉ khoảng vài chục nghìn đồng). Đặc biệt, thay vì dùng máy chủ cấu hình cao, dự án đẩy khâu phân tích hình ảnh nặng nề lên Trí tuệ nhân tạo đám mây (Google Gemini Vision API) hoàn toàn miễn phí. Sự kết hợp này tạo ra một hệ thống tự động 100%: Tự động phát hiện xe đến -> Tự động chụp ảnh -> Tự động đọc biển số -> Tự động mở cổng, với chi phí đầu tư ban đầu tiệm cận mức 0 đồng.

## 2. Đối tượng của dự án (Project Objects)
Để hiện thực hóa giải pháp trên, dự án tập trung nghiên cứu sâu vào 4 nhóm đối tượng công nghệ cốt lõi:

+ Nhóm 1: Hệ thống Vi điều khiển (Microcontrollers)
  - Nghiên cứu nền tảng vi điều khiển ESP32 (chip lõi kép 32-bit, tích hợp sẵn Wi-Fi).
  - Phân tích phương pháp phân tán tác vụ phần cứng (Hardware Decentralization): Sử dụng 2 mạch ESP32 chạy độc lập thay vì nhồi nhét vào 1 mạch duy nhất để tránh treo hệ thống. Mạch 1 chuyên giao tiếp với "thế giới thực" (đọc cảm biến siêu âm chống sập cần barie, nhại còi, điều khiển góc quay Servo). Mạch 2 chuyên lo duy trì kết nối mạng LAN và cấp phát WebServer API.

+ Nhóm 2: Công nghệ Thị giác Máy tính Đám mây (Cloud Computer Vision)
  - Nghiên cứu ứng dụng Mô hình Trí tuệ Nhân tạo Đa phương thức (Multimodal AI) - cụ thể là Google Gemini Vision API vào bài toán nhận diện ký tự quang học (OCR).
  - Khảo sát cách thức đóng gói hình ảnh thành mảng byte, thiết lập câu lệnh ngữ cảnh (Prompt Engineering) để AI tập trung trích xuất đúng biển số xe thành định dạng JSON, loại bỏ hoàn toàn các thông tin rác xung quanh môi trường đỗ xe.

+ Nhóm 3: Giao thức Mạng và Tối ưu hóa Truyền tải (Network Protocols)
  - Nghiên cứu thiết lập máy chủ trung tâm (Flask Python) làm đầu não điều phối toàn bộ luồng thông tin.
  - Tối ưu hóa luồng trích xuất hình ảnh: Thay vì dùng luồng video nặng nề, dự án nghiên cứu giao thức gửi gói tin HTTP cấp thấp (`urllib` lược bỏ toàn bộ Header trình duyệt) để ép IP Camera trên điện thoại nhả ảnh tĩnh (Snapshot) ngay lập tức, đưa độ trễ từ 2.5s xuống mức Tức thì (<0.1s).
  - Tích hợp cấp phát IP Động (DHCP) giúp hệ thống linh hoạt thích ứng với mọi modem mạng mà không bị bó buộc vào 1 dải mạng cố định.

+ Nhóm 4: Giao tiếp Nối tiếp (Serial Communication)
  - Nghiên cứu chuẩn giao tiếp bất đồng bộ UART2 (Universal Asynchronous Receiver-Transmitter) để kết nối vật lý chéo chân TX/RX giữa 2 bo mạch ESP32.
  - Thiết lập cơ chế truyền nhận tín hiệu (Signal Flags) ổn định, giúp Mạch 2 (đang giữ kết nối WiFi) truyền đạt ngay lập tức lệnh Mở/Đóng cổng sang Mạch 1 (chuyên trách cơ điện) mà không sợ bị rớt gói tin như khi gửi qua sóng WiFi.

## 3. Cách thức thực hiện (Implementation Methodology)
Để giải quyết bài toán trên, dự án được triển khai theo mô hình phân tán (Decentralized Model), chia nhỏ hệ thống thành 3 thành phần (Node) hoạt động độc lập nhưng liên kết chặt chẽ với nhau:

+ Nút Phần cứng Chấp hành (Hardware Execution Node - ESP32 Mạch 1)
  - Vai trò: Đóng vai trò là "Cơ bắp" của hệ thống, trực tiếp tương tác với môi trường vật lý.
  - Triển khai: Lập trình bằng C++ trên bo mạch ESP32. Cấu hình 2 cảm biến siêu âm HC-SR04 đặt ở lối vào và dưới barie. Áp dụng thuật toán phát hiện vật cản kết hợp biến cờ (Flag) `carAtGate` để thiết lập tính năng an toàn Zero-Crash (tuyệt đối không đóng cổng khi xe đang nằm dưới barie). Cấu hình xuất xung PWM chuẩn xác để điều khiển góc quay Servo mượt mà.

+ Nút Trung chuyển Mạng (Network Gateway Node - ESP32 Mạch 2)
  - Vai trò: Đóng vai trò là "Trạm thu phát sóng" nối liền phần cứng vật lý với hệ thống mạng LAN.
  - Triển khai: Khởi tạo module WiFi kết nối vào mạng nội bộ bằng giao thức cấu hình IP Động (DHCP). Khởi tạo thư viện `WebServer` chạy ở cổng 80, thiết lập các Endpoint API (ví dụ: `http://<IP>/open_gate`). Khi nhận được lệnh HTTP GET từ máy chủ Python, mạch này lập tức kích hoạt giao thức nối tiếp UART (qua cặp chân TX2/RX2) để truyền tín hiệu điều khiển sang Mạch 1 một cách tức thời và bảo mật.

+ Nút Máy chủ Điều khiển & Trí tuệ Nhân tạo (Central Server & AI Node - Python)
  - Vai trò: Đóng vai trò là "Bộ não" trung tâm điều phối toàn bộ chu trình tự động hóa.
  - Triển khai thu thập hình ảnh: Xây dựng module `camera.py` liên tục quét luồng ảnh tĩnh từ điện thoại Android thông qua thư viện `urllib` tối ưu tốc độ băng thông.
  - Triển khai phân tích AI: Xây dựng module `ai.py` băm nhỏ hình ảnh thành byte và gửi API lên mô hình Google Gemini. Thiết lập bộ lọc Regular Expression (Regex) để trích xuất duy nhất chuỗi ký tự biển số từ khối văn bản lộn xộn do AI trả về.
  - Triển khai lưu trữ & Web UI: Sử dụng thư viện `sqlite3` để ghi nhận mốc thời gian (Timestamp) và biển số xe vào CSDL nội bộ `history.db`. Dựng framework `Flask` tạo giao diện Web Dashboard trực quan, cho phép nhân viên bảo vệ xem lại lịch sử ra vào và nhấn nút mở cổng khẩn cấp ngay trên màn hình.

## 4. Sơ đồ đấu nối và Hướng dẫn cài đặt (Wiring Diagram & Installation Guide)

### 4.1. Sơ đồ đấu nối phần cứng (Hardware Wiring)
Dự án sử dụng 2 bo mạch ESP32 giao tiếp với nhau. Để hệ thống hoạt động ổn định, 2 bo mạch bắt buộc phải dùng chung nguồn hoặc nối chung chân GND (Ground).

```mermaid
graph TD
    subgraph SG1 ["Mạch 1: ESP32 Master Logic (Cơ Điện)"]
        ESP1["ESP32_1"]
        SR04_1["Cảm biến 1 (Lối vào)"]
        SR04_2["Cảm biến 2 (Dưới cổng)"]
        Servo["Động cơ Servo (Barie)"]
        Buzzer["Còi báo động"]
        Btn["Nút bấm Mở/Đóng"]
        
        ESP1 -- "GPIO 13 / 12" --- SR04_1
        ESP1 -- "GPIO 5 / 18" --- SR04_2
        ESP1 -- "GPIO 4 (PWM)" --- Servo
        ESP1 -- "GPIO 14" --- Buzzer
        ESP1 -- "GPIO 26" --- Btn
    end

    subgraph SG2 ["Mạch 2: ESP32 Network Gateway (WiFi)"]
        ESP2["ESP32_2"]
        LCD["Màn hình LCD I2C"]
        
        ESP2 -- "SDA / SCL" --- LCD
    end

    ESP1 <--"UART2 (Chân 16-17)"--> ESP2
    ESP1 -.- "Nối chung GND" -.- ESP2
```

+ Chi tiết sơ đồ chân Mạch 1 (ESP32 Master Logic):
  - Chân 13 (Trig) và Chân 12 (Echo) --> Nối Cảm biến siêu âm 1 (Nhận diện xe tiến vào vùng camera).
  - Chân 5 (Trig) và Chân 18 (Echo) --> Nối Cảm biến siêu âm 2 (Bảo vệ Zero-Crash, chống kẹt xe dưới barie).
  - Chân 4 --> Cấp xung PWM cho Động cơ Servo (Điều khiển nâng/hạ thanh chắn Barie).
  - Chân 14 --> Nối cực dương (+) của Còi chip (Phát tín hiệu bíp bíp khi đóng/mở).
  - Chân 26 --> Nối Nút bấm cơ học, đầu kia nút bấm nối GND (Mạch có code Pull-up nội bộ).
  - Chân 16 (RX2) và Chân 17 (TX2) --> Kéo dây giao tiếp UART sang Mạch 2.

+ Chi tiết sơ đồ chân Mạch 2 (ESP32 Network Gateway):
  - Chân 16 (RX2) --> Nối chéo vào chân 17 (TX2) của Mạch 1.
  - Chân 17 (TX2) --> Nối chéo vào chân 16 (RX2) của Mạch 1.
  - Các chân Nguồn 5V (VIN) và GND --> Phải nối chung với mạng lưới điện của Mạch 1.

### 4.2. Hướng dẫn cài đặt và Triển khai (Installation Guide)
Để tái tạo lại dự án này trên thực tế, người triển khai cần thực hiện chuẩn xác 3 bước sau:

+ Bước 1: Nạp Firmware cho Phần cứng (ESP32)
  - Mở phần mềm Arduino IDE, cài đặt gói hỗ trợ bo mạch `esp32` của Espressif.
  - Tìm và cài đặt 2 thư viện bắt buộc từ Library Manager: `ESP32Servo` và `LiquidCrystal_I2C`.
  - Mở file `IOT.ino`, biên dịch và nạp code vào Mạch 1 qua cáp Micro-USB/Type-C.
  - Mở file `IOT_2.ino`, nạp code vào Mạch 2. Ngay sau khi nạp, hãy mở Serial Monitor (Baudrate 115200) để ghi lại dải địa chỉ IP nội bộ mà Router vừa cấp tự động (DHCP) cho mạch này.

+ Bước 2: Thiết lập Máy chủ Quản lý (Python Server)
  - Yêu cầu môi trường: Cài đặt Python 3.9 trở lên trên máy tính hoặc Raspberry Pi.
  - Cài đặt các thư viện lõi thông qua Terminal/Command Prompt: `pip install flask requests opencv-python numpy google-generativeai`.
  - Thiết lập AI: Mở file `ai.py` (hoặc cấu hình) để khai báo mã khóa (API Key) được cấp miễn phí từ Google AI Studio.
  - Khởi động: Mở Terminal tại thư mục `Python_ALPR`, chạy lệnh `python server.py`. Máy chủ Web Dashboard sẽ chính thức lắng nghe tại cổng `http://localhost:5000`.

+ Bước 3: Cấu hình Camera Giám sát (Điện thoại Android)
  - Truy cập CH Play, tìm và cài đặt ứng dụng `IP Webcam` (của Pavel Khlebovich).
  - Tại giao diện ứng dụng, kéo xuống phần cấu hình Video (Video Preferences) -> Hạ độ phân giải xuống mức 1920x1080 hoặc thấp hơn. Việc này đóng vai trò sống còn giúp tốc độ truyền ảnh qua mạng LAN mượt mà và không gây quá tải cho bộ định tuyến (Router).
  - Tại phần Cài đặt năng lượng (Power Management), bắt buộc tích chọn `Keep screen awake`. Thao tác này nhằm ngăn chặn hệ điều hành Android tự động cho ứng dụng ngủ đông (Doze Mode) - nguyên nhân số 1 gây ra độ trễ 2-3s mỗi lần máy chủ yêu cầu ảnh.
  - Bấm `Start Server` ở dưới cùng. Ghi chép lại dải địa chỉ IP màu đỏ hiện trên màn hình (Ví dụ: `http://192.168.1.55:8080`) để nhập vào cấu hình của Web Dashboard.

## 5. Sơ đồ hoạt động (Operation Flow)

### 5.1. Sơ đồ luồng (Flowchart)
Sơ đồ dưới đây mô tả chính xác vòng đời (Lifecycle) của một chu trình xe ra/vào tại trạm đỗ xe thông minh.

```mermaid
sequenceDiagram
    participant Xe as Ô tô - Xe máy
    participant M1 as ESP32 Mạch 1
    participant M2 as ESP32 Mạch 2
    participant Py as Python Server
    participant Cam as IP Webcam
    participant AI as Gemini API
    participant DB as SQLite DB

    Xe->>M1: 1. Tiến vào vùng quét
    activate M1
    M1->>M1: 2. Cảm biến S1 phát hiện
    M1->>M2: 3. Gửi lệnh báo hiệu
    activate M2
    M2->>Py: 4. Gọi API báo xe đến
    deactivate M2
    activate Py
    Py->>Cam: 5. Yêu cầu chụp ảnh tĩnh
    activate Cam
    Cam-->>Py: 6. Trả về mảng byte ảnh
    deactivate Cam
    
    Py->>AI: 7. Gửi ảnh lên Đám mây
    activate AI
    Note right of AI: AI phân tích và<br/>nhận diện ký tự OCR
    AI-->>Py: 8. Trả về chuỗi JSON
    deactivate AI
    
    Py->>Py: 9. Lọc dữ liệu rác (Regex)
    Py->>DB: 10. Lưu mốc thời gian
    
    Py->>M2: 11. Gửi lệnh Mở Cổng
    deactivate Py
    activate M2
    M2->>M1: 12. Truyền cờ Mở cổng
    deactivate M2
    M1->>M1: 13. Mở Servo 90 độ
    Xe->>M1: 14. Xe đi qua Barie
    M1->>M1: 15. Cảm biến S2 quét đuôi
    Note left of M1: Đợi tới khi S2 hoàn toàn<br/>trống trải mới đóng cổng
    M1->>M1: 16. Đợi 3s và Hạ Barie
    deactivate M1
```

### 5.2. Diễn giải luồng hoạt động
+ Bước 1: Phát hiện sự kiện (Trigger)
  - Xe ô tô tiến vào vùng cổng và che khuất Cảm biến siêu âm 1. Mạch 1 ngay lập tức đọc được sự giảm sút khoảng cách, kích hoạt cờ sự kiện và truyền ký tự cảnh báo qua chân UART chéo sang Mạch 2.
+ Bước 2: Kích hoạt Máy chủ (Server Wake-up)
  - Mạch 2 gửi một truy vấn HTTP GET tới Server Python. Server lập tức sử dụng thư viện `urllib` để ép Camera điện thoại nhả một khung hình ảnh (Snapshot) ngay tại khoảnh khắc đó.
+ Bước 3: Phân tích Trí tuệ Nhân tạo (AI Processing)
  - Bức ảnh được băm thành byte, nén lại và gửi vọt lên Google Gemini API kèm theo lời nhắc (Prompt) nghiêm ngặt bắt AI chỉ được phép đọc biển số.
  - Server Python nhận kết quả từ AI, sử dụng Regular Expression (Biểu thức chính quy) để cạo bỏ tất cả chữ rác, chỉ giữ lại định dạng biển chuẩn (VD: 30F-123.45).
+ Bước 4: Lưu trữ & Thực thi (Storage & Execution)
  - Biển số, đường dẫn lưu ảnh và giờ giấc (Timestamp) được ghi đè vào Cơ sở dữ liệu SQLite.
  - Cùng lúc đó, Server phản hồi lại mạch 2 một lệnh mở cổng `/open_gate`.
  - Mạch 2 truyền tín hiệu UART báo Mạch 1. Mạch 1 kích hoạt động cơ Barie mở 90 độ và nháy còi bíp bíp.
+ Bước 5: Đóng cổng An toàn (Safe Closing)
  - Xe tiến vào sân đỗ, quét qua Cảm biến siêu âm 2. Lúc này thuật toán Zero-Crash của Mạch 1 bắt đầu làm việc. Mạch 1 liên tục giám sát Cảm biến 2, chỉ khi nào đuôi xe đã hoàn toàn đi qua (Cảm biến 2 đo được khoảng cách xa trở lại), mạch mới đếm ngược 3 giây để từ từ hạ cần Barie xuống, kết thúc một vòng tuần hoàn hoàn mỹ.

## 6. Cấu trúc chi tiết của file (Detailed File Structure)
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

## 7. Danh sách Thư viện và Hàm sử dụng (Libraries & Functions Tree)

Để dễ dàng nắm bắt, toàn bộ thư viện và hàm được phân nhóm theo Luồng công việc (Workflow) và mô tả dưới dạng cấu trúc cây (Tree).

### 7.1. Luồng Phần cứng (Hardware Workflow)

+ Mạch 1: ESP32 Master Logic (`IOT.ino`)
  - [Thư viện] `ESP32Servo`: Điều khiển góc quay chính xác cho động cơ Barie.
  - [Hàm] `setup()`: Khởi tạo chân GPIO, gắn ngắt (Interrupt) cho nút bấm.
  - [Hàm] `loop()`: Vòng lặp chính, liên tục gọi hàm đo khoảng cách và đọc tín hiệu UART.
  - [Hàm] `measureDistance()`: Phát xung `TRIG` và tính toán thời gian `ECHO` để ra khoảng cách (cm).
  - [Hàm] `handleButtonInterrupt()`: Hàm ngắt (Interrupt) dùng `IRAM_ATTR` xử lý tín hiệu nhấn nút tức thời (kèm thuật toán Debounce 500ms).
  - [Hàm] `openGate()`, `closeGate()`: Ghi góc 90 độ / 0 độ cho Servo.
  - [Hàm] `buzzerAlert()`: Nhại còi bíp bíp cảnh báo xe đang di chuyển.

+ Mạch 2: ESP32 WiFi & LAN Slave (`IOT_2.ino`)
  - [Thư viện] `WiFi`: Quản lý kết nối mạng LAN/Internet qua giao thức DHCP.
  - [Thư viện] `WebServer`: Khởi tạo máy chủ HTTP tại cổng 80 để lắng nghe lệnh từ Python.
  - [Thư viện] `HardwareSerial`: Quản lý giao tiếp nối tiếp UART2 (RX=16, TX=17) để nói chuyện với Mạch 1.
  - [Thư viện] `LiquidCrystal_I2C` & `Wire`: Giao tiếp màn hình LCD qua bus I2C.
  - [Hàm] `setup()`: Khởi tạo WiFi, LCD, thiết lập các Route API (`/open_gate`, `/close_gate`).
  - [Hàm] `loop()`: Duy trì `server.handleClient()` và kiểm tra tín hiệu UART gửi từ Mạch 1.
  - [Hàm] `handleOpenGate()`: Endpoint API, khi Python gọi tới sẽ gửi cờ (flag) qua UART bắt Mạch 1 mở cổng.
  - [Hàm] `printLCD()`: Hàm tiện ích giúp in chuỗi ký tự lên màn hình LCD dễ dàng.

### 7.2. Luồng Máy chủ Backend (Python Server Workflow)

+ Lõi Máy chủ Web (`server.py`)
  - [Thư viện] `flask`: Framework siêu nhẹ để tạo Web UI quản lý bãi xe và cung cấp API nội bộ.
  - [Thư viện] `json`, `os`: Đọc ghi file cấu hình hệ thống (`config.json`).
  - [Hàm] `index()`: Render giao diện trang chủ Bảng điều khiển (Dashboard).
  - [Hàm] `capture_only()`: Hàm kích hoạt luồng ALPR (Gọi Camera chụp ảnh -> Gọi AI nhận diện -> Gọi DB lưu trữ -> Gửi HTTP Request sang Mạch 2 mở cổng).
  - [Hàm] `history()`: Trả về dữ liệu JSON lịch sử xe ra vào cho Web UI vẽ bảng.

+ Trình điều khiển Camera (`camera.py`)
  - [Thư viện] `urllib.request`: Thư viện mạng cấp thấp, dùng để bắn gói tin cực nhẹ ép IP Webcam nhả ảnh tức thì (<0.1s).
  - [Thư viện] `numpy`: Chuyển đổi luồng byte ảnh tải về thành ma trận mảng đa chiều.
  - [Thư viện] `cv2` (OpenCV): Giải mã ma trận NumPy thành khung hình ảnh (Image Frame) để thao tác.
  - [Hàm] `set_url()`: Tự động chuẩn hóa địa chỉ IP Webcam (thêm `http://` và `/shot.jpg`).
  - [Hàm] `fetch_image()`: Gửi HTTP GET tốc độ cao để lấy 1 khung hình tĩnh mới nhất từ điện thoại.

+ Trí tuệ Nhân tạo ALPR (`ai.py`)
  - [Thư viện] `google.generativeai`: Thư viện SDK chính thức kết nối với Google Gemini Vision Pro.
  - [Thư viện] `re` (Regular Expression): Bộ lọc biểu thức chính quy để làm sạch dữ liệu.
  - [Hàm] `analyze_image_for_license_plate()`: Đóng gói ảnh JPEG, xây dựng Prompt ngữ cảnh và gửi lên Cloud AI.
  - [Hàm] `parse_gemini_response()`: Dùng Regex cắt bỏ các câu trả lời thừa của AI, chỉ giữ lại đúng chuỗi JSON chứa Biển số xe.

+ Quản lý Cơ sở dữ liệu (`db.py`)
  - [Thư viện] `sqlite3`: Thư viện cơ sở dữ liệu quan hệ gọn nhẹ (SQL), lưu trực tiếp thành file nội bộ.
  - [Thư viện] `datetime`: Lấy mốc thời gian thực khi xe qua cổng.
  - [Hàm] `init_db()`: Tạo bảng `history` nếu chưa tồn tại (gồm ID, Thời gian, Biển số, Tên file ảnh).
  - [Hàm] `add_record()`: Truy vấn `INSERT INTO` để lưu lịch sử mới.
  - [Hàm] `get_history()`: Truy vấn `SELECT` để xuất danh sách lịch sử phục vụ Web UI.

## 8. Kết quả đạt được của dự án (Current Achievements)
Tính đến thời điểm hiện tại, dự án đã hoàn thành và nghiệm thu thành công các hạng mục cốt lõi, bao phủ từ phần cứng tới phần mềm:

+ Về mặt Vi mạch Phần cứng (Hardware & Electronics)
  - Khắc phục triệt để tình trạng vi điều khiển bị treo (Watchdog Reset) bằng kiến trúc 2 mạch rời song song (Decentralization).
  - Hoàn thiện thuật toán nhận diện xe bằng hệ thống 2 Cảm biến siêu âm (HC-SR04), có khả năng khử nhiễu tự động để tránh nhận nhầm người đi bộ.
  - Tích hợp thành công tính năng "Zero-Crash": Mạch liên tục quét không gian dưới barie trước và trong quá trình hạ cổng, tự động dừng và bật ngược cần lên nếu phát hiện đuôi xe chưa đi qua hết.
  - Trang bị đầy đủ giao diện tương tác vật lý tại bốt bảo vệ: Nút bấm cơ học (có thuật toán Debounce chống rung phím) và hệ thống còi báo bíp bíp cảnh báo an toàn.

+ Về mặt Giao thức Mạng và Camera (Networking & Vision)
  - Giải quyết dứt điểm tình trạng lỗi rớt mạng cục bộ (Timeout) giữa Server và mạch ESP32 khi gọi API liên tục.
  - Cấu hình lại Mạch 2 sang cơ chế xin cấp phát IP tự động (DHCP), loại bỏ hoàn toàn việc phải nạp lại code mỗi khi mang hệ thống sang một mạng WiFi mới.
  - Bước đột phá trong Camera: Bằng việc loại bỏ thư viện `requests` cồng kềnh và chuyển sang gói tin thô cấp thấp (`urllib` không kèm Header), độ trễ chụp ảnh từ IP Webcam trên điện thoại đã giảm tới 96% (từ 2.5 giây xuống dưới 0.1 giây), đảm bảo chộp dính biển số ngay khi xe vừa lăn bánh qua vạch.

+ Về mặt Trí tuệ Nhân tạo ALPR (AI Integration)
  - Xây dựng thành công kênh giao tiếp API cực kỳ ổn định giữa máy chủ cục bộ và Google Gemini Vision.
  - Tối ưu hóa câu lệnh ngữ cảnh (Prompt Engineering) giúp AI nhận diện chính xác các định dạng biển số Việt Nam (VD: 29A-123.45), vượt qua các điều kiện khắc nghiệt như: ảnh mờ lóa sáng, góc chụp nghiêng, hay xe đang di chuyển.

+ Về mặt Phần mềm Quản trị (Web Dashboard)
  - Triển khai thành công giao diện Web LAN (Flask HTML/CSS/JS) giao tiếp mượt mà trên nhiều nền tảng thiết bị (PC, Máy tính bảng, Điện thoại).
  - Hoàn thiện hệ thống CSDL Lịch sử (SQLite), tự động lưu trữ và truy xuất mốc thời gian thực (Timestamp), file ảnh thực tế và văn bản biển số đã được AI biên dịch.
  - Tích hợp Bảng điều khiển từ xa ngay trên trình duyệt (Soft-Buttons), cho phép bảo vệ can thiệp Mở/Đóng/Dừng cổng khẩn cấp chỉ bằng một cú click chuột.
