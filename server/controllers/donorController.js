import Donor from '../models/Donor.js';

const bloodGroups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];
const pregnancyStatuses = ['N/A', 'Pregnant', 'Breastfeeding'];
const screeningBooleanFields = [
  'feelsWell',
  'hasRecentIllness',
  'onMedication',
  'recentSurgeryOrDentalProcedure',
  'recentTattooOrPiercing',
  'hasChronicConditions',
];

export async function registerDonor(request, response) {
  const {
    name,
    phone,
    bloodGroup,
    dateOfBirth,
    weight,
    longitude,
    latitude,
    feelsWell,
    hasRecentIllness,
    onMedication,
    recentSurgeryOrDentalProcedure,
    recentTattooOrPiercing,
    pregnancyStatus,
    hasChronicConditions,
    donatedWithin90Days,
    lastDonationDate,
    consentGiven,
    isAvailable,
  } = request.body;

  if (
    !name?.trim() ||
    !phone?.trim() ||
    !bloodGroups.includes(bloodGroup) ||
    !dateOfBirth ||
    !Number.isFinite(Number(weight)) ||
    Number(weight) < 50 ||
    !Number.isFinite(Number(longitude)) || Number(longitude) < -180 || Number(longitude) > 180 ||
    !Number.isFinite(Number(latitude)) || Number(latitude) < -90 || Number(latitude) > 90 ||
    screeningBooleanFields.some((field) => typeof request.body[field] !== 'boolean') ||
    !pregnancyStatuses.includes(pregnancyStatus) ||
    typeof donatedWithin90Days !== 'boolean' ||
    consentGiven !== true ||
    typeof isAvailable !== 'boolean'
  ) {
    return response.status(400).json({
      success: false,
      message: 'Complete all required details, screening answers, availability, and consent.',
    });
  }

  const parsedLastDonationDate = lastDonationDate ? new Date(lastDonationDate) : undefined;
    const parsedDateOfBirth = new Date(dateOfBirth);
    const youngestEligibleDate = new Date();
    youngestEligibleDate.setFullYear(youngestEligibleDate.getFullYear() - 18);
    const oldestEligibleDate = new Date();
    oldestEligibleDate.setFullYear(oldestEligibleDate.getFullYear() - 65);
    if (
      Number.isNaN(parsedDateOfBirth.getTime()) ||
      parsedDateOfBirth > youngestEligibleDate ||
      parsedDateOfBirth < oldestEligibleDate
    ) {
      return response.status(400).json({
        success: false,
        message: 'Registration is currently limited to donors aged 18-65.',
      });
    }

  const now = new Date();
  const donationCutoff = new Date();
  donationCutoff.setDate(donationCutoff.getDate() - 90);

  if (
    (donatedWithin90Days && (!parsedLastDonationDate || Number.isNaN(parsedLastDonationDate.getTime()) || parsedLastDonationDate <= donationCutoff || parsedLastDonationDate > now)) ||
    (!donatedWithin90Days && parsedLastDonationDate && (Number.isNaN(parsedLastDonationDate.getTime()) || parsedLastDonationDate > donationCutoff))
  ) {
    return response.status(400).json({
      success: false,
      message: 'Please provide a last donation date that matches your answer about the last 90 days.',
    });
  }

  const selfDeclaredEligible =
    feelsWell &&
    !hasRecentIllness &&
    !onMedication &&
    !recentSurgeryOrDentalProcedure &&
    !recentTattooOrPiercing &&
    pregnancyStatus === 'N/A' &&
    !hasChronicConditions &&
    !donatedWithin90Days;

  try {
    const donor = await Donor.create({
      name: name.trim(),
      phone: phone.trim(),
      bloodGroup,
      dateOfBirth,
      weight: Number(weight),
      location: {
        type: 'Point',
        coordinates: [Number(longitude), Number(latitude)],
      },
      lastDonationDate: parsedLastDonationDate,
      feelsWell,
      hasRecentIllness,
      onMedication,
      recentSurgeryOrDentalProcedure,
      recentTattooOrPiercing,
      pregnancyStatus,
      hasChronicConditions,
      consentGiven,
      selfDeclaredEligible,
      isAvailable,
      medicalEligibility: false,
    });

    return response.status(201).json({
      success: true,
      data: donor,
      screeningStatus: selfDeclaredEligible ? 'self_declared_clear' : 'temporarily_deferred',
      message: 'This is a self-reported pre-screen only. The blood bank makes the final eligibility decision.',
    });
  } catch (error) {
    if (error.name === 'ValidationError') {
      return response.status(400).json({ success: false, message: error.message });
    }
    console.error('Could not register donor:', error);
    return response.status(500).json({ success: false, message: 'Unable to register right now.' });
  }
}
