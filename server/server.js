import cors from 'cors';
import dotenv from 'dotenv';
import express from 'express';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';

dotenv.config();

const app = express();
const port = Number(process.env.PORT) || 5000;
const JWT_SECRET = process.env.JWT_SECRET || 'donorconnect-demo-secret';
const DEMO_PASSWORD = process.env.DEMO_PASSWORD || 'DonorConnect123!';

const uid = (prefix = 'id') => `${prefix}_${Math.random().toString(36).slice(2, 10)}`;

const createDonorLocation = (lat, lng, accuracy = 240) => ({
  lat,
  lng,
  accuracy,
  sharingStatus: 'OFF',
  updatedAt: new Date().toISOString(),
  source: 'simulated-gps',
});

const state = {
  users: [],
  donors: [],
  hospitals: [],
  patients: [],
  requirements: [],
  requests: [],
  notifications: [],
  documents: [],
  auditLogs: [],
  caseTimelines: [],
  locations: [],
};

function addAuditLog(event, context = {}) {
  state.auditLogs.push({
    id: uid('audit'),
    event,
    timestamp: new Date().toISOString(),
    ...context,
  });
}

function buildToken(user) {
  return jwt.sign({ sub: user.id, email: user.email, role: user.role }, JWT_SECRET, { expiresIn: '8h' });
}

function safeUser(user) {
  return {
    id: user.id,
    email: user.email,
    role: user.role,
    name: user.name,
    createdAt: user.createdAt,
  };
}

