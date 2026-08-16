import sys
import requests
import cv2
import numpy as np

def test_camera(url):
    print(f"==================================================")
    print(f"Đang kiểm tra kết nối tới Camera: {url}")
    print(f"==================================================")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    
    try:
        print("1. Đang gửi HTTP GET request (Timeout 5s)...")
        r = requests.get(url, headers=headers, timeout=5.0)
        print(f"   -> HTTP Status Code: {r.status_code}")
        print(f"   -> Kích thước dữ liệu tải về: {len(r.content)} bytes")
        
        if r.status_code == 200:
            print("2. Đang giải mã dữ liệu ảnh bằng OpenCV (cv2.imdecode)...")
            arr = np.asarray(bytearray(r.content), dtype=np.uint8)
            img = cv2.imdecode(arr, -1)
            
            if img is not None:
                print(f"   -> THÀNH CÔNG! Giải mã ảnh OK. Kích thước (WxH): {img.shape[1]}x{img.shape[0]}")
            else:
                print("   -> LỖI: Không thể giải mã dữ liệu thành ảnh. Dữ liệu tải về có thể không phải định dạng JPEG/PNG hợp lệ!")
                # Lưu file bị lỗi để phân tích
                with open("error_dump.bin", "wb") as f:
                    f.write(r.content)
                print("   -> Đã lưu dữ liệu thô vào file 'error_dump.bin' để kiểm tra.")
        else:
            print(f"   -> LỖI: Server trả về mã lỗi {r.status_code}, không thể tải ảnh.")
            
    except requests.exceptions.Timeout:
        print("   -> LỖI TIMEOUT: Hết thời gian chờ (5s). Không thể kết nối tới IP/Port này.")
    except requests.exceptions.ConnectionError:
        print("   -> LỖI KẾT NỐI: Bị từ chối kết nối. Hãy kiểm tra lại IP và Port (8080).")
    except Exception as e:
        print(f"   -> LỖI KHÔNG XÁC ĐỊNH: {e}")
        
    print(f"==================================================")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Cách dùng: python3 test_camera.py <URL_CAMERA>")
        print("Ví dụ: python3 test_camera.py http://192.168.1.100:8080/shot.jpg")
    else:
        test_camera(sys.argv[1])
