import json
import threading
import paho.mqtt.client as mqtt
import time
from core import p

class MQTTService:
    def __init__(self, system_controller):
        self.controller = system_controller
        self.client = None
        self._init_mqtt()
        
    def _init_mqtt(self):
        try:
            self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION1, client_id="ALPR_Core")
        except AttributeError:
            self.client = mqtt.Client(client_id="ALPR_Core")
            
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        threading.Thread(target=self._run_loop, daemon=True).start()
        
    def _run_loop(self):
        while True:
            try:
                p("[MQTT] Dang ket noi HiveMQ...")
                self.client.connect("broker.hivemq.com", 1883, keepalive=20)
                self.client.loop_forever()
            except Exception as e:
                p(f"[MQTT LOI] Ket noi that bai: {e}")
                time.sleep(5)
                
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            p("[MQTT] Da ket noi thanh cong!")
            client.subscribe("iot_thanglong/speed", qos=1)
        else:
            p(f"[MQTT] Tu choi ket noi. Ma loi: {rc}")
            
    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            p("[MQTT] Mat ket noi. Tu dong thu lai...")
            
    def _on_message(self, client, userdata, msg):
        if msg.topic != "iot_thanglong/speed":
            return
        try:
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)
            car_id = str(data.get("id", "UNK"))
            speed = float(data.get("speed", 0))
            direction = str(data.get("direction", "None"))
            
            p(f"\n[MQTT] Nhan toc do: {speed}km/h tu xe {car_id}")
            self.controller.trigger_violation(car_id, speed, direction)
        except Exception as e:
            p(f"[MQTT LOI] Khong the doc JSON: {e}")
            
    def publish_plate(self, car_id, speed, direction, plate):
        try:
            payload = json.dumps({"id": car_id, "speed": speed, "direction": direction, "plate": plate})
            self.client.publish("iot_thanglong/plate", payload)
        except Exception:
            pass
