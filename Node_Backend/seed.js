require('dotenv').config();
const mongoose = require('mongoose');
const Vehicle = require('./models/Vehicle');

mongoose.connect(process.env.MONGODB_URI)
.then(async () => {
    console.log('✅ Đã kết nối MongoDB. Bắt đầu tạo dữ liệu mẫu...');
    
    // Xóa dữ liệu cũ (Tùy chọn)
    await Vehicle.deleteMany({});
    
    // Tạo dummy vehicles
    const dummyVehicles = [
        { plate: "29A12345", owner_name: "Nguyen Van A", owner_email: process.env.EMAIL_USER }, 
        { plate: "30H123456", owner_name: "Tran Thi B", owner_email: process.env.EMAIL_USER }
    ];
    
    await Vehicle.insertMany(dummyVehicles);
    console.log('✅ Đã tạo dữ liệu xe mẫu thành công!');
    process.exit();
}).catch(err => {
    console.error('Lỗi:', err);
    process.exit(1);
});
