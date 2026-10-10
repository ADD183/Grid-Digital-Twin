import React, { useEffect, useState } from 'react';
import { Activity, AlertTriangle, CheckCircle2, Download, Play, RefreshCw, ShieldCheck } from 'lucide-react';
import { update1Api } from '../api/client';

const panelStyle = { padding: '20px', marginBottom: '18px' };
const buttonStyle = {
  display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '9px 13px',
  border: '1px solid rgba(255,255,255,.12)', borderRadius: '7px',
  background: 'rgba(8,145,178,.18)', color: '#e2e8f0', fontWeight: 600,
};

function Metric({ label, value, unit = '' }) {
  return (
    <div style={{ padding: '12px', border: '1px solid var(--border-color)', borderRadius: '7px', background: 'rgba(15,23,42,.55)' }}>
      <div style={{ color: 'var(--text-muted)', fontSize: '.75rem' }}>{label}</div>
      <div style={{ color: 'var(--text-main)', fontSize: '1.05rem', fontFamily: 'var(--font-mono)', marginTop: '3px' }}>
        {value}{unit}
      </div>
    </div>
  );
}

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

  const refreshStatus = async () => {
    const [telemetryStatus, surrogateStatus] = await Promise.all([
      update1Api.getTelemetry(),
      update1Api.getSurrogateStatus(),
    ]);
    setTelemetry(telemetryStatus);
    setSurrogate(surrogateStatus);
  };

  useEffect(() => {
    refreshStatus().catch((err) => setError(err.message));
    runPlan().catch((err) => setError(err.message));
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
  const statusColor = telemetry?.requires_replan ? '#f59e0b' : '#10b981';

  return (
    <section aria-label="Eight-step predictive control">
      <div className="glass-panel" style={panelStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
          <div>
            <h2 style={{ fontSize: '1.15rem', color: 'var(--text-main)' }}>Predictive Control · 8 × 15 min</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '.82rem', marginTop: '3px' }}>
              Surrogate screens candidate dispatch; every selected state is verified with pandapower AC power flow.
            </p>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '.82rem' }}>
            Initial SoC (MWh)
            <input aria-label="Initial battery state of charge" type="number" min="0" max="4" step="0.1" value={initialSoc} onChange={(event) => setInitialSoc(event.target.value)} style={{ width: '76px', padding: '7px', borderRadius: '6px', background: '#0f172a', color: '#f8fafc', border: '1px solid var(--border-color)' }} />
          </label>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '14px' }}>
          <button style={buttonStyle} onClick={runPlan} disabled={Boolean(working)}><Play size={15} />{working === 'plan' ? 'Planning…' : 'Run 8-step plan'}</button>
          <button style={buttonStyle} onClick={trainSurrogate} disabled={Boolean(working)}><Activity size={15} />{working === 'train' ? 'Training…' : 'Train surrogate'}</button>
          <button style={buttonStyle} onClick={exportEvidence} disabled={Boolean(working)}><Download size={15} />{working === 'export' ? 'Exporting…' : 'Export evidence'}</button>
          <button style={{ ...buttonStyle, background: 'rgba(100,116,139,.16)' }} onClick={() => refreshStatus().catch((err) => setError(err.message))} disabled={Boolean(working)} title="Refresh telemetry and surrogate status"><RefreshCw size={15} />Refresh status</button>
        </div>
      </div>

      <div className="glass-panel" style={panelStyle}>
        <h3 style={{ fontSize: '.95rem', marginBottom: '10px' }}>Telemetry and model readiness</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(165px, 1fr))', gap: '9px' }}>
          <Metric label="Telemetry source" value={telemetry?.reading?.source || 'Loading'} />
          <Metric label="Solar actual / forecast" value={telemetry ? `${telemetry.reading.solar_mw.toFixed(2)} / ${telemetry.forecast_solar_mw.toFixed(2)}` : '—'} unit=" MW" />
          <Metric label="Forecast drift" value={telemetry ? `${(telemetry.drift * 100).toFixed(1)}` : '—'} unit="%" />
          <Metric label="Surrogate" value={surrogate?.trained ? 'Trained' : 'Solver-only fallback'} />
        </div>
        {telemetry && (
          <div style={{ marginTop: '10px', padding: '9px 11px', borderLeft: `3px solid ${statusColor}`, background: 'rgba(15,23,42,.6)', color: statusColor, fontSize: '.82rem' }}>
            {telemetry.is_stale ? 'Telemetry is stale. ' : ''}
            {telemetry.requires_replan ? 'Replan required.' : 'No drift-triggered replan.'}
            {telemetry.used_fallback ? ' Deterministic mock feed is active.' : ''}
            {telemetry.error ? ` Feed note: ${telemetry.error}` : ''}
          </div>
        )}
        {surrogate?.metrics && <p style={{ color: 'var(--text-muted)', fontSize: '.78rem', marginTop: '9px' }}>
          Held-out voltage MAE {surrogate.metrics.voltage_mae_pu?.toFixed(4)} p.u. · line-loading MAE {surrogate.metrics.line_loading_mae_percent?.toFixed(2)}% · false-safe rate {surrogate.metrics.false_safe_rate == null ? 'not measurable (no unsafe validation samples)' : `${(surrogate.metrics.false_safe_rate * 100).toFixed(1)}%`}.
        </p>}
      </div>

      {plan && (
        <div className="glass-panel" style={panelStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', alignItems: 'center', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: plan.fully_resolved ? '#34d399' : '#f87171', fontWeight: 700 }}>
              {plan.fully_resolved ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
              {plan.fully_resolved ? 'All horizon steps physically verified safe' : 'Residual constraints remain in the horizon'}
            </div>
            <span style={{ color: 'var(--text-muted)', fontSize: '.75rem' }}>Run {plan.run_id}</span>
          </div>
          <div role="group" aria-label="MPC time-step selector" style={{ display: 'grid', gridTemplateColumns: 'repeat(8, minmax(34px, 1fr))', gap: '5px', marginBottom: '14px' }}>
            {plan.steps.map((item, index) => (
              <button key={item.step} onClick={() => setSelectedStep(index)} aria-pressed={selectedStep === index} style={{ minHeight: '38px', borderRadius: '5px', background: selectedStep === index ? '#0e7490' : item.solver.is_safe ? 'rgba(16,185,129,.12)' : 'rgba(239,68,68,.16)', color: item.solver.is_safe ? '#6ee7b7' : '#fca5a5', border: '1px solid var(--border-color)', fontFamily: 'var(--font-mono)' }}>T{item.step}</button>
            ))}
          </div>
          {step && <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(145px, 1fr))', gap: '8px' }}>
              <Metric label="Solver status" value={step.solver.converged ? (step.solver.is_safe ? 'Converged · safe' : 'Converged · violations') : 'Not converged'} />
              <Metric label="Voltage range" value={`${step.solver.min_voltage_pu?.toFixed(4) ?? '—'} – ${step.solver.max_voltage_pu?.toFixed(4) ?? '—'}`} unit=" p.u." />
              <Metric label="Max line loading" value={step.solver.max_line_loading_percent?.toFixed(2) ?? '—'} unit="%" />
              <Metric label="Battery SoC after step" value={step.state_of_charge_mwh.toFixed(3)} unit=" MWh" />
            </div>
            <p style={{ color: 'var(--text-muted)', fontSize: '.8rem', marginTop: '11px' }}>
              PV curtailment {(step.curtailment_fraction * 100).toFixed(0)}% · charge {step.battery_charge_mw.toFixed(2)} MW · discharge {step.battery_discharge_mw.toFixed(2)} MW · load shed {step.load_shed_mw.toFixed(2)} MW · {step.surrogate_used ? 'surrogate screened, solver verified' : `solver fallback: ${step.surrogate_fallback_reason || 'surrogate not used'}`}
            </p>
            {step.solver.violations.length > 0 && <ul style={{ marginTop: '8px', paddingLeft: '20px', color: '#fca5a5', fontSize: '.8rem' }}>
              {step.solver.violations.slice(0, 6).map((violation, index) => <li key={`${violation.element_type}-${violation.element_id}-${index}`}>{violation.message}</li>)}
              {step.solver.violations.length > 6 && <li>And {step.solver.violations.length - 6} more measured violations.</li>}
            </ul>}
          </>}
          {forecastProvenance && <p style={{ marginTop: '12px', color: 'var(--text-dim)', fontSize: '.73rem' }}>
            Forecast provenance: hourly model; quarter-hour points are {forecastProvenance.quarter_hour_method}. Training data ends {forecastProvenance.training_data_last_timestamp}.
          </p>}
        </div>
      )}

      {exported && <div className="glass-panel" style={{ ...panelStyle, color: '#a7f3d0', fontSize: '.82rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '6px' }}><ShieldCheck size={16} />Evidence exported for run {exported.run_id}.</div>
        {Object.entries(exported.artifacts || {}).map(([name, path]) => <div key={name}>{name}: <code>{path}</code></div>)}
      </div>}
      {error && <div role="alert" style={{ ...panelStyle, background: 'rgba(127,29,29,.3)', border: '1px solid rgba(248,113,113,.35)', color: '#fecaca' }}>{error}</div>}
    </section>
  );
}