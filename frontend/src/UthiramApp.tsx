import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import DonationJourneyPanel from './components/DonationJourneyPanel';
import TrackDonorSection from './components/TrackDonorSection';

type Role = 'Admin' | 'Blood Bank' | 'Donor';
type AccountMode = 'login' | 'register';
type Screen = 'Overview' | 'Requests' | 'Outreach' | 'Donors' | 'Analytics' | 'Notifications' | 'Compatibility' | 'Account';
type AlertStatus = 'Waiting' | 'Accepted' | 'Declined' | 'No response' | 'Cancelled';

type DonorAlert = {
  id: string;
  initials: string;
  blood: string;
  distance: number;
  locality: string;
  lastConfirmed: string;
  stage: number;
  status: AlertStatus;
};

type SubmittedBloodRequest = {
  id: string;
  facility: string;
  locality: string;
  blood: string;
  quantity: number;
  status: string;
};

type BloodBankRequestDecision = 'Accepted' | 'Declined';

const RequestIdContext = createContext('UTH-1024');
const ConfirmAcceptContext = createContext<(donorId: string) => void>(() => undefined);

const stageRanges = [
  { range: '0–5 km', duration: 120 },
  { range: '5–10 km', duration: 120 },
  { range: '10–15 km', duration: 120 },
  { range: '15–20 km', duration: 120 },
  { range: 'Beyond 20 km', duration: 120 },
];

const bloodGroups = ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'];
type RbcCompatibilityMap = Record<string, string[]>;

function isRbcCompatibilityMap(value: unknown): value is RbcCompatibilityMap {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const matrix = value as Record<string, unknown>;
  if (Object.keys(matrix).length !== bloodGroups.length) return false;
  return bloodGroups.every((recipientGroup) => {
    const donors = matrix[recipientGroup];
    return Array.isArray(donors)
      && new Set(donors).size === donors.length
      && donors.every((donorGroup) => typeof donorGroup === 'string' && bloodGroups.includes(donorGroup));
  });
}

const donorRbcRecipientGroups = (donorGroup: string, compatibility: RbcCompatibilityMap) =>
  bloodGroups.filter((recipientGroup) => compatibility[recipientGroup]?.includes(donorGroup));

const initialDonors: DonorAlert[] = [
  { id: 'DNR-1024', initials: 'AK', blood: 'O+', distance: 3.2, locality: 'Adyar', lastConfirmed: '12 min ago', stage: 0, status: 'Waiting' },
  { id: 'DNR-1088', initials: 'SM', blood: 'O+', distance: 4.6, locality: 'Besant Nagar', lastConfirmed: '28 min ago', stage: 0, status: 'Declined' },
  { id: 'DNR-1103', initials: 'RV', blood: 'O+', distance: 7.1, locality: 'Thiruvanmiyur', lastConfirmed: 'Today, 8:40 AM', stage: 1, status: 'Waiting' },
  { id: 'DNR-1182', initials: 'PK', blood: 'O+', distance: 8.4, locality: 'Guindy', lastConfirmed: 'Today, 9:10 AM', stage: 1, status: 'Waiting' },
  { id: 'DNR-1211', initials: 'JN', blood: 'O+', distance: 12.6, locality: 'Velachery', lastConfirmed: 'Yesterday', stage: 2, status: 'Waiting' },
  { id: 'DNR-1236', initials: 'TS', blood: 'O+', distance: 18.2, locality: 'Nungambakkam', lastConfirmed: 'Today, 7:55 AM', stage: 3, status: 'Waiting' },
];

const navItems: { label: Screen; icon: string }[] = [
  { label: 'Overview', icon: 'grid' },
  { label: 'Requests', icon: 'drop' },
  { label: 'Outreach', icon: 'radio' },
  { label: 'Donors', icon: 'users' },
  { label: 'Analytics', icon: 'chart' },
  { label: 'Notifications', icon: 'bell' },
  { label: 'Compatibility', icon: 'drop' },
];

function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, React.ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    drop: <path d="M12 3c-2.4 3.2-6 7.1-6 11a6 6 0 0 0 12 0c0-3.9-3.6-7.8-6-11Z" />,
    radio: <><circle cx="12" cy="12" r="2" /><path d="M8.5 8.5a5 5 0 0 0 0 7M15.5 8.5a5 5 0 0 1 0 7M5.7 5.7a9 9 0 0 0 0 12.6M18.3 5.7a9 9 0 0 1 0 12.6" /></>,
    users: <><circle cx="9" cy="8" r="3" /><path d="M3 20a6 6 0 0 1 12 0M16 5.5a3 3 0 0 1 0 5.8M18 14a5 5 0 0 1 3 4.6" /></>,
    chart: <><path d="M4 19V5M4 19h17" /><path d="m7 15 4-4 3 2 5-7" /></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" /></>,
    pin: <><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" /><circle cx="12" cy="10" r="2.5" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
    shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" /><path d="m9 12 2 2 4-4" /></>,
    menu: <><path d="M4 6h16M4 12h16M4 18h16" /></>,
    close: <><path d="m18 6-12 12M6 6l12 12" /></>,
    plus: <><path d="M12 5v14M5 12h14" /></>,
    search: <><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 4.5 4.5" /></>,
    alert: <><path d="M10.3 4.3 2.8 17.2A2 2 0 0 0 4.5 20h15a2 2 0 0 0 1.7-2.8L13.7 4.3a2 2 0 0 0-3.4 0Z" /><path d="M12 9v4m0 3h.01" /></>,
  };
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name] ?? paths.grid}</svg>;
}

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, '0');
  const remaining = (seconds % 60).toString().padStart(2, '0');
  return `${minutes}:${remaining}`;
}

function Status({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: string }) {
  return <span className={`uth-status uth-status-${tone}`}><i />{children}</span>;
}

function AccountAccess({ role, mode, message, onRoleChange, onModeChange, onSubmit }: { role: Role; mode: AccountMode; message: string; onRoleChange: (role: Role) => void; onModeChange: (mode: AccountMode) => void; onSubmit: () => void }) {
  const registering = mode === 'register';

  return <section className="uth-panel uth-account-panel">
    <div className="uth-panel-head">
      <div><span className="uth-section-label">DEMO ACCOUNT FLOW</span><h2>{registering ? 'Create a profile preview' : 'Sign in to a workspace'}</h2><p>This browser-only demo does not authenticate or save account details.</p></div>
    </div>
    <div className="uth-account-body">
      <div className="uth-account-modes" role="tablist" aria-label="Account action">
        <button type="button" role="tab" aria-selected={!registering} className={!registering ? 'is-active' : ''} onClick={() => onModeChange('login')}>Sign in</button>
        <button type="button" role="tab" aria-selected={registering} className={registering ? 'is-active' : ''} onClick={() => onModeChange('register')}>Register</button>
      </div>
      <form className="uth-account-form" onSubmit={(event) => { event.preventDefault(); onSubmit(); }}>
        <label>Workspace role
          <select value={role} onChange={(event) => {
            const value = event.currentTarget.value;
            if (value === 'Admin' || value === 'Blood Bank' || value === 'Donor') onRoleChange(value);
          }}>
            {!registering && <option value="Admin">Admin</option>}
            <option value="Blood Bank">Blood Bank</option>
            <option value="Donor">Donor</option>
          </select>
        </label>

        {!registering && role === 'Admin' && <>
          <label>Admin ID<input required autoComplete="username" placeholder="Fictional admin ID" /></label>
          <label>Passcode<input required type="password" autoComplete="current-password" placeholder="Admin passcode" /></label>
        </>}
        {!registering && role !== 'Admin' && <>
          <label>Email address<input required type="email" autoComplete="username" placeholder="name@example.test" /></label>
          <label>Passcode<input required type="password" autoComplete="current-password" placeholder="Account passcode" /></label>
        </>}

        {registering && role === 'Blood Bank' && <>
          <label>Hospital / blood bank name<input required autoComplete="organization" placeholder="Fictional hospital name" /></label>
          <label>Contact person<input required autoComplete="name" placeholder="Staff contact name" /></label>
          <label>Email address<input required type="email" autoComplete="email" placeholder="name@example.test" /></label>
          <label>Phone number<input required type="tel" autoComplete="tel" placeholder="Demo phone number" /></label>
          <label>Hospital address<input required autoComplete="street-address" placeholder="Fictional street and locality" /></label>
          <label>Create passcode<input required type="password" autoComplete="new-password" minLength={12} placeholder="At least 12 characters" /></label>
        </>}

        {registering && role === 'Donor' && <>
          <label>Full name<input required autoComplete="name" placeholder="Fictional donor name" /></label>
          <div className="uth-form-row">
            <label>Date of birth<input required type="date" autoComplete="bday" /></label>
            <label>Gender<select required defaultValue=""><option value="" disabled>Select gender</option><option>Woman</option><option>Man</option><option>Non-binary</option><option>Prefer not to say</option></select></label>
          </div>
          <label>Blood group<select required defaultValue=""><option value="" disabled>Select a group</option>{bloodGroups.map((group) => <option key={group}>{group}</option>)}</select></label>
          <label>Approximate locality<input required autoComplete="address-level2" placeholder="City or locality only" /></label>
          <label>Email address<input required type="email" autoComplete="email" placeholder="name@example.test" /></label>
          <label>Phone number<input required type="tel" autoComplete="tel" placeholder="Demo phone number" /></label>
          <label>Create passcode<input required type="password" autoComplete="new-password" minLength={12} placeholder="At least 12 characters" /></label>
          <label className="uth-account-consent"><input type="checkbox" /> I agree to receive emergency blood-request alerts.</label>
          <p className="uth-account-note">Weight, height, and diabetes details are not collected here or used for matching. They do not establish medical eligibility.</p>
        </>}

        {registering && <div className="uth-account-note uth-account-privacy"><Icon name="shield" size={16} />Donor contact details are not shown in lists. In a real workflow they require donor opt-in for a specific reservation, verified phone, and authorized access.</div>}
        {message && <p className="uth-account-message" role="status">{message}</p>}
        <button className="uth-button uth-button-primary uth-full-button" type="submit">{registering ? 'Submit demo registration' : 'Enter demo workspace'} <Icon name="arrow" size={16} /></button>
      </form>
      <p className="uth-account-disclaimer">Use fictional details only. This form is a visual prototype; entries are not transmitted, stored, or verified.</p>
    </div>
  </section>;
}

