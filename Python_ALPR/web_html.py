import json

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
    .cam-badge {{ position: absolute; bottom: 10px; right: 10px; background: rgba(0,0,0,0.6);
            color: #38bdf8; padding: 4px 10px; border-radius: 20px; font-size: 0.8rem; }}
    
    /* === ROI BOX === */
    .roi-box {{ position: absolute; border: 2px dashed #00d2ff; background: rgba(0, 210, 255, 0.15); cursor: move; }}
    .resize-handle {{ position: absolute; right: -5px; bottom: -5px; width: 12px; height: 12px; background: #ef4444; cursor: nwse-resize; border-radius: 50%; border: 2px solid white; z-index: 10; }}
    .stranger-checkbox {{ width: 20px; height: 20px; cursor: pointer; accent-color: #ef4444; }}
    /* === WIDGET CAU HINH === */
    .config-widget {{ display: none; margin-top: 1rem; padding: 1rem; background: #1e293b; border-radius: 8px; border: 1px solid #334155; }}
    .config-widget.active {{ display: block; }}
    .gear-btn {{ cursor: pointer; float: right; font-size: 1.2rem; color: #94a3b8; transition: 0.3s; }}
    .gear-btn:hover {{ color: #38bdf8; transform: rotate(90deg); }}

    /* === FORM === */
    .form-row {{ display: flex; align-items: center; gap: 10px; margin-bottom: 0.9rem; }}
    .form-row label {{ min-width: 140px; font-size: 0.88rem; color: #94a3b8; text-align: right; }}
    input[type=text] {{ flex: 1; background: rgba(0,0,0,0.4); border: 1px solid var(--border);
              color: #f1f5f9; padding: 9px 13px; border-radius: 8px;
              font-family: 'Inter',sans-serif; font-size: 0.9rem; transition: border-color 0.2s; }}
    input:focus {{ outline: none; border-color: var(--primary); }}


    /* === TABS === */
    .tab-container {{ display: flex; gap: 10px; justify-content: center; margin-bottom: 20px; }}
    .tab-btn {{ padding: 12px 24px; border: none; background: #1e293b; color: #94a3b8; cursor: pointer; border-radius: 8px; font-weight: bold; font-size: 1rem; transition: 0.3s; }}
    .tab-btn.active {{ background: #3b82f6; color: white; box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4); }}
    .tab-btn:hover:not(.active) {{ background: #334155; color: white; }}
    
    /* === STRANGER ITEM === */
    .stranger-item {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 15px; margin-bottom: 15px; display: flex; align-items: center; gap: 20px; }}
    .stranger-img {{ width: 120px; height: 120px; object-fit: cover; border-radius: 8px; border: 2px solid #475569; }}
    .stranger-info {{ flex: 1; }}
    .stranger-actions {{ display: flex; gap: 10px; }}
    
    .badge-count {{ background: #ef4444; color: white; border-radius: 50%; padding: 2px 8px; font-size: 0.8rem; margin-left: 8px; vertical-align: top; display: none; }}
    .btn-logout {{ background: linear-gradient(135deg, #64748b, #475569); color: white; }}
    /* === BUTTONS === */
    .btn {{ padding: 10px 20px; border: none; border-radius: 9px; cursor: pointer;
        font-weight: 700; font-size: 0.9rem; font-family: 'Inter',sans-serif;
        transition: all 0.2s; letter-spacing: 0.02em; }}
    .btn:hover {{ transform: translateY(-2px); filter: brightness(1.15); box-shadow: 0 4px 20px rgba(0,210,255,0.25); }}
    .btn:disabled {{ opacity: 0.5; cursor: not-allowed; transform: none; }}
    .btn-blue  {{ background: linear-gradient(135deg, #3a7bd5, #00d2ff); color: #fff; }}
    .btn-green {{ background: linear-gradient(135deg, #059669, #10b981); color: #fff; }}
    .btn-yellow {{ background: linear-gradient(135deg, #f59e0b, #fbbf24); color: #000; }}
    .btn-red  {{ background: linear-gradient(135deg, #dc2626, #ef4444); color: #fff; }}
    .btn-row  {{ display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; margin-top: 1rem; }}

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
    <h1> TRAM THU PHI VETC</h1>
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <p>EasyOCR Offline &nbsp;|&nbsp; IP Webcam &nbsp;|&nbsp; LAN HTTP</p>
      <button class="btn btn-logout" onclick="logout()" style="padding: 5px 15px; font-size: 0.8rem;">Đăng Xuất</button>
    </div>
  </header>

  <div id="ai_status_bar">AI dang khoi dong... Vui long doi!</div>

  <div class="wrap">


    <!-- TABS NAV -->
    <div class="tab-container">
      <button class="tab-btn active" id="btn_tab_system" onclick="switchTab('system')">Trạm Thu Phí</button>
      <button class="tab-btn" id="btn_tab_stranger" onclick="switchTab('stranger')">Xe Khách Lạ <span class="badge-count" id="stranger_badge">0</span></button>
      <button class="tab-btn" id="btn_tab_history" onclick="switchTab('history')">Lịch Sử Nhận Diện</button>
      <button class="tab-btn" id="btn_tab_offline" onclick="switchTab('offline')">Hàng Đợi CSV</button>
    </div>

    <!-- TAB: SYSTEM -->
    <div id="tab_system">
    <!-- KET QUA NHAN DIEN -->
    <div class="card">
      <div class="card-title">
        <span> Ket qua nhan dien bien so gan nhat</span>
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

    <!-- CAMERA IP WEBCAM -->
    <div class="cam-center-grid">
      <div class="card">
        <div class="card-title">
          &#128241; Camera IP Webcam (Dien Thoai)
          <span class="gear-btn" onclick="toggleConfig()" title="Cau hinh URL">[Cài Đặt]</span>
        </div>
        <div class="cam-wrap" id="cam_container">
          <img id="cam_view" src="/captures/latest_capture.jpg"
             alt="Chua co anh" onerror="this.style.opacity='0.2'">
          <div class="cam-badge">ANH GAN NHAT</div>
          <!-- VÙNG CHỌN ROI (Region of Interest) -->
          <div id="roi_box" class="roi-box" title="Kéo để di chuyển, nắm góc đỏ để phóng to thu nhỏ">
             <div class="resize-handle" id="roi_resize" title="Kéo để thay đổi kích thước"></div>
          </div>
        </div>
        
        <!-- WIDGET CAU HINH (An mac dinh) -->
        <div id="config_panel" class="config-widget">
          <div style="display: flex; flex-direction: column; gap: 10px;">
            <div>
              <label style="color: #94a3b8; font-size: 0.9rem;">Chế độ AI (Nhận diện):</label>
              <select id="ai_mode" style="width:100%; padding: 8px; border-radius: 4px; border: 1px solid #475569; background: #0f172a; color: white; margin-top: 5px;">
                <option value="gemini" { 'selected' if controller.config.get('ai_mode', 'gemini') == 'gemini' else '' }>Google Gemini 3.5 Flash (Thế hệ mới nhất, Cần Mạng)</option>
                <option value="easyocr" { 'selected' if controller.config.get('ai_mode', '') == 'easyocr' else '' }>EasyOCR (Nhanh vừa, Kém chuẩn hơn, 100% Offline)</option>
              </select>
            </div>
            <div>
              <label style="color: #94a3b8; font-size: 0.9rem;">Google Gemini API Key:</label>
              <input type="password" id="gemini_api_key" style="width:100%; padding: 8px; border-radius: 4px; border: 1px solid #475569; background: #0f172a; color: white; box-sizing:border-box; margin-top: 5px;"
                  value="{controller.config.get('gemini_api_key', '')}" placeholder="AIzaSy...">
            </div>
            <div>
              <label style="color: #94a3b8; font-size: 0.9rem;">URL IP Webcam (Điện thoại):</label>
              <input type="text" id="cam_url" style="width:100%; padding: 8px; border-radius: 4px; border: 1px solid #475569; background: #0f172a; color: white; box-sizing:border-box; margin-top: 5px;"
                  value="{controller.config.get('ip_camera_url', 'http://192.168.1.xxx:8080/shot.jpg')}" placeholder="Vd: http://192.168.1.100:8080">
            </div>
            <div>
              <label style="color: #94a3b8; font-size: 0.9rem;">IP Mạch 2 ESP32 (Điều khiển cổng & LCD):</label>
              <input type="text" id="iot2_ip" style="width:100%; padding: 8px; border-radius: 4px; border: 1px solid #475569; background: #0f172a; color: white; box-sizing:border-box; margin-top: 5px;"
                  value="{controller.config.get('iot2_ip', '192.168.137.199')}" placeholder="Vd: 192.168.1.199">
            </div>
            <div>
              <label style="color: #94a3b8; font-size: 0.9rem;">Telegram Bot Token:</label>
              <input type="password" id="telegram_token" style="width:100%; padding: 8px; border-radius: 4px; border: 1px solid #475569; background: #0f172a; color: white; box-sizing:border-box; margin-top: 5px;"
                  value="{controller.config.get('telegram_token', '')}" placeholder="Bot Token từ BotFather...">
            </div>
            <div>
              <label style="color: #94a3b8; font-size: 0.9rem;">MongoDB URI:</label>
              <input type="password" id="mongo_uri" style="width:100%; padding: 8px; border-radius: 4px; border: 1px solid #475569; background: #0f172a; color: white; box-sizing:border-box; margin-top: 5px;"
                  value="{controller.config.get('mongo_uri', '')}" placeholder="mongodb+srv://...">
            </div>
            <div>
              <label style="color: #94a3b8; font-size: 0.9rem;">Firebase RTDB URL:</label>
              <input type="password" id="firebase_url" style="width:100%; padding: 8px; border-radius: 4px; border: 1px solid #475569; background: #0f172a; color: white; box-sizing:border-box; margin-top: 5px;"
                  value="{controller.config.get('firebase_url', '')}" placeholder="https://your-project.firebaseio.com/">
            </div>
            <div style="display: flex; align-items: center; gap: 10px; margin-top: 5px;">
              <input type="checkbox" id="enable_firebase" { 'checked' if controller.config.get('enable_firebase', True) else '' }>
              <label for="enable_firebase" style="color: white; font-size: 0.9rem;">Bật đẩy dữ liệu lên Firebase</label>
            </div>
            <div style="display: flex; align-items: center; gap: 10px; margin-top: 5px;">
              <input type="checkbox" id="enable_telegram" { 'checked' if controller.config.get('enable_telegram', True) else '' }>
              <label for="enable_telegram" style="color: white; font-size: 0.9rem;">Bật quét MongoDB & báo Telegram</label>
            </div>
            <button class="btn btn-green" style="width: 100%; margin-top: 10px;" onclick="saveSettings()">Lưu Cài Đặt</button><a href="/history/action_logs.csv" target="_blank" class="btn btn-blue" style="width:100%; display:block; text-align:center; text-decoration:none; margin-top:10px;">Tải xuống File Nhật Ký (Log)</a>
            <div id="save_msg" style="text-align:center; color:#10b981; font-weight:bold;"></div>
          </div>
        </div>

        <div class="btn-row" style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid var(--border);">
          <button class="btn btn-blue" id="btn_capture" onclick="doCapture()">
             Chup Anh
          </button>
          <button class="btn btn-green" id="btn_ocr" onclick="doOCR()">
             Chup &amp; Nhan Dien
          </button>
          <button class="btn btn-red" id="btn_abort" onclick="abortOCR()" style="display:none;">
             Huy Nhận Diện
          </button>
        </div>
        <div id="ocr_result"></div>
      </div>
    </div>

    <!-- DIEU KHIEN CONG -->
    <div class="card">
      <div class="card-title"> Dieu khien cong thu cong (LAN)</div>
      <p style="color:#64748b; font-size:0.88rem; text-align:center; margin-bottom:1rem;">
        Lenh gui truc tiep toi Mach 2 (IOT_2) qua mang LAN noi bo.
      </p>
      <div class="btn-row">
        <button class="btn btn-blue"  onclick="gate('/open_gate')"> Mo (Tu Dong Dong Sau 3s)</button>
        <button class="btn btn-yellow" onclick="gate('/open_gate_manual')"> Mo Mai Mai (Khong Tu Dong)</button>
        <button class="btn btn-red"  onclick="gate('/close_gate')"> Dong Cong Khan Cap</button>
      </div>
    </div>


    </div><!-- end #tab_system -->

    <!-- TAB: STRANGERS -->
    <div id="tab_stranger" style="display: none;">
      <div class="card">
        <div class="card-title"> Xử Lý Xe Lạ</div>
        <p style="color:#64748b; font-size:0.88rem; text-align:center; margin-bottom:1rem;">
          Các xe chưa có trong hệ thống. Bạn có thể duyệt thêm hoặc đưa vào cảnh báo.
        </p>
        <div style="text-align: right; margin-bottom: 10px; display: flex; justify-content: flex-end; gap: 10px;">
          <button class="btn btn-logout" onclick="deleteSelected()"> Xóa Đã Chọn</button>
          <button class="btn btn-blue" onclick="loadStrangers()"> Làm Mới</button>
        </div>
        <div id="stranger_list">
          <p style="text-align:center; color:#64748b;">Đang tải dữ liệu...</p>
        </div>
      </div>
    </div>

    <!-- TAB: OFFLINE QUEUE -->
    <div id="tab_offline" style="display: none;">
      <div class="card">
        <div class="card-title"> Hàng Đợi Offline (Đang chờ Đồng bộ lên Cloud)</div>
        <p style="color:#64748b; font-size:0.88rem; text-align:center; margin-bottom:1rem;">
          Danh sách các xe được lưu tạm ở dưới ổ cứng (file CSV) vì đường truyền mạng đang gặp sự cố. Hệ thống sẽ tự động đẩy lên Cloud khi mạng ổn định. Các xe ĐÃ ĐỒNG BỘ lên Cloud sẽ biến mất khỏi danh sách này.
        </p>
        <div style="text-align: right; margin-bottom: 10px;">
          <button class="btn btn-yellow" onclick="loadOfflineQueue()" style="color:#0f172a; font-weight:bold;"> Tải lại</button>
        </div>
        <div id="offline_list">
          <p style="text-align:center; color:#64748b;">Đang tải...</p>
        </div>
      </div>
    </div>
    
    <!-- TAB: HISTORY -->
    <div id="tab_history" style="display: none;">
      <div class="card">
        <div class="card-title"> Lịch Sử Giao Thông (Từ Đám Mây)</div>
        <p style="color:#64748b; font-size:0.88rem; text-align:center; margin-bottom:1rem;">
          Hiển thị 50 lượt xe đi qua gần nhất (Đọc từ Cloud Database).
        </p>
        <div style="text-align: right; margin-bottom: 10px;">
          <button class="btn btn-blue" onclick="loadHistory()"> Làm Mới Lịch Sử</button>
        </div>
        <div id="history_list">
          <p style="text-align:center; color:#64748b;">Đang tải dữ liệu lịch sử...</p>
        </div>
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


  // ===================== ROI LOGIC =====================
  const roiBox = document.getElementById('roi_box');
  const roiResize = document.getElementById('roi_resize');
  const camWrap = document.getElementById('cam_container');
  let isDragging = false, isResizing = false;
  let startX, startY, startLeft, startTop, startW, startH;
  const initRoiStr = '{json.dumps(controller.config.get("roi", {"x":0.2, "y":0.4, "w":0.4, "h":0.3}))}';
  let roiData = JSON.parse(initRoiStr.replace(/'/g, '"'));
  
  function applyRoiStyles() {{
    roiBox.style.left = (roiData.x * 100) + '%';
    roiBox.style.top = (roiData.y * 100) + '%';
    roiBox.style.width = (roiData.w * 100) + '%';
    roiBox.style.height = (roiData.h * 100) + '%';
  }}
  applyRoiStyles();

  // Resize Handle Events
  roiResize.addEventListener('mousedown', function(e) {{
    e.stopPropagation();
    isResizing = true; startX = e.clientX; startY = e.clientY;
    startW = roiBox.offsetWidth; startH = roiBox.offsetHeight;
  }});

  // Drag Events
  roiBox.addEventListener('mousedown', function(e) {{
    isDragging = true; startX = e.clientX; startY = e.clientY;
    startLeft = roiBox.offsetLeft; startTop = roiBox.offsetTop;
  }});

  document.addEventListener('mousemove', function(e) {{
    if (isResizing) {{
      let newW = Math.max(20, Math.min(startW + e.clientX - startX, camWrap.clientWidth - roiBox.offsetLeft));
      let newH = Math.max(20, Math.min(startH + e.clientY - startY, camWrap.clientHeight - roiBox.offsetTop));
      roiBox.style.width = newW + 'px'; roiBox.style.height = newH + 'px';
    }} else if (isDragging) {{
      let newLeft = Math.max(0, Math.min(startLeft + e.clientX - startX, camWrap.clientWidth - roiBox.offsetWidth));
      let newTop = Math.max(0, Math.min(startTop + e.clientY - startY, camWrap.clientHeight - roiBox.offsetHeight));
      roiBox.style.left = newLeft + 'px'; roiBox.style.top = newTop + 'px';
    }}
  }});

  document.addEventListener('mouseup', function() {{
    if (isDragging || isResizing) {{
      isDragging = false; isResizing = false; saveRoi();
    }}
  }});

  function saveRoi() {{
    roiData = {{ x: roiBox.offsetLeft / camWrap.clientWidth, y: roiBox.offsetTop / camWrap.clientHeight, w: roiBox.offsetWidth / camWrap.clientWidth, h: roiBox.offsetHeight / camWrap.clientHeight }};
    fetch('/set_settings', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{ "roi": roiData }}) }});
  }}

  // ===================== SETTINGS =====================
  function toggleConfig() {{
    const panel = document.getElementById('config_panel');
    panel.classList.toggle('active');
  }}

  function saveSettings() {{
    const url = document.getElementById('cam_url').value;
    const iot2_ip = document.getElementById('iot2_ip').value;
    const api_key = document.getElementById('gemini_api_key').value;
    const ai_mode = document.getElementById('ai_mode').value;
    const tele = document.getElementById('telegram_token').value;
    const mongo = document.getElementById('mongo_uri').value;
    const fire = document.getElementById('firebase_url').value;
    const en_fire = document.getElementById('enable_firebase').checked;
    const en_tele = document.getElementById('enable_telegram').checked;
    
    fetch('/set_settings', {{
      method:'POST', headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{ 
        "url": url,
        "iot2_ip": iot2_ip,
        "gemini_api_key": api_key,
        "ai_mode": ai_mode,
        "telegram_token": tele,
        "mongo_uri": mongo,
        "firebase_url": fire,
        "enable_firebase": en_fire,
        "enable_telegram": en_tele
      }})
    }}).then(r=>r.json()).then(d=>{{
      document.getElementById('save_msg').innerText = d.success ? ' Đã lưu Cài đặt!' : ' Lỗi lưu!';
      setTimeout(()=>document.getElementById('save_msg').innerText='', 3000);
    }}).catch(e => {{
      console.error(e);
      document.getElementById('save_msg').innerText = ' Lỗi Mạng/Server!';
      setTimeout(()=>document.getElementById('save_msg').innerText='', 3000);
    }});
  }}
  // ===================== GATE CONTROL =====================
  function gate(path) {{
    toast('Đang gửi lệnh điều khiển cổng...');
    fetch(path)
      .then(r=>r.json())
      .then(d=>{{
        if (d.success) toast(' Đã gửi lệnh cổng thành công!');
        else toast(' Lỗi: ' + (d.error || 'Không gửi được lệnh'));
      }})
      .catch(()=>toast(' Lỗi kết nối server!'));
  }}

  // ===================== CAPTURE ONLY =====================
  function doCapture() {{
    const el = document.getElementById('ocr_result');
    const btn = document.getElementById('btn_capture');
    if (el) {{
      el.style.color = '#fbbf24';
      el.innerText = ' Dang chup anh từ IP Camera...';
    }}
    if (btn) btn.disabled = true;
    toast('Đang kết nối camera để chụp ảnh...');
    
    fetch('/capture_only').then(r=>r.json()).then(d=>{{
      if (btn) btn.disabled = false;
      if (d.success) {{
        if (el) {{
          el.style.color = '#10b981';
          el.innerText = ' Chụp ảnh thành công!';
        }}
        toast('Chụp ảnh thành công!');
        const camView = document.getElementById('cam_view');
        if (camView) {{
          camView.src = '/captures/latest_capture.jpg?t=' + Date.now();
          camView.style.opacity = '1';
        }}
      }} else {{
        if (el) {{
          el.style.color = '#ef4444';
          el.innerText = ' ' + d.error;
        }}
        toast('Lỗi camera: ' + d.error);
      }}
    }}).catch(err=>{{
      if (btn) btn.disabled = false;
      if (el) {{
        el.style.color='#ef4444';
        el.innerText=' Lỗi kết nối server!';
      }}
      toast('Lỗi kết nối server!');
    }});
  }}

  // ===================== OCR =====================
  let ocrController = null;

  function abortOCR() {{
    if (ocrController) {{
      ocrController.abort();
      ocrController = null;
    }}
    const el = document.getElementById('ocr_result');
    if (el) {{
      el.innerText = ' Đã hủy nhận diện!';
      el.style.color = '#ef4444'; 
    }}
    
    const btnOcr = document.getElementById('btn_ocr');
    const btnAbort = document.getElementById('btn_abort');
    if (btnOcr) {{
      btnOcr.disabled = false;
      btnOcr.style.display = 'inline-block';
    }}
    if (btnAbort) btnAbort.style.display = 'none';
    toast('Đã hủy tiến trình AI');
  }}

  function doOCR() {{
    const el = document.getElementById('ocr_result');
    const btn = document.getElementById('btn_ocr');
    if (el) {{
      el.style.color = '#fbbf24';
      el.innerText = ' Dang chup anh...';
    }}
    if (btn) btn.disabled = true;
    toast('Đang chụp ảnh & nhận diện AI...');
    
    fetch('/capture_only').then(r=>r.json()).then(d=>{{
      if (d.success) {{
        const camView = document.getElementById('cam_view');
        if (camView) {{
          camView.src = '/captures/latest_capture.jpg?t=' + Date.now();
          camView.style.opacity = '1';
        }}
        
        if (el) el.innerText = ' Đã chụp. Đang nhận diện biển số... (Vui lòng đợi)';
        const btnAbort = document.getElementById('btn_abort');
        if (btn) btn.style.display = 'none';
        if (btnAbort) btnAbort.style.display = 'inline-block';
        
        ocrController = new AbortController();
        fetch('/process_latest', {{ signal: ocrController.signal }}).then(r2=>r2.json()).then(d2=>{{
          if (btn) {{
            btn.disabled = false;
            btn.style.display = 'inline-block';
          }}
          if (btnAbort) btnAbort.style.display = 'none';
          if (d2.success) {{
            if (el) {{
              el.style.color = '#10b981';
              el.innerText = ' Biển số: ' + d2.plate + ' (' + d2.time + 's)';
            }}
            toast('Nhận diện thành công: ' + d2.plate);
          }} else {{
            if (el) {{
              el.style.color = '#ef4444';
              el.innerText = ' ' + d2.error;
            }}
            toast('Lỗi: ' + d2.error);
          }}
        }}).catch(e=>{{ 
          if (btn) {{
            btn.disabled = false;
            btn.style.display = 'inline-block';
          }}
          if (btnAbort) btnAbort.style.display = 'none';
          if (e.name !== 'AbortError') {{
            if (el) {{
              el.style.color='#ef4444';
              el.innerText=' Lỗi kết nối AI!';
            }}
            toast('Lỗi kết nối AI!');
          }}
        }});
        el.style.color = '#ef4444';
        el.innerText = ' ' + d.error;
      }}
    }}).catch(()=>{{ btn.disabled=false; el.style.color='#ef4444'; el.innerText=' Loi ket noi chup anh!'; }});
  }}

  // ===================== LIVE UPDATE =====================
  let lastCaptureTs = 0;
  let lastVioTs   = null;

  function updateStats() {{
    fetch('/get_stats').then(r=>r.json()).then(d=>{{
      // AI status
      const bar = document.getElementById('ai_status_bar');
      if (d.ai_ready) {{
        bar.className = 'ready';
        bar.innerText = ' EasyOCR San sang - Nhan dien Offline 100%!';
      }} else {{
        bar.className = '';
        bar.innerText = ' AI dang khoi dong... (Vui long doi ~1 phut)';
      }}

      // Anh moi nhat
      if (d.last_capture_ts && d.last_capture_ts !== lastCaptureTs) {{
        lastCaptureTs = d.last_capture_ts;
        document.getElementById('cam_view').src = '/captures/latest_capture.jpg?t=' + Date.now();
        document.getElementById('cam_view').style.opacity = '1';
      }}

      // Ket qua nhan dien
      if (d.last_violation && d.last_violation.ts !== lastVioTs) {{
        lastVioTs = d.last_violation.ts;
        const v = d.last_violation;
        document.getElementById('plate_display').innerText  = v.plate || '---';
        document.getElementById('payment_status').innerText = v.status || '---';
        document.getElementById('proc_time').innerText    = (v.proc_time || '---') + 's';
        document.getElementById('result_ts').innerText    = 'Luc: ' + (v.ts || '');

        const img = document.getElementById('result_img');
        const ph = document.getElementById('result_placeholder');
        if (v.image && v.image !== 'no_image.jpg') {{
          img.src = '/captures/' + v.image + '?t=' + Date.now();
          img.style.display = 'block'; ph.style.display = 'none';
        }} else {{
          img.style.display = 'none'; ph.style.display = 'flex';
        }}
      }}
    }}).catch(()=>{{}});
  }}

  setInterval(updateStats, 2000);
  updateStats();

  function logout() {{
    fetch('/logout', {{method: 'POST'}}).then(()=> window.location.reload);
  }}
  // TABS LOGIC
  function switchTab(tabId) {{
    const tabs = ['system', 'stranger', 'history', 'offline'];
    tabs.forEach(t => {{
      const el = document.getElementById('tab_' + t);
      const btn = document.getElementById('btn_tab_' + t);
      if(el) el.style.display = (t === tabId) ? 'block' : 'none';
      if(btn) btn.className = (t === tabId) ? 'tab-btn active' : 'tab-btn';
    }});
    if (tabId === 'stranger') loadStrangers();
    if (tabId === 'offline') loadOfflineQueue();
    if (tabId === 'history') loadHistory();
  }}
  
  
  // ===================== OFFLINE QUEUE LOGIC =====================
  function loadOfflineQueue() {{
    document.getElementById('offline_list').innerHTML = '<p style="text-align:center; color:#64748b;">Đang đọc file CSV...</p>';
    fetch('/api/offline_queue').then(r=>r.json()).then(d => {{
      if(!d.success) {{
        document.getElementById('offline_list').innerHTML = `<p style="color:#ef4444;">Lỗi: ${{d.error}}</p>`;
        return;
      }}
      const data = d.data;
      if(data.length === 0) {{
        document.getElementById('offline_list').innerHTML = '<p style="text-align:center; color:#10b981;">Tất cả dữ liệu đã được đồng bộ 100% lên Đám Mây!</p>';
        document.getElementById('offline_badge').style.display = 'none';
        return;
      }}
      
      let html = '<div style="background:#0f172a; border:1px solid #334155; border-radius:8px; overflow:hidden;">';
      html += '<div style="display:flex; padding:10px; background:#1e293b; font-weight:bold; border-bottom:1px solid #334155;">';
      html += '<div style="width:30%">Thời gian</div><div style="width:30%">Biển số</div><div style="width:40%">Tên File Ảnh</div></div>';
      
      data.forEach(item => {{
        let timeStr = new Date(parseInt(item.timestamp)).toLocaleString('vi-VN');
        html += `<div style="display:flex; padding:10px; border-bottom:1px solid #1e293b;">`;
        html += `<div style="width:30%; font-size:0.85rem; color:#94a3b8;">${{timeStr}}</div>`;
        html += `<div style="width:30%; font-weight:bold; color:#00d2ff;">${{item.plate}}</div>`;
        html += `<div style="width:40%; font-size:0.8rem; color:#64748b; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${{item.image_path}}">${{item.image_path.split(/\\\\|\\//).pop()}}</div>`;
        html += `</div>`;
      }});
      html += '</div>';
      document.getElementById('offline_list').innerHTML = html;
    }}).catch(e => {{
      document.getElementById('offline_list').innerHTML = '<p style="color:#ef4444;">Không thể đọc file CSV</p>';
    }});
  }}

  // ===================== HISTORY LOGIC =====================
  function loadHistory() {{
    document.getElementById('history_list').innerHTML = '<p style="text-align:center; color:#64748b;">Đang kéo dữ liệu từ Đám mây...</p>';
    fetch('/api/history').then(r=>r.json()).then(d => {{
      if(!d.success) {{
        document.getElementById('history_list').innerHTML = `<p style="color:#ef4444;">Lỗi: ${{d.error}}</p>`;
        return;
      }}
      const data = d.data;
      if(data.length === 0) {{
        document.getElementById('history_list').innerHTML = '<p style="text-align:center; color:#10b981;">Chưa có lịch sử xe qua trạm.</p>';
        return;
      }}
      
      let html = '<div style="background:#0f172a; border:1px solid #334155; border-radius:8px; overflow:hidden;">';
      html += '<div style="display:flex; padding:10px; background:#1e293b; font-weight:bold; border-bottom:1px solid #334155;">';
      html += '<div style="width:15%">Ảnh</div><div style="width:30%">Thời gian</div><div style="width:30%">Biển số</div><div style="width:25%">Loại xe</div></div>';
      
      data.forEach(item => {{
        let timeStr = new Date(parseInt(item.timestamp)).toLocaleString('vi-VN');
        let imgTag = `<img src="data:image/jpeg;base64,${{item.image_base64}}" style="width:55px; height:45px; object-fit:cover; border-radius:4px;">`;
        if(!item.image_base64) imgTag = `<span style="color:#64748b; font-size:0.75rem;">(No image)</span>`;
        
        let typeColor = '#64748b', typeLabel = 'Không rõ';
        if(item.vehicle_type === 'known')    {{ typeColor = '#10b981'; typeLabel = 'Xe Quen'; }}
        if(item.vehicle_type === 'stranger') {{ typeColor = '#f59e0b'; typeLabel = 'Xe Lạ'; }}
        if(item.vehicle_type === 'warning')  {{ typeColor = '#ef4444'; typeLabel = 'CANH BAO'; }}
        
        html += `<div style="display:flex; align-items:center; padding:10px; border-bottom:1px solid #1e293b;">`;
        html += `<div style="width:15%;">${{imgTag}}</div>`;
        html += `<div style="width:30%; font-size:0.82rem; color:#94a3b8;">${{timeStr}}</div>`;
        html += `<div style="width:30%; font-size:1rem; color:#fff; font-weight:bold; letter-spacing:0.08em;">${{item.plate}}</div>`;
        html += `<div style="width:25%;"><span style="background:${{typeColor}}22; color:${{typeColor}}; border:1px solid ${{typeColor}}; border-radius:20px; padding:3px 10px; font-size:0.78rem; font-weight:bold;">${{typeLabel}}</span></div>`;
        html += `</div>`;
      }});
      html += '</div>';
      document.getElementById('history_list').innerHTML = html;
    }}).catch(e => {{
      document.getElementById('history_list').innerHTML = '<p style="color:#ef4444;">Không thể kết nối Server để lấy Lịch Sử</p>';
    }});
  }}

  // STRANGERS LOGIC
  function loadStrangers() {{
    document.getElementById('stranger_list').innerHTML = '<p style="text-align:center; color:#64748b;">Đang tải...</p>';
    fetch('/api/strangers').then(r=>r.json()).then(data => {{
      if(data.error) {{
        document.getElementById('stranger_list').innerHTML = `<p style="color:#ef4444;">Lỗi: ${{data.error}}</p>`;
        return;
      }}
      let html = '';
      let count = 0;
      for(let key in data) {{
        count++;
        let item = data[key];
        let timeStr = new Date(item.timestamp).toLocaleString('vi-VN');
        html += `
        <div class="stranger-item" id="stranger_item_${{key}}">
          <input type="checkbox" class="stranger-checkbox" value="${{key}}">
          <img src="data:image/jpeg;base64,${{item.image_base64}}" class="stranger-img">
          <div class="stranger-info">
            <div style="margin-bottom: 8px;">
              <span style="color:#e2e8f0; font-size:0.9rem;">Sửa biển:</span>
              <input type="text" id="plate_input_${{key}}" value="${{item.plate}}" style="background:#0f172a; color:#fff; border:1px solid #334155; padding:5px; border-radius:4px; font-weight:bold; font-size:1.1rem; width:120px; text-transform:uppercase;">
            </div>
            <div style="font-size:0.8rem; color:#94a3b8;">Thời gian: ${{timeStr}}</div>
          </div>
          <div class="stranger-actions" style="flex-wrap: wrap;">
            <button class="btn" style="background:#3b82f6;" onclick="recheckStranger('${{key}}')"> Kiểm Tra</button>
            <button class="btn btn-green" onclick="handleStranger('${{key}}', document.getElementById('plate_input_${{key}}').value, 'approve')">Duyệt Quen</button>
            <button class="btn btn-red" onclick="handleStranger('${{key}}', document.getElementById('plate_input_${{key}}').value, 'warn')">Cảnh Báo</button>
            <button class="btn btn-logout" onclick="handleStranger('${{key}}', document.getElementById('plate_input_${{key}}').value, 'delete')">Xóa Bỏ</button>
          </div>
        </div>`;
      }}
      if(count === 0) html = '<p style="text-align:center; color:#10b981;">Tuyệt vời! Không có xe lạ nào tồn đọng.</p>';
      document.getElementById('stranger_list').innerHTML = html;
      
      // Update badge
      let badge = document.getElementById('stranger_badge');
      badge.innerText = count;
      badge.style.display = count> 0 ? 'inline-block' : 'none';
    }}).catch(e => {{
      document.getElementById('stranger_list').innerHTML = '<p style="color:#ef4444;">Không thể kết nối Server</p>';
    }});
  }}
  
  function handleStranger(key, plate, action) {{
    if(action === 'delete' && !confirm("Bạn chắc chắn muốn xóa dữ liệu xe này?")) return;
    if(action === 'warn' && !confirm(`Bạn có chắc muốn ĐƯA BIỂN SỐ ${{plate}} VÀO SỔ ĐEN CẢNH BÁO?`)) return;
    
    fetch('/api/stranger/action', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{ key: key, plate: plate, action: action }})
    }}).then(r=>r.json()).then(d => {{
      if(d.success) {{
        const el = document.getElementById('stranger_item_' + key);
        if(el) el.remove();
        let badge = document.getElementById('stranger_badge');
        if(badge) {{
          let count = parseInt(badge.innerText) || 0;
          if(count> 0) count--;
          badge.innerText = count;
          badge.style.display = count> 0 ? 'inline-block' : 'none';
        }}
        // Neu het sach thi show message
        if(document.querySelectorAll('.stranger-item').length === 0) {{
          document.getElementById('stranger_list').innerHTML = '<p style="text-align:center; color:#10b981;">Tuyệt vời! Không có xe lạ nào tồn đọng.</p>';
        }}
      }}
      else alert("Lỗi: " + d.error);
    }});
  }}

  function recheckStranger(key) {{
    const plate = document.getElementById('plate_input_' + key).value;
    if (!plate) return;
    toast('Đang kiểm tra...');
    fetch('/api/stranger/action', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{ key: key, plate: plate, action: 'recheck' }})
    }}).then(r=>r.json()).then(d=> {{
      if(d.success) {{
        if(d.result === 'known') {{
          alert(' Đã xác nhận đây là xe quen! Hệ thống đã tự động gửi thông báo Telegram cho người dùng.');
          const el = document.getElementById('stranger_item_' + key);
          if(el) el.remove();
          let badge = document.getElementById('stranger_badge');
          if(badge) {{
            let count = parseInt(badge.innerText) || 0;
            if(count> 0) count--;
            badge.innerText = count;
            badge.style.display = count> 0 ? 'inline-block' : 'none';
          }}
        }} else {{
          alert(' Biển số [' + plate + '] vẫn CHƯA CÓ trong hệ thống. Nếu đúng là xe lạ, hãy dùng nút Duyệt Quen mới, Cảnh Báo hoặc Xóa Bỏ!');
        }}
      }} else {{
        alert('Lỗi: ' + d.error);
      }}
    }});
  }}
  
  function deleteSelected() {{
    const checkboxes = document.querySelectorAll('.stranger-checkbox:checked');
    if(checkboxes.length === 0) {{
      alert("Vui lòng chọn ít nhất 1 xe để xóa!");
      return;
    }}
    if(!confirm(`Bạn chắc chắn muốn xóa ${{checkboxes.length}} xe đã chọn?`)) return;
    
    checkboxes.forEach(cb => {{
      const key = cb.value;
      const plate = document.getElementById('plate_input_' + key).value;
      fetch('/api/stranger/action', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{ key: key, plate: plate, action: 'delete' }})
      }}).then(r=>r.json()).then(d => {{
        if(d.success) {{
          const el = document.getElementById('stranger_item_' + key);
          if(el) el.remove();
          let badge = document.getElementById('stranger_badge');
          if(badge) {{
            let count = parseInt(badge.innerText) || 0;
            if(count> 0) count--;
            badge.innerText = count;
            badge.style.display = count> 0 ? 'inline-block' : 'none';
          }}
          if(document.querySelectorAll('.stranger-item').length === 0) {{
            document.getElementById('stranger_list').innerHTML = '<p style="text-align:center; color:#10b981;">Tuyệt vời! Không có xe lạ nào tồn đọng.</p>';
          }}
        }}
      }});
    }});
  }}

  setTimeout(loadStrangers, 3000); // Tu dong load ngam badge

</script>
</body>
</html>"""

def get_login_html(controller):
  return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Đăng Nhập - VETC</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {{ --primary: #00d2ff; --bg: #0f172a; --card: #1e293b; --border: #334155; }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: #f1f5f9; 
        display: flex; align-items: center; justify-content: center; height: 100vh; }}
    .login-box {{ background: var(--card); padding: 40px; border-radius: 12px; 
           border: 1px solid var(--border); box-shadow: 0 10px 30px rgba(0,0,0,0.5);
           width: 100%; max-width: 400px; text-align: center; }}
    .login-box h2 {{ margin-bottom: 20px; color: var(--primary); }}
    input[type=password] {{ width: 100%; padding: 12px; margin-bottom: 20px; 
                background: #0f172a; border: 1px solid var(--border); 
                color: white; border-radius: 8px; font-size: 1rem; }}
    button {{ width: 100%; padding: 12px; background: linear-gradient(135deg, #3a7bd5, #00d2ff); 
         color: white; border: none; border-radius: 8px; font-weight: bold; 
         font-size: 1rem; cursor: pointer; transition: 0.3s; }}
    button:hover {{ filter: brightness(1.1); transform: translateY(-2px); }}
    #error_msg {{ color: #ef4444; margin-top: 15px; font-size: 0.9rem; min-height: 20px; }}
  </style>
</head>
<body>
  <div class="login-box">
    <h2> VETC ADMIN</h2>
    <input type="password" id="pwd" placeholder="Nhập mật khẩu..." onkeypress="if(event.key==='Enter') doLogin()">
    <button onclick="doLogin()">ĐĂNG NHẬP</button>
    <div id="error_msg"></div>
  </div>
  <script>
    function doLogin() {{
      const pwd = document.getElementById('pwd').value;
      fetch('/login', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{password: pwd}})
      }}).then(r=>r.json()).then(d => {{
        if(d.success) window.location.reload();
        else document.getElementById('error_msg').innerText = " Sai mật khẩu!";
      }});
    }}
  </script>
</body>
</html>"""
