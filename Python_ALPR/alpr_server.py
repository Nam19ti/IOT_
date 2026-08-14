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
from flask import Flask, Response, jsonify

# =========================================================
# 1. CẤU HÌNH CAMERA & SERVER
# =========================================================
IP_WEBCAM_URL = "http://192.168.42.129:8080/photo.jpg"
FLASK_PORT = 5000

# =========================================================
# 2. CẤU HÌNH MQTT (HIVEMQ)
# =========================================================
HIVEMQ_BROKER = "broker.hivemq.com"
HIVEMQ_PORT = 1883

# =========================================================
# KHỞI TẠO CÁC MODULE
# =========================================================
print("Đang tải mô hình nhận diện chữ (EasyOCR)... Vui lòng đợi...")
reader = easyocr.Reader(['en'], gpu=False) 
print("Tải xong mô hình!")

hive_client = mqtt.Client(client_id="Python_AI_Core_" + str(np.random.randint(1000)))
app = Flask(__name__)

# Lưu trữ thời gian xử lý AI gần nhất để hiển thị trên Web
last_processing_time = 0.0

# =========================================================
# FLASK WEB SERVER (VIDEO STREAM + CROSSHAIR)
# =========================================================
def generate_frames():
    """Lấy ảnh từ điện thoại liên tục, vẽ crosshair và stream ra Web."""
    while True:
        try:
            res = requests.get(IP_WEBCAM_URL, timeout=1)
            if res.status_code == 200:
                nparr = np.frombuffer(res.content, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                # Vẽ Crosshair (Thước ngắm thập phân)
                h, w = frame.shape[:2]
                cx, cy = w // 2, h // 2
                cv2.line(frame, (cx - 150, cy), (cx + 150, cy), (0, 0, 255), 2)
                cv2.line(frame, (cx, cy - 150), (cx, cy + 150), (0, 0, 255), 2)
                cv2.circle(frame, (cx, cy), 10, (0, 255, 0), 2)
                
                # Vẽ khung Crop AI
                cv2.rectangle(frame, (cx - 300, cy - 200), (cx + 300, cy + 200), (0, 255, 255), 2)
                cv2.putText(frame, "Vung AI Nhien Dien", (cx - 290, cy - 210), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                
                ret, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                time.sleep(0.1)
        except Exception as e:
            time.sleep(0.5)

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/test_ocr', methods=['GET'])
def test_ocr():
    """Chức năng Test OCR Thủ Công qua Web"""
    global last_processing_time
    start_t = time.time()
    try:
        img = capture_image()
        h, w = img.shape[:2]
        cx, cy = w // 2, h // 2
        # Crop vùng trung tâm (600x400)
        cropped_img = img[max(0, cy - 200):min(h, cy + 200), max(0, cx - 300):min(w, cx + 300)]
        
        gray = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY)
        processed_img = cv2.bilateralFilter(gray, 11, 17, 17)
        results = reader.readtext(processed_img)
        
        raw_text = ""
        for (bbox, text, prob) in results:
            clean_text = ''.join(e for e in text if e.isalnum()).upper()
            raw_text += clean_text
        
        plate = "Khong Thay Bien"
        match = re.search(r"(1[1-9]|[2-9][0-9])[A-Z][0-9A-Z]?\d{4,5}", raw_text)
        if match:
            plate = match.group(0)
            
        process_time = round(time.time() - start_t, 2)
        last_processing_time = process_time
        return jsonify({"success": True, "plate": plate, "time": process_time})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/get_stats', methods=['GET'])
def get_stats():
    return jsonify({"last_time": last_processing_time})

@app.route('/')
def index():
    html = """
    <html>
        <head>
            <title>Camera Canh Chinh</title>
            <style>
                body { text-align: center; background-color: #1a1a1a; color: #fff; font-family: Arial; }
                .container { display: flex; flex-direction: column; align-items: center; }
                .btn { padding: 10px 20px; font-size: 18px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 5px; margin: 10px; }
                .btn:hover { background: #0056b3; }
                .stats { font-size: 18px; margin-top: 10px; color: #00ff00; }
                img { max-width: 90%; border: 3px solid #444; border-radius: 10px; margin-top: 20px; }
            </style>
        </head>
        <body>
            <h2>Hệ Thống Canh Chỉnh AI & Camera</h2>
            <p>Điều chỉnh camera sao cho biển số lọt vào khung vàng (Vùng AI Nhận Diện)</p>
            
            <div class="container">
                <div>
                    <button class="btn" onclick="testOCR()">Test OCR Ngay</button>
                </div>
                <div id="result" class="stats">Chưa có kết quả test.</div>
                <div id="time_stat" class="stats" style="color: #ffaa00;">Thời gian xử lý AI gần nhất: 0.0s</div>
                
                <img src="/video_feed">
            </div>

            <script>
                function testOCR() {
                    document.getElementById('result').innerText = "Đang chạy AI OCR... Vui lòng đợi!";
                    fetch('/test_ocr')
                        .then(r => r.json())
                        .then(data => {
                            if (data.success) {
                                document.getElementById('result').innerText = "Kết quả Biển Số: " + data.plate;
                                updateStats();
                            } else {
                                document.getElementById('result').innerText = "Lỗi: " + data.error;
                            }
                        });
                }
                
                function updateStats() {
                    fetch('/get_stats')
                        .then(r => r.json())
                        .then(data => {
                            document.getElementById('time_stat').innerText = "Thời gian xử lý AI gần nhất: " + data.last_time + "s";
                        });
                }
                
                // Tự động cập nhật thời gian xử lý mỗi 2 giây
                setInterval(updateStats, 2000);
            </script>
        </body>
    </html>
    """
    return html

# =========================================================
# LOGIC NHẬN DIỆN BIỂN SỐ (AI CORE)
# =========================================================
def capture_image():
    res = requests.get(IP_WEBCAM_URL, timeout=3)
    if res.status_code == 200:
        nparr = np.frombuffer(res.content, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    else:
        raise Exception(f"HTTP Status {res.status_code}")

def process_10_frames_ocr(car_id, speed, direction):
    global last_processing_time
    start_t = time.time()
    
    try:
        # 1. Chụp liên tiếp 10 bức ảnh
        frames_to_process = []
        for i in range(10):
            try:
                frames_to_process.append(capture_image())
                time.sleep(0.05) 
            except Exception as ce:
                print(f"Lỗi chụp frame {i}: {ce}")
                
        if not frames_to_process:
            raise Exception("Không thể chụp được bất kỳ ảnh nào!")
            
        print(f"    -> Đã thu thập {len(frames_to_process)} ảnh. Đang cắt tâm và chạy OCR Voting...")
        
        plate_votes = collections.defaultdict(int)
        best_plate = "Khong Thay Bien"
        best_image_frame = frames_to_process[0]
        image_filename = ""
        
        # 2. Chạy OCR cho từng khung hình (Chỉ xử lý phần tâm ảnh)
        for idx, img in enumerate(frames_to_process):
            h, w = img.shape[:2]
            cx, cy = w // 2, h // 2
            # Cắt ảnh vùng tâm (Kích thước 600x400)
            cropped_img = img[max(0, cy - 200):min(h, cy + 200), max(0, cx - 300):min(w, cx + 300)]
            
            gray = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY)
            processed_img = cv2.bilateralFilter(gray, 11, 17, 17)
            results = reader.readtext(processed_img)
            
            raw_text = ""
            for (bbox, text, prob) in results:
                clean_text = ''.join(e for e in text if e.isalnum()).upper()
                raw_text += clean_text
            
            match = re.search(r"(1[1-9]|[2-9][0-9])[A-Z][0-9A-Z]?\d{4,5}", raw_text)
            if match:
                plate = match.group(0)
                plate_votes[plate] += 1
                if plate_votes[plate] == 1:
                    best_image_frame = img # Lưu trữ bức ảnh GỐC (chưa cắt) để làm bằng chứng đẹp hơn

        # 3. Tổng hợp kết quả (Voting)
        if plate_votes:
            best_plate = max(plate_votes, key=plate_votes.get)
            print(f"    -> Bảng kết quả (Voting): {dict(plate_votes)}")
            print(f"    -> KẾT QUẢ CHỌN LỌC: {best_plate}")
            
            if not os.path.exists("violations"):
                os.makedirs("violations")
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            image_filename = f"{best_plate}_{timestamp}.jpg"
            image_path = os.path.join("violations", image_filename)
            cv2.imwrite(image_path, best_image_frame)
            print(f"    -> Đã lưu bằng chứng: {image_filename}")
        else:
            print(f"    -> Không tìm thấy biển số chuẩn trong toàn bộ {len(frames_to_process)} ảnh.")
            
        # Tính tổng thời gian xử lý
        total_time = round(time.time() - start_t, 2)
        last_processing_time = total_time
        print(f"    -> [THỜI GIAN] Quá trình chụp & phân tích 10 ảnh mất: {total_time} giây")
        
        # Gửi trả kết quả về ESP32
        payload = {
            "id": car_id,
            "speed": speed,
            "direction": direction,
            "plate": best_plate
        }
        hive_client.publish("iot_thanglong/plate", json.dumps(payload))
        print(f">>> Đã trả kết quả về ESP32: {payload}")
        
        # Đồng bộ Node.js (Cho vi phạm)
        if image_filename != "":
            try:
                node_payload = {
                    "car_id": car_id,
                    "speed": speed,
                    "direction": direction,
                    "plate": best_plate,
                    "image": image_filename,
                    "timestamp": datetime.datetime.now().isoformat()
                }
                requests.post("http://localhost:3000/api/violation", json=node_payload, timeout=2)
                print(f">>> Đã đẩy dữ liệu chờ duyệt tới Node.js Backend")
            except Exception as e:
                print(f"!!! Không thể kết nối Node.js Backend: {e}")
                
    except Exception as cam_err:
        print("!!! Lỗi Camera:", cam_err)
        payload = {"id": car_id, "speed": speed, "direction": direction, "plate": "Loi Camera"}
        hive_client.publish("iot_thanglong/plate", json.dumps(payload))

def on_hive_message(client, userdata, msg):
    if msg.topic == "iot_thanglong/speed":
        try:
            data = json.loads(msg.payload.decode('utf-8'))
            car_id = str(data.get("id", "UNKNOWN"))
            speed = data.get("speed", 0)
            direction = data.get("direction", "None")
            
            print(f"\n[+] Đã nhận TỐC ĐỘ Xe {car_id}: {speed} km/h. Bắt đầu chụp đa khung hình (10 frames)...")
            
            # Khởi chạy phân tích trong luồng nền để không chặn các request khác
            threading.Thread(target=process_10_frames_ocr, args=(car_id, speed, direction)).start()
                
        except Exception as e:
            print("Lỗi MQTT:", e)

def start_mqtt():
    try:
        hive_client.on_message = on_hive_message
        hive_client.connect(HIVEMQ_BROKER, HIVEMQ_PORT, 60)
        hive_client.subscribe("iot_thanglong/speed")
        print("- Đã kết nối HiveMQ và trực ban MQTT trong luồng nền...")
        hive_client.loop_forever()
    except Exception as e:
        print("Lỗi kết nối HiveMQ:", e)

def main():
    # Chạy MQTT trong Thread riêng để không block Web Server
    mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
    mqtt_thread.start()
    
    # Chạy Flask Web Server ở luồng chính
    print(f"\n==============================================")
    print(f"🚀 WEB UI ĐÃ MỞ TẠI: http://localhost:{FLASK_PORT}")
    print(f"==============================================\n")
    app.run(host='0.0.0.0', port=FLASK_PORT, debug=False, use_reloader=False)

if __name__ == '__main__':
    main()
