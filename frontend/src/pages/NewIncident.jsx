import { useState } from "react";
import { AlertTriangle, ArrowLeft, ArrowRight, Check, Clock3, FileText } from "lucide-react";
import { Link, useOutletContext } from "react-router-dom";
import PageHeader from "../components/common/PageHeader.jsx";
import { services, severityOptions } from "../utils/constants.js";

const initialForm = { service: "", title: "", severity: "", description: "", timeWindow: "30 minutes", context: "" };

export default function NewIncident() {
  const [form, setForm] = useState(initialForm);
  const [errors, setErrors] = useState({});
  const [attempted, setAttempted] = useState(false);
  const { notify } = useOutletContext();

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: "" }));
  }

  function validate() {
    const next = {};
    if (!form.service) next.service = "Select the affected service.";
    if (!form.title.trim()) next.title = "Incident title is required.";
    if (!form.severity) next.severity = "Choose a severity level.";
    if (form.description.trim().length < 12) next.description = "Add at least 12 characters describing the symptoms.";
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  function submit(event) {
    event.preventDefault();
    setAttempted(true);
    if (!validate()) return;
    notify({
      type: "error",
      message: "No request was sent. The backend source has no incident schema or route implementation, so the request payload cannot be safely determined.",
    });
  }

  function clearForm() {
    setForm(initialForm);
    setErrors({});
    setAttempted(false);
  }

  return (
    <main className="page-content form-page">
      <PageHeader
        eyebrow="INCIDENT INTAKE"
        title="New investigation"
        description="Capture the signal. Sentinel will coordinate investigation once the backend contract is available."
        actions={<Link className="button button-secondary" to="/incidents"><ArrowLeft size={15} /> Incidents</Link>}
      />
      <div className="form-layout">
        <form className="panel investigation-form" onSubmit={submit} noValidate>
          <div className="form-section-title"><span className="section-index">01</span><div><h2>Incident details</h2><p>Tell us what happened and where it is happening.</p></div></div>
          <div className="form-grid">
            <label className="field">
              <span>Service name <i>*</i></span>
              <select value={form.service} onChange={(event) => update("service", event.target.value)} aria-invalid={Boolean(errors.service)}>
                <option value="">Select a service</option>
                {services.map((service) => <option key={service}>{service}</option>)}
              </select>
              {errors.service && <small className="field-error">{errors.service}</small>}
            </label>
            <label className="field">
              <span>Severity <i>*</i></span>
              <select value={form.severity} onChange={(event) => update("severity", event.target.value)} aria-invalid={Boolean(errors.severity)}>
                <option value="">Select severity</option>
                {severityOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
              {errors.severity && <small className="field-error">{errors.severity}</small>}
            </label>
            <label className="field field-wide">
              <span>Incident title <i>*</i></span>
              <input value={form.title} onChange={(event) => update("title", event.target.value)} placeholder="e.g. Payment API high latency" maxLength={120} aria-invalid={Boolean(errors.title)} />
              {errors.title && <small className="field-error">{errors.title}</small>}
            </label>
            <label className="field field-wide">
              <span>Description <i>*</i></span>
              <textarea value={form.description} onChange={(event) => update("description", event.target.value)} placeholder="Describe the symptoms, impact, and what changed..." rows={5} maxLength={2000} aria-invalid={Boolean(errors.description)} />
              <small className={errors.description ? "field-error" : "field-help"}>{errors.description || `${form.description.length}/2000 characters`}</small>
            </label>
            <label className="field">
              <span>Time window</span>
              <span className="input-icon-wrap"><Clock3 size={15} /><select value={form.timeWindow} onChange={(event) => update("timeWindow", event.target.value)}><option value="15 minutes">Last 15 minutes</option><option value="30 minutes">Last 30 minutes</option><option value="1 hour">Last hour</option><option value="6 hours">Last 6 hours</option><option value="24 hours">Last 24 hours</option></select></span>
            </label>
            <label className="field">
              <span>Additional context <em>Optional</em></span>
              <span className="input-icon-wrap"><FileText size={15} /><input value={form.context} onChange={(event) => update("context", event.target.value)} placeholder="Ticket, deploy, or team reference" maxLength={500} /></span>
            </label>
          </div>
          {attempted && <div className="inline-notice notice-warning form-contract-notice"><AlertTriangle size={17} /><div><strong>Submission is blocked</strong><span>Backend request and response schemas are absent in the current workspace. This form will not send an assumed payload.</span></div></div>}
          <div className="form-actions">
            <button type="button" className="button button-ghost" onClick={clearForm}>Clear form</button>
            <button type="submit" className="button button-primary"><span>Submit investigation</span><ArrowRight size={15} /></button>
          </div>
        </form>
        <aside className="form-aside">
          <section className="panel intake-note">
            <div className="note-icon"><Check size={17} /></div>
            <h3>One coordinated workflow</h3>
            <p>Once connected, your report is routed through log, metrics, and historical evidence analysis before RCA generation.</p>
            <div className="note-flow"><span>Incident intake</span><i /><span>Agent workflow</span><i /><span>RCA report</span></div>
          </section>
          <section className="panel schema-note">
            <div className="schema-note-header"><AlertTriangle size={15} /><span>Integration readiness</span></div>
            <p>The specified incident endpoints are not implemented in the checked-in backend files. Connect the API schema before enabling submission.</p>
            <Link to="/settings">View integration settings <ArrowRight size={13} /></Link>
          </section>
        </aside>
      </div>
    </main>
  );
}