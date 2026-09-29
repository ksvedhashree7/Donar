import { useState } from 'react';
import axios from 'axios';

export default function AdminDashboard() {
  const [adminKey, setAdminKey] = useState('');
  const [authenticated, setAuthenticated] = useState(false);
  const [requests, setRequests] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(false);
  const [workingId, setWorkingId] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function loadQueue(event) {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const response = await axios.get('/api/requests/pending', {
        headers: { 'x-admin-key': adminKey },
      });
      setRequests(response.data.data);
      setAuthenticated(true);
    } catch (requestError) {
      setError(requestError.response?.data?.message ?? 'Could not load the verification queue.');
      setAuthenticated(false);
    } finally {
      setLoading(false);
    }
  }

  async function reviewRequest(requestId, decision) {
    setWorkingId(requestId);
    setError('');
    setNotice('');
    try {
      const response = await axios.put(`/api/requests/${requestId}/${decision}`, {}, {
        headers: { 'x-admin-key': adminKey },
      });
      setRequests((current) => current.filter((item) => item._id !== requestId));
      if (decision === 'approve') {
        setNotifications(response.data.data.notifications);
        setNotice(response.data.message);
      } else {
        setNotifications([]);
        setNotice(response.data.message);
      }
    } catch (requestError) {
      setError(requestError.response?.data?.message ?? 'The review action could not be completed.');
    } finally {
      setWorkingId('');
    }
  }

  function signOut() {
    setAdminKey('');
    setAuthenticated(false);
    setRequests([]);
    setNotifications([]);
    setNotice('');
    setError('');
  }

  if (!authenticated) {
    return (
      <section className="form-panel admin-login" aria-labelledby="admin-login-title">
        <div className="form-intro">
          <p className="eyebrow">AUTHORIZED REVIEWERS</p>
          <h2 id="admin-login-title">Expert verification queue</h2>
          <p>Enter the admin key configured on the server to access pending requests.</p>
        </div>
        <form onSubmit={loadQueue}>
          <label className="field-label">Admin key<input type="password" autoComplete="current-password" value={adminKey} onChange={(event) => setAdminKey(event.target.value)} required /></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="form-actions">
            <button className="search-button" type="submit" disabled={loading || !adminKey}>
              {loading ? 'Checking…' : 'Open verification queue'}<span aria-hidden="true">↗</span>
            </button>
          </div>
        </form>
      </section>
    );
  }

  return (
    <section className="dashboard verification-dashboard" aria-labelledby="verification-title">
      <div className="dashboard-heading">
        <div>
          <p className="eyebrow">HUMAN REVIEW</p>
          <h2 id="verification-title">Expert verification queue</h2>
        </div>
        <button className="back-button" type="button" onClick={signOut}>Sign out</button>
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}
      {notice && <p className="request-disclaimer" role="status">{notice}</p>}

      {requests.length ? (
        <div className="verification-list">
          {requests.map((item) => (
            <article className="verification-request" key={item._id}>
              <div className="verification-request-heading">
                <div><span className="blood-badge">{item.bloodGroup}</span><strong>{item.patientName}</strong></div>
                <span className={`urgency-label urgency-${item.urgency.toLowerCase()}`}>{item.urgency}</span>
              </div>
              <dl className="request-facts">
                <div><dt>Hospital</dt><dd>{item.hospitalName}</dd></div>
                <div><dt>Units</dt><dd>{item.unitsRequired}</dd></div>
                <div><dt>Contact</dt><dd><a href={`tel:${item.contactPhone}`}>{item.contactPhone}</a></dd></div>
                <div><dt>Submitted</dt><dd>{new Date(item.createdAt).toLocaleString()}</dd></div>
              </dl>
              <div className="review-actions">
                <button className="back-button reject-button" type="button" onClick={() => reviewRequest(item._id, 'reject')} disabled={Boolean(workingId)}>
                  {workingId === item._id ? 'Working…' : 'Reject'}
                </button>
                <button className="search-button" type="button" onClick={() => reviewRequest(item._id, 'approve')} disabled={Boolean(workingId)}>
                  Approve & notify<span aria-hidden="true">↗</span>
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state queue-empty"><span className="empty-mark" aria-hidden="true">✓</span><p>No requests are waiting for review.</p></div>
      )}

      {notifications.length > 0 && (
        <section className="notification-section" aria-labelledby="notification-title">
          <div className="requests-heading"><div><p className="eyebrow">SIMULATOR</p><h3 id="notification-title">Donor alerts created</h3></div><span className="request-count">{notifications.length.toString().padStart(2, '0')} QUEUED</span></div>
          <ul className="notification-list">
            {notifications.map((item) => <li key={item._id}><span aria-hidden="true">SMS</span><div><strong>{item.donorName}</strong><p>{item.message}</p></div><span className="verification">{item.status.toUpperCase()}</span></li>)}
          </ul>
          <p className="request-disclaimer">Simulation only. No text messages or calls have been sent.</p>
        </section>
      )}
    </section>
  );
}