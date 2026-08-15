require('dotenv').config();
const mongoose = require('mongoose');
const Vehicle = require('./models/Vehicle');
const Transaction = require('./models/Transaction');

mongoose.connect(process.env.MONGODB_URI)
.then(async () => {
    console.log('✅ Đã kết nối MongoDB. Bắt đầu tạo dữ liệu mẫu...');
    
    // Xóa dữ liệu cũ (Tùy chọn)
    await Vehicle.deleteMany({});
    await Transaction.deleteMany({});
    
    // Tạo dummy vehicles với Số dư (balance)
    const dummyVehicles = [
        { plate: "29A12345", owner_name: "Nguyen Van A", owner_email: process.env.EMAIL_USER || "admin@example.com", balance: 100000 }, 
        { plate: "30H123456", owner_name: "Tran Thi B", owner_email: process.env.EMAIL_USER || "admin@example.com", balance: 20000 } // Thieu tien qua tram (35k)
    ];
    
    await Vehicle.insertMany(dummyVehicles);
    console.log('✅ Đã tạo dữ liệu xe mẫu ETC thành công!');
    process.exit();
}).catch(err => {
    console.error('Lỗi:', err);
    process.exit(1);
});
