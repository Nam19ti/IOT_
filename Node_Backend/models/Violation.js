const mongoose = require('mongoose');

const violationSchema = new mongoose.Schema({
    plate: { type: String, required: true },
    speed: { type: Number, required: true },
    direction: { type: String },
    image_url: { type: String },
    timestamp: { type: Date, default: Date.now },
    status: { type: String, enum: ['pending', 'sent', 'rejected'], default: 'pending' }
});

module.exports = mongoose.model('Violation', violationSchema);
