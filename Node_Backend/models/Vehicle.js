const mongoose = require('mongoose');

const vehicleSchema = new mongoose.Schema({
    plate: { type: String, required: true, unique: true },
    owner_name: { type: String, required: true },
    owner_email: { type: String, required: true }
});

module.exports = mongoose.model('Vehicle', vehicleSchema);
