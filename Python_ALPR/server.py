# Import thư viện quản lý thời gian
import time
# Import thư viện xử lý đa luồng, giúp ứng dụng chạy nền các tác vụ nặng (như load AI, Cloudflare)
import threading
# Import Flask - Web framework nhẹ để tạo API và Web server
from flask import Flask, Response, jsonify, request, send_file, session
# Import OpenCV để xử lý ảnh (đọc, ghi ảnh, tiền xử lý nếu cần)
import cv2
# Import thư viện os để làm việc với đường dẫn, tệp tin và thư mục hệ thống
import os
# Import thư viện datetime để lấy thời gian thực, dùng cho log và lưu tên file
import datetime
# Import shutil hỗ trợ các thao tác sao chép file
import shutil

# Import các thành phần (modules) cốt lõi của hệ thống từ các file tự định nghĩa
from core import SystemController, p, log_action # p là hàm in log ra console
from camera import CameraClient # Class để kết nối với camera ESP32/IP camera
from ai import HybridOCR # Class chứa AI nhận diện biển số (EasyOCR + Gemini)
from cloud import CloudSync # Class đồng bộ dữ liệu lên cloud
from sync_manager import SyncManager # Class quản lý hàng đợi và tiến trình đồng bộ dữ liệu


def create_app(controller):
    """
    Hàm khởi tạo ứng dụng Web Flask.
    Truyền vào đối tượng controller chứa toàn bộ trạng thái (state) và cấu hình của hệ thống.
    """
    app = Flask(__name__)
    app.secret_key = controller.config.get("secret_key", "iot-thanglong-secret-key-123")
    
    @app.before_request
    def require_login():
        # Các đường dẫn được phép truy cập không cần đăng nhập
        allowed_endpoints = ['login', 'trigger_capture', 'serve_image']
        if request.endpoint in allowed_endpoints or (request.path and request.path.startswith('/static')):
            return
            
        if not session.get('logged_in'):
            # Nếu là request API -> Trả về lỗi 401 JSON
            if request.path.startswith('/api/') or request.path in ['/get_stats', '/capture_only', '/process_latest', '/test_ocr', '/set_settings']:
                return jsonify({"success": False, "error": "Unauthorized"}), 401
            # Nếu là request giao diện Web -> Trả về trang HTML Login
            from web_html import get_login_html
            return get_login_html(controller)
            
    @app.route('/login', methods=['POST'])
    def login():
        data = request.json or {}
        pwd = data.get("password", "")
        admin_pwd = controller.config.get("admin_password", "admin")
        if pwd == admin_pwd:
            session['logged_in'] = True
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Sai mật khẩu"})
        
    @app.route('/logout', methods=['POST'])
    def logout():
        session.pop('logged_in', None)
        return jsonify({"success": True})
        
    @app.route('/api/offline_queue', methods=['GET'])
    def get_offline_queue():
        """Đọc file CSV hiển thị lên UI cho người dùng xem"""
        import csv
        import os
        csv_file = os.path.join(os.path.dirname(__file__), "history", "pending_sync.csv")
        if not os.path.exists(csv_file):
            return jsonify({"success": True, "data": []})
        try:
            with open(csv_file, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            return jsonify({"success": True, "data": rows})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
            
    @app.route('/api/strangers', methods=['GET'])
    def get_strangers():
        """Lấy danh sách xe lạ từ MongoDB để hiển thị lên Web UI"""
        mongo_uri = controller.config.get("mongo_uri")
        if not mongo_uri:
            return jsonify({})
        try:
            import pymongo
            client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            db = client['iot_thanglong']
            
            # Lấy tất cả từ collection strangers, sắp xếp mới nhất lên đầu
            strangers = db['strangers'].find().sort("timestamp", -1)
            result = {}
            for s in strangers:
                key = str(s['_id'])
                result[key] = {
                    "plate": s.get("plate", "Unknown"),
                    "timestamp": s.get("timestamp", 0),
                    "image_base64": s.get("image_base64", "")
                }
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": str(e)})

    @app.route('/api/stranger/action', methods=['POST'])
    def handle_stranger():
        """Xử lý Duyệt / Xóa / Cảnh báo xe lạ bằng MongoDB"""
        data = request.json
        action = data.get("action") # "approve", "warn", "delete"
        plate = data.get("plate")
        key = data.get("key") # ObjectID string trên Mongo
        
        mongo_uri = controller.config.get("mongo_uri")
        if not mongo_uri:
            return jsonify({"success": False, "error": "Thiếu MongoDB URI"})
            
        try:
            import pymongo
            import re
            from bson.objectid import ObjectId
            
            client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            db = client['iot_thanglong']
            
            clean_plate = re.sub(r'[^A-Z0-9]', '', plate.upper())
            
            # 1. Thao tác thêm vào Vehicles hoặc Warnings
            if action == "approve":
                found = False
                for v in db['vehicles'].find():
                    if re.sub(r'[^A-Z0-9]', '', str(v.get("plate", "")).upper()) == clean_plate:
                        found = True; break
                if not found:
                    db['vehicles'].insert_one({"plate": plate, "telegram_id": "", "name": "Khách quen (Web)"})
                    
            elif action == "warn":
                found = False
                for w in db['warnings'].find():
                    if re.sub(r'[^A-Z0-9]', '', str(w.get("plate", "")).upper()) == clean_plate:
                        found = True; break
                if not found:
                    db['warnings'].insert_one({"plate": plate, "reason": "Cảnh báo từ Web"})
                    
            elif action == "recheck":
                record = None
                for v in db['vehicles'].find():
                    if re.sub(r'[^A-Z0-9]', '', str(v.get("plate", "")).upper()) == clean_plate:
                        record = v
                        break
                if record:
                    telegram_id = record.get("telegram_id")
                    s_record = db['strangers'].find_one({"_id": ObjectId(key)}) if key else None
                    if telegram_id and s_record and controller.config.get("enable_telegram", True):
                        telegram_token = controller.config.get("telegram_token", "").strip()
                        if telegram_token:
                            import requests, os, time
                            url = f"https://api.telegram.org/bot{telegram_token}/sendPhoto"
                            caption = f"🚗 PHÁT HIỆN XE VÀO TRẠM\n- Biển số: {plate}\n- Thời gian: {time.ctime(int(s_record.get('timestamp', time.time()*1000))/1000)}"
                            img_filename = s_record.get("image_filename")
                            sent = False
                            if img_filename:
                                img_path = os.path.join(os.path.dirname(__file__), 'history', img_filename)
                                if os.path.exists(img_path):
                                    with open(img_path, 'rb') as photo:
                                        requests.post(url, data={"chat_id": telegram_id, "caption": caption}, files={"photo": photo}, timeout=15.0)
                                        log_action("TELEGRAM_SENT", f"Sent Recheck alert (With Image) to {telegram_id} for plate {plate}")
                                    sent = True
                            if not sent:
                                requests.post(f"https://api.telegram.org/bot{telegram_token}/sendMessage", data={"chat_id": telegram_id, "text": caption}, timeout=15.0)
                                log_action("TELEGRAM_SENT", f"Sent Recheck alert (No Image) to {telegram_id} for plate {plate}")
                    
                    if key: db['strangers'].delete_one({"_id": ObjectId(key)})
                    return jsonify({"success": True, "result": "known"})
                else:
                    return jsonify({"success": True, "result": "stranger"})
            
            # 2. Xóa khỏi danh sách Xe Lạ trên MongoDB (Chỉ áp dụng cho các nút Duyệt/Cảnh báo/Xóa bỏ)
            if key and action != "recheck":
                db['strangers'].delete_one({"_id": ObjectId(key)})
                
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    
    @app.route('/captures/<filename>')
    def serve_image(filename):
        """
        [Route] /captures/<filename>
        Mục đích: Trả về file ảnh từ thư mục 'captures' để hiển thị lên Web UI.
        Giải thích: Khi UI cần tải ảnh biển số, nó sẽ gọi URL này.
        """
        # Xác định đường dẫn thư mục chứa ảnh vừa chụp
        path = os.path.join(os.path.dirname(__file__), 'captures', filename)
        # Nếu file tồn tại trên ổ cứng thì trả về file ảnh dạng jpeg
        if os.path.exists(path):
            return send_file(path, mimetype='image/jpeg')
        # Nếu không tìm thấy file, trả về lỗi 404
        return "Not found", 404
        
    
    @app.route('/history/<path:filename>')
    def serve_history(filename):
        """Trả về file log hoặc file ảnh lưu trong thư mục history"""
        import os
        path = os.path.join(os.path.dirname(__file__), 'history', filename)
        if os.path.exists(path):
            if filename.endswith(".csv"):
                return send_file(path, mimetype='text/csv')
            return send_file(path, mimetype='image/jpeg')
        return "Not found", 404
        
    @app.route('/api/history')
    def api_history():
        """Trả về 50 lịch sử nhận diện gần nhất từ MongoDB"""
        from cloud import MongoDBClient
        if not controller.config.get("enable_firebase", True):
            return jsonify({"success": False, "error": "Đám mây đang tắt. Chỉ lưu nội bộ."})
        mongo_uri = controller.config.get("mongo_uri", "").strip()
        if not mongo_uri:
            return jsonify({"success": False, "error": "Chưa cấu hình MongoDB URI."})
        try:
            db_client = MongoDBClient(mongo_uri)
            db = db_client.get_database()
            if db is None:
                return jsonify({"success": False, "error": "Không thể kết nối MongoDB."})
            
            records = list(db['history'].find().sort("timestamp", -1).limit(50))
            data = []
            for r in records:
                # Get the base64 image or just rely on the history URL if we synced it
                # actually, history objects in Mongo have "plate", "timestamp", "image_base64"
                item = {
                    "plate": r.get("plate", ""),
                    "timestamp": r.get("timestamp", 0),
                    "image_base64": r.get("image_base64", "")
                }
                data.append(item)
            return jsonify({"success": True, "data": data})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})
    @app.route('/get_stats')
    def get_stats():
        """
        [Route] /get_stats
        Mục đích: Lấy trạng thái hiện tại của hệ thống để cập nhật liên tục lên Web UI.
        Giải thích: UI gọi hàm này qua AJAX để biết AI đã load xong chưa, thời gian xử lý,
        vi phạm gần nhất và thời điểm chụp ảnh gần nhất.
        """
        return jsonify({
            "ai_ready": controller.ai_ready, # Cờ báo hiệu AI engine đã sẵn sàng
            "last_time": controller.last_process_time, # Thời gian tiêu tốn cho lần xử lý OCR gần nhất
            "last_violation": controller.last_violation, # Thông tin chi tiết của lần nhận diện gần nhất
            "last_capture_ts": controller.last_capture_ts, # Thời gian chụp ảnh lần cuối
            "last_warning_time": getattr(controller, 'last_warning_time', 0),
            "last_warning_plate": getattr(controller, 'last_warning_plate', "")
        })
        
    @app.route('/capture_only')
    def capture_only():
        """
        [Route] /capture_only
        Mục đích: Chỉ thực hiện việc kết nối camera để chụp 1 bức ảnh, lưu lại, KHÔNG chạy nhận diện.
        Giải thích: Dành cho chức năng thử nghiệm hoặc các quy trình chia nhỏ (chụp ảnh xong, sau đó mới gọi xử lý ảnh).
        """
        p("[WEB] Nhan lenh Chup Anh don thuan tu IP Webcam...")
        try:
            # Lấy 1 frame (khung hình) từ camera, không có khoảng trễ
            frames = controller.camera.capture_frames(num_frames=1, interval=0)
            # Kiểm tra tính hợp lệ của ảnh chụp
            if not frames or frames[0][0] is None:
                return jsonify({"success": False, "error": "Khong chup duoc anh. Kiem tra URL IP Webcam!"})
            
            # Tạo thư mục captures nếu chưa có
            os.makedirs("captures", exist_ok=True)
            # Lưu ảnh xuống đĩa cứng với tên 'latest_capture.jpg' để làm chuẩn
            cv2.imwrite("captures/latest_capture.jpg", frames[0][0])
            # Lưu lại thời điểm chụp ảnh vào controller
            controller.last_capture_ts = time.time()
            p("    -> Da chup va luu anh thanh cong!")
            return jsonify({"success": True})
        except Exception as e:
            p(f"    -> [LOI] {e}")
            return jsonify({"success": False, "error": str(e)})

    @app.route('/open_gate', methods=['GET', 'POST'])
    def open_gate():
        import requests, threading, time
        try:
            requests.get("http://192.168.137.199/open_gate", timeout=3)
            def auto_close():
                time.sleep(3)
                try: requests.get("http://192.168.137.199/close_gate", timeout=3)
                except: pass
            threading.Thread(target=auto_close).start()
            return jsonify({"success": True})
        except:
            return jsonify({"success": False, "error": "Khong the ket noi den ESP32"})

    @app.route('/open_gate_manual', methods=['GET', 'POST'])
    def open_gate_manual():
        import requests
        try:
            requests.get("http://192.168.137.199/open_gate_manual", timeout=3)
            return jsonify({"success": True})
        except:
            return jsonify({"success": False, "error": "Khong the ket noi den ESP32"})

    @app.route('/close_gate', methods=['GET', 'POST'])
    def close_gate():
        import requests
        try:
            requests.get("http://192.168.137.199/close_gate", timeout=3)
            return jsonify({"success": True})
        except:
            return jsonify({"success": False, "error": "Khong the ket noi den ESP32"})

    @app.route('/process_latest')
    def process_latest():
        """
        [Route] /process_latest
        Mục đích: Chạy thuật toán AI/OCR lên bức ảnh 'latest_capture.jpg' vừa được lưu trên đĩa.
        Giải thích: Kết hợp với route '/capture_only' để tạo thành luồng phân đoạn trên giao diện Web 
        (UI gọi hàm chụp, sau đó gọi hàm nhận diện).
        """
        # Trả về lỗi nếu AI chưa nạp xong lên RAM
        if not controller.ai_ready:
            return jsonify({"success": False, "error": "AI chua load xong!"})
            
        # Đường dẫn file ảnh đã được chụp gần nhất
        img_path = os.path.join(os.path.dirname(__file__), "captures", "latest_capture.jpg")
        if not os.path.exists(img_path):
            return jsonify({"success": False, "error": "Khong tim thay anh de nhan dien"})
            
        # Đánh dấu thời điểm bắt đầu xử lý để đo hiệu năng
        start = time.time()
        # Đọc ảnh từ đĩa lên ma trận OpenCV
        img = cv2.imread(img_path)
        # Format dữ liệu theo dạng (ảnh, timestamp=None) để đưa vào AI engine
        frames = [(img, None)]
        
        try:
            # GỌI AI ENGINE xử lý luồng nhận diện, trả về biển số, tên engine và ảnh đã crop
            plate, engine, cropped_frame = controller.ai_engine.process_pipeline(frames)
            
            # Lưu ảnh crop (hoặc ảnh gốc nếu không crop được) để hiển thị trên web
            crop_filename = "latest_crop.jpg"
            crop_path = os.path.join(os.path.dirname(__file__), "captures", crop_filename)
            if cropped_frame is not None:
                cv2.imwrite(crop_path, cropped_frame)
            else:
                shutil.copy2(img_path, crop_path)
            
            # Tính thời gian đã chạy
            elapsed = round(time.time() - start, 2)
            controller.last_process_time = elapsed
            
            # Cập nhật trạng thái nhận diện vào controller để Web UI có thể đọc được
            controller.last_violation = {
                "plate": plate,
                "status": "Test Thu Cong",
                "proc_time": elapsed,
                "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "image": crop_filename
            }
            
            # SAO LƯU (BACKUP) - Lưu trữ ảnh lịch sử
            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            # Đặt tên file history: thời_gian_biển_số.jpg
            history_path = os.path.join(os.path.dirname(__file__), "history", f"{timestamp_str}_{plate}.jpg")
            os.makedirs(os.path.dirname(history_path), exist_ok=True)
            # Copy ảnh từ thư mục captures sang history
            shutil.copy2(img_path, history_path)
            
            # Đồng bộ dữ liệu: Đẩy biển số và ảnh vào hàng đợi để gửi lên Cloud / CSDL (MongoDB/Firebase)
            controller.sync_manager.add_to_queue(plate, history_path)
            
            p(f"    -> [HOAN TAT OCR] Bien so='{plate}' | Time={elapsed}s")
            # Trả về JSON thành công kèm biển số
            return jsonify({"success": True, "plate": plate, "engine": engine, "time": elapsed})
        except Exception as e:
            p(f"    -> [LOI OCR]: {e}")
            return jsonify({"success": False, "error": str(e)})

    @app.route('/test_ocr')
    def test_ocr():
        """
        [Route] /test_ocr
        Mục đích: Nút test nhanh toàn bộ luồng (Chụp ảnh trực tiếp từ camera -> Nhận diện ngay lập tức).
        Giải thích: Khác với quy trình 2 bước ở trên, hàm này làm gộp cả chụp ảnh và nhận diện.
        """
        # Kiểm tra AI
        if not controller.ai_ready:
            p("[WEB] Nhan nut Test OCR nhung AI chua san sang!")
            return jsonify({"success": False, "error": "AI chua load xong!"})
            
        start = time.time()
        p("\n[WEB] Nhan lenh Test OCR thu cong...")
        try:
            # 1. Chụp ảnh từ camera
            frames = controller.camera.capture_frames(num_frames=1, interval=0.0)
            if not frames:
                p("    -> [LOI] Khong chup duoc anh tu IP Webcam!")
                return jsonify({"success": False, "error": "Loi camera hoac URL khong dung"})
                
            # 2. Lưu ảnh tạm thời
            if frames and frames[0][0] is not None:
                os.makedirs("captures", exist_ok=True)
                cv2.imwrite("captures/latest_capture.jpg", frames[0][0])
                controller.last_capture_ts = time.time()
                
            p(f"    -> Da chup {len(frames)} frame. Dang chay AI Gemini...")
            
            # 3. Gửi ảnh cho AI xử lý nhận diện biển số
            plate, engine, _ = controller.ai_engine.process_pipeline(frames)
            elapsed = round(time.time() - start, 2)
            controller.last_process_time = elapsed
            
            # 4. Ghi nhận thông tin vào controller
            controller.last_violation = {
                "plate": plate,
                "status": "Test Thu Cong",
                "proc_time": elapsed,
                "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "image": "latest_capture.jpg"
            }
            
            p(f"    -> [HOAN TAT TEST] Bien so='{plate}' | Time={elapsed}s")
            return jsonify({"success": True, "plate": plate, "engine": engine, "time": elapsed})
        except Exception as e:
            p(f"    -> [LOI TEST]: {e}")
            return jsonify({"success": False, "error": str(e)})

    @app.route('/trigger_capture')
    def trigger_capture():
        """
        [Route] /trigger_capture
        Mục đích: Điểm đón tín hiệu từ phần cứng (mạch ESP, Arduino). 
        Giải thích: Khi phần cứng phát hiện xe (có vật cản), nó sẽ gửi yêu cầu HTTP GET đến route này.
        Server sẽ tiến hành chụp ảnh và nhận diện, sau đó lưu lại lịch sử. Có cơ chế tự động thử lại 
        (retry) nếu biển số mờ hoặc không thấy.
        """
        if not controller.ai_ready:
            p("[WEB] Nhan tin hieu xe vao nhung AI chua san sang!")
            return jsonify({"success": False, "error": "AI chua load xong!"})
            
        start = time.time()
        p("\n[HETHONG] IOT_2 bao co xe vao! Dang chup anh tu IP Webcam...")
        
        # Tạm nghỉ 0.2s để đảm bảo xe chạy hẳn vào chính giữa khung hình camera
        time.sleep(0.2)
        
        try:
            # max_attempts là số lần cho phép chụp thử nếu ảnh lỗi/mờ
            max_attempts = 2
            plate = "Khong Thay Bien"
            engine = "None"
            
            # Vòng lặp chụp ảnh và nhận diện
            for attempt in range(max_attempts):
                if attempt > 0:
                    p(f"    -> [THU LAI {attempt+1}/{max_attempts}] Khong thay bien, doi 1s de chup lai...")
                    time.sleep(1.0) # Đợi 1s cho xe tiến thêm một chút rồi chụp lại
                    
                # Chụp frame
                frames = controller.camera.capture_frames(num_frames=1, interval=0.0)
                if not frames:
                    # Nếu lỗi không lấy được khung hình từ camera
                    if attempt == max_attempts - 1:
                        p("    -> [LOI] Khong chup duoc anh tu IP Camera!")
                        return jsonify({"success": False, "error": "Loi IP Camera"})
                    continue
                    
                # Lưu đè frame vừa chụp thành ảnh test mới nhất
                if frames and frames[0][0] is not None:
                    os.makedirs("captures", exist_ok=True)
                    cv2.imwrite("captures/latest_capture.jpg", frames[0][0])
                    controller.last_capture_ts = time.time()
                    
                p(f"    -> Da chup anh. Dang chay AI Nhan Dien (Lan {attempt+1})...")
                
                # Đưa khung hình vào bộ não AI
                plate, engine, cropped_frame = controller.ai_engine.process_pipeline(frames)
                
                # Lưu ảnh crop cho Web UI
                crop_filename = "latest_crop.jpg"
                crop_path = os.path.join(os.path.dirname(__file__), "captures", crop_filename)
                if cropped_frame is not None:
                    cv2.imwrite(crop_path, cropped_frame)
                else:
                    if os.path.exists("captures/latest_capture.jpg"):
                        shutil.copy2("captures/latest_capture.jpg", crop_path)
                
                # Nếu nhận diện thành công (Biển số hợp lệ, không chứa các từ khóa lỗi)
                if plate not in ("Khong Nhan Dien Duoc", "Khong Thay Bien"):
                    break # Thoát vòng lặp chụp lại
                    
            elapsed = round(time.time() - start, 2)
            controller.last_process_time = elapsed
            
            p(f"    -> [HOAN TAT] Bien so='{plate}' | Time={elapsed}s")
            
            # Cập nhật vi phạm/hành động cho Web UI
            controller.last_violation = {
                "plate": plate,
                "status": "Xe Vao Tram" if plate not in ("Khong Nhan Dien Duoc", "Khong Thay Bien") else "Loi Nhan Dien",
                "proc_time": elapsed,
                "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "image": "latest_crop.jpg"
            }

            # LƯU TRỮ LỊCH SỬ NHẬN DIỆN
            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            history_path = os.path.join(os.path.dirname(__file__), "history", f"{timestamp_str}_{plate}.jpg")
            os.makedirs(os.path.dirname(history_path), exist_ok=True)
            # Lưu bức ảnh cuối cùng đọc được biển số
            cv2.imwrite(history_path, frames[0][0])
            
            # BÀN GIAO CHO MODULE ĐỒNG BỘ - Đẩy biển số này lên mạng
            controller.sync_manager.add_to_queue(plate, history_path)
            
            return jsonify({"success": True, "plate": plate})
            
        except Exception as e:
            p(f"    -> [LOI TONG HOP]: {e}")
            return jsonify({"success": False, "error": str(e)})


    @app.route('/set_settings', methods=['POST'])
    def set_settings():
        """
        [Route] /set_settings (POST)
        Mục đích: Cập nhật thông tin cài đặt (URL Camera, API Key, Token Telegram, CSDL) từ Web UI gửi lên.
        Giải thích: Thiết lập các thông số sẽ được lưu thẳng vào config (bộ nhớ tạm), 
        và áp dụng ngay lập tức cho các module liên quan.
        """
        # Đọc dữ liệu JSON do client gửi đến
        d = request.get_json(silent=True)
        if d:
            # 1. Cập nhật Camera IP
            if 'url' in d:
                controller.config.set('ip_camera_url', d['url'])
                if controller.camera:
                    controller.camera.set_url(d['url'])
            # 2. Cập nhật Gemini API Key
            if 'gemini_api_key' in d:
                controller.config.set('gemini_api_key', d['gemini_api_key'])
            # 3. Chọn chế độ AI (EasyOCR / Gemini)
            if 'ai_mode' in d:
                controller.config.set('ai_mode', d['ai_mode'])
            # 4. Telegram Bot Token & Admin ID & Password
            if 'telegram_token' in d:
                controller.config.set('telegram_token', d['telegram_token'])
            if 'admin_telegram_id' in d:
                controller.config.set('admin_telegram_id', d['admin_telegram_id'])
            if 'admin_password' in d:
                controller.config.set('admin_password', d['admin_password'])
            # 5. MongoDB URI
            if 'mongo_uri' in d:
                controller.config.set('mongo_uri', d['mongo_uri'])
            # 6. Firebase URL
            if 'firebase_url' in d:
                controller.config.set('firebase_url', d['firebase_url'])
            # 7. Các cờ bật/tắt (Toggle)
            if 'enable_firebase' in d:
                controller.config.set('enable_firebase', d['enable_firebase'])
            if 'enable_telegram' in d:
                controller.config.set('enable_telegram', d['enable_telegram'])
            # 8. ROI (Region of Interest)
            if 'roi' in d:
                controller.config.set('roi', d['roi'])
            
            # Áp dụng thay đổi nóng (hot-reload) vào module AI mà không cần khởi động lại server
            if controller.ai_engine:
                controller.ai_engine.api_key = controller.config.get('gemini_api_key')
                controller.ai_engine.mode = controller.config.get('ai_mode', 'gemini')
                
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Invalid request"})


    @app.route('/')
    def index():
        """
        [Route] /
        Mục đích: Trang chủ của Web UI (Bảng điều khiển).
        Giải thích: Import hàm render HTML và trả về toàn bộ giao diện cho người dùng tương tác.
        """
        from web_html import get_html # Tách file chứa code HTML/JS ra module riêng cho gọn
        return get_html(controller)
        
    # Trả về đối tượng app để chạy server
    return app

