import json
import os
import sys
import datetime
import threading
import queue
import cv2

def p(msg):
    """
    Hàm in log ra màn hình console (Terminal) an toàn.
    Sử dụng sys.stdout để ép kiểu mã hóa UTF-8 hoặc ASCII nhằm tránh lỗi 
    UnicodeEncodeError khi in tiếng Việt có dấu trên môi trường Windows Terminal.
    """
    try:
        sys.stdout.write(str(msg) + "\n")
        sys.stdout.flush()
    except UnicodeEncodeError:
        sys.stdout.write(str(msg).encode('ascii', 'ignore').decode('ascii') + "\n")
        sys.stdout.flush()

class Config:
    """
    Lớp Config: Quản lý cấu hình toàn hệ thống (Đọc/Ghi file config.json)
    Cung cấp giao diện dễ dàng để truy xuất và cập nhật cấu hình mọi lúc mọi nơi.
    """
    def __init__(self, filename="config.json"):
        self.filename = filename
        
        # Dữ liệu cấu hình mặc định (Sẽ bị ghi đè nếu file config.json tồn tại)
        self.data = {
            "ip_camera_url": "http://192.168.137.233/photo.jpg",
            "iot2_ip": "192.168.137.199",
            "gemini_api_key": "",
            "ai_mode": "gemini", # Lựa chọn: 'gemini' (Mạng) hoặc 'easyocr' (Offline)
            "telegram_token": "8890661056:AAGlJpg1sjUXsZaz-mZu4U_E1Vmd9t8LEok",
            "mongo_uri": "mongodb+srv://talkwitht21_db_user:1234@cluster0.0dirlxq.mongodb.net/?appName=Cluster0",
            "firebase_url": "https://test-a2b8e-default-rtdb.firebaseio.com/",
            "enable_firebase": True,
            "enable_telegram": True
        }
        # Nạp cấu hình từ đĩa cứng (nếu có)
        self.load()

    def load(self):
        """Đọc file config.json và cập nhật vào biến lưu trữ (RAM)"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    self.data.update(json.load(f))
            except Exception as e:
                p(f"[CONFIG] Lỗi đọc file cấu hình: {e}")

    def save(self):
        """Ghi toàn bộ cấu hình hiện tại xuống file config.json (Lưu ổ cứng)"""
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            p(f"[CONFIG] Lỗi lưu file cấu hình: {e}")

    def get(self, key, default=None):
        """Truy xuất một giá trị cấu hình (Trả về default nếu không tồn tại)"""
        return self.data.get(key, default)

    def set(self, key, value):
        """Cập nhật giá trị cấu hình và tự động lưu xuống ổ cứng"""
        self.data[key] = value
        self.save()


class SystemController:
    """
    Lớp SystemController (Điều phối viên Hệ thống)
    Đóng vai trò là TRÁI TIM của toàn bộ Backend.
    Nó là cầu nối chứa tham chiếu đến tất cả các module khác (Camera, AI, SyncManager).
    Giúp các module dễ dàng tương tác và chia sẻ trạng thái cho nhau.
    """
    def __init__(self):
        # 1. Khởi tạo Module Cấu hình
        self.config = Config()
        
        # 2. Khởi tạo Trạng thái AI Engine
        self.ai_ready = False       # Cờ báo hiệu AI đã tải xong Model chưa
        self.ai_engine = None       # Con trỏ (Instance) trỏ tới lớp HybridOCR
        self.last_process_time = 0.0 # Thời gian trích xuất biển số gần nhất (Giây)
        self.last_violation = None  # Dict chứa thông tin chuyến xe gần nhất (dùng cho Web UI)
        self.last_capture_ts = 0    # Dấu thời gian chụp ảnh gần nhất
        
        # 3. Các Module Ngoại vi (Được khởi tạo sau bởi server.py)
        self.camera = None          # Module kết nối IP Camera
        self.sync_manager = None    # Luồng chạy nền đồng bộ Cloud
