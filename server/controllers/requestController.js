import BloodRequest from '../models/BloodRequest.js';
import Donor from '../models/Donor.js';
import Notification from '../models/Notification.js';

const bloodGroups = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];
const urgencies = ['Critical', 'Urgent', 'Normal'];

export async function createBloodRequest(request, response) {
  const {
    patientName,
    bloodGroup,
    unitsRequired,
    hospitalName,
    contactPhone,
    urgency = 'Normal',
    longitude,
    latitude,
  } = request.body;
  const numericUnits = Number(unitsRequired);
  const numericLongitude = Number(longitude);
  const numericLatitude = Number(latitude);

  if (
    !patientName?.trim() ||
    !bloodGroups.includes(bloodGroup) ||
    !Number.isInteger(numericUnits) || numericUnits < 1 || numericUnits > 20 ||
    !hospitalName?.trim() ||
    !contactPhone?.trim() ||
    !urgencies.includes(urgency) ||
    !Number.isFinite(numericLongitude) || numericLongitude < -180 || numericLongitude > 180 ||
    !Number.isFinite(numericLatitude) || numericLatitude < -90 || numericLatitude > 90
  ) {
    return response.status(400).json({ success: false, message: 'Complete the request details with valid units and location coordinates.' });
  }

  try {
    const bloodRequest = await BloodRequest.create({
      patientName: patientName.trim(),
      bloodGroup,
      unitsRequired: numericUnits,
      hospitalName: hospitalName.trim(),
      contactPhone: contactPhone.trim(),
      urgency,
      location: { type: 'Point', coordinates: [numericLongitude, numericLatitude] },
      status: 'Pending',
    });

    return response.status(201).json({
      success: true,
      data: bloodRequest,
      message: 'Request submitted for expert verification. It will be shared with donors only after approval.',
    });
  } catch (error) {
    if (error.name === 'ValidationError') {
      return response.status(400).json({ success: false, message: error.message });
    }
    console.error('Could not create blood request:', error);
    return response.status(500).json({ success: false, message: 'Unable to submit this request right now.' });
  }
}

export async function listPendingRequests(_request, response) {
  try {
    const requests = await BloodRequest.find({ status: 'Pending' }).sort({ createdAt: 1 });
    return response.json({ success: true, data: requests });
  } catch (error) {
    console.error('Could not load pending requests:', error);
    return response.status(500).json({ success: false, message: 'Unable to load the verification queue.' });
  }
}

export async function approveBloodRequest(request, response) {
  const now = new Date();
  const youngestEligibleDate = new Date(now);
  youngestEligibleDate.setFullYear(now.getFullYear() - 18);
  const oldestEligibleDate = new Date(now);
  oldestEligibleDate.setFullYear(now.getFullYear() - 65);
  const donationCutoff = new Date(now);
  donationCutoff.setDate(now.getDate() - 90);

  try {
    const bloodRequest = await BloodRequest.findOne({ _id: request.params.id, status: 'Pending' });
    if (!bloodRequest) {
      return response.status(404).json({ success: false, message: 'Pending request not found.' });
    }

    const donors = await Donor.find({
      bloodGroup: bloodRequest.bloodGroup,
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
      location: {
        $near: {
          $geometry: bloodRequest.location,
          $maxDistance: 20000,
        },
      },
    }).limit(3);

    bloodRequest.status = 'Approved';
    bloodRequest.verifiedBy = 'Admin verifier';
    bloodRequest.verifiedAt = now;
    await bloodRequest.save();

    const notifications = await Notification.insertMany(donors.map((donor) => ({
      donorId: donor._id,
      requestId: bloodRequest._id,
      type: 'SMS',
      status: 'Sent',
      message: `${bloodRequest.urgency}: ${bloodRequest.bloodGroup} blood needed at ${bloodRequest.hospitalName}. Contact ${bloodRequest.contactPhone} if available.`,
    })));

    return response.json({
      success: true,
      data: {
        request: bloodRequest,
        notifications: notifications.map((notification, index) => ({
          _id: notification._id,
          donorName: donors[index].name,
          donorPhone: donors[index].phone,
          type: notification.type,
          status: notification.status,
          message: notification.message,
        })),
      },
      message: `Request approved. ${notifications.length} simulated donor notification${notifications.length === 1 ? '' : 's'} created; no SMS was sent.`,
    });
  } catch (error) {
    console.error('Could not approve blood request:', error);
    return response.status(500).json({ success: false, message: 'Unable to approve this request right now.' });
  }
}

export async function rejectBloodRequest(request, response) {
  try {
    const bloodRequest = await BloodRequest.findOneAndUpdate(
      { _id: request.params.id, status: 'Pending' },
      { $set: { status: 'Rejected', verifiedBy: 'Admin verifier', verifiedAt: new Date() } },
      { new: true, runValidators: true },
    );
    if (!bloodRequest) {
      return response.status(404).json({ success: false, message: 'Pending request not found.' });
    }
    return response.json({ success: true, data: bloodRequest, message: 'Request rejected; no donor notifications were created.' });
  } catch (error) {
    console.error('Could not reject blood request:', error);
    return response.status(500).json({ success: false, message: 'Unable to reject this request right now.' });
  }
}