export default function UthiramApp() {
  const requestedRole = new URLSearchParams(window.location.search).get('role');
  const initialRole: Role = requestedRole === 'Donor' || requestedRole === 'General Donor'
    ? 'Donor'
    : requestedRole === 'Admin' ? 'Admin' : 'Blood Bank';
  const [screen, setScreen] = useState<Screen>(initialRole === 'Admin' ? 'Donors' : initialRole === 'Blood Bank' ? 'Requests' : 'Overview');
  const [role, setRole] = useState<Role>(initialRole);
  const [accountRole, setAccountRole] = useState<Role>(initialRole);
  const [accountMode, setAccountMode] = useState<AccountMode>('login');
  const [accountMessage, setAccountMessage] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const [showRequestForm, setShowRequestForm] = useState(false);
  const [confirmAccept, setConfirmAccept] = useState(false);
  const [confirmDonorId, setConfirmDonorId] = useState<string | null>(null);
  const [requestId, setRequestId] = useState('UTH-1024');
  const [requestActive, setRequestActive] = useState(true);
  const [requestStatus, setRequestStatus] = useState('Outreach active');
  const [stage, setStage] = useState(0);
  const [secondsLeft, setSecondsLeft] = useState(stageRanges[0].duration);
  const [required, setRequired] = useState(3);
  const [donors, setDonors] = useState(initialDonors);
  const [toast, setToast] = useState('');
  const [notificationsPaused, setNotificationsPaused] = useState(false);
  const [acknowledgedRequests, setAcknowledgedRequests] = useState<string[]>([]);
  const [rbcCompatibility, setRbcCompatibility] = useState<RbcCompatibilityMap | null>(null);
  const [compatibilityError, setCompatibilityError] = useState('');
  const [requestForm, setRequestForm] = useState({ facility: '', locality: '', blood: 'O+', component: 'RED_CELLS', quantity: '3', requiredBy: '' });
  const [requestDetails, setRequestDetails] = useState({ facility: 'ABC Hospital', locality: 'Adyar, Chennai', blood: 'O+' });
  const [donorSubmittedRequest, setDonorSubmittedRequest] = useState<SubmittedBloodRequest | null>(null);
  const [donorSharingActive, setDonorSharingActive] = useState(false);
  const [donorArrived, setDonorArrived] = useState(false);
  const [trackingNotifications, setTrackingNotifications] = useState<
    { type: string; title: string; time: string; tone: string }[]
  >([]);

  useEffect(() => {
    const controller = new AbortController();
    const apiUrl = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`;
    void fetch(`${apiUrl.replace(/\/$/, '')}/compatibility/rbc`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Compatibility rules could not be loaded (HTTP ${response.status}).`);
        const value: unknown = await response.json();
        if (!isRbcCompatibilityMap(value)) throw new Error('The compatibility API returned an invalid blood-group matrix.');
        setRbcCompatibility(value);
        setCompatibilityError('');
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setCompatibilityError(error instanceof Error ? error.message : 'Compatibility rules could not be loaded.');
        }
      });
    return () => controller.abort();
  }, []);

  const accepted = donors.filter((donor) => donor.status === 'Accepted').length;
  const declined = donors.filter((donor) => donor.status === 'Declined').length;
  const noResponse = donors.filter((donor) => donor.status === 'No response').length;
  const remaining = Math.max(0, required - accepted);
  const currentDonorAlerts = donors.filter((donor) => donor.stage === stage && donor.status === 'Waiting');
  const contactable = 128;
  const openAcceptConfirmation = (donorId: string) => {
    setConfirmDonorId(donorId);
    setConfirmAccept(true);
  };

  useEffect(() => {
    if (!requestActive || secondsLeft <= 0) return;
    const timer = window.setInterval(() => setSecondsLeft((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [requestActive, secondsLeft > 0]);

  useEffect(() => {
    if (requestActive && remaining === 0) stopOutreach('Enough willing donors have responded.');
  }, [requestActive, remaining]);

  useEffect(() => {
    if (requestActive && secondsLeft === 0) advanceRadius();
  }, [requestActive, secondsLeft]);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(''), 3200);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const activeRadius = stageRanges[stage]?.range ?? 'Broader area';
  const visibleNavItems = navItems.filter((item) => {
    if (role === 'Admin') return item.label === 'Donors';
    if (role === 'Donor') return ['Overview', 'Requests', 'Notifications', 'Compatibility'].includes(item.label);
    return ['Overview', 'Requests', 'Outreach'].includes(item.label);
  });
  const requestRows = useMemo(() => [
    { id: requestId, ...requestDetails, quantity: `${required} donors`, urgency: 'Urgent', status: requestStatus },
  ], [requestDetails, requestId, required, requestStatus]);

  function stopOutreach(reason: string) {
    setRequestActive(false);
    setRequestStatus(remaining === 0 ? 'Support coordinated' : 'Outreach stopped');
    setDonors((previous) => previous.map((donor) => donor.status === 'Waiting' ? { ...donor, status: 'Cancelled' } : donor));
    setToast(`${reason} All pending alerts were cancelled.`);
  }

  function advanceRadius() {
    if (!requestActive) return;
    setDonors((previous) => previous.map((donor) => donor.status === 'Waiting' && donor.stage <= stage ? { ...donor, status: 'No response' } : donor));
    const nextStage = stage + 1;
    if (nextStage >= stageRanges.length) {
      setRequestActive(false);
      setRequestStatus('Radius exhausted');
      setDonors((previous) => previous.map((donor) => donor.status === 'Waiting' ? { ...donor, status: 'Cancelled' } : donor));
      setToast('All outreach stages are complete. Coordinator follow-up is required.');
      return;
    }
    setStage(nextStage);
    setSecondsLeft(stageRanges[nextStage].duration);
    setToast(`Outreach expanded to ${stageRanges[nextStage].range}.`);
  }

  function respondToAlert(id: string, status: 'Accepted' | 'Declined') {
    const responseDonorId = status === 'Accepted' && confirmDonorId ? confirmDonorId : id;
    setDonors((previous) => previous.map((donor) => donor.id === responseDonorId ? { ...donor, status } : donor));
    setConfirmAccept(false);
    setConfirmDonorId(null);
    if (status === 'Accepted') {
      setTrackingNotifications((prev) => [
        { type: 'Live Tracking', title: `Donor accepted request ${requestId}. Active donation journey panel initialized.`, time: 'Just now', tone: 'green' },
        ...prev,
      ]);
      setToast('Response recorded. Active donation journey initialized with live tracking.');
    } else {
      setToast('Thank you for responding. No further alerts will be sent for this request.');
    }
  }

  function handleTrackingStatusChange(statusMsg: string, toastMsg: string) {
    setToast(toastMsg);
    if (statusMsg.includes('active') || statusMsg.includes('sharing')) {
      setDonorSharingActive(true);
      setTrackingNotifications((prev) => [
        { type: 'Live Tracking', title: `Donor started live location sharing for ${requestId}`, time: 'Just now', tone: 'green' },
        ...prev,
      ]);
    } else if (statusMsg.includes('paused') || statusMsg.includes('stopped')) {
      setDonorSharingActive(false);
      setTrackingNotifications((prev) => [
        { type: 'Live Tracking', title: `Donor paused live tracking for ${requestId}`, time: 'Just now', tone: 'orange' },
        ...prev,
      ]);
    } else if (statusMsg.includes('arrived')) {
      setDonorArrived(true);
      setDonorSharingActive(false);
      setTrackingNotifications((prev) => [
        { type: 'Live Tracking', title: `Donor arrived at ${requestDetails.facility} for ${requestId}!`, time: 'Just now', tone: 'green' },
        ...prev,
      ]);
    }
  }

  function simulateRequest() {
    if (role === 'Donor') {
      const submittedRequest: SubmittedBloodRequest = {
        id: `UTH-${Date.now().toString().slice(-4)}`,
        facility: requestForm.facility,
        locality: requestForm.locality,
        blood: requestForm.blood,
        quantity: Number(requestForm.quantity) || 1,
        status: 'Pending blood bank review',
      };
      setDonorSubmittedRequest(submittedRequest);
      setRequestForm({ facility: '', locality: '', blood: 'O+', component: 'RED_CELLS', quantity: '3', requiredBy: '' });
      setShowRequestForm(false);
      setScreen('Requests');
      setToast('Your blood request was submitted for blood bank review. Administrator verification is required before donor outreach.');
      return;
    }
    setDonors((previous) => previous.map((donor) => donor.status === 'Waiting' ? { ...donor, status: 'Cancelled' } : donor));
    setRequestId(`UTH-${Date.now().toString().slice(-4)}`);
    setRequired(Number(requestForm.quantity) || 3);
    setRequestDetails({ facility: requestForm.facility, locality: requestForm.locality, blood: requestForm.blood });
    setRequestStatus('Pending verification');
    setRequestActive(false);
    setStage(0);
    setSecondsLeft(stageRanges[0].duration);
    setAcknowledgedRequests([]);
    setRequestForm({ facility: '', locality: '', blood: 'O+', component: 'RED_CELLS', quantity: '3', requiredBy: '' });
    setShowRequestForm(false);
    setScreen('Requests');
    setToast('Request submitted for administrator verification. Donors have not been alerted.');
  }

  function reviewDonorRequest(decision: BloodBankRequestDecision) {
    setDonorSubmittedRequest((request) => {
      if (!request || request.status !== 'Pending blood bank review') return request;
      return {
        ...request,
        status: decision === 'Accepted'
          ? 'Accepted by blood bank — awaiting administrator verification'
          : 'Declined by blood bank',
      };
    });
    setToast(decision === 'Accepted'
      ? 'Request accepted for coordination. Administrator verification is still required before donor outreach.'
      : 'Request declined by the blood bank.');
  }

  function acknowledgeRequest(id: string) {
    setAcknowledgedRequests((previous) => previous.includes(id) ? previous : [...previous, id]);
    setToast(`${id} acknowledged for processing. Administrator verification is still required.`);
  }

  function markFulfilled() {
    setRequestActive(false);
    setRequestStatus('Fulfilled');
    setDonors((previous) => previous.map((donor) => donor.status === 'Waiting' ? { ...donor, status: 'Cancelled' } : donor));
    setToast('Requirement marked fulfilled. No additional donor alerts will be sent.');
  }

  function contentTitle() {
    if (screen === 'Account') return 'Account access';
    if (role === 'Admin') return 'Donor & blood-bank donor lists';
    if (role === 'Donor' && screen === 'Overview') return 'Your donor home';
    if (role === 'Donor' && screen === 'Requests') return 'Requests for you';
    return screen === 'Overview' ? 'Good morning, Ananya' : screen;
  }

  function switchDemoRole() {
    const nextRole = role === 'Blood Bank' ? 'Donor' : role === 'Donor' ? 'Admin' : 'Blood Bank';
    setRole(nextRole);
    setScreen(nextRole === 'Admin' ? 'Donors' : nextRole === 'Blood Bank' ? 'Requests' : 'Overview');
    setShowRequestForm(false);
    setConfirmAccept(false);
    setConfirmDonorId(null);
  }

  function openAccountAccess() {
    setAccountRole(role);
    setAccountMode('login');
    setAccountMessage('');
    setScreen('Account');
  }

  function continueInDemo(mode: AccountMode) {
    if (mode === 'register') {
      setAccountMessage('Demo only: no account was created and no personal information was saved or sent.');
      return;
    }
    setRole(accountRole);
    setScreen(accountRole === 'Admin' ? 'Donors' : accountRole === 'Blood Bank' ? 'Requests' : 'Overview');
    setToast(`Demo access only: ${accountRole} credentials are not verified or sent to the API.`);
  }

  return (
    <RequestIdContext.Provider value={requestId}>
    <ConfirmAcceptContext.Provider value={openAcceptConfirmation}>
    <div className="uth-app">
      <aside className={`uth-sidebar ${menuOpen ? 'uth-sidebar-open' : ''}`}>
        <a className="uth-brand" href="#overview" onClick={() => setScreen('Overview')} aria-label="Uthiram home">
          <span className="uth-brand-mark"><Icon name="drop" size={21} /></span>
          <span><strong>UTHIRAM</strong><small>COMMUNITY RESPONSE</small></span>
        </a>
        <div className="uth-prototype-label"><span /> Prototype workspace</div>
        <div className="uth-org-switch"><span className="uth-org-icon">A</span><span><strong>ABC Hospital</strong><small>Chennai network</small></span><span className="uth-chevron">⌄</span></div>
        <div className="uth-nav-label">WORKSPACE</div>
        <nav className="uth-nav" aria-label="Main navigation">
          {visibleNavItems.map((item) => <button key={item.label} type="button" className={`uth-nav-item ${screen === item.label ? 'is-active' : ''}`} onClick={() => { setScreen(item.label); setMenuOpen(false); }}>{item.label !== 'Requests' && <Icon name={item.icon} />}<span>{item.label}</span>{item.label === 'Requests' && <em>03</em>}</button>)}
        </nav>
        <div className="uth-sidebar-bottom">
          <div className="uth-safe-note"><Icon name="shield" size={17} /><span><strong>Privacy by design</strong><small>Approximate location only</small></span></div>
          <div className="uth-user"><span className="uth-avatar">AR</span><span><strong>Ananya Raman</strong><small>{role}</small></span><button type="button" className="uth-user-menu" title="Switch demo role" onClick={switchDemoRole}>⇄</button></div>
        </div>
      </aside>
      {menuOpen && <button className="uth-scrim" type="button" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}

      <main className="uth-main">
        <header className="uth-topbar">
          <button type="button" className="uth-icon-button uth-mobile-menu" aria-label="Open navigation" onClick={() => setMenuOpen(true)}><Icon name="menu" /></button>
          <div className="uth-crumb"><span>ABC Hospital</span><b>/</b><strong>{screen}</strong></div>
          <div className="uth-top-actions">
            <span className="uth-demo-chip"><i /> DEMO MODE</span>
            <button type="button" className="uth-account-link" onClick={openAccountAccess}>Sign in / Register</button>
            <button type="button" className="uth-icon-button uth-top-bell" aria-label="Open notifications" onClick={() => setScreen('Notifications')}><Icon name="bell" /><i /></button>
            <button type="button" className="uth-role-select" aria-label="Switch user role" onClick={switchDemoRole}><span className="uth-avatar uth-avatar-small">AR</span><span>{role}</span><b>⌄</b></button>
          </div>
        </header>

        <div className="uth-content">
          <div className="uth-heading-row">
            <div><div className="uth-eyebrow"><span className="uth-live" /> {screen === 'Account' ? 'ACCOUNT PREVIEW' : role === 'Donor' ? 'DONOR PORTAL' : role === 'Admin' ? 'ADMIN CONTROL CENTRE' : 'BLOOD BANK WORKSPACE'}</div><h1>{contentTitle()}</h1><p className="uth-subtitle">{screen === 'Account' ? 'Role-specific forms for fictional demo use. Nothing is sent or saved.' : role === 'Donor' ? 'Your availability and consent stay in your control.' : role === 'Admin' ? 'Fictional donor records only. No contact details.' : 'Submit requests and track donor responses.'}</p></div>
            <div className="uth-heading-actions">
              {screen !== 'Account' && role === 'Blood Bank' && <button className="uth-button uth-button-primary" type="button" onClick={() => setShowRequestForm(true)}><Icon name="plus" size={16} /> New request</button>}
              {screen !== 'Account' && role === 'Donor' && <button className="uth-button uth-button-primary" type="button" onClick={() => setShowRequestForm(true)}>Request blood</button>}
            </div>
          </div>

          {screen === 'Account' && <AccountAccess
            role={accountRole}
            mode={accountMode}
            message={accountMessage}
            onRoleChange={(nextRole) => { setAccountRole(nextRole); setAccountMessage(''); }}
            onModeChange={(nextMode) => {
              setAccountMode(nextMode);
              if (nextMode === 'register' && accountRole === 'Admin') setAccountRole('Blood Bank');
              setAccountMessage('');
            }}
            onSubmit={() => continueInDemo(accountMode)}
          />}

          {screen !== 'Account' && role === 'Blood Bank' && requestActive && <div className="uth-live-strip"><span className="uth-live-ring"><Icon name="radio" size={17} /></span><span><strong>Live demo outreach · {requestId}</strong><small>{activeRadius} radius · {currentDonorAlerts.length} donor alerts awaiting response</small></span><span className="uth-strip-timer"><Icon name="clock" size={15} /> {formatTime(secondsLeft)}</span><button type="button" aria-label="Open outreach" onClick={() => setScreen('Outreach')}><Icon name="arrow" size={17} /></button></div>}

          {screen === 'Overview' && <>
            {role === 'Blood Bank' && <section className="uth-metric-grid" aria-label="Community response summary">
              <article className="uth-metric"><div className="uth-metric-head"><span>Active requests</span><span className="uth-metric-icon icon-red"><Icon name="drop" size={17} /></span></div><strong>06</strong><small><i className="mini-green" /> 2 need outreach</small></article>
              <article className="uth-metric"><div className="uth-metric-head"><span>Donor profiles</span><span className="uth-metric-icon icon-green"><Icon name="users" size={17} /></span></div><strong>{contactable}</strong><small>Fictional, aggregate demo count</small></article>
              <article className="uth-metric"><div className="uth-metric-head"><span>Pending verification</span><span className="uth-metric-icon icon-orange"><Icon name="clock" size={17} /></span></div><strong>03</strong><small>Oldest request · 11 min</small></article>
              <article className="uth-metric"><div className="uth-metric-head"><span>Fulfilled today</span><span className="uth-metric-icon icon-blue"><Icon name="check" size={17} /></span></div><strong>08</strong><small>Alerts stopped automatically</small></article>
            </section>}

            {role === 'Blood Bank' && <BloodGroupAvailability />}
            {role === 'Donor' ? (
              <DonorHome
                donors={donors}
                stage={stage}
                requestActive={requestActive}
                secondsLeft={secondsLeft}
                notificationsPaused={notificationsPaused}
                compatibility={rbcCompatibility}
                setNotificationsPaused={setNotificationsPaused}
                setConfirmAccept={setConfirmAccept}
                respondToAlert={respondToAlert}
                onCompatibility={() => setScreen('Compatibility')}
                onTrackingStatusChange={handleTrackingStatusChange}
                onDonorArrived={() => setDonorArrived(true)}
              />
            ) : <>
              {accepted > 0 && (
                <TrackDonorSection
                  requestId={requestId}
                  facility={requestDetails.facility}
                  locality={requestDetails.locality}
                  isDonorSharing={donorSharingActive}
                  donorArrived={donorArrived}
                  contactShared={true}
                />
              )}
              <div className="uth-main-grid">
                <section className="uth-panel uth-requests-panel">
                  <div className="uth-panel-head"><div><span className="uth-section-label">COORDINATOR WORKLIST</span><h2>Requests needing action <span className="uth-count">03</span></h2><p>Prioritised by urgency and time remaining</p></div><button className="uth-link-button" type="button" onClick={() => setScreen('Requests')}>View all <Icon name="arrow" size={15} /></button></div>
                  <div className="uth-table-scroll"><table className="uth-table"><thead><tr><th>REQUEST</th><th>FACILITY / LOCALITY</th><th>URGENCY</th><th>STATUS</th><th /></tr></thead><tbody>{requestRows.map((request) => <tr key={request.id} onClick={() => setScreen('Outreach')}><td><strong className="uth-request-id">{request.id}</strong><span className="uth-request-blood">{request.blood} <small>· {request.quantity}</small></span></td><td><strong>{request.facility}</strong><small>{request.locality}</small></td><td><span className={`uth-urgency ${request.urgency === 'Urgent' ? 'urgent' : ''}`}><i />{request.urgency}</span></td><td><Status tone={request.status === 'Fulfilled' ? 'green' : request.status === 'Outreach active' ? 'red' : 'orange'}>{request.status}</Status></td><td><button className="uth-row-arrow" type="button" aria-label={`Open ${request.id}`} onClick={() => setScreen('Outreach')}><Icon name="arrow" size={15} /></button></td></tr>)}</tbody></table></div>
                  <div className="uth-table-foot"><span>Showing network demo requests</span><button type="button" onClick={() => setScreen('Requests')}>Request queue <Icon name="arrow" size={14} /></button></div>
                </section>
                <OutreachCard stage={stage} accepted={accepted} declined={declined} noResponse={noResponse} remaining={remaining} required={required} active={requestActive} secondsLeft={secondsLeft} onOpen={() => setScreen('Outreach')} onAdvance={advanceRadius} />
              </div>
              <div className="uth-lower-grid"><MapPanel stage={stage} /><ActivityPanel /><SafetyPanel /></div>
            </>}
          </>}

          {screen === 'Requests' && role === 'Donor' && (
            <DonorRequests
              donors={donors}
              stage={stage}
              requestActive={requestActive}
              secondsLeft={secondsLeft}
              notificationsPaused={notificationsPaused}
              submittedRequest={donorSubmittedRequest}
              onCreateRequest={() => setShowRequestForm(true)}
              setConfirmAccept={setConfirmAccept}
              respondToAlert={respondToAlert}
              onTrackingStatusChange={handleTrackingStatusChange}
              onDonorArrived={() => setDonorArrived(true)}
            />
          )}
          {screen === 'Requests' && role === 'Blood Bank' && <div className="uth-bank-requests">
            {accepted > 0 && (
              <TrackDonorSection
                requestId={requestId}
                facility={requestDetails.facility}
                locality={requestDetails.locality}
                isDonorSharing={donorSharingActive}
                donorArrived={donorArrived}
                contactShared={true}
              />
            )}
            {donorSubmittedRequest && <DonorRequestReview request={donorSubmittedRequest} onDecision={reviewDonorRequest} />}
            <RequestQueue rows={requestRows} acknowledgedRequests={acknowledgedRequests} canAcknowledge={requestStatus !== 'Pending verification'} onAcknowledge={acknowledgeRequest} onCreate={() => setShowRequestForm(true)} />
          </div>}
          {screen === 'Outreach' && role === 'Blood Bank' && (
            <>
              {accepted > 0 && (
                <TrackDonorSection
                  requestId={requestId}
                  facility={requestDetails.facility}
                  locality={requestDetails.locality}
                  isDonorSharing={donorSharingActive}
                  donorArrived={donorArrived}
                  contactShared={true}
                />
              )}
              <OutreachScreen stage={stage} secondsLeft={secondsLeft} donors={donors} accepted={accepted} declined={declined} noResponse={noResponse} remaining={remaining} required={required} active={requestActive} onAdvance={advanceRadius} onStop={() => stopOutreach('Outreach stopped by coordinator.')} onFulfil={markFulfilled} />
            </>
          )}
          {screen === 'Donors' && role === 'Admin' && <DonorDirectory donors={donors} />}
          {screen === 'Notifications' && role === 'Donor' && <NotificationsScreen trackingNotifications={trackingNotifications} />}
          {screen === 'Compatibility' && role === 'Donor' && <RbcCompatibilityPage compatibility={rbcCompatibility} error={compatibilityError} />}

          <footer className="uth-footer"><span>UTHIRAM <i>·</i> Community response prototype</span><span><Icon name="shield" size={13} /> Fictional demo data · No clinical decisions</span></footer>
        </div>
      </main>

      {showRequestForm && (role === 'Blood Bank' || role === 'Donor') && <div className="uth-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowRequestForm(false); }}><section className="uth-modal" role="dialog" aria-modal="true" aria-labelledby="request-form-title"><div className="uth-modal-head"><span className="uth-modal-icon"><Icon name="drop" /></span><button className="uth-icon-button" type="button" aria-label="Close" onClick={() => setShowRequestForm(false)}><Icon name="close" /></button></div><span className="uth-section-label">DEMO REQUEST</span><h2 id="request-form-title">{role === 'Donor' ? 'Request blood support' : 'Create a blood requirement'}</h2><p>Requests require administrator verification. Donors are not alerted before verification.</p><form onSubmit={(event) => { event.preventDefault(); simulateRequest(); }}><label>Hospital / facility<input required value={requestForm.facility} onChange={(event) => setRequestForm({ ...requestForm, facility: event.target.value })} placeholder="e.g. ABC Hospital" /></label><div className="uth-form-row"><label>Locality<input required value={requestForm.locality} onChange={(event) => setRequestForm({ ...requestForm, locality: event.target.value })} placeholder="Approximate locality" /></label><label>Blood group<select value={requestForm.blood} onChange={(event) => setRequestForm({ ...requestForm, blood: event.target.value })}>{['O+', 'O−', 'A+', 'A−', 'B+', 'B−', 'AB+', 'AB−'].map((blood) => <option key={blood}>{blood}</option>)}</select></label></div><div className="uth-form-row"><label>Blood component<select value={requestForm.component} onChange={(event) => setRequestForm({ ...requestForm, component: event.target.value })}><option value="RED_CELLS">Red cells</option><option value="PLASMA">Plasma</option><option value="PLATELETS">Platelets</option><option value="WHOLE_BLOOD">Whole blood</option><option value="OTHER">Other</option></select></label><label>Willing donors needed<input type="number" min="1" max="10" value={requestForm.quantity} onChange={(event) => setRequestForm({ ...requestForm, quantity: event.target.value })} /></label></div><label>Required by<input type="datetime-local" value={requestForm.requiredBy} onChange={(event) => setRequestForm({ ...requestForm, requiredBy: event.target.value })} /></label><div className="uth-form-warning"><Icon name="shield" size={16} /> Automated outreach is not started until the request is verified.</div><button className="uth-button uth-button-primary uth-full-button" type="submit">Submit for administrator verification <Icon name="arrow" size={16} /></button></form></section></div>}

      {confirmAccept && <div className="uth-modal-backdrop" role="presentation"><section className="uth-modal uth-confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title"><div className="uth-modal-head"><span className="uth-modal-icon green-modal-icon"><Icon name="check" /></span><button className="uth-icon-button" type="button" aria-label="Close" onClick={() => setConfirmAccept(false)}><Icon name="close" /></button></div><span className="uth-section-label">DONOR RESPONSE</span><h2 id="confirm-title">Confirm you’re willing to coordinate?</h2><p>This records your response only. It does not confirm eligibility or that a donation will take place. The hospital will follow up with next steps.</p><div className="uth-confirm-actions"><button className="uth-button uth-button-secondary" type="button" onClick={() => setConfirmAccept(false)}>Go back</button><button className="uth-button uth-button-green" type="button" onClick={() => { const waitingDonor = donors.find((donor) => donor.stage === stage && donor.status === 'Waiting'); if (waitingDonor) respondToAlert(waitingDonor.id, 'Accepted'); else setConfirmAccept(false); }}>Confirm willingness</button></div></section></div>}
      {toast && <div className="uth-toast" role="status"><Icon name="check" size={17} />{toast}<button type="button" aria-label="Dismiss" onClick={() => setToast('')}><Icon name="close" size={15} /></button></div>}
    </div>
    </ConfirmAcceptContext.Provider>
    </RequestIdContext.Provider>
  );
}

function OutreachCard({ stage, accepted, declined, noResponse, remaining, required, active, secondsLeft, onOpen, onAdvance }: { stage: number; accepted: number; declined: number; noResponse: number; remaining: number; required: number; active: boolean; secondsLeft: number; onOpen: () => void; onAdvance: () => void }) {
  const progress = Math.min(100, Math.round((accepted / required) * 100));
  return <section className="uth-panel uth-outreach-card"><div className="uth-panel-head"><div><span className="uth-section-label">RADIUS OUTREACH</span><h2>Emergency response</h2></div><Status tone={active ? 'red' : 'green'}>{active ? 'Live' : 'Stopped'}</Status></div><div className="uth-gauge-row"><div className="uth-gauge" style={{ '--gauge-progress': `${progress}%` } as React.CSSProperties}><div><strong>{accepted}<small>/{required}</small></strong><span>accepted</span></div></div><div className="uth-gauge-copy"><strong>{active ? `${remaining} more needed` : accepted >= required ? 'Support coordinated' : 'Outreach ended'}</strong><span>Willing responses</span><small><Icon name="clock" size={13} /> {active ? `${formatTime(secondsLeft)} in this radius` : 'No queued alerts'}</small></div></div><div className="uth-response-counts"><span><i className="dot-green" /> Accepted <b>{accepted}</b></span><span><i className="dot-red" /> Declined <b>{declined}</b></span><span><i className="dot-gray" /> No response <b>{noResponse}</b></span></div><div className="uth-radius-mini">{stageRanges.map((item, index) => <div className={`uth-radius-step ${index < stage ? 'completed' : index === stage && active ? 'current' : ''}`} key={item.range}><span className="uth-step-mark">{index < stage ? '✓' : index + 1}</span><span>{item.range}</span></div>)}</div><div className="uth-outreach-card-actions"><button className="uth-link-button" type="button" onClick={onOpen}>View outreach <Icon name="arrow" size={15} /></button>{active && <button className="uth-small-advance" type="button" onClick={onAdvance}>Advance demo stage</button>}</div></section>;
}

function DonorHome({
  donors,
  stage,
  requestActive,
  secondsLeft,
  notificationsPaused,
  compatibility,
  setNotificationsPaused,
  setConfirmAccept,
  respondToAlert,
  onCompatibility,
  onTrackingStatusChange,
  onDonorArrived,
}: {
  donors: DonorAlert[];
  stage: number;
  requestActive: boolean;
  secondsLeft: number;
  notificationsPaused: boolean;
  compatibility: RbcCompatibilityMap | null;
  setNotificationsPaused: (value: boolean) => void;
  setConfirmAccept: (value: boolean) => void;
  respondToAlert: (id: string, status: 'Accepted' | 'Declined') => void;
  onCompatibility: () => void;
  onTrackingStatusChange?: (status: string, toast: string) => void;
  onDonorArrived?: () => void;
}) {
  const alert = donors.find((donor) => donor.stage === stage && donor.status === 'Waiting');
  const acceptedDonor = donors.find((donor) => donor.status === 'Accepted');
  const potentialRecipients = compatibility ? donorRbcRecipientGroups('O+', compatibility) : [];
  return (
    <div className="uth-donor-home-container">
      {acceptedDonor && (
        <DonationJourneyPanel
          requestId="UTH-1024"
          bloodGroup={acceptedDonor.blood}
          facility="ABC Hospital"
          locality="Adyar, Chennai"
          onStatusChange={onTrackingStatusChange}
          onArrived={onDonorArrived}
        />
      )}
      <div className="uth-donor-home-grid">
        <section className="uth-panel uth-donor-status-panel">
          <div className="uth-panel-head"><div><span className="uth-section-label">YOUR DONOR PROFILE</span><h2>Availability & consent</h2></div><button className={`uth-toggle ${notificationsPaused ? '' : 'toggle-on'}`} type="button" role="switch" aria-checked={!notificationsPaused} onClick={() => setNotificationsPaused(!notificationsPaused)}><span /></button></div>
          <div className="uth-blood-profile"><span>O+</span><div><strong>Fictional demo group · verification simulated</strong><small>{compatibility ? `Potential red-cell recipient groups: ${potentialRecipients.join(', ')}` : 'Potential recipient groups are unavailable until compatibility rules load.'}</small></div></div>
          <button className="uth-link-button uth-compatibility-link" type="button" onClick={onCompatibility}>View blood group compatibility table <Icon name="arrow" size={15} /></button>
          <div className="uth-donor-setting"><span>Availability</span><Status tone={notificationsPaused ? 'orange' : 'green'}>{notificationsPaused ? 'Paused' : 'Available'}</Status></div>
          <div className="uth-donor-setting"><span>Emergency alerts</span><Status tone={notificationsPaused ? 'orange' : 'green'}>{notificationsPaused ? 'Paused' : 'On'}</Status></div>
          <div className="uth-donor-setting"><span>Blood bank screening</span><Status tone="neutral">Simulated in demo</Status></div>
          <div className="uth-donor-setting"><span>Contact sharing preference</span><Status tone="neutral">Per-request consent</Status></div>
          <div className="uth-donor-setting"><span>Last availability confirmation</span><small>12 minutes ago</small></div>
          <p className="uth-private-note"><Icon name="shield" size={15} /> Your phone number and exact address are never shown in public donor lists.</p>
        </section>
        {requestActive && alert && !notificationsPaused ? (
          <DonorAlertCard alert={alert} secondsLeft={secondsLeft} setConfirmAccept={setConfirmAccept} respondToAlert={respondToAlert} />
        ) : (
          <section className="uth-panel uth-no-alert">
            <span className="uth-no-alert-icon"><Icon name="check" size={21} /></span>
            <h2>{notificationsPaused ? 'Notifications are paused' : 'No active alert for you'}</h2>
            <p>{notificationsPaused ? 'You can resume emergency alerts whenever you are ready.' : 'We’ll only notify you when a verified request matches your preferences.'}</p>
            <button className="uth-button uth-button-secondary" type="button" onClick={() => setNotificationsPaused(!notificationsPaused)}>
              {notificationsPaused ? 'Resume notifications' : 'Review notification settings'}
            </button>
          </section>
        )}
        {alert && (
          <section className="uth-panel uth-participation">
            <div className="uth-panel-head"><div><span className="uth-section-label">PARTICIPATION</span><h2>Recent request activity</h2></div></div>
            <div className="uth-activity-row"><span className="uth-activity-icon"><Icon name="drop" size={16} /></span><div><strong>Emergency request near Adyar</strong><small>Response window · {formatTime(secondsLeft)} remaining</small></div><Status tone="orange">Awaiting response</Status></div>
            <div className="uth-activity-row"><span className="uth-activity-icon muted"><Icon name="check" size={16} /></span><div><strong>Availability confirmed</strong><small>Today · 12 min ago</small></div><Status tone="green">Recorded</Status></div>
          </section>
        )}
      </div>
    </div>
  );
}

function DonorRequests({
  donors,
  stage,
  requestActive,
  secondsLeft,
  notificationsPaused,
  submittedRequest,
  onCreateRequest,
  setConfirmAccept,
  respondToAlert,
  onTrackingStatusChange,
  onDonorArrived,
}: {
  donors: DonorAlert[];
  stage: number;
  requestActive: boolean;
  secondsLeft: number;
  notificationsPaused: boolean;
  submittedRequest: SubmittedBloodRequest | null;
  onCreateRequest: () => void;
  setConfirmAccept: (value: boolean) => void;
  respondToAlert: (id: string, status: 'Accepted' | 'Declined') => void;
  onTrackingStatusChange?: (status: string, toast: string) => void;
  onDonorArrived?: () => void;
}) {
  const openAlert = donors.find((donor) => donor.stage === stage && donor.status === 'Waiting');
  const acceptedDonor = donors.find((donor) => donor.status === 'Accepted');

  return (
    <div className="uth-donor-requests">
      {acceptedDonor && (
        <DonationJourneyPanel
          requestId="UTH-1024"
          bloodGroup={acceptedDonor.blood}
          facility="ABC Hospital"
          locality="Adyar, Chennai"
          onStatusChange={onTrackingStatusChange}
          onArrived={onDonorArrived}
        />
      )}
      <section className="uth-panel uth-full-panel">
        <div className="uth-panel-head">
          <div><span className="uth-section-label">YOUR BLOOD REQUESTS</span><h2>{submittedRequest ? `Request ${submittedRequest.id}` : 'Need blood support?'}</h2><p>{!submittedRequest
            ? 'Submit a blood request for blood bank review.'
            : submittedRequest.status.startsWith('Declined')
              ? 'The blood bank declined this request.'
              : submittedRequest.status.startsWith('Accepted')
                ? 'The blood bank accepted this request for coordination; administrator verification is still required.'
                : 'Your request is awaiting blood bank review.'}</p></div>
          <button className="uth-button uth-button-primary" type="button" onClick={onCreateRequest}>Request blood</button>
        </div>
      {submittedRequest ? <div className="uth-submitted-request">
        <div><span>Blood group</span><strong>{submittedRequest.blood}</strong></div>
        <div><span>Hospital / facility</span><strong>{submittedRequest.facility}</strong></div>
        <div><span>Locality</span><strong>{submittedRequest.locality}</strong></div>
        <div><span>Willing donors requested</span><strong>{submittedRequest.quantity}</strong></div>
        <div><span>Status</span><Status tone={submittedRequest.status.startsWith('Declined') ? 'orange' : submittedRequest.status.startsWith('Accepted') ? 'green' : 'orange'}>{submittedRequest.status}</Status></div>
        <p>{submittedRequest.status.startsWith('Accepted')
          ? 'The blood bank accepted the request for coordination. Administrator verification is still required before donor outreach.'
          : submittedRequest.status.startsWith('Declined')
            ? 'The blood bank declined this request. Contact the facility through an appropriate channel if you need further help.'
            : 'The request is awaiting blood bank review. Donors are not alerted until administrator verification.'} This demo status is not connected to the API.</p>
      </div> : <p className="uth-donor-request-empty">Your submitted blood request will appear here.</p>}
    </section>
    <section className="uth-panel uth-full-panel">
      <div className="uth-panel-head"><div><span className="uth-section-label">DONOR ALERTS</span><h2>{notificationsPaused ? 'Alerts are paused' : 'Requests for you'}</h2><p>{notificationsPaused ? 'Resume alerts when you are ready to receive requests.' : 'Respond to verified requests sent to you.'}</p></div></div>
      {requestActive && openAlert && !notificationsPaused
        ? <div className="uth-donor-alert-slot"><DonorAlertCard alert={openAlert} secondsLeft={secondsLeft} setConfirmAccept={setConfirmAccept} respondToAlert={respondToAlert} /></div>
        : <p className="uth-donor-request-empty">{notificationsPaused ? 'Resume notifications when you are ready.' : 'No active alert needs a response.'}</p>}
    </section>
  </div>
  );
}

function RbcCompatibilityPage({ compatibility, error }: { compatibility: RbcCompatibilityMap | null; error: string }) {
  if (!compatibility) {
    return <section className="uth-panel uth-compatibility-panel" aria-live="polite">
      <div className="uth-panel-head"><div><span className="uth-section-label">RED BLOOD CELL (RBC) ONLY</span><h2>Blood group compatibility</h2></div></div>
      <p className={error ? 'uth-compatibility-error' : 'uth-compatibility-note'} role={error ? 'alert' : 'status'}>{error || 'Loading compatibility rules from the backend…'}</p>
    </section>;
  }
  return <section className="uth-panel uth-compatibility-panel">
    <div className="uth-panel-head"><div><span className="uth-section-label">RED BLOOD CELL (RBC) ONLY</span><h2>Blood group compatibility</h2><p>Rows are recipients; columns are donor groups.</p></div></div>
    <div className="uth-compatibility-scroll" role="region" aria-label="Red blood cell compatibility table; scroll horizontally to view all donor groups" tabIndex={0}>
      <table className="uth-compatibility-table">
        <caption>Potential red-cell donor blood groups by recipient group</caption>
        <thead><tr><th scope="col">Recipient \ Donor</th>{bloodGroups.map((group) => <th scope="col" key={group}>{group}</th>)}</tr></thead>
        <tbody>{bloodGroups.map((recipientGroup) => <tr key={recipientGroup}><th scope="row">{recipientGroup}</th>{bloodGroups.map((donorGroup) => {
          const compatible = compatibility[recipientGroup]?.includes(donorGroup) ?? false;
          return <td key={donorGroup} aria-label={`${recipientGroup} recipient, ${donorGroup} donor: ${compatible ? 'potentially compatible red cells' : 'not compatible'}`}>{compatible ? '✓' : '—'}</td>;
        })}</tr>)}</tbody>
      </table>
    </div>
    <p className="uth-compatibility-legend"><strong>Legend:</strong> ✓ Potentially compatible red-cell group · — Not compatible under this general table</p>
    <p className="uth-compatibility-note">This table shows general red blood cell compatibility. Actual donation and transfusion suitability must be confirmed by qualified blood-bank professionals.</p>
    <p className="uth-compatibility-note">This table does not apply to plasma, platelets, whole blood, or other components. Unknown or unverified donor groups are not used to create notifications.</p>
  </section>;
}

function DonorAlertCard({ alert, secondsLeft, setConfirmAccept, respondToAlert }: { alert: DonorAlert; secondsLeft: number; setConfirmAccept: (value: boolean) => void; respondToAlert: (id: string, status: 'Accepted' | 'Declined') => void }) {
  const openAcceptConfirmation = useContext(ConfirmAcceptContext);
  return <section className="uth-emergency-card"><div className="uth-emergency-top"><span className="uth-emergency-tag"><i /> URGENT BLOOD REQUIREMENT</span><span className="uth-response-time"><Icon name="clock" size={15} /> {formatTime(secondsLeft)}</span></div><div className="uth-emergency-blood">O+ <span>BLOOD NEEDED</span></div><div className="uth-emergency-hospital"><strong>ABC Hospital</strong><span><Icon name="pin" size={15} /> 3.2 km away · Adyar</span></div><div className="uth-needed-by"><span>REQUIRED BY</span><strong>Today, 10:30 PM</strong></div><p>Can you help coordinate with the hospital?</p><div className="uth-alert-actions"><button type="button" className="uth-alert-accept" onClick={() => { setConfirmAccept(true); openAcceptConfirmation(alert.id); }}><Icon name="check" size={17} /> ACCEPT</button><button type="button" className="uth-alert-decline" onClick={() => respondToAlert(alert.id, 'Declined')}>DECLINE</button></div><small className="uth-alert-footnote">Your response is not confirmation of medical eligibility or donation.</small></section>;
}

function RequestQueue({ rows, acknowledgedRequests, canAcknowledge, onAcknowledge, onCreate }: { rows: { id: string; facility: string; locality: string; blood: string; quantity: string; urgency: string; status: string }[]; acknowledgedRequests: string[]; canAcknowledge: boolean; onAcknowledge: (id: string) => void; onCreate: () => void }) {
  return <section className="uth-panel uth-full-panel"><div className="uth-panel-head"><div><span className="uth-section-label">BLOOD BANK REQUESTS</span><h2>Request queue</h2><p>Acknowledge requests for processing. Verification remains administrator-only.</p></div><button className="uth-button uth-button-primary" type="button" onClick={onCreate}><Icon name="plus" size={16} /> New request</button></div><div className="uth-table-scroll"><table className="uth-table uth-large-table"><thead><tr><th>REQUEST</th><th>FACILITY</th><th>LOCALITY</th><th>URGENCY</th><th>STATUS</th><th>ACTION</th></tr></thead><tbody>{rows.map((row) => { const acknowledged = acknowledgedRequests.includes(row.id); return <tr key={row.id}><td><strong className="uth-request-id">{row.id}</strong><span className="uth-request-blood">{row.blood} · {row.quantity}</span></td><td>{row.facility}</td><td>{row.locality}</td><td><span className={`uth-urgency ${row.urgency === 'Urgent' ? 'urgent' : ''}`}><i />{row.urgency}</span></td><td><Status tone={row.status === 'Fulfilled' ? 'green' : row.status === 'Outreach active' ? 'red' : 'orange'}>{row.status}</Status></td><td><button className="uth-button uth-button-secondary" type="button" disabled={!canAcknowledge || acknowledged} onClick={() => onAcknowledge(row.id)}>{acknowledged ? 'Acknowledged' : canAcknowledge ? 'Acknowledge' : 'Awaiting verification'}</button></td></tr>; })}</tbody></table></div></section>;
}

function DonorRequestReview({ request, onDecision }: { request: SubmittedBloodRequest; onDecision: (decision: BloodBankRequestDecision) => void }) {
  const pending = request.status === 'Pending blood bank review';
  return <section className="uth-panel uth-full-panel uth-donor-review">
    <div className="uth-panel-head">
      <div><span className="uth-section-label">DONOR-SUBMITTED REQUEST</span><h2>Request {request.id}</h2><p>Review this request and accept or decline coordination. Administrator verification is still required before outreach.</p></div>
    </div>
    <div className="uth-donor-review-details">
      <div><span>Blood group</span><strong>{request.blood}</strong></div>
      <div><span>Facility</span><strong>{request.facility}</strong></div>
      <div><span>Locality</span><strong>{request.locality}</strong></div>
      <div><span>Donors requested</span><strong>{request.quantity}</strong></div>
      <div><span>Review status</span><Status tone={request.status.startsWith('Accepted') ? 'green' : 'orange'}>{request.status}</Status></div>
      {pending && <div className="uth-donor-review-actions">
        <button className="uth-button uth-button-danger-quiet" type="button" onClick={() => onDecision('Declined')}>Decline request</button>
        <button className="uth-button uth-button-green" type="button" onClick={() => onDecision('Accepted')}>Accept for coordination</button>
      </div>}
    </div>
    <p className="uth-donor-review-note">Accepting is not request verification and does not start donor outreach. Only an administrator can verify the request.</p>
  </section>;
}

function BloodGroupAvailability() {
  const availability = [
    { group: 'O-', profiles: 5, verified: 3 },
    { group: 'O+', profiles: 32, verified: 24 },
    { group: 'A-', profiles: 8, verified: 6 },
    { group: 'A+', profiles: 27, verified: 20 },
    { group: 'B-', profiles: 6, verified: 4 },
    { group: 'B+', profiles: 21, verified: 15 },
    { group: 'AB-', profiles: 4, verified: 3 },
    { group: 'AB+', profiles: 25, verified: 17 },
  ];

  return <section className="uth-panel uth-availability-panel">
    <div className="uth-panel-head"><div><span className="uth-section-label">FICTIONAL DEMO COUNTS</span><h2>Donor profiles by blood group</h2><p>Aggregate profiles only; not a donor contact list.</p></div></div>
    <div className="uth-table-scroll">
      <table className="uth-availability-table">
        <thead><tr><th scope="col">Blood group</th><th scope="col">Profiles marked available</th><th scope="col">Group verification recorded</th></tr></thead>
        <tbody>{availability.map((item) => <tr key={item.group}><th scope="row">{item.group}</th><td>{item.profiles}</td><td>{item.verified}</td></tr>)}</tbody>
      </table>
    </div>
    <p className="uth-availability-note">Counts are illustrative, not connected to the API, and do not establish donor eligibility or transfusion suitability. Contact details are shared only for a specific reservation after donor opt-in, phone verification, and authorization.</p>
  </section>;
}

function OutreachScreen({ stage, secondsLeft, donors, accepted, declined, noResponse, remaining, required, active, onAdvance, onStop, onFulfil }: { stage: number; secondsLeft: number; donors: DonorAlert[]; accepted: number; declined: number; noResponse: number; remaining: number; required: number; active: boolean; onAdvance: () => void; onStop: () => void; onFulfil: () => void }) {
  return <div className="uth-outreach-page"><div className="uth-page-top"><div><span className="uth-section-label">UTH-1024 · O+ · ABC HOSPITAL · ADYAR</span><h2>Emergency outreach</h2><p>Required: {required} willing donors <i>·</i> Current radius: {stageRanges[stage]?.range ?? '25 km'} <i>·</i> Coordinator: Ananya Raman</p></div><Status tone={active ? 'red' : 'green'}>{active ? 'Outreach active' : 'Outreach stopped'}</Status></div><div className="uth-outreach-layout"><section className="uth-panel uth-outreach-detail"><div className="uth-outreach-summary"><div><span className="uth-section-label">CURRENT RADIUS</span><strong>{stageRanges[stage]?.range ?? '25 km'}</strong><small>{active ? `${formatTime(secondsLeft)} remaining in this stage` : 'No new alerts will be sent'}</small></div><div className="uth-summary-count"><strong>{accepted}<span> / {required}</span></strong><small>Willing responses · {remaining} remaining</small></div></div><div className="uth-stage-list">{stageRanges.map((item, index) => <div className={`uth-stage-row ${index < stage ? 'stage-done' : index === stage && active ? 'stage-active' : ''}`} key={item.range}><span className="uth-stage-number">{index < stage ? <Icon name="check" size={14} /> : index + 1}</span><div className="uth-stage-info"><strong>{item.range}</strong><small>{index < stage ? 'Stage complete' : index === stage && active ? 'Alerting matching donors' : 'Waiting for previous stage'}</small></div><span className="uth-stage-timer">{index === stage && active ? formatTime(secondsLeft) : index < stage ? 'Complete' : '—'}</span><div className="uth-stage-track"><span style={{ width: index < stage ? '100%' : index === stage && active ? `${Math.max(4, 100 - (secondsLeft / item.duration * 100))}%` : '0%' }} /></div></div>)}</div><div className="uth-outreach-counts"><div><span>Accepted</span><strong className="green-text">{accepted}</strong></div><div><span>Declined</span><strong className="red-text">{declined}</strong></div><div><span>No response</span><strong>{noResponse}</strong></div><div><span>Remaining</span><strong>{remaining}</strong></div></div><div className="uth-outreach-actions">{active && <><button className="uth-button uth-button-secondary" type="button" onClick={onAdvance}>Advance radius now</button><button className="uth-button uth-button-danger-quiet" type="button" onClick={onStop}>Stop outreach</button></>}{accepted > 0 && <button className="uth-button uth-button-green" type="button" onClick={onFulfil}>Record fulfilment</button>}</div>{!active && <div className="uth-stopped-note"><Icon name="shield" size={17} /><span><strong>OUTREACH STOPPED</strong><small>Requirement has been marked fulfilled or outreach has ended. No additional donor alerts will be sent.</small></span></div>}</section><section className="uth-panel uth-matched-donors"><div className="uth-panel-head"><div><span className="uth-section-label">MATCHED BY RECORDED PREFERENCES</span><h2>Donor responses <span className="uth-count">{donors.length}</span></h2><p>Approximate locality shown; phone numbers stay private</p></div></div><div className="uth-donor-list">{donors.map((donor) => <div className="uth-donor-list-item" key={donor.id}><span className="uth-avatar donor-initials">{donor.initials}</span><div className="uth-donor-list-copy"><strong>{donor.id}</strong><small><span>{donor.blood} matches</span><i />{donor.distance} km · {donor.locality}</small><small>Availability confirmed {donor.lastConfirmed}</small></div><div className="uth-donor-response"><Status tone={donor.status === 'Accepted' ? 'green' : donor.status === 'Declined' ? 'orange' : donor.status === 'No response' ? 'neutral' : donor.status === 'Cancelled' ? 'neutral' : 'blue'}>{donor.status}</Status></div></div>)}</div><div className="uth-match-note"><Icon name="shield" size={15} /><span>Rule-based outreach match only. Blood group matching does not indicate clinical eligibility. Donors—not staff—submit alert responses.</span></div></section></div></div>;
}

function MapPanel({ stage }: { stage: number }) {
  return <section className="uth-panel uth-map-panel"><div className="uth-panel-head"><div><span className="uth-section-label">APPROXIMATE COVERAGE</span><h2>Radius map</h2><p>Fictional donor clusters around ABC Hospital</p></div><button className="uth-link-button" type="button">Localities <span>⌄</span></button></div><div className="uth-map"><div className="uth-map-street street-one" /><div className="uth-map-street street-two" /><div className="uth-map-street street-three" /><div className="uth-map-water" /><div className={`uth-map-ring ring-one ${stage >= 0 ? 'ring-on' : ''}`} /><div className={`uth-map-ring ring-two ${stage >= 1 ? 'ring-on' : ''}`} /><div className={`uth-map-ring ring-three ${stage >= 2 ? 'ring-on' : ''}`} /><div className={`uth-map-ring ring-four ${stage >= 3 ? 'ring-on' : ''}`} /><span className="uth-map-center"><Icon name="drop" size={17} /></span><span className="uth-map-label label-center">ABC Hospital</span><span className="uth-map-cluster cluster-a">12</span><span className="uth-map-cluster cluster-b">08</span><span className="uth-map-cluster cluster-c">21</span><span className="uth-map-cluster cluster-d">17</span><span className="uth-map-locality loc-a">Adyar</span><span className="uth-map-locality loc-b">Guindy</span><span className="uth-map-locality loc-c">Velachery</span><span className="uth-map-locality loc-d">T. Nagar</span></div><div className="uth-map-legend"><span><i className="map-active" /> Active radius</span><span><i className="map-cluster" /> Approximate donor cluster</span><span>Donor addresses hidden</span></div></section>;
}

function ActivityPanel() {
  return <section className="uth-panel uth-activity-panel"><div className="uth-panel-head"><div><span className="uth-section-label">RECENT UPDATES</span><h2>Coordination activity</h2></div><button className="uth-icon-button" type="button" aria-label="View all notifications"><Icon name="arrow" size={16} /></button></div><div className="uth-activity-list"><div className="uth-activity-row"><span className="activity-bullet bullet-green" /><div><strong>Request verified by coordinator</strong><small>UTH-1024 · Ananya Raman · 2 min ago</small></div></div><div className="uth-activity-row"><span className="activity-bullet bullet-orange" /><div><strong>Donor declined alert</strong><small>UTH-1024 · DNR-1088 · 1 min ago</small></div></div><div className="uth-activity-row"><span className="activity-bullet bullet-red" /><div><strong>Stage 1 outreach started</strong><small>0–5 km radius · 6 alerts queued</small></div></div></div></section>;
}

function SafetyPanel() {
  return <aside className="uth-safety-panel"><span className="uth-safety-icon"><Icon name="shield" size={19} /></span><span className="uth-section-label">CLINICAL BOUNDARY</span><h2>Coordination support,<br />not a medical decision.</h2><p>Final donor eligibility, blood compatibility, screening and collection remain with the authorised hospital or blood bank.</p><span className="uth-safety-link">All information is fictional demo data</span></aside>;
}

function DonorDirectory({ donors }: { donors: DonorAlert[] }) {
  return <section className="uth-panel uth-full-panel"><div className="uth-panel-head"><div><span className="uth-section-label">DONOR & BLOOD BANK DONOR LISTS</span><h2>Donor data</h2><p>Fictional donor records for administrator and blood-bank coordination. No contact details.</p></div></div><div className="uth-donor-directory">{donors.map((donor) => <article className="uth-directory-card" key={donor.id}><span className="uth-avatar donor-initials">{donor.initials}</span><div><strong>{donor.id}</strong><small>{donor.blood} · {donor.locality}</small></div><Status tone={donor.status === 'Accepted' ? 'green' : donor.status === 'Declined' ? 'orange' : 'blue'}>{donor.status === 'Waiting' ? 'Contactable' : donor.status}</Status><span className="uth-directory-distance">{donor.distance} km approx.</span></article>)}</div><p className="uth-directory-foot"><Icon name="shield" size={15} /> Approximate locality only. Donor responses are willingness to coordinate, not medical approval.</p></section>;
}

function NotificationsScreen({ trackingNotifications = [] }: { trackingNotifications?: { type: string; title: string; time: string; tone: string }[] }) {
  const baseNotifications = [
    { type: 'Emergency', title: 'Emergency request near you · O+ required', time: 'Just now', tone: 'red' },
    { type: 'Request updates', title: 'Request UTH-1024 has been verified', time: '2 min ago', tone: 'green' },
    { type: 'Availability', title: 'Please confirm your donor availability', time: 'Yesterday', tone: 'orange' },
    { type: 'Request updates', title: 'Request UTH-1017 has been fulfilled', time: 'Yesterday', tone: 'green' },
  ];
  const notifications = [...trackingNotifications, ...baseNotifications];
  return <section className="uth-panel uth-full-panel"><div className="uth-panel-head"><div><span className="uth-section-label">YOUR INBOX</span><h2>Notifications</h2><p>Request updates and consent-based emergency messages</p></div><button className="uth-link-button" type="button">Mark all read</button></div><div className="uth-notification-list">{notifications.map((item) => <article className="uth-notification-item" key={item.title}><span className={`uth-notification-icon notice-${item.tone}`}><Icon name={item.type === 'Emergency' ? 'alert' : item.type === 'Availability' ? 'clock' : 'check'} size={17} /></span><div><span className="uth-notification-category">{item.type}</span><strong>{item.title}</strong><small>{item.time} · Demo notification</small></div><button type="button" className="uth-notice-dismiss" aria-label="Dismiss notification"><Icon name="close" size={15} /></button></article>)}</div></section>;
}