import Donor from '../models/Donor.js';

const bloodGroups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];

export async function findMatches(request, response) {
  const { bloodGroup, longitude, latitude, maxDistanceKm } = request.body;
  const numericLongitude = Number(longitude);
  const numericLatitude = Number(latitude);
  const numericDistance = Number(maxDistanceKm);

  if (
    !bloodGroups.includes(bloodGroup) ||
    !Number.isFinite(numericLongitude) ||
    !Number.isFinite(numericLatitude) ||
    !Number.isFinite(numericDistance) ||
    numericDistance <= 0 ||
    numericLongitude < -180 || numericLongitude > 180 ||
    numericLatitude < -90 || numericLatitude > 90
  ) {
    return response.status(400).json({ success: false, message: 'Provide a blood group and valid search coordinates and distance.' });
  }

  const now = new Date();
  const youngestEligibleDate = new Date(now);
  youngestEligibleDate.setFullYear(now.getFullYear() - 18);
  const oldestEligibleDate = new Date(now);
  oldestEligibleDate.setFullYear(now.getFullYear() - 65);
  const donationCutoff = new Date(now);
  donationCutoff.setDate(now.getDate() - 90);

  try {
    const donors = await Donor.find({
      // Replace exact matching with a recipient/donor compatibility map when compatibility rules are added.
      bloodGroup,
      selfDeclaredEligible: true,
      consentGiven: true,
      dateOfBirth: { $gte: oldestEligibleDate, $lte: youngestEligibleDate },
      weight: { $gte: 50 },
      $or: [
        { lastDonationDate: { $lte: donationCutoff } },
        { lastDonationDate: { $exists: false } },
        { lastDonationDate: null },
      ],
      isAvailable: true,
      // This is only self-reported pre-screening; final clinical clearance belongs to the blood bank at donation.
      location: {
        $near: {
          $geometry: {
            type: 'Point',
            coordinates: [numericLongitude, numericLatitude],
          },
          $maxDistance: numericDistance * 1000,
        },
      },
    }).limit(10);

    return response.json({ success: true, data: donors });
  } catch (error) {
    console.error('Could not find donor matches:', error);
    return response.status(500).json({ success: false, message: 'Unable to search donors right now.' });
  }
}
