import { useState } from 'react';

type IconName = 'overview' | 'matches' | 'recipients' | 'coordination' | 'activity' | 'search' | 'bell' | 'arrow' | 'filter' | 'clock' | 'pin' | 'chevron' | 'shield' | 'menu';

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, React.ReactNode> = {
    overview: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    matches: <><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10Z" /><path d="M8.5 12h7" /></>,
    recipients: <><circle cx="9" cy="8" r="3" /><path d="M3 20a6 6 0 0 1 12 0M16 5.5a3 3 0 0 1 0 5.8M18 14a5 5 0 0 1 3 4.6" /></>,
    coordination: <><path d="M8 12h8M12 8v8" /><circle cx="12" cy="12" r="9" /></>,
    activity: <><path d="M3 12h4l3-8 4 16 3-8h4" /></>,
    search: <><circle cx="10.8" cy="10.8" r="6.8" /><path d="m16 16 4.5 4.5" /></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" /></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
    filter: <><path d="M4 6h16M7 12h10M10 18h4" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    pin: <><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" /><circle cx="12" cy="10" r="2.5" /></>,
    chevron: <path d="m9 18 6-6-6-6" />,
    shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" /><path d="m9 12 2 2 4-4" /></>,
    menu: <><path d="M4 6h16M4 12h16M4 18h16" /></>,
  };

  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

const navigation: { label: string; icon: IconName; count?: string }[] = [
  { label: 'Overview', icon: 'overview' },
  { label: 'Potential matches', icon: 'matches', count: '03' },
  { label: 'Recipients', icon: 'recipients' },
  { label: 'Coordination', icon: 'coordination' },
  { label: 'Activity log', icon: 'activity' },
];

const requests = [
  { organ: 'Kidney', blood: 'O+', place: 'Chennai', urgency: 'High', id: 'REQ-2048', status: 'Review needed', tone: 'amber' },
  { organ: 'Liver', blood: 'A+', place: 'Chennai', urgency: 'Routine', id: 'REQ-2042', status: 'Matching', tone: 'green' },
  { organ: 'Cornea', blood: 'AB+', place: 'Coimbatore', urgency: 'Routine', id: 'REQ-2039', status: 'Review needed', tone: 'amber' },
];

