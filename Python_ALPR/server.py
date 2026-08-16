import time
import threading
from flask import Flask, Response, jsonify, request, send_file
import cv2
import os
import datetime
import shutil

from core import SystemController, p
from camera import CameraClient
from ai import HybridOCR
from cloud import CloudSync
from sync_manager import SyncManager

def create_app(controller):
    app = Flask(__name__)
    
    @app.route('/captures/<filename>')
    def serve_image(filename):
        path = os.path.join(os.path.dirname(__file__), 'captures', filename)
        if os.path.exists(path):
            return send_file(path, mimetype='image/jpeg')
        return "Not found", 404
        
    @app.route('/get_stats')
    def get_stats():
        return jsonify({
            "ai_ready": controller.ai_ready,
            "last_time": controller.last_process_time,
            "last_violation": controller.last_violation,
            "last_capture_ts": controller.last_capture_ts
        })
        
    @app.route('/capture_only')
    def capture_only():
        """Chi chup anh tu ESP32-CAM, khong nhan dien."""
        p("[WEB] Nhan lenh Chup Anh don thuan tu ESP32-CAM...")
        try:
            frames = controller.camera.capture_frames(num_frames=1, interval=0)
            if not frames or frames[0][0] is None:
                return jsonify({"success": False, "error": "Khong chup duoc anh. Kiem tra URL ESP32-CAM!"})
            os.makedirs("captures", exist_ok=True)
            cv2.imwrite("captures/latest_capture.jpg", frames[0][0])
            controller.last_capture_ts = time.time()
            p("    -> Da chup va luu anh thanh cong!")
            return jsonify({"success": True})
        except Exception as e:
            p(f"    -> [LOI] {e}")
            return jsonify({"success": False, "error": str(e)})

    @app.route('/process_latest')
    def process_latest():
        """Chay OCR tren anh da chup gan nhat (Phuc vu cho UI chia lam 2 buoc)"""
        if not controller.ai_ready:
            return jsonify({"success": False, "error": "AI chua load xong!"})
            
        img_path = os.path.join(os.path.dirname(__file__), "captures", "latest_capture.jpg")
        if not os.path.exists(img_path):
            return jsonify({"success": False, "error": "Khong tim thay anh de nhan dien"})
            
        start = time.time()
        img = cv2.imread(img_path)
        frames = [(img, None)]
        
        try:
            plate, engine, _ = controller.ai_engine.process_pipeline(frames)
            elapsed = round(time.time() - start, 2)
            controller.last_process_time = elapsed
            
            controller.last_violation = {
                "plate": plate,
                "status": "Test Thu Cong",
                "proc_time": elapsed,
                "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "image": "latest_capture.jpg"
            }
            
            # Luu vao history de dong bo
            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            history_path = os.path.join(os.path.dirname(__file__), "history", f"{timestamp_str}_{plate}.jpg")
            os.makedirs(os.path.dirname(history_path), exist_ok=True)
            shutil.copy2(img_path, history_path)
            
            # PUSH vao Hang Doi Offline
            controller.sync_manager.add_to_queue(plate, history_path)
            
            p(f"    -> [HOAN TAT OCR] Bien so='{plate}' | Time={elapsed}s")
            return jsonify({"success": True, "plate": plate, "engine": engine, "time": elapsed})
        except Exception as e:
            p(f"    -> [LOI OCR]: {e}")
            return jsonify({"success": False, "error": str(e)})

    @app.route('/test_ocr')
    def test_ocr():
        if not controller.ai_ready:
            p("[WEB] Nhan nut Test OCR nhung AI chua san sang!")
            return jsonify({"success": False, "error": "AI chua load xong!"})
            
        start = time.time()
        p("\n[WEB] Nhan lenh Test OCR thu cong...")
        try:
            frames = controller.camera.capture_frames(num_frames=1, interval=0.0)
            if not frames:
                p("    -> [LOI] Khong chup duoc anh tu IP Webcam!")
                return jsonify({"success": False, "error": "Loi camera hoac URL khong dung"})
                
            if frames and frames[0][0] is not None:
                os.makedirs("captures", exist_ok=True)
                cv2.imwrite("captures/latest_capture.jpg", frames[0][0])
                controller.last_capture_ts = time.time()
                
            p(f"    -> Da chup {len(frames)} frame. Dang chay AI Gemini...")
            plate, engine, _ = controller.ai_engine.process_pipeline(frames)
            elapsed = round(time.time() - start, 2)
            controller.last_process_time = elapsed
            
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
        if not controller.ai_ready:
            p("[WEB] Nhan tin hieu xe vao nhung AI chua san sang!")
            return jsonify({"success": False, "error": "AI chua load xong!"})
            
        start = time.time()
        p("\n[HETHONG] IOT_2 bao co xe vao! Dang chup anh tu ESP32-CAM...")
        
        # Thêm chút delay siêu ngắn để xe vừa chớm vào khung hình
        time.sleep(0.2)
        
        try:
            max_attempts = 2
            plate = "Khong Thay Bien"
            engine = "None"
            
            for attempt in range(max_attempts):
                if attempt > 0:
                    p(f"    -> [THU LAI {attempt+1}/{max_attempts}] Khong thay bien, doi 1s de chup lai...")
                    time.sleep(1.0)
                    
                frames = controller.camera.capture_frames(num_frames=1, interval=0.0)
                if not frames:
                    if attempt == max_attempts - 1:
                        p("    -> [LOI] Khong chup duoc anh tu IP Camera!")
                        return jsonify({"success": False, "error": "Loi IP Camera"})
                    continue
                    
                if frames and frames[0][0] is not None:
                    os.makedirs("captures", exist_ok=True)
                    cv2.imwrite("captures/latest_capture.jpg", frames[0][0])
                    controller.last_capture_ts = time.time()
                    
                p(f"    -> Da chup anh. Dang chay AI Nhan Dien (Lan {attempt+1})...")
                plate, engine, _ = controller.ai_engine.process_pipeline(frames)
                
                if plate not in ("Khong Nhan Dien Duoc", "Khong Thay Bien"):
                    break # Nhan dien thanh cong, thoat vong lap!
                    
            elapsed = round(time.time() - start, 2)
            controller.last_process_time = elapsed
            
            p(f"    -> [HOAN TAT] Bien so='{plate}' | Time={elapsed}s")
            
            controller.last_violation = {
                "plate": plate,
                "status": "Xe Vao Tram" if plate not in ("Khong Nhan Dien Duoc", "Khong Thay Bien") else "Loi Nhan Dien",
                "proc_time": elapsed,
                "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "image": "latest_capture.jpg"
            }

            # Luu vao history de dong bo
            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            history_path = os.path.join(os.path.dirname(__file__), "history", f"{timestamp_str}_{plate}.jpg")
            os.makedirs(os.path.dirname(history_path), exist_ok=True)
            cv2.imwrite(history_path, frames[0][0])
            
            # PUSH vao Hang Doi Offline
            controller.sync_manager.add_to_queue(plate, history_path)
            
            return jsonify({"success": True, "plate": plate})
            
        except Exception as e:
            p(f"    -> [LOI TONG HOP]: {e}")
            return jsonify({"success": False, "error": str(e)})


    @app.route('/set_settings', methods=['POST'])
    def set_settings():
        d = request.get_json(silent=True)
        if d:
            if 'url' in d:
                controller.config.set('ip_camera_url', d['url'])
                if controller.camera:
                    controller.camera.set_url(d['url'])
            if 'gemini_api_key' in d:
                controller.config.set('gemini_api_key', d['gemini_api_key'])
            if 'ai_mode' in d:
                controller.config.set('ai_mode', d['ai_mode'])
            if 'telegram_token' in d:
                controller.config.set('telegram_token', d['telegram_token'])
            if 'mongo_uri' in d:
                controller.config.set('mongo_uri', d['mongo_uri'])
            if 'firebase_url' in d:
                controller.config.set('firebase_url', d['firebase_url'])
            if 'enable_firebase' in d:
                controller.config.set('enable_firebase', d['enable_firebase'])
            if 'enable_telegram' in d:
                controller.config.set('enable_telegram', d['enable_telegram'])
            
            # Cap nhat vao AI engine neu co
            if controller.ai_engine:
                controller.ai_engine.api_key = controller.config.get('gemini_api_key')
                controller.ai_engine.mode = controller.config.get('ai_mode', 'gemini')
                
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Invalid request"})


    @app.route('/')
    def index():
        from web_html import get_html # Se tao file nay rieng cho gon
        return get_html(controller)
        
    return app

