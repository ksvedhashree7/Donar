import { useEffect, useMemo, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import './App.css';

const API_BASE = '/api';

function loadSession() {
  try {
    const raw = localStorage.getItem('donorconnect_session');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveSession(session) {
  if (!session) {
    localStorage.removeItem('donorconnect_session');
    return;
  }
  localStorage.setItem('donorconnect_session', JSON.stringify(session));
}

async function requestJson(path, options = {}, session = null) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  if (session?.token) headers.Authorization = `Bearer ${session.token}`;

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const contentType = response.headers.get('content-type') || '';
  const body = contentType.includes('application/json') ? await response.json() : await response.text();

  if (!response.ok) {
    throw new Error(body?.message || 'The request could not be completed.');
  }

  return body;
}

function ProtectedRoute({ role, children, session }) {
  if (!session?.token) {
    return <Navigate to="/login" replace />;
  }
  if (role && session.user?.role !== role) {
    return <Navigate to="/" replace />;
  }
  return children;
}

function LandingPage({ session, setSession }) {
  const navigate = useNavigate();

  return (
    <div className="page-shell landing-shell">
      <header className="site-header">
        <div className="brand-wrap">
          <div className="brand-badge">DC</div>
          <div>
            <div className="brand-name">DonorConnect</div>
            <div className="brand-subtitle">Hospital-controlled donor coordination</div>
          </div>
        </div>
        <nav className="top-links">
          <a href="#about">About</a>
          <a href="#safety">Safety</a>
          <a href="#faq">FAQ</a>
          <button type="button" onClick={() => navigate(session?.token ? '/donor' : '/login')}>{session?.token ? 'Go to dashboard' : 'Hospital login'}</button>
        </nav>
      </header>

      <main className="landing-main">
        <section className="hero-section">
          <div className="hero-copy">
            <p className="eyebrow accent">HACKATHON PROTOTYPE</p>
            <h1>Responsible organ donor matching with hospital oversight.</h1>
            <p className="hero-description">DonorConnect helps hospitals review verified donor candidates, send structured requests, track consent, and monitor logistics without exposing private data to the public.</p>
            <div className="cta-row">
              <button className="primary" type="button" onClick={() => navigate('/register')}>Register as donor</button>
              <button className="secondary" type="button" onClick={() => navigate('/login')}>Hospital login</button>
            </div>
            <div className="hero-meta">
              <span>Verified donor workflow</span>
              <span>Configurable matching rules</span>
              <span>Audit trail for every action</span>
            </div>
          </div>
          <div className="hero-panel">
            <div className="mini-card">
              <span className="tiny-label">Active cases</span>
              <strong>10</strong>
            </div>
            <div className="mini-card success">
              <span className="tiny-label">Verified donors</span>
              <strong>18</strong>
            </div>
            <div className="mini-card neutral">
              <span className="tiny-label">Average response</span>
              <strong>9.4 min</strong>
            </div>
          </div>
        </section>

        <section className="info-grid" id="about">
          <div className="info-card">
            <h3>The problem</h3>
            <p>Waiting lists, fragmented donor records, and inconsistent communication slow down donor coordination for organ cases.</p>
          </div>
          <div className="info-card">
            <h3>How it works</h3>
            <p>Hospitals create a case, configure matching criteria, review verified candidates, and send donor requests through a controlled workflow.</p>
          </div>
          <div className="info-card">
            <h3>Safety and privacy</h3>
            <p>Only authorized hospital staff can access patient details, and donor location sharing is only activated after explicit consent.</p>
          </div>
        </section>

        <section className="feature-showcase">
          <div className="section-heading">
            <p className="eyebrow accent">DEMO FLOW</p>
            <h2>From donor intent to hospital case review.</h2>
          </div>
          <div className="timeline-grid">
            <div className="step-item"><span>1</span><p>Donor registers and submits intent.</p></div>
            <div className="step-item"><span>2</span><p>Hospital verifies donor and uploads documents.</p></div>
            <div className="step-item"><span>3</span><p>Case gets matched with configured criteria.</p></div>
            <div className="step-item"><span>4</span><p>Donor receives a request and accepts or declines.</p></div>
            <div className="step-item"><span>5</span><p>Location sharing and case updates follow consent.</p></div>
            <div className="step-item"><span>6</span><p>Complete audit trail records final outcome.</p></div>
          </div>
        </section>

        <section className="faq-section" id="faq">
          <div className="section-heading">
            <p className="eyebrow accent">FAQ</p>
            <h2>Important prototype notes</h2>
          </div>
          <div className="faq-list">
            <div className="faq-item">
              <h4>Is this a medical decision system?</h4>
              <p>No. This prototype only surfaces configurable candidate lists, and final eligibility remains with authorized hospitals and medical teams.</p>
            </div>
            <div className="faq-item">
              <h4>Does donor data become public?</h4>
              <p>No. Donor and patient records stay protected with role-based access and explicit consent for location sharing.</p>
            </div>
            <div className="faq-item">
              <h4>What demo accounts are included?</h4>
              <p>Donor, hospital, and admin roles are included with pre-seeded demo credentials and sample workflows.</p>
            </div>
          </div>
        </section>

        <section className="safety-panel" id="safety">
          <div className="section-heading">
            <p className="eyebrow accent">SAFETY</p>
            <h2>Privacy-first healthcare coordination</h2>
          </div>
          <div className="safety-grid">
            <div>Role-based access and JWT tokens</div>
            <div>Configurable matching rules</div>
            <div>Explicit location consent required</div>
            <div>Readable audit logs for review</div>
          </div>
        </section>
      </main>
    </div>
  );
}

function AuthPage({ session, setSession }) {
  const navigate = useNavigate();
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ email: 'donor.demo@example.com', password: 'DonorConnect123!', role: 'DONOR' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError('');

    try {
      const payload = await requestJson('/auth/login', { method: 'POST', body: JSON.stringify(form) }, session);
      const nextSession = { token: payload.token, user: payload.user };
      saveSession(nextSession);
      setSession(nextSession);
      if (payload.user.role === 'DONOR') navigate('/donor', { replace: true });
      else if (payload.user.role === 'HOSPITAL') navigate('/hospital', { replace: true });
      else navigate('/admin', { replace: true });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-header">
          <div className="brand-badge">DC</div>
          <div>
            <p className="eyebrow accent">ACCESS PORTAL</p>
            <h2>{mode === 'login' ? 'Log in to DonorConnect' : 'Create donor account'}</h2>
          </div>
        </div>

        <div className="toggle-row">
          <button type="button" className={mode === 'login' ? 'toggle active' : 'toggle'} onClick={() => setMode('login')}>Login</button>
          <button type="button" className={mode === 'register' ? 'toggle active' : 'toggle'} onClick={() => setMode('register')}>Register</button>
        </div>

        {mode === 'register' ? (
          <RegisterForm onRegistered={(nextSession) => { saveSession(nextSession); setSession(nextSession); navigate('/donor', { replace: true }); }} />
        ) : (
          <form onSubmit={handleSubmit} className="form-stack">
            <label>
              Email
              <input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required />
            </label>
            <label>
              Password
              <input type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required />
            </label>
            <label>
              Role
              <select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>
                <option value="DONOR">Donor</option>
                <option value="HOSPITAL">Hospital / Admin</option>
                <option value="SUPER_ADMIN">Super Admin</option>
              </select>
            </label>
            {error && <div className="error-box">{error}</div>}
            <button className="primary full" type="submit" disabled={loading}>{loading ? 'Signing in...' : 'Continue'}</button>
            <small className="demo-note">Demo credentials: donor.demo@example.com / hospital.demo@example.com / admin.demo@example.com with password DonorConnect123!</small>
          </form>
        )}
      </div>
    </div>
  );
}

function RegisterForm({ onRegistered }) {
  const [form, setForm] = useState({
    fullName: 'Priya Sharma',
    email: 'new.donor@example.com',
    password: 'DonorConnect123!',
    bloodGroup: 'O+',
    city: 'Bengaluru',
    area: 'Indiranagar',
    phoneNumber: '+91-9812345670',
    gender: 'Female',
    dateOfBirth: '1991-04-12',
    donationType: 'LIVING',
    emergencyContact: '+91-9898989898',
    organOptions: ['Kidney'],
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await requestJson('/auth/register', { method: 'POST', body: JSON.stringify({ ...form, role: 'DONOR', longitude: 77.6324, latitude: 12.9719 }) });
      onRegistered({ token: response.token, user: response.user });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="form-stack" onSubmit={handleSubmit}>
      <label>Full name<input value={form.fullName} onChange={(event) => setForm({ ...form, fullName: event.target.value })} required /></label>
      <label>Email<input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required /></label>
      <label>Password<input type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /></label>
      <div className="inline-grid">
        <label>Blood group<select value={form.bloodGroup} onChange={(event) => setForm({ ...form, bloodGroup: event.target.value })}><option>O+</option><option>O-</option><option>A+</option><option>A-</option><option>B+</option><option>B-</option><option>AB+</option><option>AB-</option></select></label>
        <label>Gender<select value={form.gender} onChange={(event) => setForm({ ...form, gender: event.target.value })}><option>Female</option><option>Male</option><option>Other</option></select></label>
      </div>
      <label>Date of birth<input type="date" value={form.dateOfBirth} onChange={(event) => setForm({ ...form, dateOfBirth: event.target.value })} required /></label>
      <div className="inline-grid">
        <label>City<input value={form.city} onChange={(event) => setForm({ ...form, city: event.target.value })} required /></label>
        <label>Area<input value={form.area} onChange={(event) => setForm({ ...form, area: event.target.value })} required /></label>
      </div>
      <label>Phone number<input value={form.phoneNumber} onChange={(event) => setForm({ ...form, phoneNumber: event.target.value })} required /></label>
      <label>Emergency contact<input value={form.emergencyContact} onChange={(event) => setForm({ ...form, emergencyContact: event.target.value })} /></label>
      <label>Donation type<select value={form.donationType} onChange={(event) => setForm({ ...form, donationType: event.target.value })}><option value="LIVING">Living donor</option><option value="DECEASED_INTENT">Deceased intent</option></select></label>
      {error && <div className="error-box">{error}</div>}
      <button className="primary full" type="submit" disabled={loading}>{loading ? 'Submitting...' : 'Register donor'}</button>
    </form>
  );
}

function DonorDashboard({ session }) {
  const [profile, setProfile] = useState(null);
  const [requests, setRequests] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadDashboard() {
      try {
        const [profileData, requestData, notificationData] = await Promise.all([
          requestJson('/donors/me', {}, session),
          requestJson('/donors/requests', {}, session),
          requestJson('/notifications', {}, session),
        ]);
        setProfile(profileData.data);
        setRequests(requestData.data || []);
        setNotifications(notificationData.data || []);
      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    }

    loadDashboard();
  }, [session]);

  async function handleAction(action, requestId) {
    try {
      await requestJson(`/donors/requests/${requestId}/${action}`, { method: 'POST', body: JSON.stringify({}) }, session);
      const fresh = await requestJson('/donors/requests', {}, session);
      setRequests(fresh.data || []);
    } catch (error) {
      console.error(error);
    }
  }

  if (loading) return <div className="loading-state">Loading donor dashboard...</div>;

  return (
    <div className="dashboard-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-badge">DC</div>
          <div>
            <div className="brand-name">DonorConnect</div>
            <div className="brand-subtitle">Donor</div>
          </div>
        </div>
        <nav className="nav-menu">
          <span>Dashboard</span>
          <span>Profile</span>
          <span>Donation Intent</span>
          <span>Verification</span>
          <span>Requests</span>
          <span>Location</span>
          <span>Notifications</span>
          <span>Consent</span>
          <span>History</span>
        </nav>
      </aside>

      <main className="content-panel">
        <header className="dashboard-header">
          <div>
            <p className="eyebrow accent">DONOR DASHBOARD</p>
            <h2>{profile?.fullName || 'Donor profile'}</h2>
          </div>
          <div className="status-pill success">{profile?.verificationStatus || 'VERIFICATION_PENDING'}</div>
        </header>

        <section className="metric-grid">
          <div className="metric-card"><span>Total requests</span><strong>{requests.length}</strong></div>
          <div className="metric-card"><span>Verification</span><strong>{profile?.verificationStatus}</strong></div>
          <div className="metric-card"><span>Consent</span><strong>{profile?.consentStatus || 'ACTIVE'}</strong></div>
          <div className="metric-card"><span>Notifications</span><strong>{notifications.filter((item) => !item.read).length}</strong></div>
        </section>

        <section className="two-column-layout">
          <div className="panel-card">
            <h3>Overview</h3>
            <ul className="detail-list">
              <li><span>Blood group</span><strong>{profile?.bloodGroup}</strong></li>
              <li><span>City</span><strong>{profile?.city}</strong></li>
              <li><span>Availability</span><strong>{profile?.availabilityStatus || 'AVAILABLE'}</strong></li>
              <li><span>Location sharing</span><strong>{profile?.compliance?.locationSharing ? 'ACTIVE' : 'OFF'}</strong></li>
            </ul>
          </div>

          <div className="panel-card">
            <h3>Requests</h3>
            {requests.length === 0 ? <p className="empty-copy">No donation requests yet.</p> : requests.map((request) => (
              <div className="request-card" key={request.id}>
                <div>
                  <strong>{request.hospitalName}</strong>
                  <p>{request.organType}</p>
                </div>
                <div className="request-actions">
                  <span className="status-pill neutral">{request.status}</span>
                  {request.status === 'REQUEST_SENT' && (
                    <>
                      <button className="small primary" type="button" onClick={() => handleAction('accept', request.id)}>Accept</button>
                      <button className="small secondary" type="button" onClick={() => handleAction('decline', request.id)}>Decline</button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

function HospitalDashboard({ session }) {
  const [data, setData] = useState({ donors: [], patients: [], totalRegisteredDonors: 0, verifiedDonors: 0, pendingDonorVerification: 0, activePatientCases: 0, activeMatchingRequests: 0, acceptedRequests: 0, completedCases: 0, averageResponseTime: '0' });
  const [selectedRequirement, setSelectedRequirement] = useState({ requiredOrgan: 'Kidney', bloodGroup: 'A+', casePriority: 'HIGH', hospitalLocation: 'Bengaluru', criteria: 'Verified donor, blood-group compatibility, and travel logistics check.', notes: 'Need expedited review by transplant coordinator.' });
  const [matches, setMatches] = useState([]);

  useEffect(() => {
    async function loadDashboard() {
      const payload = await requestJson('/hospitals/dashboard', {}, session);
      setData(payload.data);
    }
    loadDashboard();
  }, [session]);

  async function runMatch() {
    const requirement = {
      ...selectedRequirement,
      caseId: 'case_5001',
      requiredTimeline: new Date(Date.now() + 48 * 60 * 60 * 1000).toISOString(),
    };
    const response = await requestJson('/hospitals/requirements', { method: 'POST', body: JSON.stringify(requirement) }, session);
    const matchResponse = await requestJson(`/hospitals/requirements/${response.data.id}/match`, { method: 'POST', body: JSON.stringify({}) }, session);
    setMatches(matchResponse.data || []);
  }

  async function sendRequest(donorId) {
    await requestJson('/hospitals/matches/request_1/request', { method: 'POST', body: JSON.stringify({ donorId, caseId: 'case_5001', organType: selectedRequirement.requiredOrgan, hospitalName: 'CityCare Institute' }) }, session);
    alert('Donation request sent.');
  }

  return (
    <div className="dashboard-shell hospital-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-badge">DC</div>
          <div>
            <div className="brand-name">DonorConnect</div>
            <div className="brand-subtitle">Hospital</div>
          </div>
        </div>
        <nav className="nav-menu">
          <span>Dashboard</span>
          <span>Donors</span>
          <span>Patients</span>
          <span>Requirements</span>
          <span>Matching</span>
          <span>Active Cases</span>
          <span>Documents</span>
        </nav>
      </aside>

      <main className="content-panel hospital-content">
        <header className="dashboard-header">
          <div><p className="eyebrow accent">HOSPITAL DASHBOARD</p><h2>Operations overview</h2></div>
          <div className="status-pill neutral">{data.activePatientCases} active cases</div>
        </header>

        <section className="metric-grid">
          <div className="metric-card"><span>Total donors</span><strong>{data.totalRegisteredDonors}</strong></div>
          <div className="metric-card"><span>Verified</span><strong>{data.verifiedDonors}</strong></div>
          <div className="metric-card"><span>Pending</span><strong>{data.pendingDonorVerification}</strong></div>
          <div className="metric-card"><span>Accepted requests</span><strong>{data.acceptedRequests}</strong></div>
        </section>

        <section className="two-column-layout hospital-form-grid">
          <div className="panel-card">
            <h3>Requirement setup</h3>
            <div className="form-stack compact-form">
              <label>Required organ<select value={selectedRequirement.requiredOrgan} onChange={(event) => setSelectedRequirement({ ...selectedRequirement, requiredOrgan: event.target.value })}><option>Kidney</option><option>Liver</option><option>Heart</option><option>Lung</option></select></label>
              <label>Blood group<select value={selectedRequirement.bloodGroup} onChange={(event) => setSelectedRequirement({ ...selectedRequirement, bloodGroup: event.target.value })}><option>A+</option><option>O+</option><option>B+</option><option>AB+</option></select></label>
              <label>Priority<select value={selectedRequirement.casePriority} onChange={(event) => setSelectedRequirement({ ...selectedRequirement, casePriority: event.target.value })}><option>HIGH</option><option>STANDARD</option><option>URGENT</option></select></label>
              <label>Hospital location<input value={selectedRequirement.hospitalLocation} onChange={(event) => setSelectedRequirement({ ...selectedRequirement, hospitalLocation: event.target.value })} /></label>
              <label>Matching criteria<textarea value={selectedRequirement.criteria} onChange={(event) => setSelectedRequirement({ ...selectedRequirement, criteria: event.target.value })} rows="3" /></label>
              <label>Notes<textarea value={selectedRequirement.notes} onChange={(event) => setSelectedRequirement({ ...selectedRequirement, notes: event.target.value })} rows="3" /></label>
              <button className="primary" type="button" onClick={runMatch}>Run matching</button>
            </div>
          </div>

          <div className="panel-card">
            <h3>Candidate donors</h3>
            {matches.length === 0 ? <p className="empty-copy">Select criteria and run a review to view verified candidates.</p> : matches.map((match) => (
              <div className="match-card" key={match.candidate_id}>
                <div className="match-head">
                  <strong>{match.donor.fullName}</strong>
                  <span className="status-pill success">{match.status}</span>
                </div>
                <p>Compatibility: {match.criteria.blood_group_check}</p>
                <p>Distance: {match.criteria.distance_km} km</p>
                <p>Travel time: {match.criteria.estimated_travel_minutes} minutes</p>
                <button className="small primary" type="button" onClick={() => sendRequest(match.donorId)}>Send donation request</button>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

function AdminDashboard({ session }) {
  const [hospitals, setHospitals] = useState([]);
  const [audit, setAudit] = useState([]);

  useEffect(() => {
    async function loadAdminData() {
      const hospitalData = await requestJson('/hospitals/donors', {}, session);
      const auditData = await requestJson('/audit/cases/case_5001', {}, session);
      setHospitals(hospitalData.data || []);
      setAudit(auditData.data || []);
    }
    loadAdminData();
  }, [session]);

  return (
    <div className="dashboard-shell admin-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-badge">DC</div>
          <div>
            <div className="brand-name">DonorConnect</div>
            <div className="brand-subtitle">Admin</div>
          </div>
        </div>
        <nav className="nav-menu">
          <span>Dashboard</span>
          <span>Hospitals</span>
          <span>Users</span>
          <span>System Configuration</span>
          <span>Audit Logs</span>
        </nav>
      </aside>

      <main className="content-panel admin-content">
        <header className="dashboard-header">
          <div><p className="eyebrow accent">SUPER ADMIN</p><h2>System overview</h2></div>
        </header>
        <section className="metric-grid">
          <div className="metric-card"><span>Donors</span><strong>{hospitals.length}</strong></div>
          <div className="metric-card"><span>Hospitals</span><strong>5</strong></div>
          <div className="metric-card"><span>Cases</span><strong>10</strong></div>
          <div className="metric-card"><span>Audit log</span><strong>{audit.length}</strong></div>
        </section>
        <section className="panel-card">
          <h3>Recent audit trail</h3>
          <ul className="audit-list">
            {audit.map((entry) => <li key={entry.id}><span>{entry.event}</span><small>{new Date(entry.timestamp).toLocaleString()}</small></li>)}
          </ul>
        </section>
      </main>
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState(loadSession());

  useEffect(() => {
    saveSession(session);
  }, [session]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage session={session} setSession={setSession} />} />
        <Route path="/login" element={<AuthPage session={session} setSession={setSession} />} />
        <Route path="/register" element={<AuthPage session={session} setSession={setSession} />} />
        <Route path="/donor" element={<ProtectedRoute role="DONOR" session={session}><DonorDashboard session={session} /></ProtectedRoute>} />
        <Route path="/hospital" element={<ProtectedRoute role="HOSPITAL" session={session}><HospitalDashboard session={session} /></ProtectedRoute>} />
        <Route path="/admin" element={<ProtectedRoute role="SUPER_ADMIN" session={session}><AdminDashboard session={session} /></ProtectedRoute>} />
      </Routes>
    </BrowserRouter>
  );
}

