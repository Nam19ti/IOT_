import cv2
import numpy as np
import easyocr
import json
import paho.mqtt.client as mqtt
import requests
import time
import os
import datetime
import re
import collections
import threading
import google.generativeai as genai
from PIL import Image
from flask import Flask, Response, jsonify, request

# =========================================================
# 1. CẤU HÌNH CAMERA & SERVER & API KEY
# =========================================================
CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"ip_camera_url": "http://192.168.42.129:8080/photo.jpg", "gemini_api_key": "", "tb_token": "GkUmbnN2vDPBljtNCKfo"}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

config_data = load_config()
IP_WEBCAM_URL = config_data["ip_camera_url"]
GEMINI_API_KEY = config_data.get("gemini_api_key", "")
TB_TOKEN = config_data.get("tb_token", "GkUmbnN2vDPBljtNCKfo")
FLASK_PORT = 5000

# Khởi tạo Gemini Model
gemini_model = None
def init_gemini(api_key):
    global gemini_model
    if api_key and api_key.strip() != "":
        try:
            genai.configure(api_key=api_key.strip())
            gemini_model = genai.GenerativeModel('gemini-1.5-flash-8b')
            print("🌟 Đã cấu hình thành công Gemini API (Model Flash 8B)!")
        except Exception as e:
            print("⚠️ Lỗi cấu hình Gemini API:", e)
            gemini_model = None
    else:
        gemini_model = None
        print("⚠️ Chưa có Gemini API Key, sẽ sử dụng hoàn toàn EasyOCR.")

init_gemini(GEMINI_API_KEY)

# =========================================================
# 2. CẤU HÌNH MQTT (HIVEMQ)
# =========================================================
HIVEMQ_BROKER = "broker.hivemq.com"
HIVEMQ_PORT = 1883

# =========================================================
# KHỞI TẠO CÁC MODULE LOCAL (EASYOCR)
# =========================================================
print("Đang tải mô hình nhận diện chữ cục bộ (EasyOCR)... Vui lòng đợi...")
reader = easyocr.Reader(['en'], gpu=False) 
print("Tải xong mô hình EasyOCR!")

hive_client = mqtt.Client(client_id="Python_AI_Core_" + str(np.random.randint(1000)))
app = Flask(__name__)

last_processing_time = 0.0

# =========================================================
# VIDEO STREAM & MOTION TRACKING
# =========================================================
class VideoStream:
    def __init__(self, url):
        self.set_url(url)
        self.latest_frame = None
        self.latest_bbox = None 
        self.running = True
        self.lock = threading.Lock()
        self.fgbg = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=30, detectShadows=False)
        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()

    def set_url(self, url):
        self.url = url.replace('/photo.jpg', '/video')
        self.cap = cv2.VideoCapture(self.url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
        if hasattr(self, 'fgbg'):
            self.fgbg = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=30, detectShadows=False)

    def update(self):
        while self.running:
            if not self.cap.isOpened():
                time.sleep(1)
                self.cap.open(self.url)
                continue
            
            ret, frame = self.cap.read()
            if ret:
                h_orig, w_orig = frame.shape[:2]
                small_frame = cv2.resize(frame, (640, int(640 * h_orig / w_orig)))
                
                fgmask = self.fgbg.apply(small_frame)
                _, thresh = cv2.threshold(fgmask, 200, 255, cv2.THRESH_BINARY)
                thresh = cv2.dilate(thresh, None, iterations=4)
                
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                max_area = 0
                best_bbox = None
                
                for c in contours:
                    area = cv2.contourArea(c)
                    if area > 1500: 
                        if area > max_area:
                            max_area = area
                            x_s, y_s, w_s, h_s = cv2.boundingRect(c)
                            scale_x = w_orig / 640
                            scale_y = h_orig / int(640 * h_orig / w_orig)
                            
                            best_bbox = (int(x_s * scale_x), int(y_s * scale_y), 
                                         int(w_s * scale_x), int(h_s * scale_y))

                with self.lock:
                    self.latest_frame = frame
                    self.latest_bbox = best_bbox
            else:
                self.cap.release()
                time.sleep(1)
                
    def get_data(self):
        with self.lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy(), self.latest_bbox
            return None, None

    def change_camera(self, new_url):
        self.set_url(new_url)

