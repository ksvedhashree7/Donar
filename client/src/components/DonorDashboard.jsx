function formatDate(dateValue) {
  if (!dateValue) return 'No donation recorded';
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(dateValue));
}

function getDaysUntilEligible(dateValue) {
  if (!dateValue) return null;
  const nextDate = new Date(dateValue);
  nextDate.setDate(nextDate.getDate() + 90);
  return Math.max(0, Math.ceil((nextDate.getTime() - Date.now()) / 86400000));
}

export default function DonorDashboard({ donor }) {
  const profile = donor ?? {
    name: 'Meera Iyer',
    bloodGroup: 'O+',
    isVerified: true,
    selfDeclaredEligible: true,
    isAvailable: true,
    lastDonationDate: (() => {
      const date = new Date();
      date.setDate(date.getDate() - 58);
      return date.toISOString();
    })(),
  };
  const daysRemaining = getDaysUntilEligible(profile.lastDonationDate);
  const clearToContact = profile.selfDeclaredEligible && profile.isAvailable;

  return (
    <section className="dashboard" aria-labelledby="dashboard-title">
      <div className="dashboard-heading">
        <div><p className="eyebrow">YOUR DONOR SPACE</p><h2 id="dashboard-title">A little status check</h2></div>
        <span className="profile-reference">UT / PROFILE</span>
      </div>

      <section className="profile-strip" aria-label="Donor profile">
        <span className="profile-blood">{profile.bloodGroup ?? 'O+'}</span>
        <div className="profile-identity"><h3>{profile.name ?? 'Community donor'}</h3><span>New Delhi · Donor community</span></div>
        <span className={`profile-verified ${profile.isVerified ? 'is-verified' : ''}`}>
          <span aria-hidden="true">{profile.isVerified ? '✓' : '○'}</span>{profile.isVerified ? 'VERIFIED' : 'VERIFICATION PENDING'}
        </span>
      </section>

      <div className="dashboard-grid">
        <section className={`eligibility-card ${clearToContact ? 'clear' : 'deferred'}`}>
          <p className="eyebrow">SELF-REPORTED PRE-SCREEN</p>
          <div className="eligibility-status">
            <span className="eligibility-icon" aria-hidden="true">{clearToContact ? '✓' : '!'}</span>
            <div><h3>{clearToContact ? 'No current flags reported' : 'Temporarily deferred'}</h3><p>{clearToContact ? 'You may be shown in donor searches.' : 'You will not appear in donor searches right now.'}</p></div>
          </div>
          <p className="clinical-note">This is not medical clearance. The blood bank confirms final eligibility at donation.</p>
        </section>

        <section className="history-card">
          <p className="eyebrow">DONATION HISTORY</p>
          <div className="history-date"><strong>{formatDate(profile.lastDonationDate)}</strong><span>Most recent donation</span></div>
          <div className="countdown-row">
            <span className="countdown-number">{daysRemaining === null ? '—' : daysRemaining === 0 ? 'Ready' : daysRemaining}</span>
            <span>{daysRemaining === null ? 'days until next donation window' : daysRemaining === 0 ? '90-day interval reached' : 'days until 90-day interval'}</span>
          </div>
        </section>
      </div>

      <section className="requests-section">
        <div className="requests-heading"><div><p className="eyebrow">COMMUNITY MATCHES</p><h3>Active requests</h3></div><span className="request-count">00 ACTIVE</span></div>
        <div className="request-empty"><span className="request-mark" aria-hidden="true">+</span><div><strong>No hospital matches yet</strong><span>When a verified blood bank requests a compatible donor, it will appear here.</span></div></div>
      </section>
    </section>
  );
}
