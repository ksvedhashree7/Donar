import { useState } from 'react';
import axios from 'axios';

const bloodGroups = ['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'];

const initialForm = {
  patientName: '',
  bloodGroup: 'O+',
  unitsRequired: '1',
  hospitalName: '',
  contactPhone: '',
  urgency: 'Normal',
  latitude: '28.6139',
  longitude: '77.209',
};

export default function BloodRequestForm() {
  const [form, setForm] = useState(initialForm);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [submitted, setSubmitted] = useState(false);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submitRequest(event) {
    event.preventDefault();
    setSubmitting(true);
    setError('');

    try {
      await axios.post('/api/requests', {
        ...form,
        unitsRequired: Number(form.unitsRequired),
        latitude: Number(form.latitude),
        longitude: Number(form.longitude),
      });
      setSubmitted(true);
    } catch (requestError) {
      setError(
        requestError.response?.data?.message ??
          'The request could not be submitted. Confirm the API and database are available, then try again.',
      );
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <section className="form-panel request-panel" aria-labelledby="request-success-title" aria-live="polite">
        <div className="form-intro">
          <p className="eyebrow">REQUEST RECEIVED</p>
          <h2 id="request-success-title">Pending expert verification</h2>
          <p>Donors will only be contacted after an authorized reviewer approves this request.</p>
        </div>
        <div className="request-status-banner"><span className="status-dot" /> PENDING VERIFICATION</div>
        <button className="back-button" type="button" onClick={() => { setForm(initialForm); setSubmitted(false); }}>Submit another request</button>
      </section>
    );
  }

  return (
    <section className="form-panel request-panel" aria-labelledby="blood-request-title">
      <div className="form-intro">
        <p className="eyebrow">HOSPITAL / CARE TEAM</p>
        <h2 id="blood-request-title">Request blood</h2>
        <p>Every request is reviewed before any donor is contacted.</p>
      </div>

      <form onSubmit={submitRequest}>
        <div className="form-fields request-fields">
          <label className="field-label">Patient name or reference<input autoComplete="off" value={form.patientName} onChange={(event) => update('patientName', event.target.value)} required maxLength={100} /></label>
          <label className="field-label">Blood group<select value={form.bloodGroup} onChange={(event) => update('bloodGroup', event.target.value)}>{bloodGroups.map((group) => <option key={group}>{group}</option>)}</select></label>
          <label className="field-label">Units required<input type="number" min="1" max="20" step="1" value={form.unitsRequired} onChange={(event) => update('unitsRequired', event.target.value)} required /></label>
          <label className="field-label">Urgency<select value={form.urgency} onChange={(event) => update('urgency', event.target.value)}><option>Normal</option><option>Urgent</option><option>Critical</option></select></label>
          <label className="field-label">Hospital name<input autoComplete="organization" value={form.hospitalName} onChange={(event) => update('hospitalName', event.target.value)} required maxLength={120} /></label>
          <label className="field-label">Contact phone<input autoComplete="tel" type="tel" value={form.contactPhone} onChange={(event) => update('contactPhone', event.target.value)} required maxLength={30} /></label>
          <label className="field-label">Hospital latitude<input type="number" min="-90" max="90" step="any" value={form.latitude} onChange={(event) => update('latitude', event.target.value)} required /></label>
          <label className="field-label">Hospital longitude<input type="number" min="-180" max="180" step="any" value={form.longitude} onChange={(event) => update('longitude', event.target.value)} required /></label>
        </div>
        <p className="request-disclaimer">Patient and contact details are shared only with authorized reviewers. This prototype does not send SMS or make calls.</p>
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="form-actions">
          <button className="search-button" type="submit" disabled={submitting}>
            {submitting ? 'Submitting…' : 'Submit for verification'}<span aria-hidden="true">↗</span>
          </button>
        </div>
      </form>
    </section>
  );
}