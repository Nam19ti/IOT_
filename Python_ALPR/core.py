import json
import os
import sys
import datetime
import threading
import queue
import cv2

def p(msg):
    try:
        sys.stdout.write(str(msg) + "\n")
        sys.stdout.flush()
    except UnicodeEncodeError:
        sys.stdout.write(str(msg).encode('ascii', 'ignore').decode('ascii') + "\n")
        sys.stdout.flush()

class Config:
    def __init__(self, filename="config.json"):
        self.filename = filename
        self.data = {
            "ip_camera_url": "http://192.168.137.233/photo.jpg",
            "iot2_ip": "192.168.137.199"
        }
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    self.data.update(json.load(f))
            except Exception as e:
                p(f"[CONFIG] Loi doc file: {e}")

    def save(self):
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            p(f"[CONFIG] Loi luu file: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()


class SystemController:
    """Trung tam quan ly trang thai he thong"""
    def __init__(self):
        self.config = Config()
        
        # Trang thai AI
        self.ai_ready = False
        self.ai_engine = None
        self.last_process_time = 0.0
        self.last_violation = None
        self.last_capture_ts = 0
        
        # Modules
        self.camera = None
        self.cloud = None

