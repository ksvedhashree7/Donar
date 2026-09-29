import dotenv from 'dotenv';
import mongoose from 'mongoose';
import Donor from './models/Donor.js';

dotenv.config();

const bloodGroups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];
const names = [
  'Aarav Sharma', 'Diya Verma', 'Ishaan Gupta', 'Ananya Singh', 'Kabir Mehta',
  'Meera Iyer', 'Arjun Rao', 'Aadhya Nair', 'Vivaan Kapoor', 'Sara Khan',
  'Reyansh Das', 'Myra Joshi', 'Advik Reddy', 'Saanvi Patel', 'Krish Malhotra',
  'Anika Bose', 'Rohan Menon', 'Tara Sethi', 'Neil Thomas', 'Ira Chawla',
];

function randomBetween(minimum, maximum) {
  return Math.random() * (maximum - minimum) + minimum;
}

function dateAtAge(age) {
  const dateOfBirth = new Date();
  dateOfBirth.setFullYear(dateOfBirth.getFullYear() - age);
  dateOfBirth.setDate(dateOfBirth.getDate() - Math.floor(randomBetween(0, 365)));
  return dateOfBirth;
}

function donationDate(index) {
  if (index % 4 === 0) return undefined;
  const daysAgo = index % 4 === 1 ? 35 : index % 4 === 2 ? 120 : 180;
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  return date;
}

async function seed() {
  if (!process.env.MONGO_URI) {
    throw new Error('MONGO_URI is required. Add it to server/.env before seeding.');
  }

  await mongoose.connect(process.env.MONGO_URI);
  const donors = names.map((name, index) => ({
    name,
    bloodGroup: index % 8 === 0 ? 'O+' : bloodGroups[Math.floor(Math.random() * bloodGroups.length)],
    dateOfBirth: dateAtAge(Math.floor(randomBetween(18, 66))),
    weight: Math.floor(randomBetween(52, 96)),
    location: {
      type: 'Point',
      coordinates: [randomBetween(77.09, 77.33), randomBetween(28.50, 28.73)],
    },
    lastDonationDate: donationDate(index),
    feelsWell: true,
    hasRecentIllness: false,
    onMedication: false,
    recentSurgeryOrDentalProcedure: false,
    recentTattooOrPiercing: false,
    pregnancyStatus: 'N/A',
    hasChronicConditions: false,
    consentGiven: true,
    selfDeclaredEligible: index % 4 !== 1,
    isAvailable: true,
    medicalEligibility: false,
    isVerified: Math.random() > 0.45,
    phone: `+91-555-01${String(index + 1).padStart(4, '0')}`,
  }));

  try {
    const inserted = await Donor.insertMany(donors);
    console.log(`Seeded ${inserted.length} donors.`);
  } finally {
    await mongoose.disconnect();
  }
}

seed().catch((error) => {
  console.error('Could not seed donors:', error.message);
  process.exitCode = 1;
});
