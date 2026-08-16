import os
import csv
import time
import threading
import requests
import cv2
import base64
from core import p

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
        Hàm lõi: Thực thi việc đẩy 1 bản ghi lên 3 nền tảng Cloud.
        Trả về True nếu thành công (hoặc cấu hình bị tắt).
        Trả về False nếu Lỗi Mạng (Để hàng đợi không bị xóa).
        """
        config = self.controller.config
        
        # ==========================================
        # BƯỚC 1: ĐẨY DỮ LIỆU LÊN FIREBASE REALTIME DB
        # ==========================================
        if config.get("enable_firebase", True):
            firebase_url = config.get("firebase_url", "").strip()
            if firebase_url:
                # Chuẩn hóa URL Firebase (Thêm https và .json vào cuối để gọi API)
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
                    # Gọi API REST POST của Firebase
                    r = requests.post(firebase_url, json=payload, timeout=10.0)
                    r.raise_for_status() # Sinh lỗi nếu mã HTTP > 400
                    p("  -> [1/3] Firebase: OK")
                except Exception as e:
                    p(f"  -> [1/3] Firebase LỖI: {e}")
                    return False # Báo lỗi mạng để Fallback (giữ lại trong hàng đợi)
            else:
                p("  -> [1/3] Firebase: Bỏ qua (Chưa cấu hình URL)")
        else:
            p("  -> [1/3] Firebase: Tắt theo cài đặt")

        # ==========================================
        # BƯỚC 2: TRA CỨU ID CHỦ PHƯƠNG TIỆN TRONG MONGODB
        # ==========================================
        if config.get("enable_telegram", True):
            mongo_uri = config.get("mongo_uri")
            
        # Nếu người dùng không điền Link Mongo, tự động pass qua luôn không lưu trữ rườm rà
        if not mongo_uri or not pymongo:
            p("  -> [2/3] MongoDB: Bỏ qua (Thiếu URI hoặc chưa cài pymongo)")
            return True 

        telegram_id = None
        try:
            # Kết nối Mongo với Timeout ngắn (5s) để không bị treo
            client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            db = client['iot_thanglong']
            col = db['vehicles']
            
            # Tìm biển số trong bộ sưu tập (Collection)
            record = col.find_one({"plate": plate})
            if record and "telegram_id" in record:
                telegram_id = record["telegram_id"]
                p(f"  -> [2/3] MongoDB: Tìm thấy Telegram ID = {telegram_id}")
            else:
                p(f"  -> [2/3] MongoDB: Không tìm thấy Telegram ID nào cho biển số {plate}")
                return True # Xe khách lạ, không có telegram để gửi -> Pass qua dòng này để xóa khỏi queue
        except Exception as e:
            p(f"  -> [2/3] MongoDB LỖI: {e}")
            return False # Lỗi kết nối CSDL, trả False để chờ vòng lặp sau thử lại

        # ==========================================
        # BƯỚC 3: GỬI HÌNH ẢNH VÀ CẢNH BÁO QUA TELEGRAM BOT
        # ==========================================
        telegram_token = config.get("telegram_token")
        if telegram_id and telegram_token:
            try:
                # Dùng Bot API của Telegram để nã tin nhắn hình ảnh (Multipart FormData)
                url = f"https://api.telegram.org/bot{telegram_token}/sendPhoto"
                caption = f"🚗 PHÁT HIỆN XE VÀO TRẠM\n- Biển số: {plate}\n- Thời gian: {time.ctime(int(timestamp)/1000)}"
                
                if os.path.exists(img_path):
                    with open(img_path, 'rb') as photo:
                        data = {"chat_id": telegram_id, "caption": caption}
                        files = {"photo": photo}
                        r = requests.post(url, data=data, files=files, timeout=15.0)
                        r.raise_for_status()
                    p("  -> [3/3] Telegram: Đã gửi tin nhắn thành công!")
                else:
                    p("  -> [3/3] Telegram: Không tìm thấy file ảnh vật lý trên ổ cứng!")
            except Exception as e:
                p(f"  -> [3/3] Telegram LỖI: {e}")
                return False # Lỗi gửi tin, giữ trong queue để gửi bù
        else:
            p("  -> [2-3/3] Telegram: Tắt theo cài đặt")
                
        # Tất cả các bước hoàn tất hoặc bị bỏ qua có chủ đích
        return True
