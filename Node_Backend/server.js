require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const nodemailer = require('nodemailer');
const path = require('path');

const Vehicle = require('./models/Vehicle');
const Violation = require('./models/Violation');

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

// Cấu hình Nodemailer
const transporter = nodemailer.createTransport({
    service: 'gmail',
    auth: {
        user: process.env.EMAIL_USER,
        pass: process.env.EMAIL_PASS
    }
});

// Hàm gửi email phạt nguội
async function sendPenaltyEmail(vehicle, violation) {
    const mailOptions = {
        from: process.env.EMAIL_USER,
        to: vehicle.owner_email,
        subject: `[Thông báo vi phạm giao thông] - Biển số ${vehicle.plate}`,
        html: `
            <h2>Kính gửi ông/bà ${vehicle.owner_name},</h2>
            <p>Hệ thống giám sát giao thông ghi nhận phương tiện của quý khách đã có hành vi vi phạm vượt quá tốc độ.</p>
            <ul>
                <li><strong>Biển số:</strong> ${vehicle.plate}</li>
                <li><strong>Tốc độ đo được:</strong> ${violation.speed} km/h</li>
                <li><strong>Thời gian vi phạm:</strong> ${new Date(violation.timestamp).toLocaleString('vi-VN')}</li>
            </ul>
            <p><strong>Hình ảnh bằng chứng:</strong></p>
            <img src="${violation.image_url}" alt="Ảnh vi phạm" style="max-width: 600px; border: 2px solid red;"/>
            <br/>
            <p>Đề nghị ông/bà tới cơ quan chức năng để giải quyết nộp phạt theo quy định.</p>
            <p>Trân trọng,</p>
            <p>Hệ thống giám sát giao thông thông minh IOT Thăng Long</p>
        `
    };

    await transporter.sendMail(mailOptions);
    console.log(`📧 Đã gửi email phạt nguội thành công tới: ${vehicle.owner_email}`);
}

// ==========================================
// API ENDPOINTS
// ==========================================

// Nhận dữ liệu từ Python và Đưa vào hàng đợi chờ duyệt (pending)
app.post('/api/violation', async (req, res) => {
    try {
        const { car_id, plate, speed, direction, image, timestamp } = req.body;
        console.log(`\n🚨 Có vi phạm mới: Biển ${plate}, Tốc độ ${speed} km/h. Đang chờ duyệt...`);

        const imageUrl = `${process.env.PI_LOCAL_IP}/violations/${image}`;

        const newViolation = new Violation({
            plate,
            speed,
            direction,
            image_url: imageUrl,
            timestamp: timestamp || Date.now(),
            status: 'pending' // Chờ con người duyệt
        });
        await newViolation.save();

        res.status(200).json({ success: true, message: 'Đã đưa vào danh sách chờ duyệt.' });
    } catch (error) {
        console.error('❌ Lỗi xử lý vi phạm:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// Lấy danh sách vi phạm (để render lên Dashboard)
app.get('/api/violations', async (req, res) => {
    try {
        const violations = await Violation.find().sort({ timestamp: -1 });
        res.json(violations);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Duyệt và Gửi Phạt
app.post('/api/violations/:id/send', async (req, res) => {
    try {
        const { plate } = req.body;
        const violation = await Violation.findById(req.params.id);
        if (!violation) return res.status(404).json({ error: 'Không tìm thấy biên bản' });

        // Cập nhật biển số nếu người dùng có sửa chữa trên giao diện
        if (plate && plate !== violation.plate) {
            console.log(`✏️ Biển số đã được sửa tay từ ${violation.plate} thành ${plate}`);
            violation.plate = plate;
        }

        const vehicle = await Vehicle.findOne({ plate: violation.plate });
        if (!vehicle) {
            return res.status(400).json({ error: `Không tìm thấy thông tin chủ xe biển ${violation.plate} trong CSDL` });
        }

        await sendPenaltyEmail(vehicle, violation);
        violation.status = 'sent';
        await violation.save();

        res.json({ success: true, message: 'Đã cập nhật và gửi phạt nguội thành công!' });
    } catch (error) {
        console.error('❌ Lỗi gửi phạt:', error);
        res.status(500).json({ error: 'Lỗi máy chủ khi gửi mail' });
    }
});

// Hủy/Xóa Biên Bản
app.post('/api/violations/:id/reject', async (req, res) => {
    try {
        const violation = await Violation.findById(req.params.id);
        if (!violation) return res.status(404).json({ error: 'Không tìm thấy biên bản' });

        violation.status = 'rejected';
        await violation.save();

        res.json({ success: true, message: 'Đã hủy biên bản vi phạm.' });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`🚀 Node.js Backend Server đang chạy tại http://localhost:${PORT}`);
    console.log(`🌍 Mở trình duyệt tại http://localhost:${PORT} để vào Dashboard`);
});