def load_ai_bg(controller):
    """
    Hàm load bộ model AI ở dưới nền (Background Thread).
    Mục đích: Khởi tạo mô hình AI nặng (như EasyOCR hoặc gọi kết nối Cloud) mà không làm đứng (block)
    quá trình khởi động ứng dụng Web. Ứng dụng Web vẫn chạy lên bình thường và người dùng phải đợi "AI Ready".
    """
    p("[HETHONG] Dang nap AI Engine (HybridOCR)...")
    # Khởi tạo instance của lớp HybridOCR với các config hiện tại
    controller.ai_engine = HybridOCR(
        api_key=controller.config.get('gemini_api_key', ''),
        mode=controller.config.get('ai_mode', 'gemini')
    )
    # Bật cờ báo hiệu AI đã tải xong
    controller.ai_ready = True
    p("[HETHONG] AI Engine Da San Sang!")
    p("==========================================")
    p("  EASYOCR ĐÃ SẴN SÀNG NHẬN DIỆN 100% OFFLINE!")
    p("==========================================\n")

def start_cloudflare_tunnel(controller, port=5000):
    """
    Hàm tạo đường hầm (Tunnel) Cloudflare.
    Mục đích: Cho phép người dùng truy cập trang Web UI và các API từ bất kỳ đâu 
    trên Internet thông qua URL Public (xxx.trycloudflare.com) thay vì chỉ dùng được mạng nội bộ (LAN).
    Đồng thời tự động gửi link này về Telegram Admin.
    """
    try:
        from pycloudflared import try_cloudflare
        import requests
        p("[CLOUDFLARE] Dang mo Cloudflare Tunnel...")
        # Tạo tunnel ánh xạ port 5000 của localhost ra ngoài mạng Internet
        tunnel = try_cloudflare(port=port, verbose=False)
        p("="*50)
        p(f"  TRUY CAP TU XA QUA INTERNET:")
        p(f"  >> {tunnel.tunnel}")
        p("="*50)
        
        # Gửi link qua Telegram
        token = controller.config.get("telegram_token", "").strip()
        admin_id = controller.config.get("admin_telegram_id", "8785323128").strip()
        if token and admin_id:
            try:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                msg = f"🟢 HỆ THỐNG ALPR ĐÃ KHỞI ĐỘNG!\n🌐 Link truy cập Web UI từ xa:\n{tunnel.tunnel}"
                requests.post(url, json={"chat_id": admin_id, "text": msg}, timeout=10)
                log_action("TELEGRAM_SENT", "Sent Cloudflare Tunnel link to Admin")
                p(f"[CLOUDFLARE] Đã gửi link cho Admin Telegram ({admin_id})")
            except Exception as e:
                p(f"[CLOUDFLARE] Không thể gửi link qua Telegram: {e}")
                
    except ImportError:
        # Xử lý trường hợp chưa cài đặt thư viện
        p("[CLOUDFLARE] Chua cai pycloudflared. Chay: pip install pycloudflared")
    except Exception as e:
        p(f"[CLOUDFLARE] Loi khoi dong tunnel: {e}")

