
  // ===================== TOAST =====================
  function toast(msg, dur=3000) {
    const t = document.getElementById('_toast');
    t.innerText = msg; t.style.opacity = '1';
    setTimeout( => t.style.opacity = '0', dur);
  }


  // ===================== ROI LOGIC =====================
  const roiBox = document.getElementById('roi_box');
  const camWrap = document.getElementById('cam_container');
  let isDragging = false, startX, startY, startLeft, startTop;
  const initRoiStr = '{json.dumps(controller.config.get("roi", {"x":0.2, "y":0.4, "w":0.4, "h":0.3}))}';
  let roiData = JSON.parse(initRoiStr.replace(/'/g, '"'));
  
  function applyRoiStyles() {
    roiBox.style.left = (roiData.x * 100) + '%';
    roiBox.style.top = (roiData.y * 100) + '%';
    roiBox.style.width = (roiData.w * 100) + '%';
    roiBox.style.height = (roiData.h * 100) + '%';
  }
  applyRoiStyles;

  roiBox.addEventListener('mousedown', function(e) {
    if (e.offsetX> roiBox.clientWidth - 20 && e.offsetY> roiBox.clientHeight - 20) return;
    isDragging = true; startX = e.clientX; startY = e.clientY;
    startLeft = roiBox.offsetLeft; startTop = roiBox.offsetTop;
  });

  document.addEventListener('mousemove', function(e) {
    if (!isDragging) return;
    let newLeft = Math.max(0, Math.min(startLeft + e.clientX - startX, camWrap.clientWidth - roiBox.offsetWidth));
    let newTop = Math.max(0, Math.min(startTop + e.clientY - startY, camWrap.clientHeight - roiBox.offsetHeight));
    roiBox.style.left = newLeft + 'px'; roiBox.style.top = newTop + 'px';
  });

  document.addEventListener('mouseup', function {
    if (isDragging) { isDragging = false; saveRoi; }
  });

  function saveRoi() {
    roiData = { x: roiBox.offsetLeft / camWrap.clientWidth, y: roiBox.offsetTop / camWrap.clientHeight, w: roiBox.offsetWidth / camWrap.clientWidth, h: roiBox.offsetHeight / camWrap.clientHeight };
    fetch('/set_settings', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ "roi": roiData }) });
  }
  // ===================== SETTINGS =====================
  const IOT2_IP = '192.168.137.199'; // IP tinh Mạch 2

  function toggleConfig() {
    const panel = document.getElementById('config_panel');
    panel.classList.toggle('active');
  }

  function saveSettings() {
    const url = document.getElementById('cam_url').value;
    const api_key = document.getElementById('gemini_api_key').value;
    const ai_mode = document.getElementById('ai_mode').value;
    const tele = document.getElementById('telegram_token').value;
    const mongo = document.getElementById('mongo_uri').value;
    const fire = document.getElementById('firebase_url').value;
    const en_fire = document.getElementById('enable_firebase').checked;
    const en_tele = document.getElementById('enable_telegram').checked;
    fetch('/set_settings', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ 
        "url": url,
        "gemini_api_key": api_key,
        "ai_mode": ai_mode,
        "telegram_token": tele,
        "mongo_uri": mongo,
        "firebase_url": fire,
        "enable_firebase": en_fire,
        "enable_telegram": en_tele
      })
    }).then(r=>r.json()()).then(d=>{
      document.getElementById('save_msg').innerText = d.success ? ' Đã lưu Cài đặt!' : ' Lỗi lưu!';
      setTimeout(=>document.getElementById('save_msg').innerText='', 3000);
    }).catch(e => {
      console.error(e);
      document.getElementById('save_msg').innerText = ' Lỗi Mạng/Server!';
      setTimeout(=>document.getElementById('save_msg').innerText='', 3000);
    });
  }
  // ===================== GATE CONTROL =====================
  function gate(path) {
    toast('Dang gui lenh...');
    fetch(path)
      .then(r=>r.json()())
      .then(d=>{
        if(d.success) toast(' Đã gửi lệnh cổng!');
        else toast(' Lỗi: ' + d.error);
      })
      .catch(=>toast(' Không thể gửi lệnh!'));
  }

  // ===================== CAPTURE ONLY =====================
  function doCapture() {
    const el = document.getElementById('ocr_result');
    const btn = document.getElementById('btn_capture');
    el.style.color = '#fbbf24';
    el.innerText = '📷 Dang chup anh...';
    btn.disabled = true;
    fetch('/capture_only').then(r=>r.json()()).then(d=>{
      btn.disabled = false;
      if (d.success) {
        el.style.color = '#10b981';
        el.innerText = ' Chup anh thanh cong!';
        document.getElementById('cam_view').src = '/captures/latest_capture.jpg?t=' + Date.now();
        document.getElementById('cam_view').style.opacity = '1';
      } else {
        el.style.color = '#ef4444';
        el.innerText = ' ' + d.error;
      }
    }).catch(()=>{ btn.disabled=false; el.style.color='#ef4444'; el.innerText=' Loi ket noi server!'; });
  }

  // ===================== OCR =====================
  let ocrController = null;

  function abortOCR() {
    if (ocrController) {
      ocrController.abort;
      ocrController = null;
    }
    const el = document.getElementById('ocr_result');
    el.innerText = ' Đã hủy nhận diện!';
    el.style.color = '#ef4444'; 
    
    document.getElementById('btn_ocr').disabled = false;
    document.getElementById('btn_ocr').style.display = 'inline-block';
    document.getElementById('btn_abort').style.display = 'none';
    toast('Đã hủy tiến trình AI');
  }

  function doOCR() {
    const el = document.getElementById('ocr_result');
    const btn = document.getElementById('btn_ocr');
    el.style.color = '#fbbf24';
    el.innerText = ' Dang chup anh...';
    btn.disabled = true;
    
    fetch('/capture_only').then(r=>r.json()()).then(d=>{
      if (d.success) {
        document.getElementById('cam_view').src = '/captures/latest_capture.jpg?t=' + Date.now();
        document.getElementById('cam_view').style.opacity = '1';
        
        el.innerText = ' Da chup. Dang nhan dien bien so... (Vui long doi)';
        document.getElementById('btn_ocr').style.display = 'none';
        document.getElementById('btn_abort').style.display = 'inline-block';
        
        ocrController = new AbortController();
        fetch('/process_latest', { signal: ocrController.signal }).then(r2=>r2.json()).then(d2=>{
          btn.disabled = false;
          document.getElementById('btn_ocr').style.display = 'inline-block';
          document.getElementById('btn_abort').style.display = 'none';
          if (d2.success) {
            el.style.color = '#10b981';
            el.innerText = ' Bien so: ' + d2.plate + ' (' + d2.time + 's)';
          } else {
            el.style.color = '#ef4444';
            el.innerText = ' ' + d2.error;
          }
        }).catch(e=>{ 
          btn.disabled=false; 
          document.getElementById('btn_ocr').style.display = 'inline-block';
          document.getElementById('btn_abort').style.display = 'none';
          if(e.name === 'AbortError') {
            console.log('Fetch aborted');
          } else {
            el.style.color='#ef4444'; el.innerText=' Loi ket noi nhan dien!'; 
          }
        });
        
      } else {
        btn.disabled = false;
        el.style.color = '#ef4444';
        el.innerText = ' ' + d.error;
      }
    }).catch(()=>{ btn.disabled=false; el.style.color='#ef4444'; el.innerText=' Loi ket noi chup anh!'; });
  }

  // ===================== LIVE UPDATE =====================
  let lastCaptureTs = 0;
  let lastVioTs   = null;

  function updateStats() {
    fetch('/get_stats').then(r=>r.json()()).then(d=>{
      // AI status
      const bar = document.getElementById('ai_status_bar');
      if (d.ai_ready) {
        bar.className = 'ready';
        bar.innerText = ' EasyOCR San sang - Nhan dien Offline 100%!';
      } else {
        bar.className = '';
        bar.innerText = ' AI dang khoi dong... (Vui long doi ~1 phut)';
      }

      // Anh moi nhat
      if (d.last_capture_ts && d.last_capture_ts !== lastCaptureTs) {
        lastCaptureTs = d.last_capture_ts;
        document.getElementById('cam_view').src = '/captures/latest_capture.jpg?t=' + Date.now();
        document.getElementById('cam_view').style.opacity = '1';
      }

      // Ket qua nhan dien
      if (d.last_violation && d.last_violation.ts !== lastVioTs) {
        lastVioTs = d.last_violation.ts;
        const v = d.last_violation;
        document.getElementById('plate_display').innerText  = v.plate || '---';
        document.getElementById('payment_status').innerText = v.status || '---';
        document.getElementById('proc_time').innerText    = (v.proc_time || '---') + 's';
        document.getElementById('result_ts').innerText    = 'Luc: ' + (v.ts || '');

        const img = document.getElementById('result_img');
        const ph = document.getElementById('result_placeholder');
        if (v.image && v.image !== 'no_image.jpg') {
          img.src = '/captures/' + v.image + '?t=' + Date.now();
          img.style.display = 'block'; ph.style.display = 'none';
        } else {
          img.style.display = 'none'; ph.style.display = 'flex';
        }
      }
    }).catch(()=>{});
  }

  setInterval(updateStats, 2000);
  updateStats();

  function logout() {
    fetch('/logout', {method: 'POST'}).then(()=> window.location.reload);
  }
  // TABS LOGIC
  function switchTab(tabId) {
    document.getElementById('tab_system').style.display = tabId === 'system' ? 'block' : 'none';
    document.getElementById('tab_stranger').style.display = tabId === 'stranger' ? 'block' : 'none';
    document.getElementById('btn_tab_system').className = tabId === 'system' ? 'tab-btn active' : 'tab-btn';
    document.getElementById('btn_tab_stranger').className = tabId === 'stranger' ? 'tab-btn active' : 'tab-btn';
    if (tabId === 'stranger') loadStrangers();
  }
  
  
  // ===================== OFFLINE QUEUE LOGIC =====================
  function loadOfflineQueue() {
    document.getElementById('offline_list').innerHTML = '<p style="text-align:center; color:#64748b;">Đang đọc file CSV...</p>';
    fetch('/api/offline_queue').then(r=>r.json()()).then(d => {
      if(!d.success) {
        document.getElementById('offline_list').innerHTML = `<p style="color:#ef4444;">Lỗi: ${d.error}</p>`;
        return;
      }
      const data = d.data;
      if(data.length === 0) {
        document.getElementById('offline_list').innerHTML = '<p style="text-align:center; color:#10b981;">Tất cả dữ liệu đã được đồng bộ 100% lên Đám Mây!</p>';
        document.getElementById('offline_badge').style.display = 'none';
        return;
      }
      
      let html = '<div style="background:#0f172a; border:1px solid #334155; border-radius:8px; overflow:hidden;">';
      html += '<div style="display:flex; padding:10px; background:#1e293b; font-weight:bold; border-bottom:1px solid #334155;">';
      html += '<div style="width:30%">Thời gian</div><div style="width:30%">Biển số</div><div style="width:40%">Tên File Ảnh</div></div>';
      
      data.forEach(item => {
        let timeStr = new Date(parseInt(item.timestamp)).toLocaleString('vi-VN');
        html += `<div style="display:flex; padding:10px; border-bottom:1px solid #1e293b;">`;
        html += `<div style="width:30%; font-size:0.85rem; color:#94a3b8;">${timeStr}</div>`;
        html += `<div style="width:30%; font-weight:bold; color:#00d2ff;">${item.plate}</div>`;
        html += `<div style="width:40%; font-size:0.8rem; color:#64748b; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${item.img_path}</div>`;
        html += `</div>`;
      });
      html += '</div>';
      document.getElementById('offline_list').innerHTML = html;
      
      // Update badge
      let badge = document.getElementById('offline_badge');
      badge.innerText = data.length;
      badge.style.display = 'inline-block';
    });
  }

  // STRANGERS LOGIC
  function loadStrangers() {
    document.getElementById('stranger_list').innerHTML = '<p style="text-align:center; color:#64748b;">Đang tải...</p>';
    fetch('/api/strangers').then(r=>r.json()()).then(data => {
      if(data.error) {
        document.getElementById('stranger_list').innerHTML = `<p style="color:#ef4444;">Lỗi: ${data.error}</p>`;
        return;
      }
      let html = '';
      let count = 0;
      for(let key in data) {
        count++;
        let item = data[key];
        let timeStr = new Date(item.timestamp).toLocaleString('vi-VN');
        html += `
        <div class="stranger-item">
          <img src="data:image/jpeg;base64,${item.image_base64}" class="stranger-img">
          <div class="stranger-info">
            <div style="margin-bottom: 8px;">
              <span style="color:#e2e8f0; font-size:0.9rem;">Sửa biển:</span>
              <input type="text" id="plate_input_${key}" value="${item.plate}" style="background:#0f172a; color:#fff; border:1px solid #334155; padding:5px; border-radius:4px; font-weight:bold; font-size:1.1rem; width:120px; text-transform:uppercase;">
            </div>
            <div style="font-size:0.8rem; color:#94a3b8;">Thời gian: ${timeStr}</div>
          </div>
          <div class="stranger-actions" style="flex-wrap: wrap;">
            <button class="btn" style="background:#3b82f6;" onclick="recheckStranger('${key}')"> Kiểm Tra</button>
            <button class="btn btn-green" onclick="handleStranger('${key}', document.getElementById('plate_input_${key}').value, 'approve')">Duyệt Quen</button>
            <button class="btn btn-red" onclick="handleStranger('${key}', document.getElementById('plate_input_${key}').value, 'warn')">Cảnh Báo</button>
            <button class="btn btn-logout" onclick="handleStranger('${key}', document.getElementById('plate_input_${key}').value, 'delete')">Xóa Bỏ</button>
          </div>
        </div>`;
      }
      if(count === 0) html = '<p style="text-align:center; color:#10b981;">Tuyệt vời! Không có xe lạ nào tồn đọng.</p>';
      document.getElementById('stranger_list').innerHTML = html;
      
      // Update badge
      let badge = document.getElementById('stranger_badge');
      badge.innerText = count;
      badge.style.display = count> 0 ? 'inline-block' : 'none';
    }).catch(e => {
      document.getElementById('stranger_list').innerHTML = '<p style="color:#ef4444;">Không thể kết nối Server</p>';
    });
  }
  
  function handleStranger(key, plate, action) {
    if(action === 'delete' && !confirm("Bạn chắc chắn muốn xóa dữ liệu xe này?")) return;
    if(action === 'warn' && !confirm(`Bạn có chắc muốn ĐƯA BIỂN SỐ ${plate} VÀO SỔ ĐEN CẢNH BÁO?`)) return;
    
    fetch('/api/stranger/action', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ key: key, plate: plate, action: action })
    }).then(r=>r.json()()).then(d => {
      if(d.success) loadStrangers();
      else alert("Lỗi: " + d.error);
    });
  }

  function recheckStranger(key) {
    const plate = document.getElementById('plate_input_' + key).value;
    if (!plate) return;
    toast('Đang kiểm tra...');
    fetch('/api/stranger/action', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ key: key, plate: plate, action: 'recheck' })
    }).then(r=>r.json()()).then(d=> {
      if(d.success) {
        if(d.result === 'known') {
          alert(' Đã xác nhận đây là xe quen! Hệ thống đã tự động gửi thông báo Telegram cho người dùng.');
          const el = document.getElementById('stranger_item_' + key);
          if(el) el.remove;
          let badge = document.getElementById('stranger_badge');
          if(badge) {
            let count = parseInt(badge.innerText) || 0;
            if(count> 0) count--;
            badge.innerText = count;
            badge.style.display = count> 0 ? 'inline-block' : 'none';
          }
        } else {
          alert(' Biển số [' + plate + '] vẫn CHƯA CÓ trong hệ thống. Nếu đúng là xe lạ, hãy dùng nút Duyệt Quen mới, Cảnh Báo hoặc Xóa Bỏ!');
        }
      } else {
        alert('Lỗi: ' + d.error);
      }
    });
  }
  
  setTimeout(loadStrangers, 3000); // Tu dong load ngam badge




    function doLogin() {
      const pwd = document.getElementById('pwd').value;
      fetch('/login', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({password: pwd})
      }).then(r=>r.json()()).then(d => {
        if(d.success) window.location.reload();
        else document.getElementById('error_msg').innerText = " Sai mật khẩu!";
      });
    }
  