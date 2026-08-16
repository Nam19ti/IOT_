import time
import threading
from flask import Flask, Response, jsonify, request, send_file
import cv2
import os

from core import SystemController, p
from camera import CameraClient
from ai import HybridOCR
from cloud import CloudSync

def create_app(controller):
    app = Flask(__name__)
    
    @app.route('/violations/<filename>')
    def serve_image(filename):
        path = os.path.join(os.path.dirname(__file__), 'violations', filename)
        if os.path.exists(path):
            return send_file(path, mimetype='image/jpeg')
        return "Not found", 404
        
    @app.route('/get_stats')
    def get_stats():
        return jsonify({
            "ai_ready": controller.ai_ready,
            "last_time": controller.last_process_time,
            "last_violation": controller.last_violation,
            "queue_size": controller.task_queue.qsize(),
            "last_capture_ts": controller.last_capture_ts
        })
        
    @app.route('/test_ocr')
    def test_ocr():
        if not controller.ai_ready:
            p("[WEB] Nhan nut Test OCR nhung AI chua san sang!")
            return jsonify({"success": False, "error": "AI chua load xong!"})
            
        start = time.time()
        p("\n[WEB] Nhan lenh Test OCR thu cong...")
        try:
            frames = controller.camera.capture_frames(num_frames=3, interval=0.05)
            if not frames:
                p("    -> [LOI] Khong chup duoc anh tu IP Webcam!")
                return jsonify({"success": False, "error": "Loi camera hoac URL khong dung"})
                
            if frames and frames[0][0] is not None:
                os.makedirs("violations", exist_ok=True)
                cv2.imwrite("violations/latest_capture.jpg", frames[0][0])
                controller.last_capture_ts = time.time()
                
            p(f"    -> Da chup {len(frames)} frame. Dang chay AI Gemini...")
            plate, engine, _ = controller.ai_engine.process_pipeline(frames)
            elapsed = round(time.time() - start, 2)
            controller.last_process_time = elapsed
            
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
        
        # Thêm chút delay để xe đi vào vừa khung hình (Tùy chỉnh góc camera)
        time.sleep(1.0)
        
        try:
            frames = controller.camera.capture_frames(num_frames=3, interval=0.1)
            if not frames:
                p("    -> [LOI] Khong chup duoc anh tu ESP32-CAM!")
                return jsonify({"success": False, "error": "Loi ESP32-CAM"})
                
            if frames and frames[0][0] is not None:
                os.makedirs("violations", exist_ok=True)
                cv2.imwrite("violations/latest_capture.jpg", frames[0][0])
                controller.last_capture_ts = time.time()
                
            p(f"    -> Da chup {len(frames)} frame. Dang chay EasyOCR Offline...")
            plate, engine, _ = controller.ai_engine.process_pipeline(frames)
            elapsed = round(time.time() - start, 2)
            controller.last_process_time = elapsed
            
            p(f"    -> [HOAN TAT] Bien so='{plate}' | Time={elapsed}s")
            
            if plate and plate not in ("Khong Nhan Dien Duoc", "Khong Thay Bien"):
                # Đẩy lên Firebase Queue cho Node.js trừ tiền
                controller.cloud.publish_ai_result(plate, 0, "IN", "violations/latest_capture.jpg")
                p(f"    -> Đã đẩy giao dịch {plate} sang Node.js!")
                
            return jsonify({"success": True, "plate": plate})
            
        except Exception as e:
            p(f"    -> [LOI TONG HOP]: {e}")
            return jsonify({"success": False, "error": str(e)})

    @app.route('/set_settings', methods=['POST'])
    def set_settings():
        d = request.json
        if 'url' in d:
            controller.config.set('ip_camera_url', d['url'])
            if controller.camera:
                controller.camera.set_url(d['url'])
        if 'iot2_ip' in d:
            controller.config.set('iot2_ip', d['iot2_ip'])
        return jsonify({"success": True})

    @app.route('/')
    def index():
        from web_html import get_html # Se tao file nay rieng cho gon
        return get_html(controller)
        
    return app

def load_ai_bg(controller):
    p("[HETHONG] Dang nap AI Engine (EasyOCR Offline)...")
    controller.ai_engine = HybridOCR()
    controller.ai_ready = True
    p("\n==========================================")
    p("  EASYOCR ĐÃ SẴN SÀNG NHẬN DIỆN 100% OFFLINE!")
    p("==========================================\n")

if __name__ == '__main__':
    p("=" * 50)
    p("  KHOI DONG ALPR SYSTEM (NEW ARCHITECTURE)  ")
    p("=" * 50)
    
    # 1. Khoi tao Controller
    controller = SystemController()
    
    # 2. Lien ket cac module
    controller.camera = CameraClient(controller.config.get("ip_camera_url"))
    controller.cloud = CloudSync(controller.config.get("tb_token"))
    
    # 3. Load AI (Background)
    threading.Thread(target=load_ai_bg, args=(controller,), daemon=True).start()
    
    # 4. Chay Web UI
    app = create_app(controller)
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
