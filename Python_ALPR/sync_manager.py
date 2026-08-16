import os
import csv
import time
import threading
import requests
import cv2
import base64
from core import p

try:
    import pymongo
except ImportError:
    pymongo = None

class SyncManager:
    def __init__(self, controller):
        self.controller = controller
        self.csv_file = os.path.join(os.path.dirname(__file__), "history", "pending_sync.csv")
        self.history_dir = os.path.join(os.path.dirname(__file__), "history")
        os.makedirs(self.history_dir, exist_ok=True)
        
        self.is_running = True
        self.sync_thread = threading.Thread(target=self._sync_worker, daemon=True)
        self.sync_thread.start()
        
    def stop(self):
        self.is_running = False

    def add_to_queue(self, plate, img_path, speed=0, direction="Unknown"):
        timestamp = int(time.time() * 1000)
        file_exists = os.path.isfile(self.csv_file)
        
        try:
            with open(self.csv_file, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['timestamp', 'plate', 'speed', 'direction', 'img_path'])
                writer.writerow([timestamp, plate, speed, direction, img_path])
            p(f"[SYNC] Da luu vao hang doi Offline (CSV): {plate}")
        except Exception as e:
            p(f"[SYNC LOI] Khong the ghi file CSV: {e}")

    def _img_to_b64(self, img_path):
        try:
            img = cv2.imread(img_path)
            if img is None: return ""
            _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 70])
            return base64.b64encode(buf).decode('utf-8')
        except Exception:
            return ""

    def _sync_worker(self):
        while self.is_running:
            time.sleep(10)
            
            if not os.path.exists(self.csv_file):
                continue
                
            rows = []
            try:
                with open(self.csv_file, mode='r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    rows = list(reader)
            except Exception as e:
                p(f"[SYNC LOI] Khong doc duoc CSV: {e}")
                continue

            if not rows:
                continue

            # Tien hanh dong bo dong dau tien
            row = rows[0]
            timestamp, plate, speed, direction, img_path = row
            
            p(f"[SYNC] Dang xu ly dong bo cho bien so: {plate}")
            success = self._process_single_sync(timestamp, plate, speed, direction, img_path)
            
            if success:
                # Xoa dong vua xu ly, luu lai CSV
                rows.pop(0)
                try:
                    with open(self.csv_file, mode='w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        if header:
                            writer.writerow(header)
                        writer.writerows(rows)
                    p(f"[SYNC] Da xoa khoi hang doi (CSV) bien so: {plate}")
                except Exception as e:
                    p(f"[SYNC LOI] Khong the cap nhat lai CSV: {e}")
            else:
                p(f"[SYNC] Ket noi mang gian doan hoac loi. Cho 10s...")

    def _process_single_sync(self, timestamp, plate, speed, direction, img_path):
        config = self.controller.config
        
        # 1. Day len Firebase
        if config.get("enable_firebase", True):
            firebase_url = config.get("firebase_url", "").strip()
            if firebase_url:
                if not firebase_url.startswith("http"):
                    firebase_url = "https://" + firebase_url
                if not firebase_url.endswith('/'):
                    firebase_url += '/'
                firebase_url += "queue.json"
                
                b64 = self._img_to_b64(img_path)
                payload = {
                    "car_id": "CAR_" + str(timestamp),
                    "speed": speed,
                    "direction": direction,
                    "plate": plate,
                    "image_base64": b64,
                    "timestamp": int(timestamp)
                }
                try:
                    r = requests.post(firebase_url, json=payload, timeout=10.0)
                    r.raise_for_status()
                    p("  -> [1/3] Firebase: OK")
                except Exception as e:
                    p(f"  -> [1/3] Firebase LOI: {e}")
                    return False # Fallback ve offline
            else:
                p("  -> [1/3] Firebase: Bo qua (Chua cau hinh URL)")
        else:
            p("  -> [1/3] Firebase: Tat theo cai dat")

        # 2. Tra cuu MongoDB & Gui Telegram
        if config.get("enable_telegram", True):
            mongo_uri = config.get("mongo_uri")
        if not mongo_uri or not pymongo:
            p("  -> [2/3] MongoDB: Bo qua (Thieu URI hoac pymongo)")
            return True # Neu khong cau hinh thi coi nhu pass de khong block queue

        telegram_id = None
        try:
            client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            db = client['iot_thanglong']
            col = db['vehicles']
            record = col.find_one({"plate": plate})
            if record and "telegram_id" in record:
                telegram_id = record["telegram_id"]
                p(f"  -> [2/3] MongoDB: Tim thay Telegram ID = {telegram_id}")
            else:
                p(f"  -> [2/3] MongoDB: Khong tim thay Telegram ID cho {plate}")
                return True # Khong co nguoi nhan thi cung la pass
        except Exception as e:
            p(f"  -> [2/3] MongoDB LOI: {e}")
            return False # Loi ket noi MongoDB

        # 3. Gui Telegram neu co
        telegram_token = config.get("telegram_token")
        if telegram_id and telegram_token:
            try:
                url = f"https://api.telegram.org/bot{telegram_token}/sendPhoto"
                caption = f"🚗 PHÁT HIỆN XE VÀO TRẠM\n- Biển số: {plate}\n- Thời gian: {time.ctime(int(timestamp)/1000)}"
                if os.path.exists(img_path):
                    with open(img_path, 'rb') as photo:
                        data = {"chat_id": telegram_id, "caption": caption}
                        files = {"photo": photo}
                        r = requests.post(url, data=data, files=files, timeout=15.0)
                        r.raise_for_status()
                    p("  -> [3/3] Telegram: Da gui tin nhan!")
                else:
                    p("  -> [3/3] Telegram: Khong tim thay anh de gui!")
            except Exception as e:
                p(f"  -> [3/3] Telegram LOI: {e}")
                return False
        else:
            p("  -> [2-3/3] Telegram: Tat theo cai dat")
                
        return True
