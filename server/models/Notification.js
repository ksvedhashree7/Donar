import mongoose from 'mongoose';

const notificationSchema = new mongoose.Schema({
  donorId: { type: mongoose.Schema.Types.ObjectId, ref: 'Donor', required: true },
  requestId: { type: mongoose.Schema.Types.ObjectId, ref: 'BloodRequest', required: true },
  type: { type: String, enum: ['SMS', 'CALL'], required: true },
  message: { type: String, required: true },
  status: { type: String, enum: ['Sent', 'Delivered', 'Failed'], default: 'Sent' },
  sentAt: { type: Date, default: Date.now },
});

export default mongoose.model('Notification', notificationSchema);