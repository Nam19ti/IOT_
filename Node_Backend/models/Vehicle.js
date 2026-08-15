const mongoose = require('mongoose');

const vehicleSchema = new mongoose.Schema({
    plate: { type: String, required: true, unique: true },
    owner_name: { type: String, required: true },
    owner_email: { type: String, required: true },
    balance: { type: Number, default: 0 } // Số dư tài khoản ví điện tử (VNĐ)
});

module.exports = mongoose.model('Vehicle', vehicleSchema);
