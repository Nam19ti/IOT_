import cv2
import urllib.request
import numpy as np
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
        """
        if not self.url:
            p("[CAMERA LỖI] URL Camera đang bị trống!")
            return None
            
        try:
            # Timeout 2.5 giây để nếu sai IP camera sẽ báo lỗi ngay, không bị treo 30s
            req = urllib.request.urlopen(self.url, timeout=2.5)
            arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
            img = cv2.imdecode(arr, -1)
            
            if img is not None and img.size > 0:
                return img
        except Exception as e:
            p(f"[CAMERA LỖI CHỤP HTTP]: {e} (URL: {self.url})")
            
        # Chỉ dùng VideoCapture fallback nếu URL chứa luồng video (như rtsp:// hoặc .mjpg/.mp4)
        if "rtsp://" in self.url or ".mjpg" in self.url or ".mp4" in self.url:
            try:
                cap = cv2.VideoCapture(self.url)
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None and frame.size > 0:
                    return frame
            except Exception as e2:
                p(f"[CAMERA LỖI VIDEO STREAM]: {e2}")

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