streamer = VideoStream(IP_WEBCAM_URL)

# =========================================================
# FLASK WEB SERVER
# =========================================================
def generate_frames():
    error_img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(error_img, "Mat ket noi Camera!", (120, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
    cv2.putText(error_img, "Kiem tra lai IP phia tren", (140, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    ret, error_buffer = cv2.imencode('.jpg', error_img)
    error_frame = error_buffer.tobytes()

    while True:
        try:
            frame, bbox = streamer.get_data()
            if frame is not None:
                if bbox is not None:
                    x, y, w, h = bbox
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 3)
                    cv2.putText(frame, "Tracking", (x, max(30, y-10)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                
                ret, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                time.sleep(0.03)
            else:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + error_frame + b'\r\n')
                time.sleep(1)
        except Exception as e:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + error_frame + b'\r\n')
            time.sleep(1)

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/set_settings', methods=['POST'])
def set_settings():
    global IP_WEBCAM_URL, GEMINI_API_KEY, TB_TOKEN, config_data
    data = request.json
    new_url = data.get('url')
    new_key = data.get('api_key')
    new_tb = data.get('tb_token')
    
    if new_url:
        IP_WEBCAM_URL = new_url
        config_data["ip_camera_url"] = new_url
        streamer.change_camera(new_url)
        
    if new_key is not None:
        GEMINI_API_KEY = new_key
        config_data["gemini_api_key"] = new_key
        init_gemini(new_key)
        
    if new_tb:
        TB_TOKEN = new_tb
        config_data["tb_token"] = new_tb
        
    save_config(config_data)
    return jsonify({"success": True, "message": "Đã lưu cài đặt thành công!"})

@app.route('/get_stats', methods=['GET'])
def get_stats():
    return jsonify({"last_time": last_processing_time})

@app.route('/')
def index():
    html = f"""
    <html>
        <head>
            <title>Căn Chỉnh Camera & AI - IOT Thăng Long</title>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
            <style>
                :root {{
                    --primary: #00d2ff;
                    --secondary: #3a7bd5;
                    --bg: #0f172a;
                    --glass-bg: rgba(30, 41, 59, 0.7);
                    --glass-border: rgba(255, 255, 255, 0.1);
                    --danger: #ef4444;
                    --success: #10b981;
                }}

                body {{
                    margin: 0;
                    padding: 0;
                    font-family: 'Inter', sans-serif;
                    background: var(--bg);
                    background-image: 
                        radial-gradient(at 0% 0%, rgba(58, 123, 213, 0.15) 0px, transparent 50%),
                        radial-gradient(at 100% 100%, rgba(0, 210, 255, 0.1) 0px, transparent 50%);
                    color: #fff;
                    min-height: 100vh;
                }}

                .header {{
                    padding: 2rem;
                    text-align: center;
                    border-bottom: 1px solid var(--glass-border);
                    background: rgba(15, 23, 42, 0.8);
                    backdrop-filter: blur(12px);
                    margin-bottom: 2rem;
                }}

                .header h1 {{
                    margin: 0;
                    font-weight: 800;
                    font-size: 2.5rem;
                    background: linear-gradient(to right, var(--primary), var(--secondary));
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }}

                .container {{
                    max-width: 900px;
                    margin: 0 auto;
                    padding: 0 1rem;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                }}

                .config-box, .action-box {{
                    background: var(--glass-bg);
                    border: 1px solid var(--glass-border);
                    border-radius: 16px;
                    padding: 1.5rem;
                    backdrop-filter: blur(16px);
                    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
                    width: 100%;
                    margin-bottom: 2rem;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    gap: 15px;
                }}
                
                .form-row {{
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 10px;
                    width: 100%;
                }}

                input[type="text"], input[type="password"] {{
                    background: rgba(0,0,0,0.3);
                    border: 1px solid var(--glass-border);
                    color: #f1f5f9;
                    font-size: 1.1rem;
                    padding: 10px 15px;
                    border-radius: 8px;
                    width: 350px;
                    font-family: 'Inter', sans-serif;
                    transition: border-color 0.2s;
                }}
                
                input[type="text"]:focus, input[type="password"]:focus {{
                    outline: none;
                    border-color: var(--primary);
                    box-shadow: 0 0 10px rgba(0, 210, 255, 0.3);
                }}

                .btn {{
                    padding: 12px 25px;
                    font-size: 16px;
                    cursor: pointer;
                    background: linear-gradient(135deg, var(--secondary), var(--primary));
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: 600;
                    font-family: 'Inter', sans-serif;
                    transition: all 0.2s;
                }}

                .btn:hover {{
                    box-shadow: 0 0 15px rgba(0, 210, 255, 0.5);
                    transform: translateY(-2px);
                }}
                
                .btn-success {{ background: linear-gradient(135deg, #059669, #10b981); }}
                .btn-success:hover {{ box-shadow: 0 0 15px rgba(16, 185, 129, 0.5); }}

                .stats {{ font-size: 1.2rem; font-weight: 600; margin-top: 10px; color: var(--success); }}
                .time-stat {{ color: #fcd34d; font-size: 1rem; margin-top: 5px; }}

                .stream-img {{
                    max-width: 100%;
                    border-radius: 12px;
                    border: 1px solid var(--glass-border);
                    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                    background: #111;
                    min-height: 400px;
                }}
            </style>
        </head>
        <body>
            <header class="header">
                <h1>Căn Chỉnh Camera & AI</h1>
                <p style="color: #94a3b8; margin-top: 0.5rem;">Cấu hình kết nối và Test nhận diện (Hỗ trợ Gemini API)</p>
            </header>
            
            <div class="container">
                <div class="config-box">
                    <div class="form-row">
                        <label style="font-size: 1.1rem; font-weight: 600; width: 150px; text-align: right;">IP Camera:</label>
                        <input type="text" id="cam_ip" value="{IP_WEBCAM_URL}" placeholder="http://192.168.1.xxx:8080/photo.jpg">
                    </div>
                    <div class="form-row">
                        <label style="font-size: 1.1rem; font-weight: 600; width: 150px; text-align: right;">Gemini API Key:</label>
                        <input type="password" id="gemini_key" value="{GEMINI_API_KEY}" placeholder="Nhập API Key để dùng Cloud AI...">
                    </div>
                    <div class="form-row">
                        <label style="font-size: 1.1rem; font-weight: 600; width: 150px; text-align: right;">ThingsBoard Token:</label>
                        <input type="text" id="tb_token" value="{TB_TOKEN}" placeholder="Token của thiết bị trên ThingsBoard">
                    </div>
                    <button class="btn btn-success" style="margin-top: 10px;" onclick="saveSettings()">Lưu Cấu Hình</button>
                    <div id="save_result" style="color: #fcd34d; width: 100%; font-size: 15px; margin-top: 5px; font-weight:600; text-align:center;"></div>
                </div>

                <div class="action-box">
                    <p style="color: #cbd5e1; font-weight: 300;">Hệ thống sẽ ưu tiên dùng Gemini API. Nếu mất mạng sẽ tự lùi về dùng EasyOCR.</p>
                    <button class="btn" onclick="testOCR()">Chụp & Test Nhận Diện Ngay</button>
                    <div id="result" class="stats">Chưa có kết quả test.</div>
                    <div id="time_stat" class="time-stat">Thời gian xử lý AI gần nhất: 0.0s</div>
                </div>
                
                <img src="/video_feed" class="stream-img" id="stream_img" alt="Đang chờ kết nối Camera...">
            </div>

            <script>
                function saveSettings() {{
                    const newUrl = document.getElementById('cam_ip').value;
                    const newKey = document.getElementById('gemini_key').value;
                    const newTb = document.getElementById('tb_token').value;
                    document.getElementById('save_result').innerText = "Đang lưu cấu hình...";
                    
                    fetch('/set_settings', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ url: newUrl, api_key: newKey, tb_token: newTb }})
                    }})
                    .then(r => r.json())
                    .then(data => {{
                        document.getElementById('save_result').innerText = data.message;
                        if(data.success) {{
                            document.getElementById('stream_img').src = '/video_feed?t=' + new Date().getTime();
                        }}
                        setTimeout(() => document.getElementById('save_result').innerText = '', 3000);
                    }})
                    .catch(e => {{
                        document.getElementById('save_result').innerText = "Lỗi mạng khi lưu.";
                    }});
                }}

                function testOCR() {{
                    document.getElementById('result').innerText = "Đang chạy AI... Vui lòng đợi!";
                    fetch('/test_ocr')
                        .then(r => r.json())
                        .then(data => {{
                            if (data.success) {{
                                document.getElementById('result').innerText = "Biển Số (" + data.engine + "): " + data.plate;
                                updateStats();
                            }} else {{
                                document.getElementById('result').innerText = "Lỗi: " + data.error;
                            }}
                        }});
                }}
                
                function updateStats() {{
                    fetch('/get_stats')
                        .then(r => r.json())
                        .then(data => {{
                            document.getElementById('time_stat').innerText = "Thời gian xử lý AI gần nhất: " + data.last_time + "s";
                        }});
                }}
                
                setInterval(updateStats, 2000);
            </script>
        </body>
    </html>
    """
    return html

# =========================================================
# LOGIC NHẬN DIỆN BIỂN SỐ (GEMINI + EASYOCR FALLBACK)
# =========================================================
def generate_rotations(img):
    yield img
    yield cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    yield cv2.rotate(img, cv2.ROTATE_180)
    yield cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    
    image_center = tuple(np.array(img.shape[1::-1]) / 2)
    for angle in [15, -15, 30, -30, 45, -45]:
        rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
        yield cv2.warpAffine(img, rot_mat, img.shape[1::-1], flags=cv2.INTER_LINEAR)

def crop_dynamic_roi(img, bbox):
    h_orig, w_orig = img.shape[:2]
    if bbox is not None:
        x, y, w, h = bbox
        pad = 80
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(w_orig, x + w + pad)
        y2 = min(h_orig, y + h + pad)
        return img[y1:y2, x1:x2]
    else:
        cx, cy = w_orig // 2, h_orig // 2
        return img[max(0, cy - 300):min(h_orig, cy + 300), max(0, cx - 400):min(w_orig, cx + 400)]

def try_gemini_ocr(cv2_img):
    """Gửi ảnh cho Gemini AI nhận diện"""
    if gemini_model is None:
        return None
    
    try:
        # Chuyển đổi BGR sang RGB cho PIL
        img_rgb = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        
        prompt = "Bạn là hệ thống nhận diện biển số giao thông. Hãy đọc biển số xe trong ảnh này. Chỉ trả về CÁC CHỮ CÁI VÀ CHỮ SỐ VIẾT LIỀN NHAU (ví dụ: 29A12345), tuyệt đối không có khoảng trắng, không có dấu gạch ngang, không có text dư thừa. Nếu hình ảnh quá mờ không thể thấy rõ bất kỳ biển số nào, hãy trả về chính xác chữ 'NONE'."
        
        response = gemini_model.generate_content([prompt, pil_img])
        result_text = response.text.strip().upper()
        
        if result_text != "NONE" and len(result_text) >= 5:
            # Lọc lại bằng Regex để chắc chắn chuẩn form
            match = re.search(r"(1[1-9]|[2-9][0-9])[A-Z][0-9A-Z]?\d{4,5}", result_text)
            if match:
                return match.group(0)
            # Dù Gemini đôi lúc không khớp form Regex cứng (do biển số kiểu mới), nhưng nếu nó trả về chuỗi ngắn hợp lệ, ta vẫn có thể cân nhắc.
            # Ở đây ta ưu tiên xài Regex để tránh text rác.
            
        return None
    except Exception as e:
        print("    -> [GEMINI ERROR]:", e)
        return None

def process_image_pipeline(frames_data):
    """
    Hàm phân tích cốt lõi: 
    1. Thử gọi Gemini trên bức ảnh rõ nhất.
    2. Fallback sang EasyOCR nếu Gemini thất bại.
    Returns: (plate, used_engine, best_image_frame)
    """
    def get_bbox_area(item):
        if item[1] is not None:
            return item[1][2] * item[1][3]
        return 0
        
    frames_data.sort(key=get_bbox_area, reverse=True)
    frames_data = frames_data[:5] # Chỉ lấy 5 ảnh gần nhất
    
    # Lấy ảnh đẹp nhất (To nhất) để gửi cho Gemini thử sức trước
    best_frame_tuple = frames_data[0]
    best_img, best_bbox = best_frame_tuple
    cropped_best = crop_dynamic_roi(best_img, best_bbox)
    
    # ---------------------------
    # TẦNG 1: THỬ GEMINI API (CLOUD)
    # ---------------------------
    if gemini_model is not None:
        print("    -> Gửi ảnh đẹp nhất lên Gemini 1.5 Flash...")
        gemini_result = try_gemini_ocr(cropped_best)
        if gemini_result:
            print(f"    -> [SUCCESS] Gemini đã đọc được: {gemini_result}")
            return gemini_result, "Gemini", best_img
        print("    -> Gemini không đọc được hoặc lỗi rớt mạng. Chuyển sang kích hoạt EasyOCR dự phòng...")

    # ---------------------------
    # TẦNG 2: DỰ PHÒNG EASYOCR (LOCAL)
    # ---------------------------
    plate_votes = collections.defaultdict(int)
    best_plate = "Khong Thay Bien"
    
    for img, bbox in frames_data:
        cropped_img = crop_dynamic_roi(img, bbox)
        
        gray = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY)
        processed_img = cv2.bilateralFilter(gray, 11, 17, 17)
        
        kernel = np.array([[0, -1, 0], [-1, 5,-1], [0, -1, 0]])
        sharpened_img = cv2.filter2D(processed_img, -1, kernel)
        
        plate_found_in_frame = False
        for r_img in generate_rotations(sharpened_img):
            results = reader.readtext(r_img)
            
            raw_text = ""
            for (bbox_ocr, text, prob) in results:
                clean_text = ''.join(e for e in text if e.isalnum()).upper()
                raw_text += clean_text
            
            match = re.search(r"(1[1-9]|[2-9][0-9])[A-Z][0-9A-Z]?\d{4,5}", raw_text)
            if match:
                plate = match.group(0)
                plate_votes[plate] += 1
                plate_found_in_frame = True
                break 
        
        # Early Exit cho EasyOCR
        if plate_found_in_frame:
            if any(votes >= 2 for votes in plate_votes.values()):
                break 

    if plate_votes:
        best_plate = max(plate_votes, key=plate_votes.get)
        return best_plate, "EasyOCR", best_img
        
    return best_plate, "Failed", best_img


def process_10_frames_ocr(car_id, speed, direction):
    global last_processing_time
    start_t = time.time()
    
    try:
        frames_data = []
        for i in range(10):
            try:
                f, b = streamer.get_data()
                if f is not None:
                    frames_data.append((f, b))
                time.sleep(0.04)
            except:
                pass
                
        if not frames_data:
            raise Exception("Không thể chụp được ảnh.")
            
        print(f"    -> Đã bắt 10 frames. Chạy Pipeline (Gemini/EasyOCR)...")
        
        plate, engine, best_image_frame = process_image_pipeline(frames_data)
        
        image_filename = ""
        if plate != "Khong Thay Bien":
            if not os.path.exists("violations"):
                os.makedirs("violations")
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            image_filename = f"{plate}_{timestamp}.jpg"
            image_path = os.path.join("violations", image_filename)
            
            if frames_data[0][1] is not None:
                bx, by, bw, bh = frames_data[0][1]
                cv2.rectangle(best_image_frame, (bx, by), (bx+bw, by+bh), (0, 0, 255), 4)
                
            cv2.imwrite(image_path, best_image_frame)
            
            # --- TÍCH HỢP GỬI ẢNH LÊN THINGSBOARD ---
            try:
                import base64
                # Thu nhỏ ảnh lại để ThingsBoard không bị lag (640x480)
                tb_img = cv2.resize(best_image_frame, (640, int(640 * best_image_frame.shape[0] / best_image_frame.shape[1])))
                # Nén JPEG chất lượng 60%
                _, buffer = cv2.imencode('.jpg', tb_img, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
                img_b64 = base64.b64encode(buffer).decode('utf-8')
                tb_payload = {"image": "data:image/jpeg;base64," + img_b64}
                
                # Gửi thẳng API
                requests.post(f"http://mqtt.thingsboard.cloud/api/v1/{TB_TOKEN}/telemetry", json=tb_payload, timeout=2)
                print("    -> [THINGSBOARD] Đã đẩy ảnh bằng chứng lên mây thành công!")
            except Exception as e:
                print("    -> [THINGSBOARD ERROR] Lỗi đẩy ảnh:", e)
            # ----------------------------------------
            
        total_time = round(time.time() - start_t, 2)
        last_processing_time = total_time
        print(f"    -> [HOÀN TẤT] Biển số: {plate} | Engine: {engine} | Thời gian: {total_time}s")
        
        # Gửi MQTT
        payload = {"id": car_id, "speed": speed, "direction": direction, "plate": plate}
        hive_client.publish("iot_thanglong/plate", json.dumps(payload))
        
        # Gửi Node.js
        if image_filename != "":
            try:
                node_payload = {
                    "car_id": car_id, "speed": speed, "direction": direction,
                    "plate": plate, "image": image_filename,
                    "timestamp": datetime.datetime.now().isoformat()
                }
                requests.post("http://localhost:3000/api/violation", json=node_payload, timeout=2)
            except:
                pass
                
    except Exception as cam_err:
        print("Lỗi Process:", cam_err)
        hive_client.publish("iot_thanglong/plate", json.dumps({"id": car_id, "speed": speed, "direction": direction, "plate": "Loi Camera"}))

@app.route('/test_ocr', methods=['GET'])
def test_ocr():
    """Test OCR Thủ Công qua Web"""
    global last_processing_time
    start_t = time.time()
    try:
        frame, bbox = streamer.get_data()
        if frame is None:
            raise Exception("Chưa lấy được ảnh camera.")
            
        plate, engine, best_img = process_image_pipeline([(frame, bbox)])
        
        process_time = round(time.time() - start_t, 2)
        last_processing_time = process_time
        return jsonify({"success": True, "plate": plate, "engine": engine, "time": process_time})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ... (Phần MQTT và Main giữ nguyên như cấu trúc cũ)
def on_hive_message(client, userdata, msg):
    if msg.topic == "iot_thanglong/speed":
        try:
            data = json.loads(msg.payload.decode('utf-8'))
            car_id = str(data.get("id", "UNKNOWN"))
            speed = data.get("speed", 0)
            direction = data.get("direction", "None")
            threading.Thread(target=process_10_frames_ocr, args=(car_id, speed, direction)).start()
        except Exception as e:
            pass

def start_mqtt():
    try:
        hive_client.on_message = on_hive_message
        hive_client.connect(HIVEMQ_BROKER, HIVEMQ_PORT, 60)
        hive_client.subscribe("iot_thanglong/speed")
        print("- Đã kết nối HiveMQ")
        hive_client.loop_forever()
    except Exception as e:
        pass

def main():
    mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
    mqtt_thread.start()
    
    print(f"\n==============================================")
    print(f"🚀 WEB UI ĐÃ MỞ TẠI: http://localhost:{FLASK_PORT}")
    print(f"==============================================\n")
    app.run(host='0.0.0.0', port=FLASK_PORT, debug=False, use_reloader=False)

if __name__ == '__main__':
    main()