export default function App() {
  const [activePage, setActivePage] = useState('Overview');
  const [menuOpen, setMenuOpen] = useState(false);
  const [showAllRequests, setShowAllRequests] = useState(false);

  return (
    <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
        <a className="brand" href="#overview" aria-label="Kindred home">
          <span className="brand-mark"><span /></span>
          <span className="brand-name">kindred<span>.</span><small>TRANSPLANT NETWORK</small></span>
        </a>

        <div className="workspace-label">WORKSPACE</div>
        <button className="workspace-switcher" type="button">
          <span className="hospital-monogram">D</span>
          <span className="workspace-copy"><strong>Demo Transplant Center</strong><small>Hospital workspace</small></span>
          <Icon name="chevron" size={15} />
        </button>

        <div className="nav-label">WORKSPACE</div>
        <nav className="main-nav" aria-label="Main navigation">
          {navigation.map((item) => (
            <button key={item.label} className={`nav-item ${activePage === item.label ? 'active' : ''}`} onClick={() => setActivePage(item.label)} type="button">
              <Icon name={item.icon} size={18} />
              <span>{item.label}</span>
              {item.count && <span className="nav-count">{item.count}</span>}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="sandbox-card"><span className="sandbox-dot" /><div><strong>Sandbox environment</strong><small>All records are mock data</small></div></div>
          <button className="profile-button" type="button">
            <span className="avatar avatar-small">AR</span>
            <span className="profile-copy"><strong>Dr. Ananya Raman</strong><small>Transplant coordinator</small></span>
            <Icon name="chevron" size={15} />
          </button>
        </div>
      </aside>

      <main className="main-area" id="overview">
        <header className="topbar">
          <button className="mobile-menu icon-button" aria-label="Toggle navigation" onClick={() => setMenuOpen(!menuOpen)} type="button"><Icon name="menu" /></button>
          <div className="breadcrumbs"><span>Demo Transplant Center</span><Icon name="chevron" size={14} /><strong>{activePage}</strong></div>
          <div className="topbar-actions">
            <label className="search-box"><Icon name="search" size={17} /><input aria-label="Search records" placeholder="Search records" /><kbd>⌘ K</kbd></label>
            <button className="icon-button notification-button" aria-label="Notifications" type="button"><Icon name="bell" size={19} /><i /></button>
            <span className="avatar avatar-top">AR</span>
          </div>
        </header>

        <div className="content-wrap">
          <section className="welcome-row">
            <div>
              <div className="eyebrow"><span className="live-dot" /> HOSPITAL COORDINATION</div>
              <h1>{activePage === 'Overview' ? 'Good morning, Dr. Raman' : activePage}</h1>
              <p className="welcome-subtitle">Here’s the latest across your transplant coordination workspace.</p>
            </div>
            <div className="date-chip"><span className="date-icon">30</span><span>Wednesday, September 30, 2026</span></div>
          </section>

          <section className="metric-grid" aria-label="Workspace summary">
            <article className="metric-card">
              <div className="metric-top"><span>Active requirements</span><span className="metric-icon icon-sage"><Icon name="recipients" size={17} /></span></div>
              <div className="metric-number">06</div><div className="metric-foot"><span className="metric-note">Across 3 hospitals</span><span className="trend-neutral">Mock data</span></div>
            </article>
            <article className="metric-card">
              <div className="metric-top"><span>Awaiting review</span><span className="metric-icon icon-peach"><Icon name="clock" size={17} /></span></div>
              <div className="metric-number">03</div><div className="metric-foot"><span className="metric-note">Potential matches</span><span className="trend-amber">Needs attention</span></div>
            </article>
            <article className="metric-card">
              <div className="metric-top"><span>Open coordination</span><span className="metric-icon icon-blue"><Icon name="coordination" size={17} /></span></div>
              <div className="metric-number">02</div><div className="metric-foot"><span className="metric-note">Consent-based cases</span><span className="trend-neutral">Mock data</span></div>
            </article>
            <article className="metric-card metric-card-note">
              <span className="note-icon"><Icon name="shield" size={17} /></span>
              <div><strong>Review stays human</strong><p>Every potential match needs a clinician’s review.</p></div>
              <Icon name="arrow" size={17} />
            </article>
          </section>

          <div className="dashboard-grid">
            <section className="panel requests-panel">
              <div className="panel-heading">
                <div><div className="section-kicker">WORKLIST</div><h2>Active requirements <span className="heading-count">03</span></h2><p>Prioritized requests from your hospital network</p></div>
                <button className="text-button" type="button" onClick={() => setShowAllRequests(!showAllRequests)}>{showAllRequests ? 'Show fewer' : 'View all'} <Icon name="arrow" size={15} /></button>
              </div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>REQUIREMENT</th><th>HOSPITAL</th><th>URGENCY</th><th>STATUS</th><th><span className="sr-only">Open requirement</span></th></tr></thead>
                  <tbody>{(showAllRequests ? [...requests, ...requests] : requests).map((request, index) => (
                    <tr key={`${request.id}-${index}`}>
                      <td><div className="requirement-cell"><span className={`organ-icon organ-${request.organ.toLowerCase()}`}>{request.organ === 'Kidney' ? 'K' : request.organ === 'Liver' ? 'L' : 'C'}</span><span><strong>{request.organ} <em>{request.blood}</em></strong><small>{request.id}</small></span></div></td>
                      <td><span className="hospital-cell">{index === 0 ? 'Demo Transplant Center' : request.place}</span><small className="table-secondary">{request.place}</small></td>
                      <td><span className={`urgency ${request.urgency === 'High' ? 'urgency-high' : ''}`}><i />{request.urgency}</span></td>
                      <td><span className={`status-pill ${request.tone}`}><i />{request.status}</span></td>
                      <td><button className="row-arrow" type="button" aria-label={`Open ${request.id}`}><Icon name="chevron" size={16} /></button></td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
              <div className="table-footer"><span>Showing {showAllRequests ? '6' : '3'} sample requirements</span><button className="filter-button" type="button"><Icon name="filter" size={15} /> Filter</button></div>
            </section>

            <section className="panel match-panel">
              <div className="panel-heading match-heading">
                <div><div className="section-kicker">NEEDS CLINICAL REVIEW</div><h2>Potential match</h2></div>
                <span className="match-index">01 / 03</span>
              </div>
              <div className="match-request"><span className="match-organ">K</span><span><strong>Kidney · O+</strong><small>REQ-2048 · High urgency</small></span><span className="request-open">OPEN</span></div>
              <div className="match-person"><div className="donor-avatar">D<span>+</span></div><div className="donor-info"><span className="donor-id">DONOR RECORD</span><strong>DNR-1024</strong><small><span className="verified-mark">✓</span> Verified by Dr. A. Raman · Demo Center · 15 Sep 2026</small></div><button className="row-arrow" type="button" aria-label="Open donor record"><Icon name="chevron" size={16} /></button></div>
              <div className="match-facts"><div><Icon name="pin" size={16} /><span><strong>8.4 km</strong><small>Distance estimate</small></span></div><div><span className="availability-mark" /><span><strong>Available</strong><small>Last updated today</small></span></div></div>
              <div className="review-callout"><span className="review-symbol">!</span><div><strong>Potential Match: Requires Medical Review</strong><p>Screening details are not a medical decision. Review all fields with the transplant team.</p></div></div>
              <button className="primary-button" type="button" onClick={() => setActivePage('Potential matches')}>Review potential match <Icon name="arrow" size={17} /></button>
              <div className="match-disclaimer"><Icon name="shield" size={14} /> No donor contact is made from this screen.</div>
            </section>
          </div>

          <section className="bottom-grid">
            <div className="panel activity-panel">
              <div className="panel-heading compact-heading"><div><div className="section-kicker">RECENT UPDATES</div><h2>Coordination activity</h2></div><button className="icon-button subtle-icon" type="button" aria-label="View activity"><Icon name="arrow" size={16} /></button></div>
              <div className="activity-list">
                <div className="activity-entry"><span className="activity-bullet sage-bullet" /><div><p><strong>Medical review requested</strong><span> · Kidney requirement REQ-2048</span></p><small>By Dr. Ananya Raman <i>·</i> 18 min ago</small></div><span className="activity-tag">REVIEW</span></div>
                <div className="activity-entry"><span className="activity-bullet blue-bullet" /><div><p><strong>Consent confirmed</strong><span> · Coordination case CASE-018</span></p><small>Hospital team <i>·</i> 2 hours ago</small></div><span className="activity-tag">CONSENT</span></div>
                <div className="activity-entry"><span className="activity-bullet peach-bullet" /><div><p><strong>Availability updated</strong><span> · Donor record DNR-1024</span></p><small>Donor portal <i>·</i> Yesterday</small></div><span className="activity-tag">RECORD</span></div>
              </div>
            </div>
            <aside className="disclaimer-panel"><div className="disclaimer-top"><span className="disclaimer-icon"><Icon name="shield" size={19} /></span><span className="section-kicker">IMPORTANT</span></div><h2>Decision support,<br />not a medical authority.</h2><p>Kindred surfaces potential matches for authorized hospital teams. Medical eligibility, allocation, and approval remain with clinicians and the relevant authorities.</p><a href="#safety">Read safety & privacy <Icon name="arrow" size={14} /></a></aside>
          </section>

          <footer className="page-footer"><span>Kindred <i>·</i> Hospital workspace</span><span><span className="footer-status"><i /> Mock sandbox</span><span className="footer-divider">|</span> Data shown is illustrative only</span></footer>
        </div>
      </main>
      {menuOpen && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} type="button" />}
    </div>
  );
}