def load_ai_bg(controller):
    p("[HETHONG] Dang nap AI Engine (HybridOCR)...")
    controller.ai_engine = HybridOCR(
        api_key=controller.config.get('gemini_api_key', ''),
        mode=controller.config.get('ai_mode', 'gemini')
    )
    controller.ai_ready = True
    p("[HETHONG] AI Engine Da San Sang!")
    p("==========================================")
    p("  EASYOCR ĐÃ SẴN SÀNG NHẬN DIỆN 100% OFFLINE!")
    p("==========================================\n")

def start_cloudflare_tunnel(port=5000):
    """Tu dong khoi dong Cloudflare Tunnel va in URL ra man hinh."""
    try:
        from pycloudflared import try_cloudflare
        p("[CLOUDFLARE] Dang mo Cloudflare Tunnel...")
        tunnel = try_cloudflare(port=port, verbose=False)
        p("="*50)
        p(f"  TRUY CAP TU XA QUA INTERNET:")
        p(f"  >> {tunnel.tunnel}")
        p("="*50)
    except ImportError:
        p("[CLOUDFLARE] Chua cai pycloudflared. Chay: pip install pycloudflared")
    except Exception as e:
        p(f"[CLOUDFLARE] Loi khoi dong tunnel: {e}")

if __name__ == '__main__':
    p("=" * 50)
    p("  KHOI DONG ALPR SYSTEM (NEW ARCHITECTURE)  ")
    p("=" * 50)
    
    # 1. Khoi tao Controller
    controller = SystemController()
    
    # 2. Lien ket cac module
    controller.camera = CameraClient(controller.config.get("ip_camera_url"))
    controller.cloud = CloudSync(controller.config.get("tb_token"))
    controller.sync_manager = SyncManager(controller)
    
    # 3. Load AI (Background)
    threading.Thread(target=load_ai_bg, args=(controller,), daemon=True).start()
    
    # 4. Khoi dong Cloudflare Tunnel (Background) de truy cap tu xa
    threading.Thread(target=start_cloudflare_tunnel, args=(5000,), daemon=True).start()
    
    # 5. Chay Web UI
    app = create_app(controller)
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
