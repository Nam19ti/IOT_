import cv2
import urllib.request
import numpy as np
import requests
from core import p

class CameraClient:
    """
    Lớp CameraClient (Trình điều khiển Camera qua Mạng LAN)
    Chức năng chính:
    - Bắt luồng ảnh tĩnh (Snapshot) thông qua HTTP GET từ điện thoại Android (App IP Webcam).
    - Tự động chuẩn hóa địa chỉ URL người dùng nhập vào.
    - Ép kiểu dữ liệu luồng byte thành mảng đa chiều NumPy để thư viện OpenCV xử lý được.
    """
    def __init__(self, url):
        self.url = url
        # Gọi hàm set_url để tự động thêm http:// hoặc sửa lỗi URL ngay từ lúc khởi tạo
        self.set_url(url)

    def set_url(self, new_url):
        """
        Hàm gán và chuẩn hóa URL.
        Rất hữu ích vì người dùng thường lười gõ đầy đủ "http://" hoặc quên mất hậu tố "/shot.jpg".
        """
        self.url = new_url.strip() if new_url else ""
        if self.url:
            # Tự động chèn giao thức http nếu thiếu
            if not (self.url.startswith("http://") or self.url.startswith("https://") or self.url.startswith("rtsp://")):
                self.url = "http://" + self.url
                
            # Chỉ thêm /shot.jpg nếu URL chỉ gồm host:port hoặc kết thúc bằng /
            from urllib.parse import urlparse
            parsed = urlparse(self.url)
            if not parsed.path or parsed.path == "/":
                self.url = self.url.rstrip("/") + "/shot.jpg"
        p(f"[CAMERA] Đã cập nhật URL luồng ảnh: {self.url}")

    def fetch_image(self):
        """
        Lấy 1 khung hình (Frame) duy nhất từ luồng IP Webcam / Camera.
        Sử dụng Browser User-Agent để tránh bị app Android / Web server chặn.
        """
        if not self.url:
            p("[CAMERA LỖI] URL Camera đang bị trống!")
            return None

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
        }

        # 1. Thử dùng thư viện `requests` kèm User-Agent của Trình Duyệt
        try:
            r = requests.get(self.url, headers=headers, timeout=5.0)
            if r.status_code == 200 and r.content:
                arr = np.asarray(bytearray(r.content), dtype=np.uint8)
                img = cv2.imdecode(arr, -1)
                if img is not None and img.size > 0:
                    return img
            else:
                p(f"[CAMERA LỖI HTTP STATUS {r.status_code}]: {self.url}")
        except Exception as e:
            p(f"[CAMERA LỖI REQUESTS]: {e} (URL: {self.url})")

        # 2. Fallback urllib có Request Header
        try:
            req = urllib.request.Request(self.url, headers=headers)
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                arr = np.asarray(bytearray(resp.read()), dtype=np.uint8)
                img = cv2.imdecode(arr, -1)
                if img is not None and img.size > 0:
                    return img
        except Exception as e2:
            p(f"[CAMERA LỖI URLLIB]: {e2}")

        # 3. Fallback VideoCapture nếu là luồng video stream
        if "rtsp://" in self.url or ".mjpg" in self.url or ".mp4" in self.url:
            try:
                cap = cv2.VideoCapture(self.url)
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None and frame.size > 0:
                    return frame
            except Exception as e3:
                p(f"[CAMERA LỖI STREAM]: {e3}")

        return None

    def get_data(self):
        """
        (Hàm Legacy / Giữ lại cho tương thích ngược)
        Trả về nguyên khung hình (Full Frame).
        """
        frame = self.fetch_image()
        return frame, None

    def capture_frames(self, num_frames=1, interval=0):
        """
        Chụp một mảng các khung hình.
        Tuy nhiên trong phiên bản Zero-Crash này, ta chỉ cần chụp chính xác 1 bức ảnh sắc nét nhất 
        để tiết kiệm tài nguyên CPU.
        """
        frame = self.fetch_image()
        if frame is not None and frame.size > 0:
            return [(frame, None)]
        return []