# Đoạn mã thực thi chính khi chạy file bằng câu lệnh `python server.py`
if __name__ == '__main__':
    p("=" * 50)
    p("  KHOI DONG ALPR SYSTEM (NEW ARCHITECTURE)  ")
    p("=" * 50)
    
    # 1. Khởi tạo Controller: 'Bộ não' lưu trữ mọi thông tin chung của hệ thống
    controller = SystemController()
    
    # 2. Liên kết các module phụ trợ vào hệ thống chính (Controller)
    # 2.1 Móc module quản lý camera với URL trong file config
    controller.camera = CameraClient(controller.config.get("ip_camera_url"))
    # 2.2 Móc module quản lý Cloud (ví dụ: ThingsBoard)
    controller.cloud = CloudSync(controller.config.get("tb_token"))
    # 2.3 Móc module quản lý hàng đợi và đồng bộ dữ liệu (Telegram, Firebase, MongoDB)
    controller.sync_manager = SyncManager(controller)
    
    # 3. Chạy luồng nền (Thread) nạp AI: Giúp app không bị kẹt ở bước nạp thư viện ML nặng
    threading.Thread(target=load_ai_bg, args=(controller,), daemon=True).start()
    
    # 4. Chạy luồng nền (Thread) tạo Cloudflare Tunnel: Khởi động song song để lấy link Public
    threading.Thread(target=start_cloudflare_tunnel, args=(controller, 5000), daemon=True).start()
    
    # 5. Khởi tạo đối tượng Flask App
    app = create_app(controller)
    
    # 6. Chạy Web Server trên mọi IP (0.0.0.0) và cổng 5000
    # Tắt chế độ tự tải lại (use_reloader=False) để tránh xung đột với các Thread chạy ngầm (AI, Cloudflare)
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
