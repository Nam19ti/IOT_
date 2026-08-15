import requests
import cv2
import base64
import time
import threading
from core import p

    def _img_to_b64_full(self, img_frame):
        if img_frame is None or img_frame.size == 0:
            return ""
        try:
            # Giam chat luong xuong 70% de bot nang, nhung KHONG resize de giu do net
            _, buf = cv2.imencode('.jpg', img_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            return base64.b64encode(buf).decode('utf-8')
        except Exception as e:
            p(f"[CLOUD] Loi Encode anh: {e}")
            return ""

    def push_firebase(self, car_id, speed, direction, plate, image_frame=None):
        firebase_url = self.config.get("firebase_url", "")
        if not firebase_url:
            p("[FIREBASE LOI] Chua cau hinh firebase_url trong config.json")
            return
            
        # Dam bao url ket thuc bang /
        if not firebase_url.endswith('/'):
            firebase_url += '/'
            
        def _task():
            b64 = self._img_to_b64_full(image_frame)
            payload = {
                "car_id": car_id,
                "speed": speed,
                "direction": direction,
                "plate": plate,
                "image_base64": b64,
                "timestamp": time.time() * 1000 # Milliseconds
            }
            
            url = f"{firebase_url}queue.json"
            try:
                requests.post(url, json=payload, timeout=10.0)
                p("[FIREBASE] Da day bien ban vi pham len Dam May thanh cong!")
            except Exception as e:
                p(f"[FIREBASE LOI] {e}")
                
        threading.Thread(target=_task, daemon=True).start()