function ensureDemoUsers() {
  if (state.users.length) return;

  const donorUser = {
    id: 'user_donor_demo',
    name: 'Demo Donor',
    email: 'donor.demo@example.com',
    passwordHash: bcrypt.hashSync(DEMO_PASSWORD, 10),
    role: 'DONOR',
    createdAt: new Date().toISOString(),
  };

  const hospitalUser = {
    id: 'user_hospital_demo',
    name: 'Demo Hospital Admin',
    email: 'hospital.demo@example.com',
    passwordHash: bcrypt.hashSync(DEMO_PASSWORD, 10),
    role: 'HOSPITAL',
    createdAt: new Date().toISOString(),
  };

  const adminUser = {
    id: 'user_admin_demo',
    name: 'System Admin',
    email: 'admin.demo@example.com',
    passwordHash: bcrypt.hashSync(DEMO_PASSWORD, 10),
    role: 'SUPER_ADMIN',
    createdAt: new Date().toISOString(),
  };

  state.users.push(donorUser, hospitalUser, adminUser);

  const donor = {
    id: 'donor_1001',
    userId: donorUser.id,
    fullName: 'Ananya Raman',
    dateOfBirth: '1994-06-14',
    gender: 'Female',
    phoneNumber: '+91-9876543210',
    email: donorUser.email,
    bloodGroup: 'O+',
    city: 'Bengaluru',
    area: 'Koramangala',
    emergencyContact: '+91-9988776655',
    organOptions: ['Kidney', 'Liver'],
    donationType: 'LIVING',
    availabilityStatus: 'AVAILABLE',
    consentStatus: 'ACTIVE',
    verificationStatus: 'VERIFIED',
    hospitalVerificationStatus: 'COMPLETE',
    location: createDonorLocation(12.9352, 77.6245, 150),
    lastUpdated: new Date().toISOString(),
    donationIntent: {
      status: 'REGISTERED',
      organs: ['Kidney', 'Liver'],
      consentDate: new Date().toISOString(),
    },
    isAvailable: true,
    compliance: { consent: true, locationSharing: false },
    verificationHistory: [{ status: 'VERIFIED', note: 'Hospital review complete', updatedAt: new Date().toISOString() }],
  };

  const hospital = {
    id: 'hospital_4001',
    name: 'CityCare Institute',
    email: hospitalUser.email,
    location: { city: 'Bengaluru', lat: 12.9716, lng: 77.5946 },
    tier: 'TIER_1',
    isActive: true,
  };

  const caseRecord = {
    id: 'case_5001',
    patientName: 'Rohit Menon',
    age: 41,
    gender: 'Male',
    bloodGroup: 'A+',
    requiredOrgan: 'Kidney',
    medicalPriority: 'HIGH',
    hospitalId: hospital.id,
    hospitalName: hospital.name,
    department: 'Nephrology',
    requiredBy: new Date(Date.now() + 18 * 60 * 60 * 1000).toISOString(),
    status: 'MATCH_REVIEW',
    assignedCoordinator: 'Dr. Nisha Rao',
    verificationStatus: 'CASE_APPROVED',
    createdAt: new Date().toISOString(),
  };

  const requirement = {
    id: 'req_9001',
    caseId: caseRecord.id,
    requiredOrgan: 'Kidney',
    bloodGroup: 'A+',
    casePriority: 'HIGH',
    requiredTimeline: new Date(Date.now() + 36 * 60 * 60 * 1000).toISOString(),
    hospitalLocation: 'Bengaluru',
    criteria: 'Blood type compatibility, donor verification, and travel logistics review.',
    notes: 'Fast-track review for transplant coordination.',
    status: 'ACTIVE',
    createdAt: new Date().toISOString(),
  };

  const matchRequest = {
    id: 'request_7001',
    caseId: caseRecord.id,
    donorId: donor.id,
    organType: 'Kidney',
    hospitalName: hospital.name,
    createdAt: new Date().toISOString(),
    expiresAt: new Date(Date.now() + 120 * 60 * 1000).toISOString(),
    status: 'REQUEST_SENT',
  };

  const notification = {
    id: 'notif_1',
    recipientId: donor.id,
    recipientRole: 'DONOR',
    type: 'NEW_DONATION_REQUEST',
    message: 'CityCare Institute requested a kidney donation review.',
    read: false,
    createdAt: new Date().toISOString(),
  };

  state.donors.push(donor);
  state.hospitals.push(hospital);
  state.patients.push(caseRecord);
  state.requirements.push(requirement);
  state.requests.push(matchRequest);
  state.notifications.push(notification);
  state.locations.push({ id: uid('location'), donorId: donor.id, caseId: caseRecord.id, currentLatitude: donor.location.lat, currentLongitude: donor.location.lng, timestamp: donor.location.updatedAt, status: 'READY', accuracy: donor.location.accuracy });
  state.caseTimelines.push({ id: uid('timeline'), caseId: caseRecord.id, events: ['CASE_CREATED', 'DONOR_SEARCH', 'MATCH_REVIEW', 'REQUEST_SENT', 'DONOR_ACCEPTED', 'LOCATION_SHARING_ACTIVE', 'CASE_COMPLETED'], updatedAt: new Date().toISOString() });
  state.documents.push({ id: uid('doc'), donorId: donor.id, fileName: 'id-proof.pdf', fileType: 'IDENTITY', uploadedBy: 'Hospital intake', uploadedAt: new Date().toISOString(), verificationStatus: 'VERIFIED', notes: 'Simple verification reference.' });

  addAuditLog('DEMO_SEED_READY', { donorId: donor.id, hospitalId: hospital.id, caseId: caseRecord.id });
}

function bloodCompatible(recipientGroup, donorGroup) {
  const compatibilityMap = {
    'O-': ['O-', 'O+'],
    'O+': ['O+', 'O-'],
    'A-': ['A-', 'O-'],
    'A+': ['A+', 'A-', 'O+', 'O-'],
    'B-': ['B-', 'O-'],
    'B+': ['B+', 'B-', 'O+', 'O-'],
    'AB-': ['AB-', 'A-', 'B-', 'O-'],
    'AB+': ['AB+', 'AB-', 'A+', 'A-', 'B+', 'B-', 'O+', 'O-'],
  };

  return compatibilityMap[donorGroup]?.includes(recipientGroup) ?? false;
}

