import { useState } from 'react';
import axios from 'axios';

const initialForm = {
  name: '',
  phone: '',
  bloodGroup: 'O+',
  dateOfBirth: '',
  weight: '',
  donatedWithin90Days: null,
  lastDonationDate: '',
  feelsWell: null,
  onMedication: null,
  hasRecentIllness: null,
  recentSurgeryOrDentalProcedure: null,
  recentTattooOrPiercing: null,
  pregnancyStatus: '',
  hasChronicConditions: null,
  consentGiven: false,
  isAvailable: true,
};

const bloodGroups = ['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'];
const steps = ['Your details', 'Health check-in', 'Consent & availability'];

export default function DonorRegister({ onRegistered }) {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submitRegistration(event) {
    event.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      const response = await axios.post('/api/donors/register', {
        ...form,
        weight: Number(form.weight),
        longitude: 77.209,
        latitude: 28.6139,
        lastDonationDate: form.donatedWithin90Days ? form.lastDonationDate : undefined,
      });
      onRegistered(response.data.data);
    } catch (requestError) {
      setError(
        requestError.response?.data?.message ??
          'Registration could not be submitted. Check that the API and database are available, then try again.',
      );
    } finally {
      setSubmitting(false);
    }
  }

  function nextStep(event) {
    event.preventDefault();
    setError('');

    if (step === 1) {
      const screeningFields = [
        'feelsWell',
        'donatedWithin90Days',
        'onMedication',
        'hasRecentIllness',
        'recentSurgeryOrDentalProcedure',
        'recentTattooOrPiercing',
        'hasChronicConditions',
      ];
      if (screeningFields.some((field) => typeof form[field] !== 'boolean') || !form.pregnancyStatus) {
        setError('Please answer every screening question before continuing.');
        return;
      }
      if (form.donatedWithin90Days && !form.lastDonationDate) {
        setError('Add your most recent donation date to continue.');
        return;
      }
    }

    if (step === 0) {
      const birthDate = new Date(`${form.dateOfBirth}T00:00:00`);
      const today = new Date();
      const youngestEligibleDate = new Date(today);
      youngestEligibleDate.setFullYear(today.getFullYear() - 18);
      const oldestEligibleDate = new Date(today);
      oldestEligibleDate.setFullYear(today.getFullYear() - 65);

      if (birthDate > youngestEligibleDate || birthDate < oldestEligibleDate) {
        setError('Registration is currently limited to donors aged 18-65.');
        return;
      }
      if (Number(form.weight) < 50) {
        setError('The current minimum weight for registration is 50 kg.');
        return;
      }
    }

    setStep((current) => Math.min(current + 1, steps.length - 1));
  }

  const radioQuestion = (field, question, yesLabel = 'Yes', noLabel = 'No') => (
    <fieldset className="question-row">
      <legend>{question}</legend>
      <div className="choice-group">
        <label className={`choice ${form[field] ? 'selected' : ''}`}>
          <input type="radio" name={field} checked={form[field] === true} onChange={() => update(field, true)} />
          {yesLabel}
        </label>
        <label className={`choice ${form[field] === false ? 'selected' : ''}`}>
          <input type="radio" name={field} checked={form[field] === false} onChange={() => update(field, false)} />
          {noLabel}
        </label>
      </div>
    </fieldset>
  );

  return (
    <section className="form-panel" aria-labelledby="register-title">
      <div className="form-intro">
        <p className="eyebrow">JOIN THE COMMUNITY</p>
        <h2 id="register-title">Become a donor</h2>
        <p>Your answers help the team prepare. They are not a medical clearance.</p>
      </div>

      <ol className="form-steps" aria-label="Registration progress">
        {steps.map((label, index) => (
          <li className={index === step ? 'current' : index < step ? 'complete' : ''} key={label}>
            <span>{index < step ? '✓' : `0${index + 1}`}</span>{label}
          </li>
        ))}
      </ol>

      <form onSubmit={step < 2 ? nextStep : submitRegistration}>
        {step === 0 && (
          <div className="form-fields">
            <label className="field-label">Full name<input autoComplete="name" value={form.name} onChange={(event) => update('name', event.target.value)} required /></label>
            <label className="field-label">Phone number<input autoComplete="tel" type="tel" value={form.phone} onChange={(event) => update('phone', event.target.value)} required /></label>
            <label className="field-label">Blood group<select value={form.bloodGroup} onChange={(event) => update('bloodGroup', event.target.value)}>{bloodGroups.map((group) => <option key={group}>{group}</option>)}</select></label>
            <label className="field-label">Date of birth<input type="date" value={form.dateOfBirth} onChange={(event) => update('dateOfBirth', event.target.value)} required /></label>
            <label className="field-label">Weight (kg)<input type="number" min="50" step="0.1" value={form.weight} onChange={(event) => update('weight', event.target.value)} required /></label>
          </div>
        )}

        {step === 1 && (
          <div className="screening-fields">
            {radioQuestion('feelsWell', 'Are you feeling well and fit to donate today?')}
            {radioQuestion('donatedWithin90Days', 'Have you donated blood in the last 90 days?')}
            {form.donatedWithin90Days && (
              <label className="field-label donation-date">Most recent donation date<input type="date" value={form.lastDonationDate} onChange={(event) => update('lastDonationDate', event.target.value)} max={new Date().toISOString().slice(0, 10)} required /></label>
            )}
            {radioQuestion('onMedication', 'Are you currently taking any medications?')}
            {radioQuestion('hasRecentIllness', 'Fever, infection, or antibiotics in the last 2 weeks?')}
            {radioQuestion('recentSurgeryOrDentalProcedure', 'Have you had recent surgery or a dental procedure?')}
            {radioQuestion('recentTattooOrPiercing', 'Tattoo or piercing in the last 6 months?')}
            <fieldset className="question-row">
              <legend>Are you pregnant or breastfeeding?</legend>
              <div className="choice-group">
                {['N/A', 'Pregnant', 'Breastfeeding'].map((value) => (
                  <label className={`choice ${form.pregnancyStatus === value ? 'selected' : ''}`} key={value}>
                    <input type="radio" name="pregnancyStatus" checked={form.pregnancyStatus === value} onChange={() => update('pregnancyStatus', value)} />
                    {value === 'N/A' ? 'No / N/A' : value}
                  </label>
                ))}
              </div>
            </fieldset>
            {radioQuestion('hasChronicConditions', 'Chronic conditions such as heart disease or diabetes?')}
            <p className="screening-note">Some answers may mean a temporary deferral. A blood-bank professional makes the final decision.</p>
          </div>
        )}

        {step === 2 && (
          <div className="consent-fields">
            <label className="consent-row">
              <input type="checkbox" checked={form.consentGiven} onChange={(event) => update('consentGiven', event.target.checked)} required />
              <span>I confirm my information is true and consent to share my contact details with verified blood banks.</span>
            </label>
            <label className="consent-row">
              <input type="checkbox" checked={form.isAvailable} onChange={(event) => update('isAvailable', event.target.checked)} />
              <span>I am currently available to be contacted if matched.</span>
            </label>
            <div className="clinical-notice"><strong>Prescreening is not medical clearance.</strong><span>Blood-bank staff will check blood pressure, pulse, hemoglobin, and required infection screens, then confirm final eligibility.</span></div>
          </div>
        )}

        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="form-actions">
          {step > 0 && <button className="back-button" type="button" onClick={() => { setError(''); setStep((current) => current - 1); }}>Back</button>}
          <button className="search-button" type="submit" disabled={submitting || (step === 2 && !form.consentGiven)}>
            {submitting ? 'Submitting…' : step === 2 ? 'Complete registration' : 'Continue'}<span aria-hidden="true">↗</span>
          </button>
        </div>
      </form>
    </section>
  );
}
