import cv2
import urllib.request
import numpy as np
from core import p

class CameraClient:
    def __init__(self, url):
        self.url = url
        self.set_url(url)

    def set_url(self, new_url):
        self.url = new_url.strip() if new_url else ""
        if self.url:
            if not self.url.startswith("http://") and not self.url.startswith("https://"):
                self.url = "http://" + self.url
                
            # Chi tu dong them neu nguoi dung quen them duong dan anh
            if not self.url.endswith(".jpg"):
                if self.url.endswith("/"):
                    self.url += "shot.jpg"
                else:
                    self.url += "/shot.jpg"
        p(f"[CAMERA] Da cap nhat URL: {self.url}")

    def fetch_image(self):
        """Lay 1 frame tu IP Webcam an toan nhat co the"""
        if not self.url:
            return None
        try:
            req = urllib.request.urlopen(self.url, timeout=10.0)
            arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
            img = cv2.imdecode(arr, -1)
            # CHECK MANG NUMPY AN TOAN:
            if img is not None and img.size > 0:
                return img
        except Exception:
            pass
        return None

    def get_data(self):
        """Khong dung MOG2 nua. Tra ve nguyen khung hinh (Full Frame)"""
        frame = self.fetch_image()
        return frame, None

    def capture_frames(self, num_frames=1, interval=0):
        """Chi chup 1 anh duy nhat de tiet kiem CPU"""
        frame = self.fetch_image()
        if frame is not None and frame.size > 0:
            return [(frame, None)]
        return []
