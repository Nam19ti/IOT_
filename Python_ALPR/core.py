import json
import os
import sys
import datetime
import threading
import queue
import cv2

def p(msg):
    """Log an toan tren Windows CMD"""
    sys.stdout.write(str(msg) + "\n")
    sys.stdout.flush()

class Config:
    def __init__(self, filename="config.json"):
        self.filename = filename
        self.data = {
            "ip_camera_url": "http://192.168.1.100:8080/photo.jpg",
            "gemini_api_key": "",
            "firebase_url": ""
        }
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    self.data.update(json.load(f))
            except Exception as e:
                p(f"[CONFIG] Loi doc file: {e}")

    def save(self):
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            p(f"[CONFIG] Loi luu file: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()


class SystemController:
    """Trung tam quan ly trang thai he thong de tranh dung do luong"""
    def __init__(self):
        self.config = Config()
        
        # Trang thai AI
        self.ai_ready = False
        self.ai_engine = None
        self.last_process_time = 0.0
        self.last_violation = None
        self.last_capture_ts = 0
        
        # Modules
        self.camera = None
        self.cloud = None
        self.mqtt = None
        
        # Hang doi xu ly tuan tu
        self.task_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

    def _worker_loop(self):
        """Lay xe trong hang doi ra phan tich tuan tu"""
        while True:
            task = self.task_queue.get()
            if task is None:
                break
            
            car_id, speed, direction, frames_data = task
            self._process_violation(car_id, speed, direction, frames_data)
            self.task_queue.task_done()

    def trigger_violation(self, car_id, speed, direction):
        """Duoc goi boi MQTT khi co xe chay qua"""
        if not self.ai_ready:
            p(f"    -> [CANH BAO] AI chua san sang. Chi luu toc do {speed}km/h.")
            if self.cloud:
                self.cloud.push_firebase(car_id, speed, direction, "AI loading...")
            if self.mqtt:
                self.mqtt.publish_plate(car_id, speed, direction, "AI loading...")
            return
            
        # 1. CHUP ANH NGAY LAP TUC TRUYEN SANG HANG DOI
        # Dieu nay giup bat dung khoanh khac xe qua du hang doi co dang ban OCR cho xe truoc do.
        captured_frames = []
        if self.camera:
            try:
                captured_frames = self.camera.capture_frames(num_frames=3, interval=0.05)
                # Luu ngay hinh anh dau tien de hien thi len Web UI
                if captured_frames and captured_frames[0][0] is not None:
                    os.makedirs("violations", exist_ok=True)
                    cv2.imwrite("violations/latest_capture.jpg", captured_frames[0][0])
                    import time
                    self.last_capture_ts = time.time()
            except Exception as e:
                p(f"    -> [LOI CAMERA] {e}")
                
        p(f"    -> [CAMERA] Da chup {len(captured_frames)} anh lien tiep. Cho vao hang doi (Cho: {self.task_queue.qsize()} xe)")
        self.task_queue.put((car_id, speed, direction, captured_frames))

    def _process_violation(self, car_id, speed, direction, frames_data):
        """Ham thuc thi that su, chay tuan tu"""
        import time
        start_t = time.time()
        p(f"\n[XU LY] ID={car_id} | Toc do={speed} km/h | Chieu={direction}")
        
        try:
            if not frames_data or len(frames_data) == 0:
                raise Exception("Camera khong the chup anh luc nhan tin hieu!")

            p(f"    -> Dang chay AI tren {len(frames_data)} anh...")
            plate, engine, best_frame = self.ai_engine.process_pipeline(frames_data)
            
            # Luu anh
            image_filename = "no_image.jpg"
            if plate not in ("Khong Thay Bien", "Loi Camera", "Khong"):
                os.makedirs("violations", exist_ok=True)
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                image_filename = f"{plate}_{ts}.jpg"
                img_path = os.path.join("violations", image_filename)
                
                # Ve thong tin vi pham len anh (Watermark bang chung)
                if best_frame is not None and best_frame.size > 0:
                    # Tao nen den nhat de chu de doc
                    overlay = best_frame.copy()
                    cv2.rectangle(overlay, (0, 0), (450, 110), (0, 0, 0), -1)
                    cv2.addWeighted(overlay, 0.6, best_frame, 0.4, 0, best_frame)
                    
                    # In chu
                    time_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    cv2.putText(best_frame, f"TRAM THU PHI ETC", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 165, 255), 2) # Cam (Cam nhat)
                    cv2.putText(best_frame, f"THOI GIAN: {time_str}", (15, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2) # Vang
                    cv2.putText(best_frame, f"BIEN SO: {plate}", (15, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2) # Xanh
                    
                    cv2.imwrite(img_path, best_frame)
            elapsed = round(time.time() - start_t, 2)
            self.last_process_time = elapsed
            
            self.last_violation = {
                "plate": plate,
                "speed": speed,
                "direction": direction,
                "engine": engine,
                "proc_time": elapsed,
                "image": image_filename,
                "ts": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            }
            
            p(f"    -> [HOAN TAT] Bien so='{plate}' | Time={elapsed}s")
            
            # Day len Cloud
            if self.cloud:
                self.cloud.push_firebase(car_id, speed, direction, plate, best_frame)
                
            # Tra ve MQTT
            if self.mqtt:
                self.mqtt.publish_plate(car_id, speed, direction, plate)
                
        except Exception as e:
            p(f"    -> [LOI NGHIEM TRONG]: {e}")
            if self.cloud:
                self.cloud.push_firebase(car_id, speed, direction, "Loi Camera")
            if self.mqtt:
                self.mqtt.publish_plate(car_id, speed, direction, "Loi Camera")
