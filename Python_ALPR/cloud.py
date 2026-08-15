import requests
import cv2
import base64
import time
import threading
from core import p

class CloudSync:
    def __init__(self, tb_token):
        self.tb_url = "https://thingsboard.cloud/api/v1"
        self.node_url = "http://localhost:3000/api/violation"
        self.tb_token = tb_token

    def set_tb_token(self, token):
        self.tb_token = token
        p(f"[CLOUD] Da cap nhat TB Token: {token}")

    def _img_to_b64(self, img_frame):
        if img_frame is None or img_frame.size == 0:
            return ""
        try:
            # Resize anh xuong rat nho (VD: rong 320px) de nhet vua gioi han 32KB cua ThingsBoard
            h, w = img_frame.shape[:2]
            scale = 320 / float(w)
            new_dim = (320, int(h * scale))
            resized = cv2.resize(img_frame, new_dim, interpolation=cv2.INTER_AREA)
            
            # Giam chat luong xuong 50% de ep dung luong
            _, buf = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, 50])
            
            # Tra ve chuoi chuan Base64 hinh anh de the <img> tren ThingsBoard co the hien thi ngay
            return "data:image/jpeg;base64," + base64.b64encode(buf).decode('utf-8')
        except Exception as e:
            p(f"[CLOUD] Loi Encode anh: {e}")
            return ""

    def push_thingsboard(self, speed, plate, image_frame=None):
        if not self.tb_token:
            return
            
        def _task():
            b64 = self._img_to_b64(image_frame)
            payload = {"speed": speed, "plate": plate, "image_base64": b64}
            url = f"{self.tb_url}/{self.tb_token}/telemetry"
            try:
                requests.post(url, json=payload, timeout=5.0)
                p("[THINGSBOARD] Da day du lieu!")
            except Exception as e:
                p(f"[THINGSBOARD LOI] {e}")
                
        threading.Thread(target=_task, daemon=True).start()

    def push_nodejs(self, car_id, speed, direction, plate, image_filename="no_image.jpg"):
        def _task():
            payload = {
                "car_id": car_id,
                "speed": speed,
                "direction": direction,
                "plate": plate,
                "image": image_filename
            }
            try:
                requests.post(self.node_url, json=payload, timeout=3.0)
                p("[NODEJS] Da luu ho so vi pham!")
            except Exception as e:
                p(f"[NODEJS LOI] {e}")
                pass
                
        threading.Thread(target=_task, daemon=True).start()