function haversineDistanceKm(lat1, lon1, lat2, lon2) {
  const toRad = (value) => (value * Math.PI) / 180;
  const earthRadiusKm = 6371;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
  return 2 * earthRadiusKm * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function runMatchingEngine(requirement) {
  return state.donors
    .filter((donor) => donor.verificationStatus === 'VERIFIED' && donor.isAvailable && donor.consentStatus === 'ACTIVE')
    .map((donor) => {
      const organAvailable = donor.organOptions?.includes(requirement.requiredOrgan) ?? false;
      const bloodCheck = bloodCompatible(requirement.bloodGroup, donor.bloodGroup);
      const distanceKm = haversineDistanceKm(
        12.9716,
        77.5946,
        donor.location?.lat ?? 12.9716,
        donor.location?.lng ?? 77.5946,
      );
      const travelMinutes = Math.max(15, Math.round(distanceKm * 3.5));
      const score =
        (organAvailable ? 38 : 0) +
        (bloodCheck ? 32 : 0) +
        (donor.verificationStatus === 'VERIFIED' ? 18 : 0) +
        (donor.isAvailable ? 10 : 0) +
        Math.max(0, 10 - Math.round(distanceKm / 15));

      return {
        candidate_id: donor.id,
        donorId: donor.id,
        status: organAvailable && bloodCheck && donor.verificationStatus === 'VERIFIED' ? 'POTENTIAL_MATCH' : 'HOSPITAL_REVIEW_REQUIRED',
        score,
        criteria: {
          verification: donor.verificationStatus,
          organ_available: organAvailable,
          blood_group_check: bloodCheck ? 'Compatible' : 'Needs review',
          distance_km: Number(distanceKm.toFixed(1)),
          estimated_travel_minutes: travelMinutes,
          hospital_verification: donor.hospitalVerificationStatus,
        },
        donor: {
          id: donor.id,
          fullName: donor.fullName,
          bloodGroup: donor.bloodGroup,
          city: donor.city,
          availabilityStatus: donor.availabilityStatus,
          verificationStatus: donor.verificationStatus,
        },
      };
    })
    .sort((a, b) => b.score - a.score);
}

function requireAuth(request, response, next) {
  const header = request.headers.authorization || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : null;
  if (!token) {
    return response.status(401).json({ success: false, message: 'Missing JWT token.' });
  }

  try {
    const payload = jwt.verify(token, JWT_SECRET);
    const user = state.users.find((entry) => entry.id === payload.sub);
    if (!user) {
      return response.status(401).json({ success: false, message: 'Invalid or expired token.' });
    }
    request.user = user;
    next();
  } catch (error) {
    return response.status(401).json({ success: false, message: 'Your session has expired. Please log in again.' });
  }
}

function requireRole(...roles) {
  return (request, response, next) => {
    if (!request.user || !roles.includes(request.user.role)) {
      return response.status(403).json({ success: false, message: 'You do not have permission to access this endpoint.' });
    }
    next();
  };
}

function getDonorForUser(userId) {
  return state.donors.find((donor) => donor.userId === userId) || null;
}

function getHospitalForUser(userId) {
  return state.hospitals.find((hospital) => hospital.email === state.users.find((user) => user.id === userId)?.email) || null;
}

app.use(cors());
app.use(express.json({ limit: '2mb' }));

app.get('/', (_request, response) => response.json({ name: 'DonorConnect API', status: 'online' }));

app.post('/api/auth/register', async (request, response) => {
  ensureDemoUsers();
  const { fullName, email, password, role = 'DONOR', bloodGroup, city, area, phoneNumber, gender, dateOfBirth, organOptions } = request.body;

  if (!fullName || !email || !password || !bloodGroup || !city || !area || !phoneNumber || !gender || !dateOfBirth) {
    return response.status(400).json({ success: false, message: 'Please complete all donor registration fields.' });
  }

  if (state.users.some((user) => user.email.toLowerCase() === String(email).toLowerCase())) {
    return response.status(409).json({ success: false, message: 'An account already exists for this email address.' });
  }

  const user = {
    id: uid('user'),
    name: fullName,
    email: String(email).trim().toLowerCase(),
    passwordHash: bcrypt.hashSync(String(password), 10),
    role: role === 'HOSPITAL' ? 'HOSPITAL' : 'DONOR',
    createdAt: new Date().toISOString(),
  };

  state.users.push(user);

  const donor = {
    id: uid('donor'),
    userId: user.id,
    fullName,
    dateOfBirth,
    gender,
    phoneNumber,
    email: user.email,
    bloodGroup,
    city,
    area,
    emergencyContact: request.body.emergencyContact || '+91-9000000000',
    organOptions: organOptions || ['Kidney'],
    donationType: request.body.donationType || 'LIVING',
    availabilityStatus: 'AVAILABLE',
    consentStatus: 'ACTIVE',
    verificationStatus: 'VERIFICATION_PENDING',
    hospitalVerificationStatus: 'PENDING',
    location: createDonorLocation(request.body.latitude || 12.97, request.body.longitude || 77.59, 250),
    isAvailable: true,
    compliance: { consent: true, locationSharing: false },
    verificationHistory: [{ status: 'VERIFICATION_PENDING', note: 'Awaiting hospital review.', updatedAt: new Date().toISOString() }],
    donationIntent: { status: 'PENDING', organs: organOptions || ['Kidney'], consentDate: null },
  };

  state.donors.push(donor);
  addAuditLog('DONOR_REGISTERED', { donorId: donor.id, email: user.email });

  return response.status(201).json({
    success: true,
    message: 'Registration submitted for donor verification.',
    user: safeUser(user),
    token: buildToken(user),
    donor,
  });
});

app.post('/api/auth/login', (request, response) => {
  ensureDemoUsers();
  const { email, password } = request.body;
  const user = state.users.find((entry) => entry.email.toLowerCase() === String(email || '').trim().toLowerCase());
  if (!user) {
    return response.status(401).json({ success: false, message: 'Invalid email or password.' });
  }

  const validPassword = bcrypt.compareSync(String(password || ''), user.passwordHash);
  if (!validPassword) {
    return response.status(401).json({ success: false, message: 'Invalid email or password.' });
  }

  const donor = getDonorForUser(user.id);
  const hospital = getHospitalForUser(user.id);
  addAuditLog('USER_LOGIN', { userId: user.id, role: user.role });

  return response.json({
    success: true,
    token: buildToken(user),
    user: safeUser(user),
    profile: donor || hospital || null,
  });
});

app.post('/api/auth/forgot-password', (request, response) => {
  const { email } = request.body;
  if (!email) {
    return response.status(400).json({ success: false, message: 'Email is required.' });
  }

  addAuditLog('PASSWORD_RESET_REQUEST', { email });
  return response.json({
    success: true,
    message: 'If an account matches this email, a reset link or guidance has been generated for the demo workflow.',
  });
});

app.get('/api/auth/me', requireAuth, (request, response) => {
  const profile = getDonorForUser(request.user.id) || getHospitalForUser(request.user.id) || null;
  return response.json({ success: true, user: safeUser(request.user), profile });
});

app.get('/api/donors/me', requireAuth, requireRole('DONOR'), (request, response) => {
  const donor = getDonorForUser(request.user.id);
  if (!donor) return response.status(404).json({ success: false, message: 'Donor profile not found.' });
  return response.json({ success: true, data: donor });
});

app.put('/api/donors/me', requireAuth, requireRole('DONOR'), (request, response) => {
  const donor = getDonorForUser(request.user.id);
  if (!donor) return response.status(404).json({ success: false, message: 'Donor profile not found.' });
  Object.assign(donor, request.body);
  addAuditLog('DONOR_PROFILE_UPDATED', { donorId: donor.id, userId: request.user.id });
  return response.json({ success: true, data: donor });
});

app.post('/api/donors/donation-intent', requireAuth, requireRole('DONOR'), (request, response) => {
  const donor = getDonorForUser(request.user.id);
  if (!donor) return response.status(404).json({ success: false, message: 'Donor profile not found.' });
  donor.donationIntent = {
    status: 'REGISTERED',
    organs: request.body.organs || donor.organOptions || [],
    consentDate: new Date().toISOString(),
  };
  donor.consentStatus = 'ACTIVE';
  donor.availabilityStatus = 'AVAILABLE';
  donor.lastUpdated = new Date().toISOString();
  addAuditLog('DONATION_INTENT_UPDATED', { donorId: donor.id, organs: donor.donationIntent.organs });
  return response.json({ success: true, data: donor });
});

app.get('/api/donors/verification-status', requireAuth, requireRole('DONOR'), (request, response) => {
  const donor = getDonorForUser(request.user.id);
  if (!donor) return response.status(404).json({ success: false, message: 'Donor profile not found.' });
  return response.json({ success: true, data: { status: donor.verificationStatus, hospitalVerificationStatus: donor.hospitalVerificationStatus, history: donor.verificationHistory || [] } });
});

app.get('/api/donors/requests', requireAuth, requireRole('DONOR'), (request, response) => {
  const donor = getDonorForUser(request.user.id);
  const partnerRequests = state.requests.filter((entry) => entry.donorId === donor.id);
  return response.json({ success: true, data: partnerRequests });
});

app.post('/api/donors/requests/:id/accept', requireAuth, requireRole('DONOR'), (request, response) => {
  const donor = getDonorForUser(request.user.id);
  const donationRequest = state.requests.find((entry) => entry.id === request.params.id);
  if (!donationRequest) return response.status(404).json({ success: false, message: 'Request not found.' });
  donationRequest.status = 'ACCEPTED';
  donor.verificationStatus = 'ACCEPTED';
  donor.availabilityStatus = 'MATCHED';
  donor.compliance.locationSharing = true;
  state.locations.push({ id: uid('location'), donorId: donor.id, caseId: donationRequest.caseId, currentLatitude: donor.location.lat, currentLongitude: donor.location.lng, timestamp: new Date().toISOString(), status: 'ACTIVE', accuracy: donor.location.accuracy });
  state.notifications.push({ id: uid('notif'), recipientRole: 'HOSPITAL', message: `Donor ${donor.fullName} accepted request ${donationRequest.id}.`, read: false, createdAt: new Date().toISOString() });
  addAuditLog('REQUEST_ACCEPTED', { donorId: donor.id, caseId: donationRequest.caseId, requestId: donationRequest.id });
  return response.json({ success: true, message: 'Request accepted and location sharing flow activated.', data: donationRequest });
});

app.post('/api/donors/requests/:id/decline', requireAuth, requireRole('DONOR'), (request, response) => {
  const donor = getDonorForUser(request.user.id);
  const donationRequest = state.requests.find((entry) => entry.id === request.params.id);
  if (!donationRequest) return response.status(404).json({ success: false, message: 'Request not found.' });
  donationRequest.status = 'DECLINED';
  donor.availabilityStatus = 'AVAILABLE';
  donor.verificationStatus = 'VERIFIED';
  state.notifications.push({ id: uid('notif'), recipientRole: 'HOSPITAL', message: `Donor ${donor.fullName} declined request ${donationRequest.id}.`, read: false, createdAt: new Date().toISOString() });
  addAuditLog('REQUEST_DECLINED', { donorId: donor.id, requestId: donationRequest.id, reason: request.body.reason || 'No reason provided' });
  return response.json({ success: true, message: 'Request declined and logged for hospital review.', data: donationRequest });
});

app.put('/api/donors/availability', requireAuth, requireRole('DONOR'), (request, response) => {
  const donor = getDonorForUser(request.user.id);
  donor.isAvailable = !!request.body.isAvailable;
  donor.availabilityStatus = donor.isAvailable ? 'AVAILABLE' : 'TEMPORARILY_UNAVAILABLE';
  donor.lastUpdated = new Date().toISOString();
  addAuditLog('DONOR_AVAILABILITY_UPDATED', { donorId: donor.id, isAvailable: donor.isAvailable });
  return response.json({ success: true, data: donor });
});

app.post('/api/donors/location/start', requireAuth, requireRole('DONOR'), (request, response) => {
  const donor = getDonorForUser(request.user.id);
  donor.compliance.locationSharing = true;
  donor.location.sharingStatus = 'ACTIVE';
  donor.location.updatedAt = new Date().toISOString();
  state.notifications.push({ id: uid('notif'), recipientRole: 'HOSPITAL', message: 'Donor location access has been enabled for the active case.', read: false, createdAt: new Date().toISOString() });
  addAuditLog('LOCATION_SHARING_ENABLED', { donorId: donor.id, status: 'ACTIVE' });
  return response.json({ success: true, message: 'Exact location sharing has been explicitly enabled for the active hospital case.', data: donor.location });
});

app.post('/api/donors/location/stop', requireAuth, requireRole('DONOR'), (request, response) => {
  const donor = getDonorForUser(request.user.id);
  donor.compliance.locationSharing = false;
  donor.location.sharingStatus = 'OFF';
  donor.location.updatedAt = new Date().toISOString();
  addAuditLog('LOCATION_SHARING_STOPPED', { donorId: donor.id });
  return response.json({ success: true, message: 'Location sharing was stopped for this case.', data: donor.location });
});

app.get('/api/hospitals/dashboard', requireAuth, requireRole('HOSPITAL', 'SUPER_ADMIN'), (request, response) => {
  const verifiedDonors = state.donors.filter((donor) => donor.verificationStatus === 'VERIFIED').length;
  const pendingDonors = state.donors.filter((donor) => donor.verificationStatus === 'VERIFICATION_PENDING').length;
  const activeCases = state.patients.filter((patient) => patient.status !== 'CASE_COMPLETED').length;
  const activeRequests = state.requests.filter((entry) => ['REQUEST_SENT', 'ACCEPTED', 'MATCH_REVIEW'].includes(entry.status)).length;
  const acceptedRequests = state.requests.filter((entry) => entry.status === 'ACCEPTED').length;
  const completedCases = state.patients.filter((patient) => patient.status === 'CASE_COMPLETED').length;

  return response.json({
    success: true,
    data: {
      totalRegisteredDonors: state.donors.length,
      verifiedDonors,
      pendingDonorVerification: pendingDonors,
      activePatientCases: activeCases,
      activeMatchingRequests: activeRequests,
      acceptedRequests,
      completedCases,
      averageResponseTime: '9.4 min',
      donors: state.donors,
      patients: state.patients,
    },
  });
});

app.get('/api/hospitals/donors', requireAuth, requireRole('HOSPITAL', 'SUPER_ADMIN'), (request, response) => {
  return response.json({ success: true, data: state.donors });
});

app.get('/api/hospitals/donors/:id', requireAuth, requireRole('HOSPITAL', 'SUPER_ADMIN'), (request, response) => {
  const donor = state.donors.find((entry) => entry.id === request.params.id);
  if (!donor) return response.status(404).json({ success: false, message: 'Donor not found.' });
  return response.json({ success: true, data: donor });
});

app.post('/api/hospitals/donors/:id/verify', requireAuth, requireRole('HOSPITAL', 'SUPER_ADMIN'), (request, response) => {
  const donor = state.donors.find((entry) => entry.id === request.params.id);
  if (!donor) return response.status(404).json({ success: false, message: 'Donor not found.' });
  const nextStatus = request.body.status || 'VERIFIED';
  donor.verificationStatus = nextStatus;
  donor.hospitalVerificationStatus = nextStatus === 'VERIFIED' ? 'COMPLETE' : 'REJECTED';
  donor.verificationHistory = [...(donor.verificationHistory || []), { status: nextStatus, note: request.body.note || 'Hospital verification updated.', updatedAt: new Date().toISOString() }];
  state.notifications.push({ id: uid('notif'), recipientId: donor.id, recipientRole: 'DONOR', type: nextStatus === 'VERIFIED' ? 'VERIFICATION_APPROVED' : 'VERIFICATION_REJECTED', message: nextStatus === 'VERIFIED' ? 'Your donor verification has been approved.' : 'Your donor verification requires additional information.', read: false, createdAt: new Date().toISOString() });
  addAuditLog('DONOR_VERIFICATION_UPDATED', { donorId: donor.id, status: nextStatus });
  return response.json({ success: true, data: donor });
});

app.post('/api/hospitals/donors/:id/documents', requireAuth, requireRole('HOSPITAL', 'SUPER_ADMIN'), (request, response) => {
  const donor = state.donors.find((entry) => entry.id === request.params.id);
  if (!donor) return response.status(404).json({ success: false, message: 'Donor not found.' });

  const newDocument = {
    id: uid('doc'),
    donorId: donor.id,
    fileName: request.body.fileName || 'verification.pdf',
    fileType: request.body.fileType || 'IDENTITY',
    uploadedBy: request.user.email,
    uploadedAt: new Date().toISOString(),
    verificationStatus: 'PENDING',
    notes: request.body.notes || 'Awaiting review',
  };
  state.documents.push(newDocument);
  addAuditLog('MEDICAL_DOCUMENT_UPLOADED', { donorId: donor.id, documentId: newDocument.id });
  return response.status(201).json({ success: true, data: newDocument });
});

app.get('/api/hospitals/patients', requireAuth, requireRole('HOSPITAL', 'SUPER_ADMIN'), (request, response) => {
  return response.json({ success: true, data: state.patients });
});

app.post('/api/hospitals/patients', requireAuth, requireRole('HOSPITAL', 'SUPER_ADMIN'), (request, response) => {
  const patient = {
    id: uid('case'),
    patientName: request.body.patientName,
    age: Number(request.body.age),
    gender: request.body.gender,
    bloodGroup: request.body.bloodGroup,
    requiredOrgan: request.body.requiredOrgan,
    medicalPriority: request.body.medicalPriority || 'STANDARD',
    hospitalId: request.body.hospitalId || 'hospital_4001',
    hospitalName: request.body.hospitalName || 'CityCare Institute',
    department: request.body.department || 'Transplant Unit',
    requiredBy: request.body.requiredBy || new Date().toISOString(),
    status: 'PATIENT_PREPARED',
    assignedCoordinator: request.body.assignedCoordinator || 'Transplant Coordinator',
    verificationStatus: 'CASE_APPROVED',
    createdAt: new Date().toISOString(),
  };
  state.patients.push(patient);
  addAuditLog('PATIENT_CASE_CREATED', { caseId: patient.id, patientName: patient.patientName });
  return response.status(201).json({ success: true, data: patient });
});

app.post('/api/hospitals/requirements', requireAuth, requireRole('HOSPITAL', 'SUPER_ADMIN'), (request, response) => {
  const requirement = {
    id: uid('req'),
    caseId: request.body.caseId,
    requiredOrgan: request.body.requiredOrgan,
    bloodGroup: request.body.bloodGroup,
    casePriority: request.body.casePriority || 'STANDARD',
    requiredTimeline: request.body.requiredTimeline || new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
    hospitalLocation: request.body.hospitalLocation || 'Bengaluru',
    criteria: request.body.criteria || 'Blood group and hospital-defined operational criteria.',
    notes: request.body.notes || 'Matching review in progress.',
    status: 'ACTIVE',
    createdAt: new Date().toISOString(),
  };
  state.requirements.push(requirement);
  addAuditLog('ORGAN_REQUIREMENT_CREATED', { requirementId: requirement.id, caseId: requirement.caseId });
  return response.status(201).json({ success: true, data: requirement });
});

app.post('/api/hospitals/requirements/:id/match', requireAuth, requireRole('HOSPITAL', 'SUPER_ADMIN'), (request, response) => {
  const requirement = state.requirements.find((entry) => entry.id === request.params.id);
  if (!requirement) return response.status(404).json({ success: false, message: 'Requirement not found.' });
  const results = runMatchingEngine(requirement);
  addAuditLog('MATCH_ENGINE_RUN', { requirementId: requirement.id, candidates: results.length });
  return response.json({ success: true, data: results, requirement });
});

app.post('/api/hospitals/matches/:id/request', requireAuth, requireRole('HOSPITAL', 'SUPER_ADMIN'), (request, response) => {
  const donor = state.donors.find((entry) => entry.id === request.body.donorId);
  if (!donor) return response.status(404).json({ success: false, message: 'Candidate donor not found.' });

  const requestRecord = {
    id: uid('request'),
    caseId: request.body.caseId || 'case_5001',
    donorId: donor.id,
    organType: request.body.organType || 'Kidney',
    hospitalName: request.body.hospitalName || 'CityCare Institute',
    createdAt: new Date().toISOString(),
    expiresAt: new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString(),
    status: 'REQUEST_SENT',
  };

  state.requests.push(requestRecord);
  state.notifications.push({ id: uid('notif'), recipientId: donor.id, recipientRole: 'DONOR', type: 'NEW_DONATION_REQUEST', message: `${requestRecord.hospitalName} has sent a donation request for ${requestRecord.organType}.`, read: false, createdAt: new Date().toISOString() });
  addAuditLog('DONATION_REQUEST_SENT', { donorId: donor.id, requestId: requestRecord.id, caseId: requestRecord.caseId });
  return response.status(201).json({ success: true, data: requestRecord });
});

app.get('/api/hospitals/cases/:id', requireAuth, requireRole('HOSPITAL', 'SUPER_ADMIN'), (request, response) => {
  const patient = state.patients.find((entry) => entry.id === request.params.id);
  if (!patient) return response.status(404).json({ success: false, message: 'Case not found.' });
  const timeline = state.caseTimelines.find((entry) => entry.caseId === patient.id) || { events: [] };
  return response.json({ success: true, data: { patient, timeline } });
});

app.put('/api/hospitals/cases/:id/status', requireAuth, requireRole('HOSPITAL', 'SUPER_ADMIN'), (request, response) => {
  const patient = state.patients.find((entry) => entry.id === request.params.id);
  if (!patient) return response.status(404).json({ success: false, message: 'Case not found.' });
  patient.status = request.body.status || patient.status;
  if (!state.caseTimelines.some((entry) => entry.caseId === patient.id)) {
    state.caseTimelines.push({ id: uid('timeline'), caseId: patient.id, events: [patient.status], updatedAt: new Date().toISOString() });
  } else {
    const timeline = state.caseTimelines.find((entry) => entry.caseId === patient.id);
    timeline.events = [...new Set([...(timeline.events || []), patient.status])];
    timeline.updatedAt = new Date().toISOString();
  }
  addAuditLog('CASE_STATUS_UPDATED', { caseId: patient.id, status: patient.status });
  return response.json({ success: true, data: patient });
});

app.get('/api/cases/:id/location', requireAuth, requireRole('HOSPITAL', 'DONOR', 'SUPER_ADMIN'), (request, response) => {
  const locationRecord = state.locations.find((entry) => entry.caseId === request.params.id || entry.donorId === request.params.id) || {
    currentLatitude: 12.9352,
    currentLongitude: 77.6245,
    timestamp: new Date().toISOString(),
    status: 'READY',
    accuracy: 220,
  };
  return response.json({ success: true, data: locationRecord });
});

app.post('/api/cases/:id/location/update', requireAuth, requireRole('HOSPITAL', 'DONOR', 'SUPER_ADMIN'), (request, response) => {
  const locationRecord = state.locations.find((entry) => entry.caseId === request.params.id) || {
    id: uid('location'),
    caseId: request.params.id,
    donorId: request.body.donorId || 'donor_1001',
    currentLatitude: 12.9352,
    currentLongitude: 77.6245,
    timestamp: new Date().toISOString(),
    status: 'ACTIVE',
    accuracy: 180,
  };

  locationRecord.currentLatitude = request.body.latitude ?? locationRecord.currentLatitude;
  locationRecord.currentLongitude = request.body.longitude ?? locationRecord.currentLongitude;
  locationRecord.timestamp = new Date().toISOString();
  locationRecord.accuracy = request.body.accuracy ?? locationRecord.accuracy;
  locationRecord.status = request.body.status || 'ACTIVE';

  if (request.user.role === 'DONOR') {
    const donor = getDonorForUser(request.user.id);
    donor.location = { ...donor.location, lat: locationRecord.currentLatitude, lng: locationRecord.currentLongitude, updatedAt: locationRecord.timestamp, sharingStatus: 'ACTIVE', accuracy: locationRecord.accuracy };
  }

  if (!state.locations.some((entry) => entry.caseId === request.params.id)) {
    state.locations.push(locationRecord);
  }
  addAuditLog('CASE_LOCATION_UPDATED', { caseId: request.params.id, latitude: locationRecord.currentLatitude, longitude: locationRecord.currentLongitude });
  return response.json({ success: true, data: locationRecord });
});

app.get('/api/notifications', requireAuth, (request, response) => {
  const notifications = state.notifications.filter((entry) => entry.recipientId === request.user.id || entry.recipientRole === request.user.role || !entry.recipientId);
  return response.json({ success: true, data: notifications });
});

app.put('/api/notifications/:id/read', requireAuth, (request, response) => {
  const notification = state.notifications.find((entry) => entry.id === request.params.id);
  if (!notification) return response.status(404).json({ success: false, message: 'Notification not found.' });
  notification.read = true;
  return response.json({ success: true, data: notification });
});

app.get('/api/audit/cases/:id', requireAuth, requireRole('HOSPITAL', 'SUPER_ADMIN'), (request, response) => {
  const logs = state.auditLogs.filter((entry) => entry.caseId === request.params.id || entry.donorId === request.params.id || entry.requestId === request.params.id || entry.event.includes('CASE'));
  return response.json({ success: true, data: logs });
});

app.use((error, _request, response, _next) => {
  console.error('Unhandled server error:', error);
  response.status(500).json({ success: false, message: 'Unanticipated error. Please try again.' });
});

ensureDemoUsers();
app.listen(port, () => console.log(`DonorConnect API listening on port ${port}`));

