const mongoose = require('mongoose');

const transactionSchema = new mongoose.Schema({
    plate: { type: String, required: true },
    amount: { type: Number, required: true }, // Số tiền trừ
    image_url: { type: String }, // Ảnh chụp biển số làm bằng chứng
    timestamp: { type: Date, default: Date.now },
    status: { 
        type: String, 
        enum: ['success', 'failed_insufficient_funds', 'failed_unregistered'], 
        required: true 
    }
});

module.exports = mongoose.model('Transaction', transactionSchema);
