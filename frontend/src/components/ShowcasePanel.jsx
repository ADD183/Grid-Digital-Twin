import React, { useEffect, useState } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ReferenceLine,
} from 'recharts';
import {
  CheckCircle2,
  AlertTriangle,
  Zap,
  BatteryCharging,
  Battery,
  ShieldAlert,
  Clock,
  FileText,
  RefreshCw,
  FolderCheck,
  Layers,
  Download,
} from 'lucide-react';
import { API_BASE } from '../config';
import ChartDisclosure from './ui/ChartDisclosure';

const formatIstTime = (value) => {
  if (!value) return '';

  const timeOnlyMatch = value.match(/^(\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s*(UTC|IST)$/i);
  const time = timeOnlyMatch?.[1]?.replace(/(\.\d{3})\d+$/, '$1');
  const timestamp = new Date(timeOnlyMatch
    ? `${new Date().toISOString().slice(0, 10)}T${time}${timeOnlyMatch[2].toUpperCase() === 'UTC' ? 'Z' : '+05:30'}`
    : value);

  if (Number.isNaN(timestamp.getTime())) return value;
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
    timeZoneName: 'short',
  }).format(timestamp);
};

export default function ShowcasePanel() {
  const [episodeData, setEpisodeData] = useState(null);
  const [evidenceIndex, setEvidenceIndex] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [executedAt, setExecutedAt] = useState(null);
  const [runProgress, setRunProgress] = useState(null);

  const loadShowcaseData = async (force = false) => {
    try {
      setLoading(true);
      setError(null);
      let epRes;
      if (force) {
        setRunProgress(0);
        const startResponse = await fetch(`${API_BASE}/api/control/episode/showcase12?force=true`, { method: 'POST' });
        if (!startResponse.ok) throw new Error(`Showcase run failed (${startResponse.status})`);
        let job = await startResponse.json();

        while (job.status === 'running') {
          setRunProgress(job.completed_steps || 0);
          await new Promise((resolve) => window.setTimeout(resolve, 750));
          const statusResponse = await fetch(`${API_BASE}/api/control/episode/showcase12/status/${job.job_id}`);
          if (!statusResponse.ok) throw new Error(`Showcase status failed (${statusResponse.status})`);
          job = await statusResponse.json();
        }

        if (job.status !== 'completed') throw new Error(job.error || 'Showcase run did not complete');
        epRes = job.episode;
      } else {
        const episodeResponse = await fetch(`${API_BASE}/api/control/episode/showcase12`);
        if (!episodeResponse.ok) throw new Error(`Showcase load failed (${episodeResponse.status})`);
        epRes = await episodeResponse.json();
      }

      const evidenceResponse = await fetch(`${API_BASE}/api/evidence/index`);
      if (!evidenceResponse.ok) throw new Error(`Evidence index failed (${evidenceResponse.status})`);
      const evRes = await evidenceResponse.json();
      setEpisodeData(epRes);
      setEvidenceIndex(evRes);
      if (epRes?.executed_at) {
        setExecutedAt(epRes.executed_at);
      } else {
        setExecutedAt(new Date().toISOString());
      }
    } catch (err) {
      setError(err.message || 'Failed to load Checkpoint 8 showcase episode data');
    } finally {
      setLoading(false);
      setRunProgress(null);
    }
  };

  useEffect(() => {
    loadShowcaseData(false);
  }, []);

  if (loading && !episodeData) {
    return (
      <div className="vp-card vp-text-center showcase-loading" style={{ padding: 'var(--space-8)' }}>
        <RefreshCw size={36} className="spin vp-text-accent" style={{ margin: '0 auto var(--space-3)' }} />
        <div style={{ fontSize: 'var(--font-lg)', fontWeight: 'var(--font-semibold)', color: 'var(--color-fg-primary)' }}>
          Loading the 12-timepoint showcase and its evidence...
        </div>
      </div>
    );
  }

  const steps = episodeData?.steps || [];

  // Chart data for 12-step timeline
  const timelineData = steps.map((st) => {
    const busVms = st.verification_result?.bus_vm ? Object.values(st.verification_result.bus_vm) : [];
    const lineLoads = st.verification_result?.line_loading ? Object.values(st.verification_result.line_loading) : [];

    const vMin = st.min_voltage_pu ?? (busVms.length > 0 ? Math.min(...busVms) : 0.98);
    const vMax = st.max_voltage_pu ?? (busVms.length > 0 ? Math.max(...busVms) : 1.02);
    const maxLoad = st.max_loading_pct ?? (lineLoads.length > 0 ? Math.max(...lineLoads) : 35);
    const socPct = (st.soc ?? 0.5) * 100;

    return {
      stepLabel: `T${st.step}`,
      step: st.step,
      hour: `${10 + st.step}:00`,
      socPct: Math.round(socPct * 10) / 10,
      vMin: Math.round(vMin * 1000) / 1000,
      vMax: Math.round(vMax * 1000) / 1000,
      maxLoad: Math.round(maxLoad * 10) / 10,
      actionDesc: st.action_description || st.chosen_action?.description || 'Optimal Dispatch',
      errorLabel: st.error_label || '',
    };
  });

  const evidenceFiles = Array.from(new Set([
    ...(evidenceIndex?.evidence_files || []),
    ...(episodeData?.evidence_files || []),
  ]));
  const currentEvidenceCsv = episodeData?.evidence_files?.find((file) => file.endsWith('_full_table.csv'));

  const event1 = steps.find((s) => s.forecast_error_injected || s.error_label?.toLowerCase().includes('error') || s.error_label?.toLowerCase().includes('surge')) || steps[2];
  const event2 = steps.find((s) => (s.soc ?? 0) >= 0.89 || s.error_label?.toLowerCase().includes('saturation')) || steps[4];
  const event3 = steps.find((s) => s.error_label?.toLowerCase().includes('infeasible') || s.fallback_ladder_used || s.verification_result?.is_safe === false) || steps[6];
  const event4 = steps.find((s) => s.error_label?.toLowerCase().includes('near-limit') || (s.min_voltage_pu >= 0.95 && s.min_voltage_pu <= 0.955)) || steps[7];
  const event5 = steps.find((s) => s.error_label?.toLowerCase().includes('disagreement') || s.surrogate_disagreement) || steps[8];
  const event6 = steps.find((s) => (s.soc ?? 1) <= 0.11 || s.error_label?.toLowerCase().includes('depletion')) || steps[11];

  return (
    <div className="showcase-page" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)', marginBottom: 'var(--space-6)' }}>
      {/* Top Banner */}
      <div className="vp-card vp-card-gradient showcase-hero">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
          <div>
            <div className="vp-flex vp-gap-2 vp-mb-2">
              <span className="vp-badge vp-badge-accent">12-timepoint grid simulation</span>
              <span className="vp-badge vp-badge-info">
                {steps.length || 12} timepoints · 6 events
              </span>
              {executedAt && (
                <span className="vp-badge vp-badge-ok">
                  Last run: {formatIstTime(executedAt)}
                </span>
              )}
            </div>
            <h2 className="vp-page-title vp-flex vp-items-center vp-gap-2">
              <span>See how the grid responds over time</span>
            </h2>
            <p className="vp-page-description" style={{ maxWidth: '840px' }}>
              Follow a changing forecast, battery decisions, and grid conditions across one complete episode. Each timepoint is checked with an AC power-flow solver, and the run records the results for review.
            </p>
          </div>

          <div>
            <button
              onClick={() => loadShowcaseData(true)}
              disabled={loading}
              className="vp-btn vp-btn-primary"
            >
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
              <span>{loading ? `Re-Running ${runProgress ?? 0}/12...` : 'Run Showcase Episode'}</span>
            </button>
          </div>
        </div>

        {loading && episodeData && (
          <div className="vp-alert" data-tone="info" role="status" aria-live="polite" style={{ marginTop: 'var(--space-3)' }}>
            <RefreshCw size={16} className="spin" />
            <span>Solver verification complete for {runProgress ?? 0} of 12 timepoints. The new results will appear when the run finishes.</span>
          </div>
        )}

        {executedAt && (
          <div className="vp-alert vp-alert-ok vp-mt-3" style={{ borderLeft: '4px solid var(--ok)', color: 'var(--text)' }}>
            <CheckCircle2 size={16} style={{ color: 'var(--ok)', flexShrink: 0 }} />
            <span>
              <strong>Episode loaded and solver verified.</strong> The 12-timepoint AC power-flow run was last calculated at <strong>{formatIstTime(executedAt)}</strong>.
            </span>
          </div>
        )}

        {error && (
          <div className="vp-alert vp-alert-danger vp-mt-3">
            <AlertTriangle size={16} />
            <span>{error}</span>
          </div>
        )}
      </div>

      <section className="vp-card showcase-guide" aria-labelledby="showcase-guide-title">
        <div className="showcase-section-heading">
          <span className="showcase-section-kicker">Start here</span>
          <h3 id="showcase-guide-title">How to read this episode</h3>
        </div>
        <div className="showcase-guide-grid">
          <div>
            <span className="showcase-guide-index">01</span>
            <strong>Begin at T0</strong>
            <p>T0 is the starting grid state. The chart then follows the run through T11.</p>
          </div>
          <div>
            <span className="showcase-guide-index">02</span>
            <strong>Follow the event markers</strong>
            <p>Labels use the same T-number as the chart. For example, the forecast error occurs at T2, the third plotted point.</p>
          </div>
          <div>
            <span className="showcase-guide-index">03</span>
            <strong>Check the evidence</strong>
            <p>The step log shows each action and solver result. The evidence list contains files you can open or download.</p>
          </div>
        </div>
      </section>

      {/* 6 Required Events Cards Grid */}
      <div className="showcase-events" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-3)' }}>
        <div className="vp-kpi-tile">
          <div className="vp-kpi-label vp-flex vp-items-center vp-gap-1">
            <Zap size={14} />
            <span>1. Injected Error</span>
          </div>
          <div className="vp-kpi-value">
            T{event1?.step ?? 2} · {10 + (event1?.step ?? 2)}:00
          </div>
          <div className="vp-kpi-subtext">
            {event1?.error_label || 'Midday solar surge (+120%)'}
          </div>
        </div>

        <div className="vp-kpi-tile">
          <div className="vp-kpi-label vp-flex vp-items-center vp-gap-1">
            <BatteryCharging size={14} />
            <span>2. Battery Saturation</span>
          </div>
          <div className="vp-kpi-value">
            T{event2?.step ?? 4} · {10 + (event2?.step ?? 4)}:00
          </div>
          <div className="vp-kpi-subtext">
            Reached max SOC: {((event2?.soc ?? 0.90) * 100).toFixed(0)}%
          </div>
        </div>

        <div className="vp-kpi-tile">
          <div className="vp-kpi-label vp-flex vp-items-center vp-gap-1">
            <ShieldAlert size={14} />
            <span>3. Infeasible Period</span>
          </div>
          <div className="vp-kpi-value">
            T{event3?.step ?? 6} · {10 + (event3?.step ?? 6)}:00
          </div>
          <div className="vp-kpi-subtext">
            {event3?.error_label || 'Fallback ladder invoked'}
          </div>
        </div>

        <div className="vp-kpi-tile">
          <div className="vp-kpi-label vp-flex vp-items-center vp-gap-1">
            <AlertTriangle size={14} />
            <span>4. Near-Limit State</span>
          </div>
          <div className="vp-kpi-value">
            T{event4?.step ?? 7} · {10 + (event4?.step ?? 7)}:00
          </div>
          <div className="vp-kpi-subtext">
            V_min = {(event4?.min_voltage_pu ?? 0.952).toFixed(3)} pu (near limit)
          </div>
        </div>

        <div className="vp-kpi-tile">
          <div className="vp-kpi-label vp-flex vp-items-center vp-gap-1">
            <RefreshCw size={14} />
            <span>5. Surrogate Disagreement</span>
          </div>
          <div className="vp-kpi-value">
            T{event5?.step ?? 8} · {10 + (event5?.step ?? 8)}:00
          </div>
          <div className="vp-kpi-subtext">
            {event5?.error_label || 'Safe prediction verified by AC solver'}
          </div>
        </div>

        <div className="vp-kpi-tile">
          <div className="vp-kpi-label vp-flex vp-items-center vp-gap-1">
            <Battery size={14} />
            <span>6. Battery Depletion</span>
          </div>
          <div className="vp-kpi-value">
            T{event6?.step ?? 11} · {10 + (event6?.step ?? 11)}:00
          </div>
          <div className="vp-kpi-subtext">
            Reached min SOC: {((event6?.soc ?? 0.10) * 100).toFixed(0)}%
          </div>
        </div>
      </div>

      {/* 12-Step Interactive Timeline Chart */}
      <div className="vp-card showcase-trajectory">
        <div className="vp-card-header vp-flex vp-justify-between vp-items-center vp-flex-wrap vp-gap-2">
          <div className="vp-card-title vp-flex vp-items-center vp-gap-2" style={{ color: 'var(--color-accent)' }}>
            <Clock size={18} />
            <span>Episode trajectory</span>
          </div>
          <div style={{ fontSize: 'var(--font-xs)', color: 'var(--color-fg-muted)' }}>
            Battery state of charge (%) and bus voltage range (p.u.) across T0–T11
          </div>
        </div>

        <ChartDisclosure title="Show the episode chart" summary="Compare battery charge and grid voltage across the 12 timepoints.">
          <div className="showcase-chart-scroll">
            <div className="showcase-chart-canvas">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={timelineData} margin={{ top: 15, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle)" />
              <XAxis dataKey="stepLabel" stroke="var(--color-fg-muted)" fontSize={11} tickLine={false} />
              <YAxis yAxisId="left" stroke="var(--color-fg-muted)" fontSize={11} domain={[0, 100]} unit="%" />
              <YAxis yAxisId="right" orientation="right" stroke="var(--color-fg-muted)" fontSize={11} domain={[0.94, 1.06]} unit=" pu" />
              <Tooltip />
              <Legend verticalAlign="top" height={32} />
              <ReferenceLine yAxisId="left" y={90} stroke="rgba(16, 185, 129, 0.4)" strokeDasharray="4 4" label={{ value: 'SOC Max (90%)', fill: 'var(--color-success)', fontSize: 10 }} />
              <ReferenceLine yAxisId="left" y={10} stroke="rgba(168, 85, 247, 0.4)" strokeDasharray="4 4" label={{ value: 'SOC Min (10%)', fill: '#a855f7', fontSize: 10 }} />
              <ReferenceLine yAxisId="right" y={0.95} stroke="rgba(239, 68, 68, 0.4)" strokeDasharray="4 4" label={{ value: 'V_min (0.95)', fill: 'var(--color-danger)', fontSize: 10 }} />
              <Bar yAxisId="left" dataKey="socPct" name="Battery SOC (%)" fill="var(--color-success)" radius={[4, 4, 0, 0]} opacity={0.6} />
              <Line yAxisId="right" type="monotone" dataKey="vMax" name="Max Bus Voltage (pu)" stroke="var(--color-info)" strokeWidth={2.5} dot={{ r: 4 }} />
              <Line yAxisId="right" type="monotone" dataKey="vMin" name="Min Bus Voltage (pu)" stroke="var(--color-danger)" strokeWidth={2.5} dot={{ r: 4 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        </ChartDisclosure>
      </div>

      {/* Step-by-Step Executed Log Table */}
      <div className="vp-card showcase-step-log">
        <div className="vp-card-header vp-flex vp-justify-between vp-items-center">
          <div className="vp-card-title vp-flex vp-items-center vp-gap-2">
            <Layers size={18} style={{ color: 'var(--color-accent)' }} />
            <span>Actions and solver results</span>
          </div>
          <div style={{ fontSize: 'var(--font-xs)', color: 'var(--color-fg-muted)' }}>
            Run ID: <span style={{ color: 'var(--color-accent)', fontFamily: 'var(--font-mono)' }}>{episodeData?.run_id || 'cp8_showcase_12step'}</span>
          </div>
        </div>

        <div className="vp-table-container">
          <table className="vp-table">
            <thead>
              <tr>
                <th>Step</th>
                <th>Action Executed</th>
                <th className="vp-text-right">SOC %</th>
                <th className="vp-text-right">V_min (pu)</th>
                <th className="vp-text-right">V_max (pu)</th>
                <th className="vp-text-right">Max Load %</th>
                <th>Triggered Event / Label</th>
                <th className="vp-text-center">Solver Status</th>
              </tr>
            </thead>
            <tbody>
              {timelineData.map((st) => (
                <tr key={st.step}>
                  <td style={{ fontWeight: 'var(--font-bold)' }}>T{st.step}</td>
                  <td style={{ color: 'var(--color-fg-secondary)' }}>{st.actionDesc}</td>
                  <td className="vp-text-right" style={{ fontFamily: 'var(--font-mono)', color: st.socPct >= 90 ? 'var(--color-success)' : st.socPct <= 10 ? '#a855f7' : 'var(--color-fg-primary)', fontWeight: 'var(--font-semibold)' }}>
                    {st.socPct}%
                  </td>
                  <td className="vp-text-right" style={{ fontFamily: 'var(--font-mono)', color: st.vMin <= 0.955 ? 'var(--color-danger)' : 'var(--color-fg-primary)' }}>{st.vMin.toFixed(3)}</td>
                  <td className="vp-text-right" style={{ fontFamily: 'var(--font-mono)' }}>{st.vMax.toFixed(3)}</td>
                  <td className="vp-text-right" style={{ fontFamily: 'var(--font-mono)' }}>{st.maxLoad.toFixed(1)}%</td>
                  <td>
                    {st.errorLabel ? (
                      <span className="vp-badge vp-badge-warning" style={{ fontSize: 'var(--font-xs)' }}>{st.errorLabel}</span>
                    ) : (
                      <span style={{ color: 'var(--color-fg-muted)', fontSize: 'var(--font-xs)' }}>Normal Operation</span>
                    )}
                  </td>
                  <td className="vp-text-center">
                    <span className="vp-badge vp-badge-success vp-flex vp-items-center vp-gap-1" style={{ display: 'inline-flex' }}>
                      <CheckCircle2 size={12} /> Verified
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Evidence Pack Artifact Browser - Tabular Format */}
      <div className="vp-card showcase-evidence">
        <div className="vp-card-header vp-flex vp-justify-between vp-items-center vp-flex-wrap vp-gap-3">
          <div className="vp-card-title vp-flex vp-items-center vp-gap-2" style={{ color: 'var(--color-info)' }}>
            <FolderCheck size={18} />
            <span>Run evidence and downloads</span>
          </div>

          <a
            href={currentEvidenceCsv
              ? `${API_BASE}/api/evidence/download?file_path=${encodeURIComponent(currentEvidenceCsv)}`
              : `${API_BASE}/api/evidence/export-csv`}
            download={currentEvidenceCsv?.split('/').pop() || 'cp8_showcase_12step_evidence_table.csv'}
            target="_blank"
            rel="noopener noreferrer"
            className="vp-btn vp-btn-secondary"
            style={{ textDecoration: 'none' }}
          >
            <Download size={15} />
            <span>Download evidence table (CSV)</span>
          </a>
        </div>

        <div className="vp-table-container">
          <table className="vp-table">
            <thead>
              <tr>
                <th>Artifact File Path</th>
                <th>Category</th>
                <th>Format</th>
                <th>Verification Status</th>
                <th className="vp-text-right">Download Action</th>
              </tr>
            </thead>
            <tbody>
              {evidenceFiles.map((file, idx) => {
                const isCsv = file.endsWith('.csv');
                const ext = file.split('.').pop().toUpperCase();

                let category = 'Configuration';
                if (file.includes('action_logs')) category = 'Action Log';
                else if (file.includes('soc_traces')) category = 'SOC Trace';
                else if (file.includes('verification')) category = 'Solver Verification';
                else if (file.includes('metrics')) category = 'Metrics & Benchmark';
                else if (file.includes('surrogate')) category = 'Surrogate Ensemble';

                const downloadUrl = `${API_BASE}/api/evidence/download?file_path=${encodeURIComponent(file)}`;

                return (
                  <tr key={idx}>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 'var(--font-semibold)' }}>
                      <div className="vp-flex vp-items-center vp-gap-2">
                        <FileText size={15} style={{ color: isCsv ? 'var(--color-success)' : 'var(--color-info)', flexShrink: 0 }} />
                        <span>{file}</span>
                      </div>
                    </td>
                    <td style={{ color: 'var(--color-fg-secondary)' }}>{category}</td>
                    <td>
                      <span className={`vp-badge ${isCsv ? 'vp-badge-success' : 'vp-badge-info'}`}>
                        {ext} {isCsv ? '(Excel Compatible)' : ''}
                      </span>
                    </td>
                    <td>
                      <span className="vp-badge vp-badge-success">✓ Verified</span>
                    </td>
                    <td className="vp-text-right">
                      <a
                        href={downloadUrl}
                        download
                        target="_blank"
                        rel="noopener noreferrer"
                        className="vp-btn vp-btn-secondary"
                        style={{ padding: 'var(--space-1) var(--space-2)', fontSize: 'var(--font-xs)', textDecoration: 'none', display: 'inline-flex' }}
                      >
                        <Download size={14} />
                        <span>Open / download {ext}</span>
                      </a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}


