import cv2
import numpy as np
import easyocr
import json
import paho.mqtt.client as mqtt
import requests
import time
import os
import datetime

# =========================================================
# 1. CẤU HÌNH CAMERA ĐIỆN THOẠI (SMARTPHONE)
# =========================================================
USE_USB_WEBCAM = False 
IP_WEBCAM_URL = "http://192.168.42.129:8080/photo.jpg" 
USB_CAM_INDEX = 1 

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

usb_cap = None
if USE_USB_WEBCAM:
    print(f"Đang kết nối với USB Webcam số {USB_CAM_INDEX}...")
    usb_cap = cv2.VideoCapture(USB_CAM_INDEX)
    usb_cap.set(cv2.CAP_PROP_BUFFERSIZE, 1) 
    if not usb_cap.isOpened():
        print("!!! Lỗi: Không thể mở USB Webcam!")
    else:
        print("Kết nối USB Webcam thành công!")

def capture_image():
    if USE_USB_WEBCAM and usb_cap is not None:
        usb_cap.read()
        usb_cap.read()
        ret, frame = usb_cap.read()
        if ret:
            return frame
        else:
            raise Exception("Webcam mất kết nối")
    else:
        res = requests.get(IP_WEBCAM_URL, timeout=3)
        if res.status_code == 200:
            nparr = np.frombuffer(res.content, np.uint8)
            return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            raise Exception(f"HTTP Status {res.status_code}")

def on_hive_message(client, userdata, msg):
    if msg.topic == "iot_thanglong/speed":
        try:
            data = json.loads(msg.payload.decode('utf-8'))
            car_id = str(data["id"])
            speed = data["speed"]
            direction = data["direction"]
            
            print(f"\n[+] Đã nhận TỐC ĐỘ Xe {car_id}: {speed} km/h. Bắt đầu chụp ảnh...")
            
            try:
                img = capture_image()
                print(f"    -> Đã lấy được ảnh nét! Đang chạy AI...")
                
                results = reader.readtext(img)
                plate_text = ""
                for (bbox, text, prob) in results:
                    clean_text = ''.join(e for e in text if e.isalnum()).upper()
                    if len(clean_text) >= 4:
                        plate_text += clean_text + "-"
                
                plate_text = plate_text.rstrip("-")
                if not plate_text:
                    plate_text = "Khong Thay Bien"
                    
                print(f"> Kết quả AI Xe {car_id}: [{plate_text}]")
                
                # Gửi trả KẾT QUẢ TỔNG HỢP về lại Slave thông qua HiveMQ
                payload = {
                    "id": car_id,
                    "speed": speed,
                    "direction": direction,
                    "plate": plate_text
                }
                
                hive_client.publish("iot_thanglong/plate", json.dumps(payload))
                print(f">>> Đã đẩy trả toàn bộ kết quả về ESP32 Slave: {payload}")
                
            except Exception as cam_err:
                print("!!! Lỗi Camera:", cam_err)
                payload = {"id": car_id, "speed": speed, "direction": direction, "plate": "Loi Camera"}
                hive_client.publish("iot_thanglong/plate", json.dumps(payload))
                
        except Exception as e:
            print("Lỗi MQTT:", e)

def main():
    try:
        hive_client.on_message = on_hive_message
        hive_client.connect(HIVEMQ_BROKER, HIVEMQ_PORT, 60)
        hive_client.subscribe("iot_thanglong/speed")
        print("- Đã kết nối HiveMQ và đang trực ban lắng nghe tốc độ...")
        hive_client.loop_forever()
    except Exception as e:
        print("Lỗi kết nối HiveMQ:", e)

if __name__ == '__main__':
    main()
