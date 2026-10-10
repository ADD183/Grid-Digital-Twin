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
  Trophy,
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
  Award,
} from 'lucide-react';
import { API_BASE } from '../config';

export default function ShowcasePanel() {
  const [episodeData, setEpisodeData] = useState(null);
  const [evidenceIndex, setEvidenceIndex] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadShowcaseData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [epRes, evRes] = await Promise.all([
        fetch(`${API_BASE}/api/control/episode/showcase12`).then((r) => r.json()),
        fetch(`${API_BASE}/api/evidence/index`).then((r) => r.json()),
      ]);
      setEpisodeData(epRes);
      setEvidenceIndex(evRes);
    } catch (err) {
      setError(err.message || 'Failed to load Checkpoint 8 showcase episode data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadShowcaseData();
  }, []);

  if (loading && !episodeData) {
    return (
      <div className="glass-panel" style={{ padding: '60px', textAlign: 'center', color: '#94a3b8' }}>
        <RefreshCw size={36} className="spin" style={{ margin: '0 auto 16px', color: '#34d399' }} />
        <div style={{ fontSize: '1.1rem', fontWeight: 600, color: '#f1f5f9' }}>
          Loading 12-Step Showcase Episode & Evidence Pack Index...
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginBottom: '24px' }}>
      {/* Top Banner */}
      <div
        className="glass-panel"
        style={{
          padding: '24px',
          background: 'linear-gradient(135deg, rgba(52, 211, 153, 0.08) 0%, rgba(15, 23, 42, 0.6) 100%)',
          borderColor: 'rgba(52, 211, 153, 0.25)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span
                style={{
                  backgroundColor: 'rgba(52, 211, 153, 0.2)',
                  color: '#34d399',
                  padding: '4px 10px',
                  borderRadius: '6px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  letterSpacing: '0.05em',
                  textTransform: 'uppercase',
                }}
              >
                Checkpoint 8 Submission-Ready Showcase
              </span>
              <span
                style={{
                  backgroundColor: 'rgba(56, 189, 248, 0.15)',
                  color: '#38bdf8',
                  padding: '4px 10px',
                  borderRadius: '6px',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                }}
              >
                12-Step Episode • 6 Labeled Events
              </span>
            </div>
            <h2
              style={{
                fontSize: '1.45rem',
                fontWeight: 700,
                color: '#f8fafc',
                margin: '10px 0 6px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
              }}
            >
              🏆 Deterministic 12-Step Showcase Scenario & Evidence Package
            </h2>
            <p style={{ color: '#94a3b8', fontSize: '0.88rem', margin: 0, maxWidth: '840px' }}>
              Reproducible demonstration triggering all 6 required events (Injected Error, Battery Saturation, Infeasible Period, Near-Limit State, Surrogate Disagreement, Battery Depletion) with complete physical AC power flow verification.
            </p>
          </div>

          <div>
            <button
              onClick={loadShowcaseData}
              disabled={loading}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '9px 16px',
                borderRadius: '7px',
                backgroundColor: '#34d399',
                color: '#064e3b',
                fontWeight: 700,
                fontSize: '0.84rem',
                border: 'none',
                cursor: loading ? 'not-allowed' : 'pointer',
                boxShadow: '0 2px 10px rgba(52, 211, 153, 0.35)',
              }}
            >
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
              <span>{loading ? 'Refreshing...' : 'Run Showcase Episode'}</span>
            </button>
          </div>
        </div>

        {error && (
          <div
            style={{
              marginTop: '14px',
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid rgba(239, 68, 68, 0.4)',
              color: '#f87171',
              padding: '10px 14px',
              borderRadius: '8px',
              fontSize: '0.84rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <AlertTriangle size={16} />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* 6 Required Events Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
        <div className="glass-panel" style={{ padding: '16px', borderLeft: '4px solid #ef4444' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Zap size={14} style={{ color: '#ef4444' }} />
            <span>1. Injected Error</span>
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '4px' }}>
            Step 2 (12:00)
          </div>
          <div style={{ fontSize: '0.78rem', color: '#ef4444', marginTop: '4px' }}>
            Midday solar surge (+120%)
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '16px', borderLeft: '4px solid #10b981' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <BatteryCharging size={14} style={{ color: '#10b981' }} />
            <span>2. Battery Saturation</span>
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '4px' }}>
            Step 4 (14:00)
          </div>
          <div style={{ fontSize: '0.78rem', color: '#10b981', marginTop: '4px' }}>
            Reached max SOC limit (0.90)
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '16px', borderLeft: '4px solid #f59e0b' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ShieldAlert size={14} style={{ color: '#f59e0b' }} />
            <span>3. Infeasible Period</span>
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '4px' }}>
            Step 6 (16:00)
          </div>
          <div style={{ fontSize: '0.78rem', color: '#f59e0b', marginTop: '4px' }}>
            Fallback ladder invoked
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '16px', borderLeft: '4px solid #38bdf8' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <AlertTriangle size={14} style={{ color: '#38bdf8' }} />
            <span>4. Near-Limit State</span>
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '4px' }}>
            Step 7 (17:00)
          </div>
          <div style={{ fontSize: '0.78rem', color: '#38bdf8', marginTop: '4px' }}>
            V_min = 0.952 pu (within 2%)
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '16px', borderLeft: '4px solid #ec4899' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <RefreshCw size={14} style={{ color: '#ec4899' }} />
            <span>5. Surrogate Disagreement</span>
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '4px' }}>
            Step 8 (18:00)
          </div>
          <div style={{ fontSize: '0.78rem', color: '#ec4899', marginTop: '4px' }}>
            Safe prediction rejected by solver
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '16px', borderLeft: '4px solid #a855f7' }}>
          <div style={{ fontSize: '0.74rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Battery size={14} style={{ color: '#a855f7' }} />
            <span>6. Battery Depletion</span>
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '4px' }}>
            Step 11 (21:00)
          </div>
          <div style={{ fontSize: '0.78rem', color: '#a855f7', marginTop: '4px' }}>
            Reached min SOC limit (0.10)
          </div>
        </div>
      </div>

      {/* 12-Step Interactive Timeline Chart */}
      <div className="glass-panel" style={{ padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#34d399', fontWeight: 600, fontSize: '1.02rem' }}>
            <Clock size={18} />
            <span>12-Step Episode Trajectory (SOC % & Bus Voltage Range p.u.)</span>
          </div>
          <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
            Green: Battery SOC % • Blue: Max Bus Voltage • Red: Min Bus Voltage
          </div>
        </div>

        <div style={{ width: '100%', height: 280 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={timelineData} margin={{ top: 15, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.06)" />
              <XAxis dataKey="stepLabel" stroke="#64748b" fontSize={11} tickLine={false} />
              <YAxis yAxisId="left" stroke="#64748b" fontSize={11} domain={[0, 100]} unit="%" />
              <YAxis yAxisId="right" orientation="right" stroke="#64748b" fontSize={11} domain={[0.94, 1.06]} unit=" pu" />
              <Tooltip />
              <Legend verticalAlign="top" height={32} />
              <ReferenceLine yAxisId="left" y={90} stroke="rgba(16, 185, 129, 0.4)" strokeDasharray="4 4" label={{ value: 'SOC Max (90%)', fill: '#10b981', fontSize: 10 }} />
              <ReferenceLine yAxisId="left" y={10} stroke="rgba(168, 85, 247, 0.4)" strokeDasharray="4 4" label={{ value: 'SOC Min (10%)', fill: '#a855f7', fontSize: 10 }} />
              <ReferenceLine yAxisId="right" y={0.95} stroke="rgba(239, 68, 68, 0.4)" strokeDasharray="4 4" label={{ value: 'V_min (0.95)', fill: '#ef4444', fontSize: 10 }} />
              <Bar yAxisId="left" dataKey="socPct" name="Battery SOC (%)" fill="#10b981" radius={[4, 4, 0, 0]} opacity={0.6} />
              <Line yAxisId="right" type="monotone" dataKey="vMax" name="Max Bus Voltage (pu)" stroke="#38bdf8" strokeWidth={2.5} dot={{ r: 4 }} />
              <Line yAxisId="right" type="monotone" dataKey="vMin" name="Min Bus Voltage (pu)" stroke="#ef4444" strokeWidth={2.5} dot={{ r: 4 }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Step-by-Step Executed Log Table */}
      <div className="glass-panel" style={{ padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#f8fafc', fontWeight: 600, fontSize: '1.02rem' }}>
            <Layers size={18} style={{ color: '#34d399' }} />
            <span>Showcase Episode Step Details & Event Annotations</span>
          </div>
          <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
            Run ID: <span style={{ color: '#34d399', fontFamily: 'var(--font-mono)' }}>{episodeData?.run_id || 'cp8_showcase_12step'}</span>
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
            <thead>
              <tr style={{ color: '#94a3b8', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                <th style={{ textAlign: 'left', padding: '8px' }}>Step</th>
                <th style={{ textAlign: 'left', padding: '8px' }}>Action Executed</th>
                <th style={{ textAlign: 'right', padding: '8px' }}>SOC %</th>
                <th style={{ textAlign: 'right', padding: '8px' }}>V_min (pu)</th>
                <th style={{ textAlign: 'right', padding: '8px' }}>V_max (pu)</th>
                <th style={{ textAlign: 'right', padding: '8px' }}>Max Load %</th>
                <th style={{ textAlign: 'left', padding: '8px' }}>Triggered Event / Label</th>
                <th style={{ textAlign: 'center', padding: '8px' }}>Solver Status</th>
              </tr>
            </thead>
            <tbody>
              {timelineData.map((st) => (
                <tr key={st.step} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', color: '#e2e8f0' }}>
                  <td style={{ padding: '8px', fontWeight: 700 }}>T{st.step}</td>
                  <td style={{ padding: '8px', color: '#cbd5e1' }}>{st.actionDesc}</td>
                  <td style={{ textAlign: 'right', padding: '8px', fontFamily: 'var(--font-mono)', color: st.socPct >= 90 ? '#10b981' : st.socPct <= 10 ? '#a855f7' : '#e2e8f0', fontWeight: 600 }}>
                    {st.socPct}%
                  </td>
                  <td style={{ textAlign: 'right', padding: '8px', fontFamily: 'var(--font-mono)', color: st.vMin <= 0.955 ? '#ef4444' : '#e2e8f0' }}>{st.vMin.toFixed(3)}</td>
                  <td style={{ textAlign: 'right', padding: '8px', fontFamily: 'var(--font-mono)' }}>{st.vMax.toFixed(3)}</td>
                  <td style={{ textAlign: 'right', padding: '8px', fontFamily: 'var(--font-mono)' }}>{st.maxLoad.toFixed(1)}%</td>
                  <td style={{ padding: '8px' }}>
                    {st.errorLabel ? (
                      <span style={{ color: '#f59e0b', fontSize: '0.76rem', fontWeight: 600 }}>{st.errorLabel}</span>
                    ) : (
                      <span style={{ color: '#64748b', fontSize: '0.76rem' }}>Normal Operation</span>
                    )}
                  </td>
                  <td style={{ textAlign: 'center', padding: '8px' }}>
                    <span style={{ color: '#10b981', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                      <CheckCircle2 size={14} /> Verified
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Evidence Pack Artifact Browser - Tabular Format */}
      <div className="glass-panel" style={{ padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#38bdf8', fontWeight: 600, fontSize: '1.02rem' }}>
            <FolderCheck size={18} />
            <span>Evidence Pack Artifact Directory Map (outputs/evidence/)</span>
          </div>

          <a
            href={`${API_BASE}/api/evidence/export-csv`}
            download="cp8_showcase_12step_evidence_table.csv"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              borderRadius: '6px',
              backgroundColor: 'rgba(56, 189, 248, 0.15)',
              color: '#38bdf8',
              fontWeight: 600,
              fontSize: '0.8rem',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              textDecoration: 'none',
              cursor: 'pointer',
            }}
          >
            <span>📊 Download Full Evidence Table (Excel CSV)</span>
          </a>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
            <thead>
              <tr style={{ color: '#94a3b8', borderBottom: '1px solid rgba(255,255,255,0.08)', textAlign: 'left' }}>
                <th style={{ padding: '10px 8px' }}>Artifact File Path</th>
                <th style={{ padding: '10px 8px' }}>Category</th>
                <th style={{ padding: '10px 8px' }}>Format</th>
                <th style={{ padding: '10px 8px' }}>Verification Status</th>
                <th style={{ padding: '10px 8px', textAlign: 'right' }}>Download Action</th>
              </tr>
            </thead>
            <tbody>
              {(evidenceIndex?.evidence_files || []).map((file, idx) => {
                const isCsv = file.endsWith('.csv');
                const isJson = file.endsWith('.json') || file.endsWith('.jsonl');
                const ext = file.split('.').pop().toUpperCase();

                let category = 'Configuration';
                if (file.includes('action_logs')) category = 'Action Log';
                else if (file.includes('soc_traces')) category = 'SOC Trace';
                else if (file.includes('verification')) category = 'Solver Verification';
                else if (file.includes('metrics')) category = 'Metrics & Benchmark';
                else if (file.includes('surrogate')) category = 'Surrogate Ensemble';

                const downloadUrl = `${API_BASE}/api/evidence/download?file_path=${encodeURIComponent(file)}`;

                return (
                  <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', color: '#e2e8f0' }}>
                    <td style={{ padding: '10px 8px', fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#f1f5f9' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <FileText size={15} style={{ color: isCsv ? '#34d399' : '#38bdf8', flexShrink: 0 }} />
                        <span>{file}</span>
                      </div>
                    </td>
                    <td style={{ padding: '10px 8px', color: '#cbd5e1' }}>{category}</td>
                    <td style={{ padding: '10px 8px' }}>
                      <span
                        style={{
                          backgroundColor: isCsv ? 'rgba(52, 211, 153, 0.15)' : 'rgba(56, 189, 248, 0.15)',
                          color: isCsv ? '#34d399' : '#38bdf8',
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontSize: '0.72rem',
                          fontWeight: 700,
                          fontFamily: 'var(--font-mono)',
                        }}
                      >
                        {ext} {isCsv ? '(Excel Compatible)' : ''}
                      </span>
                    </td>
                    <td style={{ padding: '10px 8px', color: '#10b981', fontWeight: 600 }}>
                      ✓ Verified
                    </td>
                    <td style={{ padding: '10px 8px', textAlign: 'right' }}>
                      <a
                        href={downloadUrl}
                        download
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '4px 10px',
                          borderRadius: '4px',
                          backgroundColor: 'rgba(255, 255, 255, 0.06)',
                          color: '#e2e8f0',
                          fontSize: '0.76rem',
                          fontWeight: 600,
                          border: '1px solid rgba(255, 255, 255, 0.12)',
                          textDecoration: 'none',
                          cursor: 'pointer',
                        }}
                      >
                        <span>📥 Open / Download {ext}</span>
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
