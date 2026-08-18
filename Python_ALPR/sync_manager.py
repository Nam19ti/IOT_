import os
import csv
import time
import threading
import requests
import cv2
import base64
from core import p, log_action

# ==========================================
# KHỞI TẠO VÀ KIỂM TRA THƯ VIỆN DATABASE
# ==========================================
try:
    import pymongo
except ImportError:
    pymongo = None

class SyncManager:
    """
    Lớp SyncManager (Trình quản lý Đồng bộ)
    Chức năng chính:
    - Quản lý Hàng đợi Ngoại tuyến (Offline Queue): Khi mất mạng, lưu tạm dữ liệu vào file CSV.
    - Quản lý Luồng chạy nền (Background Thread): Tự động đẩy dữ liệu từ CSV lên các dịch vụ Cloud khi có mạng.
    - Đồng bộ đa kênh: Firebase (Lịch sử Realtime), MongoDB (Truy vấn User), Telegram (Gửi cảnh báo).
    """
    def __init__(self, controller):
        self.controller = controller
        
        # Đường dẫn tới file lưu trữ đệm CSV (Hàng đợi)
        self.csv_file = os.path.join(os.path.dirname(__file__), "history", "pending_sync.csv")
        self.history_dir = os.path.join(os.path.dirname(__file__), "history")
        os.makedirs(self.history_dir, exist_ok=True) # Đảm bảo thư mục history luôn tồn tại
        
        # Biến cờ kiểm soát vòng lặp của luồng đồng bộ
        self.is_running = True
        
        # Khởi tạo và chạy luồng nền Daemon (Tự động chết khi Server chính dừng)
        self.sync_thread = threading.Thread(target=self._sync_worker, daemon=True)
        self.sync_thread.start()
        
    def stop(self):
        """Dừng tiến trình đồng bộ khi tắt Server"""
        self.is_running = False

    def add_to_queue(self, plate, img_path, speed=0, direction="Unknown"):
        """
        Thêm một bản ghi nhận diện mới vào cuối hàng đợi CSV.
        Được gọi bởi server.py ngay khi AI nhận diện xong (Dù có mạng hay không).
        Điều này đảm bảo luồng Web Server chính không bao giờ bị nghẽn (Blocking) do chờ mạng.
        """
        timestamp = int(time.time() * 1000) # Lấy mốc thời gian millisecond
        file_exists = os.path.isfile(self.csv_file)
        
        try:
            # Mở file CSV ở chế độ append ('a') để ghi thêm vào dòng cuối
            with open(self.csv_file, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Nếu file mới toanh, ghi dòng tiêu đề (Header) trước
                if not file_exists:
                    writer.writerow(['timestamp', 'plate', 'speed', 'direction', 'img_path'])
                
                # Ghi dữ liệu của chuyến xe
                writer.writerow([timestamp, plate, speed, direction, img_path])
            p(f"[SYNC] Đã lưu vào hàng đợi Offline (CSV): {plate}")
        except Exception as e:
            p(f"[SYNC LỖI] Không thể ghi file CSV: {e}")

    def _img_to_b64(self, img_path):
        """
        Hàm tiện ích: Đọc ảnh từ ổ cứng, nén nó (Quality 70%) 
        và chuyển sang chuỗi Base64 để nhét thẳng vào JSON gửi lên Firebase.
        """
        try:
            img = cv2.imread(img_path)
            if img is None: return ""
            _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 70])
            return base64.b64encode(buf).decode('utf-8')
        except Exception:
            return ""

    def _sync_worker(self):
        """
        HÀM CHẠY NỀN VĨNH VIỄN (Background Worker).
        Nhiệm vụ: Cứ mỗi 10 giây thức dậy 1 lần, mở file CSV ra xem có bản ghi nào chưa gửi không.
        Nếu có, bốc dòng trên cùng ra gửi. Gửi thành công thì xóa dòng đó đi. Gửi thất bại thì giữ nguyên để gửi lại sau.
        """
        while self.is_running:
            time.sleep(10) # Chu kỳ nghỉ 10s tránh ăn CPU
            
            if not os.path.exists(self.csv_file):
                continue # Nếu không có file CSV -> Hàng đợi rỗng -> Bỏ qua
                
            rows = []
            try:
                # Đọc toàn bộ nội dung file CSV lên RAM
                with open(self.csv_file, mode='r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    header = next(reader, None) # Lấy dòng tiêu đề
                    rows = list(reader) # Lấy tất cả các bản ghi còn lại
            except Exception as e:
                p(f"[SYNC LỖI] Không đọc được CSV: {e}")
                continue

            if not rows:
                continue # Không có dữ liệu -> Bỏ qua

            # Lấy bản ghi cũ nhất (ở dòng trên cùng của danh sách) để xử lý trước (FIFO)
            row = rows[0]
            if len(row) < 5:
                # Bỏ qua dòng bị lỗi định dạng (ví dụ dòng trắng cuối file)
                rows.pop(0)
                try:
                    with open(self.csv_file, mode='w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        if header:
                            writer.writerow(header)
                        writer.writerows(rows)
                except: pass
                continue
                
            timestamp, plate, speed, direction, img_path = row
            
            p(f"[SYNC] Đang xử lý đồng bộ cho biển số: {plate}")
            
            # Gọi hàm xử lý (Bắn lên DB và gửi Telegram)
            success = self._process_single_sync(timestamp, plate, speed, direction, img_path)
            
            # Chỉ khi NÀO ĐẨY LÊN MẠNG THÀNH CÔNG thì mới xóa bản ghi khỏi file CSV
            if success:
                rows.pop(0) # Xóa dòng vừa xử lý thành công khỏi list
                try:
                    # Ghi đè lại toàn bộ phần còn lại vào file CSV
                    with open(self.csv_file, mode='w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        if header:
                            writer.writerow(header)
                        writer.writerows(rows)
                    p(f"[SYNC] Đã xóa khỏi hàng đợi (CSV) biển số: {plate}")
                except Exception as e:
                    p(f"[SYNC LỖI] Không thể cập nhật lại CSV: {e}")
            else:
                p(f"[SYNC] Kết nối mạng gián đoạn hoặc lỗi. Chờ 10s để thử lại bản ghi này...")

    def _process_single_sync(self, timestamp, plate, speed, direction, img_path):
        """
        Hàm lõi: Phân loại xe (Quen/Lạ/Cảnh báo) qua MongoDB.
        Đẩy lên Firebase và Telegram tương ứng.
        """
        config = self.controller.config
        all_success = True
        
        # Biến trạng thái
        vehicle_type = "stranger" # "known", "warning", "stranger"
        telegram_id = None
        
        # ==========================================
        # BƯỚC 1: TRA CỨU & LƯU LÊN MONGODB
        # ==========================================
        mongo_uri = config.get("mongo_uri", "").strip()
        if mongo_uri and pymongo:
            try:
                import re
                client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
                db = client['iot_thanglong']
                
                # Fetch all warnings and vehicles to compare ignoring special characters
                clean_plate = re.sub(r'[^A-Z0-9]', '', plate.upper())
                
                warn_record = None
                for w in db['warnings'].find():
                    if re.sub(r'[^A-Z0-9]', '', str(w.get("plate", "")).upper()) == clean_plate:
                        warn_record = w
                        break
                        
                if warn_record:
                    vehicle_type = "warning"
                    p(f"  -> [1/2] MongoDB: CAUTION! Biển số cảnh báo {plate}")
                    # Báo tín hiệu ra UI
                    self.controller.last_warning_time = time.time()
                    self.controller.last_warning_plate = plate
                else:
                    record = None
                    for v in db['vehicles'].find():
                        if re.sub(r'[^A-Z0-9]', '', str(v.get("plate", "")).upper()) == clean_plate:
                            record = v
                            break
                            
                    if record:
                        vehicle_type = "known"
                        telegram_id = record.get("telegram_id")
                        p(f"  -> [1/2] MongoDB: Xe quen (ID = {telegram_id})")
                    else:
                        vehicle_type = "stranger"
                        p(f"  -> [1/2] MongoDB: Xe lạ {plate}")
                        
                        # XỬ LÝ XE LẠ: LƯU VÀO MONGODB COLLECTION STRANGERS
                        b64 = self._img_to_b64(img_path)
                        # Xóa cũ trước khi chèn mới để tránh trùng (tuỳ chọn)
                        db['strangers'].delete_one({"plate": plate})
                        db['strangers'].insert_one({
                            "plate": plate,
                            "image_base64": b64,
                            "image_filename": os.path.basename(img_path),
                            "timestamp": int(timestamp)
                        })
                        p(f"  -> [1/2] MongoDB: Đã lưu ảnh Xe lạ vào DB.")
                
                # ===================================================
                # LƯU VÀO COLLECTION HISTORY (Bất kể xe quen hay lạ)
                # ===================================================
                b64_hist = self._img_to_b64(img_path)
                db['history'].insert_one({
                    "plate": plate,
                    "timestamp": int(timestamp),
                    "vehicle_type": vehicle_type,  # "known", "warning", "stranger"
                    "image_base64": b64_hist,
                    "image_filename": os.path.basename(img_path),
                })
                p(f"  -> [1/2] MongoDB History: Đã lưu lịch sử xe {plate} ({vehicle_type})")
                        
            except Exception as e:
                p(f"  -> [1/2] MongoDB LỖI (Mất Mạng?): {e}")
                # Cập nhật ra UI để người dùng biết là xe đang qua nhưng mất mạng
                self.controller.last_violation = {
                    "plate": plate,
                    "status": "Mất mạng - Đang lưu tạm",
                    "proc_time": 0,
                    "ts": time.strftime("%H:%M:%S", time.localtime(timestamp/1000)),
                    "image": os.path.basename(img_path)
                }
                return False # Lỗi DB, không biết quen lạ, trả False để chờ lại
        else:
            p("  -> [1/2] MongoDB: Bỏ qua (Thiếu URI hoặc chưa cài pymongo)")
            # Không có Mongo thì coi như xong luôn, không treo hàng đợi
            return True

        # ==========================================
        # BƯỚC 2: GỬI TELEGRAM BOT (Chỉ áp dụng xe Quen/Cảnh báo)
        # ==========================================
        if config.get("enable_telegram", True):
            telegram_token = config.get("telegram_token", "").strip()
            
            target_chat_id = None
            if vehicle_type == "known" and telegram_id:
                target_chat_id = telegram_id
            elif vehicle_type in ("warning", "stranger"):
                target_chat_id = config.get("admin_telegram_id", "8785323128").strip()
                
            if target_chat_id and telegram_token:
                try:
                    url = f"https://api.telegram.org/bot{telegram_token}/sendPhoto"
                    if vehicle_type == "warning":
                        prefix = "⚠️ XE CẢNH BÁO XUẤT HIỆN"
                    elif vehicle_type == "known":
                        prefix = "🚗 XE QUEN VÀO TRẠM"
                    else:
                        prefix = "❓ XE LẠ VÀO TRẠM"
                    caption = f"{prefix}\n- Biển số: {plate}\n- Thời gian: {time.ctime(int(timestamp)/1000)}"
                    
                    if os.path.exists(img_path):
                        with open(img_path, 'rb') as photo:
                            data = {"chat_id": target_chat_id, "caption": caption}
                            files = {"photo": photo}
                            r = requests.post(url, data=data, files=files, timeout=15.0)
                            r.raise_for_status()
                        p(f"  -> [2/2] Telegram: Đã gửi thông báo cho {target_chat_id}!")
                    else:
                        p("  -> [3/3] Telegram: Không tìm thấy file ảnh vật lý trên ổ cứng!")
                except Exception as e:
                    p(f"  -> [3/3] Telegram LỖI: {e}")
                    # KHÔNG gán all_success = False ở đây nữa để tránh spam MongoDB nếu cấu hình Telegram bị sai
            else:
                if vehicle_type == "stranger":
                    p("  -> [3/3] Telegram: Bỏ qua (Do là xe lạ)")
                else:
                    p("  -> [3/3] Telegram: Không gửi (Thiếu Token hoặc ID)")
        else:
            p("  -> [3/3] Telegram: Tắt theo cài đặt")
                
        return all_success
