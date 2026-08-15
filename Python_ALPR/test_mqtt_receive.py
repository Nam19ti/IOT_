"""
Script test nhanh - khong can AI, khong can Camera
Chi kiem tra xem Python co nhan duoc tin hieu MQTT tu ESP32 hay khong
Chay bang lenh: python test_mqtt_receive.py
"""
import paho.mqtt.client as mqtt
import time
import json

print("=" * 50)
print("  TEST NHAN TIN HIEU MQTT TU ESP32")
print("  Hay BAM NUT NGUONG TREN MACH ESP32 ngay bay gio")
print("=" * 50)

received_count = 0

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"\n[OK] Da ket noi HiveMQ thanh cong!")
        result, mid = client.subscribe("iot_thanglong/speed", qos=1)
        print(f"[OK] Da dang ky lang nghe: iot_thanglong/speed (QoS=1)")
        print(f"\n>>> Dang cho tin hieu tu ESP32... Hay bam nut toc do tren mach! <<<\n")
    else:
        print(f"[LOI] Bi tu choi ket noi, ma loi: {rc}")

def on_disconnect(client, userdata, rc):
    print(f"[CANH BAO] Mat ket noi (rc={rc}). Dang tu dong ket noi lai...")

def on_message(client, userdata, msg):
    global received_count
    received_count += 1
    print(f"\n{'='*50}")
    print(f"[THANH CONG] Da nhan duoc tin hieu lan thu {received_count}!")
    print(f"  Topic  : {msg.topic}")
    print(f"  Payload: {msg.payload.decode('utf-8')}")
    try:
        data = json.loads(msg.payload.decode('utf-8'))
        print(f"  ID     : {data.get('id')}")
        print(f"  Toc do : {data.get('speed')} km/h")
        print(f"  Chieu  : {data.get('direction')}")
    except:
        pass
    print(f"{'='*50}\n")

# Tao client - tuong thich ca paho v1 va v2
try:
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
        client_id="TEST_RECEIVER_12345"
    )
except AttributeError:
    client = mqtt.Client(client_id="TEST_RECEIVER_12345")

client.on_connect    = on_connect
client.on_disconnect = on_disconnect
client.on_message    = on_message

print("[...] Dang ket noi den broker.hivemq.com:1883 ...")
try:
    client.connect("broker.hivemq.com", 1883, keepalive=60)
except Exception as e:
    print(f"[LOI MANG] Khong the ket noi: {e}")
    print("Kiem tra lai internet cua may tinh!")
    exit(1)

# Chay 60 giay de test
start = time.time()
try:
    while time.time() - start < 60:
        client.loop(timeout=1.0)
        elapsed = int(time.time() - start)
        if elapsed % 10 == 0 and elapsed > 0:
            print(f"[...] Dang cho... ({elapsed}s) | Da nhan: {received_count} tin hieu")
            time.sleep(1)
except KeyboardInterrupt:
    pass

print(f"\n[KET QUA] Tong so tin hieu nhan duoc trong 60 giay: {received_count}")
if received_count == 0:
    print("[PHAN TICH]")
    print("  -> Python KHONG nhan duoc gi ca!")
    print("  -> Nguyen nhan co the:")
    print("     1. ESP32 Slave chua ket noi duoc WiFi hoac HiveMQ")
    print("     2. ESP32 dang publish sai topic (khong phai iot_thanglong/speed)")
    print("     3. Day UART giua 2 ESP32 bi long/dut")
    print("  -> Mo Serial Monitor cua ESP32 Slave de kiem tra log!")
else:
    print(f"[OK] MQTT hoat dong binh thuong! Nhan duoc {received_count} tin hieu.")
client.disconnect()
