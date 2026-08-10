import cv2
import numpy as np
import easyocr
import json
import paho.mqtt.client as mqtt

# =========================================================
# CẤU HÌNH MQTT
# =========================================================
# 1. HiveMQ (Dùng để nhận dữ liệu nội bộ siêu tốc từ 2 con ESP32)
HIVEMQ_BROKER = "broker.hivemq.com"
HIVEMQ_PORT = 1883

# 2. ThingsBoard (Dùng để báo cáo kết quả cuối cùng lên Web)
TB_BROKER = "mqtt.thingsboard.cloud"
TB_PORT = 1883
TB_TOKEN = "TOKEN_CUA_ESP32_SLAVE" # ĐIỀN TOKEN CỦA BẠN VÀO ĐÂY

# =========================================================
# KHỞI TẠO CÁC MODULE VÀ BIẾN TOÀN CỤC
# =========================================================
print("Đang tải mô hình nhận diện chữ (EasyOCR)... Vui lòng đợi...")
reader = easyocr.Reader(['en'], gpu=False) 
print("Tải xong mô hình!")

# Cuốn sổ ghi chép tốc độ tạm thời của từng xe (Chống nhầm lẫn Session ID)
# Định dạng: { "1": {"speed": 25.3, "dir": "Trai->Phai"}, "2": {...} }
cars_db = {}

# Khởi tạo 2 MQTT Client riêng biệt
hive_client = mqtt.Client(client_id="Python_AI_Core_" + str(np.random.randint(1000)))
tb_client = mqtt.Client(client_id="TB_Publisher_" + str(np.random.randint(1000)))
tb_client.username_pw_set(TB_TOKEN)

# =========================================================
# XỬ LÝ KHI NHẬN ĐƯỢC TIN NHẮN TỪ HIVEMQ
# =========================================================
def on_hive_message(client, userdata, msg):
    topic = msg.topic
    
    # 1. NẾU NHẬN ĐƯỢC TỐC ĐỘ TỪ SLAVE
    if topic == "iot_thanglong/speed":
        try:
            data = json.loads(msg.payload.decode('utf-8'))
            car_id = str(data["id"])
            cars_db[car_id] = {
                "speed": data["speed"],
                "direction": data["direction"]
            }
            print(f"\n[+] Đã ghi sổ TỐC ĐỘ của Xe ID {car_id}: {data['speed']} km/h")
        except Exception as e:
            print("Lỗi đọc JSON tốc độ:", e)

    # 2. NẾU NHẬN ĐƯỢC ẢNH TỪ CAM
    elif topic.startswith("iot_thanglong/image/"):
        car_id = topic.split("/")[-1]
        print(f"\n[+] Đã nhận ẢNH của Xe ID {car_id}. Đang chạy AI...")
        
        try:
            # Chuyển đổi mảng byte thành ảnh OpenCV
            nparr = np.frombuffer(msg.payload, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            cv2.imwrite(f"capture_xe_{car_id}.jpg", img) # Lưu ra file để kiểm tra

            # Nhận diện
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

            # Ghép với tốc độ trong sổ và gửi lên ThingsBoard
            if car_id in cars_db:
                car_info = cars_db.pop(car_id) # Lấy ra và xóa khỏi sổ
                
                payload = {
                    "speed": car_info["speed"],
                    "direction": car_info["direction"],
                    "license_plate": plate_text
                }
                
                # Bắn lên ThingsBoard
                tb_client.publish("v1/devices/me/telemetry", json.dumps(payload))
                print(f">>> ĐÃ GỬI LÊN THINGSBOARD: {payload}")
            else:
                print(f"!!! Lỗi: Nhận được ảnh Xe {car_id} nhưng không tìm thấy tốc độ trong sổ!")
                
        except Exception as e:
            print(f"Lỗi xử lý ảnh xe {car_id}:", e)

# =========================================================
# HÀM MAIN CHẠY SERVER
# =========================================================
def main():
    # Kết nối ThingsBoard
    try:
        tb_client.connect(TB_BROKER, TB_PORT, 60)
        tb_client.loop_start()
        print("- Đã kết nối ThingsBoard.")
    except Exception as e:
        print("Lỗi kết nối ThingsBoard:", e)

    # Kết nối HiveMQ và Subscribe
    try:
        hive_client.on_message = on_hive_message
        hive_client.connect(HIVEMQ_BROKER, HIVEMQ_PORT, 60)
        
        hive_client.subscribe("iot_thanglong/speed")
        hive_client.subscribe("iot_thanglong/image/#") # Dấu # để bắt mọi ID
        
        print("- Đã kết nối HiveMQ và đang trực ban lắng nghe MQTT...")
        
        # Vòng lặp duy trì kết nối
        hive_client.loop_forever()
    except Exception as e:
        print("Lỗi kết nối HiveMQ:", e)

if __name__ == '__main__':
    main()
