import mongoose from 'mongoose';

const bloodGroups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];

const donorSchema = new mongoose.Schema({
  name: { type: String, required: true, trim: true },
  bloodGroup: { type: String, enum: bloodGroups, required: true },
  dateOfBirth: { type: Date, required: true },
  weight: { type: Number, required: true, min: 50 },
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
  lastDonationDate: { type: Date },
  hemoglobinLevel: { type: Number, min: 0 },
  bloodPressure: { type: String, trim: true },
  feelsWell: { type: Boolean, required: true },
  hasRecentIllness: { type: Boolean, default: false },
  onMedication: { type: Boolean, default: false },
  recentSurgeryOrDentalProcedure: { type: Boolean, required: true },
  recentTattooOrPiercing: { type: Boolean, default: false },
  pregnancyStatus: {
    type: String,
    enum: ['N/A', 'Pregnant', 'Breastfeeding'],
    default: 'N/A',
  },
  hasChronicConditions: { type: Boolean, default: false },
  consentGiven: { type: Boolean, required: true },
  selfDeclaredEligible: { type: Boolean, default: false },
  isAvailable: { type: Boolean, default: true },
  medicalEligibility: { type: Boolean, default: false },
  isVerified: { type: Boolean, default: false },
  phone: { type: String, required: true, trim: true },
});

donorSchema.index({ location: '2dsphere' });

export default mongoose.model('Donor', donorSchema);
