require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const nodemailer = require('nodemailer');
const path = require('path');
const fs = require('fs');

const Vehicle = require('./models/Vehicle');
const Transaction = require('./models/Transaction');

const app = express();
app.use(cors());
app.use(express.json());

// Phục vụ giao diện Dashboard (Frontend)
app.use(express.static(path.join(__dirname, 'public')));
// Phục vụ tĩnh thư mục ảnh vi phạm từ Python
app.use('/violations', express.static(path.resolve(__dirname, process.env.PYTHON_VIOLATIONS_DIR)));

// Kết nối MongoDB
mongoose.connect(process.env.MONGODB_URI)
  .then(() => console.log('✅ Đã kết nối MongoDB'))
  .catch(err => console.error('❌ Lỗi kết nối MongoDB:', err));

const TOLL_FEE = 35000; // Giá vé qua trạm ETC

// ==========================================
// TỰ ĐỘNG THU PHÍ TỪ FIREBASE QUEUE
// ==========================================
async function processFirebaseQueue() {
    const firebaseUrl = process.env.FIREBASE_URL;
    if (!firebaseUrl) return;

    const baseUrl = firebaseUrl.endsWith('/') ? firebaseUrl : firebaseUrl + '/';

    try {
        const res = await fetch(`${baseUrl}queue.json`);
        const data = await res.json();

        if (data) {
            for (const [key, carEvent] of Object.entries(data)) {
                console.log(`\n🚗 Đã nhận tín hiệu xe qua trạm: Biển số ${carEvent.plate}`);
                
                let imageUrl = '/violations/no_image.jpg';

                // Giai ma Base64 -> Anh .jpg de luu vao o cung
                if (carEvent.image_base64) {
                    const base64Data = carEvent.image_base64.replace(/^data:image\/jpeg;base64,/, "");
                    const fileName = `${carEvent.plate}_${Date.now()}.jpg`;
                    const filePath = path.join(__dirname, process.env.PYTHON_VIOLATIONS_DIR, fileName);
                    
                    const dirPath = path.dirname(filePath);
                    if (!fs.existsSync(dirPath)){
                        fs.mkdirSync(dirPath, { recursive: true });
                    }
                    fs.writeFileSync(filePath, base64Data, 'base64');
                    imageUrl = `/violations/${fileName}`;
                }

                // 1. Kiểm tra xe trong hệ thống ETC
                const vehicle = await Vehicle.findOne({ plate: carEvent.plate });
                let status = 'success';
                let iot2_action = 'deny_gate'; // Mac dinh la tu choi

                if (!vehicle) {
                    console.log(`❌ Xe ${carEvent.plate} chưa đăng ký ETC!`);
                    status = 'failed_unregistered';
                } else if (vehicle.balance < TOLL_FEE) {
                    console.log(`❌ Xe ${carEvent.plate} không đủ số dư (Còn: ${vehicle.balance}đ)!`);
                    status = 'failed_insufficient_funds';
                } else {
                    // Trừ tiền
                    vehicle.balance -= TOLL_FEE;
                    await vehicle.save();
                    console.log(`✅ Đã trừ ${TOLL_FEE}đ xe ${carEvent.plate}. Số dư mới: ${vehicle.balance}đ`);
                    iot2_action = 'open_gate'; // Cho phep mo cong
                }

                // GỬI LỆNH ĐÓNG/MỞ CỔNG XUỐNG IOT_2 QUA MẠNG LAN
                const iot2Ip = process.env.IOT2_IP || '192.168.137.199'; // IP cua IOT_2
                try {
                    console.log(`>> Đang gửi lệnh ${iot2_action} tới IOT_2 (${iot2Ip})...`);
                    await fetch(`http://${iot2Ip}/${iot2_action}?plate=${carEvent.plate}`);
                } catch (e) {
                    console.error(`❌ Không thể kết nối tới IOT_2 tại ${iot2Ip}:`, e.message);
                }

                // Luu vao Lịch sử giao dịch (MongoDB)
                const newTx = new Transaction({
                    plate: carEvent.plate,
                    amount: TOLL_FEE,
                    image_url: imageUrl,
                    timestamp: carEvent.timestamp || Date.now(),
                    status: status
                });
                await newTx.save();

                // Xoa ban ghi khoi Hang doi (Queue) Firebase sau khi da xu ly xong
                await fetch(`${baseUrl}queue/${key}.json`, { method: 'DELETE' });
            }
        }
    } catch (error) {
        console.error('❌ Lỗi kết nối Firebase Queue:', error.message);
// Quét (Pull) Firebase Queue mỗi 3 giây
setInterval(() => {
    processFirebaseQueue();
}, 3000);


// ==========================================
// GỬI EMAIL THÔNG BÁO (NHẮC NẠP TIỀN HOẶC HÓA ĐƠN)
// ==========================================
async function sendETCEmail(vehicle, transaction, admin_email, app_password) {
    const transporter = nodemailer.createTransport({
        service: 'gmail',
        auth: {
            user: admin_email,
            pass: app_password
        }
    });

    const imageFileName = transaction.image_url.split('/').pop();
    const imageFilePath = path.join(__dirname, process.env.PYTHON_VIOLATIONS_DIR, imageFileName);

    let subject = "";
    let htmlContent = "";

    if (transaction.status === 'success') {
        subject = `[VETC] Hóa đơn điện tử qua trạm - Biển số ${vehicle.plate}`;
        htmlContent = `
            <h2>Kính gửi ông/bà ${vehicle.owner_name},</h2>
            <p>Hệ thống VETC thông báo quý khách vừa qua trạm thu phí thành công.</p>
            <ul>
                <li><strong>Biển số:</strong> ${vehicle.plate}</li>
                <li><strong>Số tiền bị trừ:</strong> -${transaction.amount.toLocaleString()} VNĐ</li>
                <li><strong>Số dư còn lại:</strong> ${vehicle.balance.toLocaleString()} VNĐ</li>
                <li><strong>Thời gian qua trạm:</strong> ${new Date(transaction.timestamp).toLocaleString('vi-VN')}</li>
            </ul>
            <p><strong>Hình ảnh xe qua trạm:</strong></p>
            <img src="cid:car_image" alt="Ảnh xe" style="max-width: 600px; border: 2px solid #10b981;"/>
            <br/>
            <p>Trân trọng,</p>
            <p>Trung tâm Điều hành ETC Thăng Long</p>
        `;
    } else {
        subject = `[VETC CẢNH BÁO] Tài khoản không đủ tiền - Biển số ${vehicle.plate}`;
        htmlContent = `
            <h2>Kính gửi ông/bà ${vehicle.owner_name},</h2>
            <p>Hệ thống VETC thông báo quý khách vừa qua trạm thu phí nhưng <strong>Tài khoản không đủ số dư</strong>.</p>
            <ul>
                <li><strong>Biển số:</strong> ${vehicle.plate}</li>
                <li><strong>Số dư hiện tại:</strong> ${vehicle.balance.toLocaleString()} VNĐ (Cần tối thiểu ${transaction.amount.toLocaleString()} VNĐ)</li>
                <li><strong>Thời gian qua trạm:</strong> ${new Date(transaction.timestamp).toLocaleString('vi-VN')}</li>
            </ul>
            <p><strong>Hình ảnh xe qua trạm:</strong></p>
            <img src="cid:car_image" alt="Ảnh xe" style="max-width: 600px; border: 2px solid #ef4444;"/>
            <br/>
            <p>Vui lòng nạp thêm tiền vào tài khoản VETC để tiếp tục sử dụng dịch vụ và thanh toán dư nợ.</p>
            <p>Trân trọng,</p>
            <p>Trung tâm Điều hành ETC Thăng Long</p>
        `;
    }

    const mailOptions = {
        from: admin_email,
        to: vehicle.owner_email,
        subject: subject,
        html: htmlContent,
        attachments: [
            {
                filename: imageFileName,
                path: imageFilePath,
                cid: 'car_image'
            }
        ]
    };

    await transporter.sendMail(mailOptions);
    console.log(`📧 Đã gửi email ETC thành công tới: ${vehicle.owner_email}`);
}


// ==========================================
// API ENDPOINTS (Dành cho Web Dashboard)
// ==========================================

// Lấy danh sách giao dịch
app.get('/api/transactions', async (req, res) => {
    try {
        const transactions = await Transaction.find().sort({ timestamp: -1 }).lean();
        
        // Tra cứu thông tin chủ xe cho từng giao dịch
        const enrichedTxs = await Promise.all(transactions.map(async (tx) => {
            const vehicle = await Vehicle.findOne({ plate: tx.plate }).lean();
            if (vehicle) {
                tx.owner_name = vehicle.owner_name;
                tx.owner_email = vehicle.owner_email;
                tx.balance = vehicle.balance;
            } else {
                tx.owner_name = "Xe chưa đăng ký";
                tx.owner_email = "Không có email";
                tx.balance = 0;
            }
            return tx;
        }));

        res.json(enrichedTxs);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Gửi Email thông báo
app.post('/api/transactions/:id/send-email', async (req, res) => {
    try {
        const { admin_email, app_password } = req.body;
        const tx = await Transaction.findById(req.params.id);
        if (!tx) return res.status(404).json({ error: 'Không tìm thấy giao dịch' });

        const vehicle = await Vehicle.findOne({ plate: tx.plate });
        if (!vehicle) {
            return res.status(400).json({ error: `Không tìm thấy thông tin chủ xe biển ${tx.plate}` });
        }

        if (!admin_email || !app_password) {
            return res.status(401).json({ error: 'Vui lòng điền Email và Mật khẩu ứng dụng!' });
        }

        await sendETCEmail(vehicle, tx, admin_email, app_password);
        res.json({ success: true, message: 'Đã gửi Email thông báo thành công tới ' + vehicle.owner_email });
    } catch (error) {
        console.error('❌ Lỗi gửi email:', error);
        res.status(500).json({ error: 'Lỗi máy chủ khi gửi mail: Kiểm tra lại Mật khẩu ứng dụng' });
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`🚀 Node.js Backend Server (VETC) đang chạy tại http://localhost:${PORT}`);
});
