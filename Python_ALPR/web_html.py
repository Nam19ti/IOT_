def get_html(controller):
    cam_url = controller.config.get('ip_camera_url', '')
    
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ALPR Dashboard - IOT Thang Long</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #00d2ff; --secondary: #3a7bd5;
            --success: #10b981; --danger: #ef4444; --warn: #fbbf24;
            --bg: #0f172a; --card: rgba(15,23,42,0.85);
            --border: rgba(255,255,255,0.08);
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: #f1f5f9; min-height: 100vh; }}
        
        header {{ text-align: center; padding: 2rem 1rem 1rem; }}
        header h1 {{ font-size: 2.2rem; font-weight: 800; background: linear-gradient(135deg, var(--primary), var(--secondary)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        header p {{ color: #64748b; margin-top: 0.4rem; font-size: 0.95rem; }}

        #ai_status_bar {{ margin: 0.5rem auto; max-width: 900px; padding: 0.6rem 1.2rem; border-radius: 8px; font-weight: 600; text-align: center; background: rgba(251,191,36,0.15); border: 1px solid var(--warn); color: var(--warn); transition: all 0.5s; }}
        #ai_status_bar.ready {{ background: rgba(16,185,129,0.15); border-color: var(--success); color: var(--success); }}

        .main-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; max-width: 1300px; margin: 1rem auto; padding: 0 1rem; }}
        @media(max-width: 900px) {{ .main-grid {{ grid-template-columns: 1fr; }} }}

        .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 1.5rem; box-shadow: 0 8px 32px rgba(0,0,0,0.4); }}
        .card-title {{ font-size: 1rem; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 1rem; }}

        .form-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 0.8rem; }}
        .form-row label {{ min-width: 130px; font-size: 0.9rem; color: #94a3b8; text-align: right; }}
        input[type=text], input[type=password] {{ flex: 1; background: rgba(0,0,0,0.4); border: 1px solid var(--border); color: #f1f5f9; padding: 9px 13px; border-radius: 8px; font-family: 'Inter', sans-serif; font-size: 0.9rem; transition: border-color 0.2s; }}
        input:focus {{ outline: none; border-color: var(--primary); }}

        .btn {{ padding: 10px 22px; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.95rem; font-family: 'Inter', sans-serif; transition: all 0.2s; letter-spacing: 0.02em; }}
        .btn-primary {{ background: linear-gradient(135deg, var(--secondary), var(--primary)); color: #fff; }}
        .btn-green   {{ background: linear-gradient(135deg, #059669, var(--success)); color: #fff; }}
        .btn:hover   {{ transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,210,255,0.35); }}
        .btn-row     {{ display: flex; gap: 10px; justify-content: center; margin-top: 0.8rem; }}

        .stream-wrap {{ position: relative; border-radius: 12px; overflow: hidden; background: #000; border: 1px solid var(--border); }}
        .stream-wrap img {{ width: 100%; display: block; }}
        .stream-label {{ position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.6); padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; color: var(--primary); border: 1px solid var(--primary); }}

        #violation_panel {{ background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 1.5rem; margin: 1.5rem auto; max-width: 1300px; padding-left: 1rem; padding-right: 1rem; }}
        .vio-grid {{ display: grid; grid-template-columns: auto 1fr; gap: 1.5rem; align-items: start; }}
        @media(max-width: 600px) {{ .vio-grid {{ grid-template-columns: 1fr; }} }}
        #vio_img {{ width: 320px; max-width: 100%; border-radius: 10px; border: 2px solid var(--danger); display: none; }}
        #vio_placeholder {{ width: 320px; height: 200px; border-radius: 10px; border: 2px dashed var(--border); display: flex; align-items: center; justify-content: center; color: #475569; font-size: 0.9rem; }}
        .vio-info {{ display: flex; flex-direction: column; gap: 0.8rem; }}
        .vio-badge {{ display: inline-block; padding: 6px 16px; border-radius: 30px; font-weight: 700; font-size: 1.8rem; letter-spacing: 0.1em; background: rgba(239,68,68,0.15); border: 2px solid var(--danger); color: var(--danger); width: fit-content;}}
        .vio-row {{ font-size: 1rem; color: #cbd5e1; }}
        .vio-row span {{ color: #f1f5f9; font-weight: 600; }}

        #ocr_result {{ font-size: 1.2rem; font-weight: 700; margin-top: 0.8rem; min-height: 1.5rem; text-align: center; color: var(--success); }}
        #save_msg {{ color: var(--warn); font-weight: 600; text-align: center; margin-top: 0.5rem; min-height: 1.2rem; }}
    </style>
</head>
<body>
    <header>
        <h1>&#128663; TRAM THU PHI VETC</h1>
        <p>EasyOCR Offline &nbsp;|&nbsp; LAN HTTP &nbsp;|&nbsp; ESP32-CAM</p>
    </header>

    <div id="ai_status_bar">AI dang khoi dong... Vui long doi!</div>

    <!-- KET QUA NHAN DIEN GAN NHAT -->
    <div id="violation_panel">
        <div class="card">
            <div class="card-title" style="display:flex; justify-content:space-between;">
                <span>&#128247; KET QUA NHAN DIEN BIEN SO GAN NHAT</span>
                <span id="queue_status" style="font-size:0.8rem; color:var(--success);">Trang thai: OK</span>
            </div>
            <div class="vio-grid">
                <div>
                    <div id="vio_placeholder">Chua co anh nao</div>
                    <img id="vio_img" src="" alt="Anh bien so">
                </div>
                <div class="vio-info">
                    <div class="vio-badge" id="vio_plate">---</div>
                    <div class="vio-row">Trang thai: <span id="vio_status">---</span></div>
                    <div class="vio-row">Thoi gian xu ly: <span id="vio_time">---</span></div>
                    <div class="vio-row" style="color:#64748b; font-size:0.85rem;" id="vio_ts"></div>
                </div>
            </div>
        </div>
    </div>

    <div class="main-grid">
        <div class="card">
            <div class="card-title">&#127909; CAMERA ESP32-CAM</div>
            <div class="stream-wrap" style="position: relative; background: #000; min-height: 200px; display: flex; align-items: center; justify-content: center;">
                <img id="latest_cam_view" src="/violations/latest_capture.jpg" style="max-width: 100%; max-height: 400px; object-fit: contain; border-radius: 8px;" alt="Chua co anh chup." onerror="this.style.opacity='0.3'">
                <div class="stream-label" style="position: absolute; top: 10px; right: 10px; background: rgba(0,0,0,0.6); padding: 4px 8px; border-radius: 4px; font-size: 0.8rem;">ANH CHUP GAN NHAT</div>
            </div>
            <div class="btn-row" style="margin-top: 1rem;">
                <button class="btn btn-primary" id="btn_capture" onclick="testCapture()">&#128247; Chup Anh Tu ESP-CAM</button>
                <button class="btn btn-green" id="btn_ocr" onclick="testOCR()">&#128269; Chup &amp; Nhan Dien Ngay</button>
            </div>
            <div id="ocr_result"></div>
        </div>

        <div class="card">
            <div class="card-title">&#9881; CAU HINH HE THONG</div>
            <div class="form-row">
                <label>URL ESP32-CAM:</label>
                <input type="text" id="cameraUrl" value="{controller.config.get('ip_camera_url', 'http://192.168.137.233/photo.jpg')}" placeholder="http://192.168.137.233/photo.jpg">
            </div>
            <div class="form-row">
                <label>IP Mạch 2 (IOT_2):</label>
                <input type="text" id="iot2_ip" value="{controller.config.get('iot2_ip', '192.168.137.199')}" placeholder="192.168.137.199">
            </div>
            <div class="btn-row">
                <button class="btn btn-green" onclick="saveSettings()">Luu Cau Hinh</button>
            </div>
            <div id="save_msg"></div>
        </div>

        <div class="card" style="grid-column: 1 / -1;">
            <div class="card-title">&#128275; ĐIỀU KHIỂN CỔNG THỦ CÔNG (LAN)</div>
            <p style="color: #94a3b8; font-size: 0.9rem; text-align: center; margin-bottom: 1rem;">Lưu ý: Bạn phải điền đúng IP Mạch 2 ở ô Cấu Hình bên trên trước khi điều khiển.</p>
            <div class="btn-row" style="gap: 1.5rem;">
                <button class="btn btn-primary" onclick="controlGate('/open_gate')">Mở (Tự Đóng Sau 3s Xe Qua)</button>
                <button class="btn btn-warn" style="background: linear-gradient(135deg, #fbbf24, #f59e0b); color: #000;" onclick="controlGate('/open_gate_manual')">Mở Mãi Mãi (Không Tự Đóng)</button>
                <button class="btn btn-danger" style="background: linear-gradient(135deg, #ef4444, #dc2626); color: #fff;" onclick="controlGate('/close_gate')">Đóng Cổng Khẩn Cấp</button>
            </div>
        </div>
    </div>

<script>
    function saveSettings() {{
        const newUrl = document.getElementById('cameraUrl').value;
        const iot2Ip = document.getElementById('iot2_ip').value;
        fetch('/set_settings', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{ url: newUrl, iot2_ip: iot2Ip }})
        }}).then(r => r.json()).then(data => {{
            if(data.success) alert("Đã lưu Cấu hình thành công!");
        }});
    }}

    function controlGate(actionPath) {{
        const iot2Ip = document.getElementById('iot2_ip').value;
        if (!iot2Ip) {{ alert('Vui long nhap IP Mach 2!'); return; }}
        fetch('http://' + iot2Ip + actionPath)
            .then(r => r.text())
            .then(txt => alert('Mach 2: ' + txt))
            .catch(() => alert('Khong ket noi duoc Mach 2!'));
    }}

    function testCapture() {{
        const el = document.getElementById('ocr_result');
        const btn = document.getElementById('btn_capture');
        el.style.color = '#fbbf24'; el.innerText = 'Dang chup anh tu ESP32-CAM...';
        btn.disabled = true;
        fetch('/test_ocr').then(r => r.json()).then(d => {{
            btn.disabled = false;
            if (d.success) {{
                el.style.color = '#10b981';
                el.innerText = 'Bien so: ' + d.plate + ' (' + d.time + 's)';
                document.getElementById('latest_cam_view').src = '/violations/latest_capture.jpg?t=' + Date.now();
            }} else {{
                el.style.color = '#ef4444';
                el.innerText = '❌ ' + d.error;
            }}
        }}).catch(() => {{ btn.disabled = false; el.style.color='#ef4444'; el.innerText='❌ Loi ket noi server!'; }});
    }}

    function testOCR() {{
        const el = document.getElementById('ocr_result');
        const btn = document.getElementById('btn_ocr');
        el.style.color = '#fbbf24'; el.innerText = 'Dang chup & nhan dien bien so...';
        btn.disabled = true;
        fetch('/test_ocr').then(r => r.json()).then(d => {{
            btn.disabled = false;
            if (d.success) {{
                el.style.color = '#10b981';
                el.innerText = 'Bien so: ' + d.plate + ' (' + d.time + 's)';
                document.getElementById('latest_cam_view').src = '/violations/latest_capture.jpg?t=' + Date.now();
            }} else {{
                el.style.color = '#ef4444';
                el.innerText = '❌ ' + d.error;
            }}
        }}).catch(() => {{ btn.disabled = false; el.style.color='#ef4444'; el.innerText='❌ Loi ket noi server!'; }});
    }}

    let lastVioTs = null;
    let localLastCaptureTs = 0;

    function updateStats() {{
        fetch('/get_stats').then(r => r.json()).then(d => {{
            const bar = document.getElementById('ai_status_bar');
            if (d.ai_ready) {{
                bar.className = 'ready';
                bar.innerText = 'AI SAN SANG HOAT DONG!';
            }} else {{
                bar.className = '';
                bar.innerText = 'AI DANG KHOI DONG... (Cho 1 phut)';
            }}
            
            document.getElementById('queue_status').innerText = 'Trang thai: OK';

            // Hien thi anh chup gan nhat
            if (d.last_capture_ts && d.last_capture_ts !== localLastCaptureTs) {{
                localLastCaptureTs = d.last_capture_ts;
                document.getElementById('latest_cam_view').src = '/violations/latest_capture.jpg?t=' + new Date().getTime();
            }}

            if (d.last_violation && d.last_violation.ts !== lastVioTs) {{
                lastVioTs = d.last_violation.ts;
                const v = d.last_violation;

                document.getElementById('vio_plate').innerText = v.plate || '---';
                document.getElementById('vio_status').innerText = v.status || '---';
                document.getElementById('vio_time').innerText = (v.proc_time || '---') + 's';
                document.getElementById('vio_ts').innerText = 'Luc: ' + v.ts;

                const img = document.getElementById('vio_img');
                const ph = document.getElementById('vio_placeholder');
                if (v.image && v.image !== 'no_image.jpg') {{
                    img.src = '/violations/' + v.image + '?t=' + Date.now();
                    img.style.display = 'block';
                    ph.style.display = 'none';
                }} else {{
                    img.style.display = 'none';
                    ph.style.display = 'flex';
                }}
            }}
        }}).catch(() => {{}});
    }}

    setInterval(updateStats, 2000);
    updateStats();
</script>
</body>
</html>"""
