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
            if not self.url.startswith("http://") and not self.url.startswith("https://"):
                self.url = "http://" + self.url
                
            # IP Webcam Android cung cấp ảnh tĩnh ở đường dẫn /photo.jpg hoặc /shot.jpg
            # Nếu người dùng chỉ nhập IP (vd: 192.168.1.5:8080), tự động gắp /shot.jpg vào đuôi
            if not self.url.endswith(".jpg"):
                if self.url.endswith("/"):
                    self.url += "shot.jpg"
                else:
                    self.url += "/shot.jpg"
        p(f"[CAMERA] Đã cập nhật URL luồng ảnh: {self.url}")

    def fetch_image(self):
        """
        Lấy 1 khung hình (Frame) duy nhất từ luồng IP Webcam.
        Được thiết kế cực kỳ an toàn (Bọc try-catch) để nếu camera rớt mạng, 
        Server Python không bị văng lỗi (Crash) mà chỉ âm thầm trả về None.
        """
        if not self.url:
            return None
            
        try:
            # Tạo HTTP Request với Timeout 10s để tránh bị treo Server nếu mạng nội bộ yếu
            req = urllib.request.urlopen(self.url, timeout=10.0)
            
            # Đọc byte nhị phân thô từ mạng và ép kiểu thành mảng NumPy 1 chiều (uint8)
            arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
            
            # Dùng OpenCV giải mã mảng 1 chiều đó thành Ma trận ảnh đa chiều (BGR Format)
            img = cv2.imdecode(arr, -1)
            
            # CHECK MẢNG NUMPY AN TOÀN: Đảm bảo ảnh tải về không bị lỗi hay trống rỗng
            if img is not None and img.size > 0:
                return img
        except Exception:
            pass # Nuốt lỗi, coi như chụp xịt
            
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

