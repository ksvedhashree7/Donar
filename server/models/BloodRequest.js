import mongoose from 'mongoose';

const bloodGroups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];

const bloodRequestSchema = new mongoose.Schema({
  patientName: { type: String, required: true, trim: true },
  bloodGroup: { type: String, enum: bloodGroups, required: true },
  unitsRequired: { type: Number, required: true, min: 1 },
  hospitalName: { type: String, required: true, trim: true },
  contactPhone: { type: String, required: true, trim: true },
  urgency: { type: String, enum: ['Critical', 'Urgent', 'Normal'], default: 'Normal' },
  location: {
    type: {
      type: String,
      enum: ['Point'],
      default: 'Point',
      required: true,
    },
    coordinates: {
      type: [Number],
      required: true,
      validate: {
        validator: (coordinates) => coordinates.length === 2,
        message: 'Location coordinates must be [longitude, latitude].',
      },
    },
  },
  status: { type: String, enum: ['Pending', 'Approved', 'Rejected', 'Fulfilled'], default: 'Pending' },
  verifiedBy: { type: String, trim: true },
  verifiedAt: { type: Date },
}, { timestamps: true });

bloodRequestSchema.index({ location: '2dsphere' });

export default mongoose.model('BloodRequest', bloodRequestSchema);