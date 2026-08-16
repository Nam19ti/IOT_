def get_html(controller):
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VETC - Tram Thu Phi Thang Long</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: #00d2ff; --secondary: #3a7bd5;
            --success: #10b981; --danger: #ef4444; --warn: #fbbf24;
            --bg: #0f172a; --card: rgba(15,23,42,0.9);
            --border: rgba(255,255,255,0.08);
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: #f1f5f9; min-height: 100vh;
                background-image: radial-gradient(at 0% 0%, rgba(0,210,255,0.08) 0px, transparent 60%),
                                  radial-gradient(at 100% 100%, rgba(58,123,213,0.06) 0px, transparent 60%); }}

        header {{ text-align: center; padding: 2rem 1rem 1.2rem; border-bottom: 1px solid var(--border); }}
        header h1 {{ font-size: 2.4rem; font-weight: 800;
                     background: linear-gradient(135deg, var(--primary), var(--secondary));
                     -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        header p {{ color: #64748b; margin-top: 0.4rem; font-size: 0.9rem; letter-spacing: 0.05em; }}

        #ai_status_bar {{ margin: 1rem auto; max-width: 960px; padding: 0.65rem 1.5rem;
                          border-radius: 10px; font-weight: 700; text-align: center; font-size: 0.95rem;
                          background: rgba(251,191,36,0.12); border: 1px solid var(--warn); color: var(--warn);
                          transition: all 0.5s; }}
        #ai_status_bar.ready {{ background: rgba(16,185,129,0.12); border-color: var(--success); color: var(--success); }}

        .wrap {{ max-width: 1320px; margin: 0 auto; padding: 1.5rem 1rem; display: flex; flex-direction: column; gap: 1.5rem; }}

        .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 18px;
                 padding: 1.5rem; box-shadow: 0 8px 40px rgba(0,0,0,0.45); }}
        .card-title {{ font-size: 0.85rem; font-weight: 700; color: #64748b; text-transform: uppercase;
                       letter-spacing: 0.08em; margin-bottom: 1.2rem; display: flex;
                       justify-content: space-between; align-items: center; }}

        /* === KET QUA NHAN DIEN === */
        .result-grid {{ display: grid; grid-template-columns: 340px 1fr; gap: 1.5rem; align-items: center; }}
        @media(max-width:700px) {{ .result-grid {{ grid-template-columns: 1fr; }} }}
        #result_img {{ width: 100%; border-radius: 12px; border: 2px solid var(--primary); display: none; }}
        #result_placeholder {{ width: 100%; height: 210px; border-radius: 12px; border: 2px dashed var(--border);
                               display: flex; align-items: center; justify-content: center;
                               color: #475569; font-size: 0.9rem; }}
        .plate-badge {{ font-size: 2.2rem; font-weight: 800; letter-spacing: 0.12em;
                        padding: 10px 24px; border-radius: 12px; width: fit-content;
                        background: rgba(0,210,255,0.1); border: 2px solid var(--primary);
                        color: var(--primary); margin-bottom: 1rem; }}
        .info-row {{ color: #94a3b8; font-size: 1rem; margin-bottom: 0.5rem; }}
        .info-row span {{ color: #f1f5f9; font-weight: 600; }}

        /* === CAMERA === */
        .cam-center-grid {{ display: grid; grid-template-columns: 1fr; max-width: 800px; margin: 0 auto; gap: 1.5rem; }}
        .cam-wrap {{ position: relative; border-radius: 12px; overflow: hidden;
                     background: #000; border: 1px solid var(--border); min-height: 200px;
                     display: flex; align-items: center; justify-content: center; }}
        .cam-wrap img {{ width: 100%; max-height: 360px; object-fit: contain; display: block; }}
        .cam-badge {{ position: absolute; top: 10px; right: 10px; background: rgba(0,0,0,0.7);
                      padding: 4px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 700;
                      color: var(--primary); border: 1px solid var(--primary); }}

        /* === FORM === */
        .form-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 0.9rem; }}
        .form-row label {{ min-width: 140px; font-size: 0.88rem; color: #94a3b8; text-align: right; }}
        input[type=text] {{ flex: 1; background: rgba(0,0,0,0.4); border: 1px solid var(--border);
                            color: #f1f5f9; padding: 9px 13px; border-radius: 8px;
                            font-family: 'Inter',sans-serif; font-size: 0.9rem; transition: border-color 0.2s; }}
        input:focus {{ outline: none; border-color: var(--primary); }}

        /* === BUTTONS === */
        .btn {{ padding: 10px 20px; border: none; border-radius: 9px; cursor: pointer;
                font-weight: 700; font-size: 0.9rem; font-family: 'Inter',sans-serif;
                transition: all 0.2s; letter-spacing: 0.02em; }}
        .btn:hover {{ transform: translateY(-2px); filter: brightness(1.15); box-shadow: 0 4px 20px rgba(0,210,255,0.25); }}
        .btn:disabled {{ opacity: 0.5; cursor: not-allowed; transform: none; }}
        .btn-blue   {{ background: linear-gradient(135deg, #3a7bd5, #00d2ff); color: #fff; }}
        .btn-green  {{ background: linear-gradient(135deg, #059669, #10b981); color: #fff; }}
        .btn-yellow {{ background: linear-gradient(135deg, #f59e0b, #fbbf24); color: #000; }}
        .btn-red    {{ background: linear-gradient(135deg, #dc2626, #ef4444); color: #fff; }}
        .btn-row    {{ display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; margin-top: 1rem; }}

        /* === OCR RESULT === */
        #ocr_result {{ font-size: 1.05rem; font-weight: 700; margin-top: 0.8rem;
                       min-height: 1.5rem; text-align: center; transition: color 0.3s; }}

        /* === SAVE MSG === */
        #save_msg {{ font-size: 0.9rem; font-weight: 600; text-align: center;
                     margin-top: 0.6rem; min-height: 1.2rem; color: var(--success); }}

        /* === TOAST === */
        #_toast {{ position: fixed; bottom: 2rem; left: 50%; transform: translateX(-50%);
                   background: #1e293b; border: 1px solid rgba(255,255,255,0.12);
                   color: #f1f5f9; padding: 0.75rem 1.5rem; border-radius: 12px;
                   font-weight: 600; z-index: 9999; opacity: 0; transition: opacity 0.4s;
                   pointer-events: none; white-space: nowrap; }}
    </style>
</head>
<body>
    <header>
        <h1>&#128663; TRAM THU PHI VETC</h1>
        <p>EasyOCR Offline &nbsp;|&nbsp; ESP32-CAM &nbsp;|&nbsp; LAN HTTP</p>
    </header>

    <div id="ai_status_bar">AI dang khoi dong... Vui long doi!</div>

    <div class="wrap">

        <!-- KET QUA NHAN DIEN -->
        <div class="card">
            <div class="card-title">
                <span>&#128247; Ket qua nhan dien bien so gan nhat</span>
                <span id="sys_status" style="color:var(--success); font-size:0.8rem;">San sang</span>
            </div>
            <div class="result-grid">
                <div>
                    <div id="result_placeholder">Chua co anh nhan dien nao</div>
                    <img id="result_img" src="" alt="Anh bien so">
                </div>
                <div>
                    <div class="plate-badge" id="plate_display">---</div>
                    <div class="info-row">Trang thai: <span id="payment_status">---</span></div>
                    <div class="info-row">Thoi gian xu ly: <span id="proc_time">---</span></div>
                    <div class="info-row" style="color:#475569; font-size:0.82rem;" id="result_ts"></div>
                </div>
            </div>
        </div>

        <!-- CAMERA ESP32-CAM -->
        <div class="cam-center-grid">
            <div class="card">
                <div class="card-title">&#127909; Camera ESP32-CAM</div>
                <div class="cam-wrap">
                    <img id="cam_view" src="/violations/latest_capture.jpg"
                         alt="Chua co anh" onerror="this.style.opacity='0.2'">
                    <div class="cam-badge">ANH GAN NHAT</div>
                </div>
                <div class="btn-row">
                    <button class="btn btn-blue" id="btn_capture" onclick="doCapture()">
                        &#128247; Chup Anh
                    </button>
                    <button class="btn btn-green" id="btn_ocr" onclick="doOCR()">
                        &#128269; Chup &amp; Nhan Dien
                    </button>
                </div>
                <div id="ocr_result"></div>
            </div>
        </div>

        <!-- DIEU KHIEN CONG -->
        <div class="card">
            <div class="card-title">&#128275; Dieu khien cong thu cong (LAN)</div>
            <p style="color:#64748b; font-size:0.88rem; text-align:center; margin-bottom:1rem;">
                Lenh gui truc tiep toi Mach 2 (IOT_2) qua mang LAN noi bo.
            </p>
            <div class="btn-row">
                <button class="btn btn-blue"   onclick="gate('/open_gate')">&#128275; Mo (Tu Dong Dong Sau 3s)</button>
                <button class="btn btn-yellow" onclick="gate('/open_gate_manual')">&#9728; Mo Mai Mai (Khong Tu Dong)</button>
                <button class="btn btn-red"    onclick="gate('/close_gate')">&#128683; Dong Cong Khan Cap</button>
            </div>
        </div>

    </div><!-- end .wrap -->

    <div id="_toast"></div>

<script>
    // ===================== TOAST =====================
    function toast(msg, dur=3000) {{
        const t = document.getElementById('_toast');
        t.innerText = msg; t.style.opacity = '1';
        setTimeout(() => t.style.opacity = '0', dur);
    }}

    // ===================== SETTINGS =====================
    // IP tinh co dinh - khong can chinh trong web
    const IOT2_IP = '192.168.137.199';

    // ===================== GATE CONTROL =====================
    function gate(path) {{
        toast('Dang gui lenh...');
        fetch('http://' + IOT2_IP + path)
            .then(r=>r.text())
            .then(txt=>toast('✅ ' + txt))
            .catch(()=>toast('❌ Khong ket noi duoc Mach 2 (' + IOT2_IP + ')!'));
    }}

    // ===================== CAPTURE ONLY =====================
    function doCapture() {{
        const el  = document.getElementById('ocr_result');
        const btn = document.getElementById('btn_capture');
        el.style.color = '#fbbf24';
        el.innerText = '📷 Dang chup anh tu ESP32-CAM...';
        btn.disabled = true;
        fetch('/capture_only').then(r=>r.json()).then(d=>{{
            btn.disabled = false;
            if (d.success) {{
                el.style.color = '#10b981';
                el.innerText = '✅ Chup anh thanh cong!';
                document.getElementById('cam_view').src = '/violations/latest_capture.jpg?t=' + Date.now();
            }} else {{
                el.style.color = '#ef4444';
                el.innerText = '❌ ' + d.error;
            }}
        }}).catch(()=>{{ btn.disabled=false; el.style.color='#ef4444'; el.innerText='❌ Loi ket noi server!'; }});
    }}

    // ===================== OCR =====================
    function doOCR() {{
        const el  = document.getElementById('ocr_result');
        const btn = document.getElementById('btn_ocr');
        el.style.color = '#fbbf24';
        el.innerText = '🔍 Dang chup & nhan dien bien so...';
        btn.disabled = true;
        fetch('/test_ocr').then(r=>r.json()).then(d=>{{
            btn.disabled = false;
            if (d.success) {{
                el.style.color = '#10b981';
                el.innerText = '✅ Bien so: ' + d.plate + '  (' + d.time + 's)';
                document.getElementById('cam_view').src = '/violations/latest_capture.jpg?t=' + Date.now();
            }} else {{
                el.style.color = '#ef4444';
                el.innerText = '❌ ' + d.error;
            }}
        }}).catch(()=>{{ btn.disabled=false; el.style.color='#ef4444'; el.innerText='❌ Loi ket noi server!'; }});
    }}

    // ===================== LIVE UPDATE =====================
    let lastCaptureTs = 0;
    let lastVioTs     = null;

    function updateStats() {{
        fetch('/get_stats').then(r=>r.json()).then(d=>{{
            // AI status
            const bar = document.getElementById('ai_status_bar');
            if (d.ai_ready) {{
                bar.className = 'ready';
                bar.innerText = '✅ EasyOCR San sang - Nhan dien Offline 100%!';
            }} else {{
                bar.className = '';
                bar.innerText = '⏳ AI dang khoi dong... (Vui long doi ~1 phut)';
            }}

            // Anh moi nhat
            if (d.last_capture_ts && d.last_capture_ts !== lastCaptureTs) {{
                lastCaptureTs = d.last_capture_ts;
                document.getElementById('cam_view').src = '/violations/latest_capture.jpg?t=' + Date.now();
            }}

            // Ket qua nhan dien
            if (d.last_violation && d.last_violation.ts !== lastVioTs) {{
                lastVioTs = d.last_violation.ts;
                const v = d.last_violation;
                document.getElementById('plate_display').innerText   = v.plate || '---';
                document.getElementById('payment_status').innerText  = v.status || '---';
                document.getElementById('proc_time').innerText       = (v.proc_time || '---') + 's';
                document.getElementById('result_ts').innerText       = 'Luc: ' + (v.ts || '');

                const img = document.getElementById('result_img');
                const ph  = document.getElementById('result_placeholder');
                if (v.image && v.image !== 'no_image.jpg') {{
                    img.src = '/violations/' + v.image + '?t=' + Date.now();
                    img.style.display = 'block'; ph.style.display = 'none';
                }} else {{
                    img.style.display = 'none'; ph.style.display = 'flex';
                }}
            }}
        }}).catch(()=>{{}});
    }}

    setInterval(updateStats, 2000);
    updateStats();
</script>
</body>
</html>"""
