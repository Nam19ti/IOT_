import requests
import cv2
import base64
import time
import threading
from core import p

class CloudSync:
    def __init__(self, tb_token=""):
        pass

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

    def publish_ai_result(self, plate, speed, direction, img_path):
        # Doc anh tu duong dan thanh numpy array roi goi push_firebase
        img_frame = cv2.imread(img_path)
        # TODO: Lay config firebase url
        self.push_firebase("CAR_" + str(int(time.time())), speed, direction, plate, img_frame)

    def push_firebase(self, car_id, speed, direction, plate, image_frame=None):
        # Hardcode firebase_url tạm thời hoặc đọc từ file JSON nếu cần
        firebase_url = "https://test-a2b8e-default-rtdb.firebaseio.com/"
        if not firebase_url:
            p("[FIREBASE LOI] Chua cau hinh firebase_url")
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
