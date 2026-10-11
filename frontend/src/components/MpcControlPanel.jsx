import React, { useEffect, useState } from 'react';
import { Activity, AlertTriangle, CheckCircle2, Download, Play, RefreshCw, ShieldCheck, Cpu } from 'lucide-react';
import { update1Api } from '../api/client';

function Metric({ label, value, unit = '', tone = 'info' }) {
  return (
    <div className="vp-kpi-tile" data-tone={tone}>
      <span className="vp-kpi-label">{label}</span>
      <div className="vp-kpi-value" style={{ fontSize: '1.2rem', marginTop: '2px' }}>
        {value}{unit}
      </div>
    </div>
  );
}

const formatIstTime = (timestamp) => new Intl.DateTimeFormat('en-IN', {
  hour: 'numeric',
  minute: '2-digit',
  second: '2-digit',
  hour12: true,
  timeZone: 'Asia/Kolkata',
}).format(new Date(timestamp));

export default function MpcControlPanel() {
  const [telemetry, setTelemetry] = useState(null);
  const [surrogate, setSurrogate] = useState(null);
  const [plan, setPlan] = useState(null);
  const [selectedStep, setSelectedStep] = useState(0);
  const [initialSoc, setInitialSoc] = useState('2');
  const [working, setWorking] = useState('');
  const [error, setError] = useState('');
  const [exported, setExported] = useState(null);
  const [forecastProvenance, setForecastProvenance] = useState(null);
  const [statusUpdatedAt, setStatusUpdatedAt] = useState(null);

  const refreshStatus = async () => {
    const [telemetryStatus, surrogateStatus] = await Promise.all([
      update1Api.getTelemetry(),
      update1Api.getSurrogateStatus(),
    ]);
    setTelemetry(telemetryStatus);
    setSurrogate(surrogateStatus);
    setStatusUpdatedAt(new Date().toISOString());
  };

  useEffect(() => {
    refreshStatus().catch((err) => setError(err.message));
  }, []);

  const runPlan = async () => {
    setWorking('plan');
    setError('');
    setExported(null);
    try {
      const forecast = await update1Api.getForecast();
      setForecastProvenance(forecast.provenance);
      const nextPlan = await update1Api.runMpc({
        forecasts: forecast.points,
        initial_state_of_charge_mwh: Number(initialSoc),
      });
      setPlan(nextPlan);
      setSelectedStep(0);
    } catch (err) {
      setError(err.message);
    } finally {
      setWorking('');
    }
  };

  const trainSurrogate = async () => {
    setWorking('train');
    setError('');
    try {
      const result = await update1Api.trainSurrogate(32);
      setSurrogate({ trained: true, metrics: result.metrics, model_path: result.model_path });
    } catch (err) {
      setError(err.message);
    } finally {
      setWorking('');
    }
  };

  const exportEvidence = async () => {
    setWorking('export');
    setError('');
    try {
      setExported(await update1Api.exportArtifacts(32));
      await refreshStatus();
    } catch (err) {
      setError(err.message);
    } finally {
      setWorking('');
    }
  };

  const step = plan?.steps?.[selectedStep];

  return (
    <section aria-label="Eight-step predictive control">

      {/* SECTION 1: HEADER & CONTROLS */}
      <div className="vp-card" style={{ marginBottom: '20px' }}>
        <div className="vp-page-header">
          <div>
            <h2 className="vp-page-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Cpu size={22} color="var(--accent)" />
              <span>Plan actions for the next two hours</span>
            </h2>
            <p className="vp-page-desc">
              Set a starting battery level, run a plan, and review its expected impact before applying an action.
            </p>
          </div>

          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '.84rem' }}>
            Starting battery charge (MWh)
            <input
              aria-label="Initial battery state of charge"
              type="number"
              min="0"
              max="4"
              step="0.1"
              value={initialSoc}
              onChange={(event) => setInitialSoc(event.target.value)}
              style={{
                width: '80px',
                padding: '6px 10px',
                borderRadius: 'var(--r-sm)',
                backgroundColor: 'var(--surface-raised)',
                color: 'var(--text)',
                border: '1px solid var(--border)',
                fontFamily: 'var(--font-mono)',
                outline: 'none'
              }}
            />
          </label>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '14px' }}>
          <button className="vp-btn vp-btn-primary" onClick={runPlan} disabled={Boolean(working)}>
            <Play size={15} />
            <span>{working === 'plan' ? 'Planning…' : 'Run plan'}</span>
          </button>

          <button className="vp-btn vp-btn-secondary" onClick={trainSurrogate} disabled={Boolean(working)}>
            <Activity size={15} />
            <span>{working === 'train' ? 'Updating…' : 'Update model'}</span>
          </button>

          <button className="vp-btn vp-btn-secondary" onClick={exportEvidence} disabled={Boolean(working)}>
            <Download size={15} />
            <span>{working === 'export' ? 'Exporting…' : 'Export evidence'}</span>
          </button>

          <button className="vp-btn vp-btn-ghost" onClick={() => refreshStatus().catch((err) => setError(err.message))} disabled={Boolean(working)} title="Refresh telemetry and surrogate status">
            <RefreshCw size={15} />
            <span>Refresh status</span>
          </button>
        </div>
      </div>

      {/* SECTION 2: TELEMETRY & MODEL READINESS */}
      <div className="vp-card" style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: '8px', marginBottom: '12px' }}>
          <h3 style={{ fontSize: '.95rem', fontWeight: 600, color: 'var(--text)' }}>Current readings</h3>
          {statusUpdatedAt && (
            <span className="vp-kpi-subtext">Updated {formatIstTime(statusUpdatedAt)} IST</span>
          )}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
          <Metric label="Telemetry Source" value={telemetry?.reading?.source || 'Loading'} tone="info" />
          <Metric label="Solar Actual / Forecast" value={telemetry ? `${telemetry.reading.solar_mw.toFixed(2)} / ${telemetry.forecast_solar_mw.toFixed(2)}` : '—'} unit=" MW" tone="info" />
          <Metric label="Forecast Drift" value={telemetry ? `${(telemetry.drift * 100).toFixed(1)}` : '—'} unit="%" tone={telemetry?.drift > 0.15 ? 'warn' : 'ok'} />
          <Metric label="Surrogate Model" value={surrogate?.trained ? 'Trained' : 'Solver-only fallback'} tone={surrogate?.trained ? 'ok' : 'info'} />
        </div>

        {telemetry && (
          <div className="vp-alert" data-tone={telemetry.requires_replan ? 'warn' : 'ok'} style={{ marginTop: '12px' }}>
            <span>
              {telemetry.is_stale ? 'Telemetry is stale. ' : ''}
              {telemetry.requires_replan ? 'Replan required.' : 'No drift-triggered replan.'}
              {telemetry.used_fallback ? ' Deterministic mock feed is active.' : ''}
              {telemetry.error ? ` Feed note: ${telemetry.error}` : ''}
            </span>
          </div>
        )}

        {surrogate?.metrics && (
          <p style={{ color: 'var(--text-muted)', fontSize: '.78rem', marginTop: '10px' }}>
            Held-out voltage MAE {surrogate.metrics.voltage_mae_pu?.toFixed(4)} p.u. · line-loading MAE {surrogate.metrics.line_loading_mae_percent?.toFixed(2)}% · false-safe rate {surrogate.metrics.false_safe_rate == null ? 'not measurable (no unsafe validation samples)' : `${(surrogate.metrics.false_safe_rate * 100).toFixed(1)}%`}.
          </p>
        )}
      </div>

      {!plan && !working && (
        <div className="vp-dashboard-empty" role="status" style={{ marginBottom: '20px' }}>
          Choose a starting battery level, then select <strong>Run plan</strong> to see the eight-period results.
        </div>
      )}

      {/* SECTION 3: PLAN HORIZON & STEP INSPECTOR */}
      {plan && (
        <div className="vp-card" style={{ marginBottom: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', alignItems: 'center', marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {plan.fully_resolved ? <CheckCircle2 size={18} color="var(--ok)" /> : <AlertTriangle size={18} color="var(--danger)" />}
              <span style={{ fontWeight: 600, color: plan.fully_resolved ? 'var(--ok)' : 'var(--danger)', fontSize: '0.95rem' }}>
                {plan.fully_resolved ? 'All horizon steps physically verified safe' : 'Residual constraints remain in the horizon'}
              </span>
            </div>
            <span className="vp-badge" data-tone="neutral">Run {plan.run_id}</span>
          </div>

          {/* Time-step Selector */}
          <div role="group" aria-label="MPC time-step selector" className="vp-segmented" style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', gap: '4px', marginBottom: '16px', overflowX: 'auto' }}>
            {plan.steps.map((item, index) => (
              <button
                key={item.step}
                onClick={() => setSelectedStep(index)}
                aria-pressed={selectedStep === index}
                className={`vp-segmented-btn ${selectedStep === index ? 'active' : ''}`}
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontWeight: 600,
                  fontSize: '0.82rem',
                  padding: '8px 4px',
                  color: selectedStep === index ? 'var(--accent)' : item.solver.is_safe ? 'var(--ok)' : 'var(--danger)'
                }}
              >
                T{item.step}
              </button>
            ))}
          </div>

          {step && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '10px' }}>
                <Metric label="Solver Status" value={step.solver.converged ? (step.solver.is_safe ? 'Converged · safe' : 'Converged · violations') : 'Not converged'} tone={step.solver.is_safe ? 'ok' : 'danger'} />
                <Metric label="Voltage Range" value={`${step.solver.min_voltage_pu?.toFixed(4) ?? '—'} – ${step.solver.max_voltage_pu?.toFixed(4) ?? '—'}`} unit=" p.u." tone="info" />
                <Metric label="Max Line Loading" value={step.solver.max_line_loading_percent?.toFixed(2) ?? '—'} unit="%" tone={step.solver.max_line_loading_percent <= 100 ? 'ok' : 'danger'} />
                <Metric label="Battery SoC After Step" value={step.state_of_charge_mwh.toFixed(3)} unit=" MWh" tone="info" />
              </div>

              <p style={{ color: 'var(--text-muted)', fontSize: '.82rem', marginTop: '12px', lineHeight: 1.4 }}>
                PV curtailment {(step.curtailment_fraction * 100).toFixed(0)}% · charge {step.battery_charge_mw.toFixed(2)} MW · discharge {step.battery_discharge_mw.toFixed(2)} MW · load shed {step.load_shed_mw.toFixed(2)} MW · {step.surrogate_used ? 'surrogate screened, solver verified' : `solver fallback: ${step.surrogate_fallback_reason || 'surrogate not used'}`}
              </p>

              {step.solver.violations.length > 0 && (
                <ul style={{ marginTop: '10px', paddingLeft: '20px', color: 'var(--danger)', fontSize: '.82rem', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {step.solver.violations.slice(0, 6).map((violation, index) => (
                    <li key={`${violation.element_type}-${violation.element_id}-${index}`}>{violation.message}</li>
                  ))}
                  {step.solver.violations.length > 6 && (
                    <li>And {step.solver.violations.length - 6} more measured violations.</li>
                  )}
                </ul>
              )}
            </>
          )}

          {forecastProvenance && (
            <p style={{ marginTop: '12px', color: 'var(--text-faint)', fontSize: '.75rem' }}>
              Forecast provenance: hourly model; quarter-hour points are {forecastProvenance.quarter_hour_method}. Training data ends {forecastProvenance.training_data_last_timestamp}.
            </p>
          )}
        </div>
      )}

      {exported && (
        <div className="vp-alert" data-tone="ok" style={{ marginBottom: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '7px', fontWeight: 600, marginBottom: '4px' }}>
              <ShieldCheck size={16} />
              <span>Evidence exported for run {exported.run_id}.</span>
            </div>
            {Object.entries(exported.artifacts || {}).map(([name, path]) => (
              <div key={name} style={{ fontSize: '0.78rem' }}>{name}: <code className="mono">{path}</code></div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="vp-alert" data-tone="danger">
          <span>{error}</span>
        </div>
      )}
    </section>
  );
}
