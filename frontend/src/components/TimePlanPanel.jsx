import React, { useEffect, useState } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line,
  BarChart,
  Bar,
  ComposedChart,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ReferenceLine,
} from 'recharts';
import {
  Play,
  RefreshCw,
  BatteryCharging,
  Battery,
  Zap,
  TrendingUp,
  AlertTriangle,
  ShieldCheck,
  CheckCircle2,
  Clock,
  Sliders,
  Cpu,
  Layers,
  Info,
} from 'lucide-react';
import { controlApi } from '../api/client';

export default function TimePlanPanel() {
  const [episode, setEpisode] = useState(null);
  const [limits, setLimits] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedStepIdx, setSelectedStepIdx] = useState(0);

  // Simulation controls
  const [injectError, setInjectError] = useState(true);
  const [forceInfeasible, setForceInfeasible] = useState(false);
  const [initialSoc, setInitialSoc] = useState(0.5);

  // Load limits and initial showcase episode on mount
  useEffect(() => {
    let isMounted = true;
    async function init() {
      try {
        setLoading(true);
        const [limitsData, showcaseData] = await Promise.all([
          controlApi.getLimits(),
          controlApi.getShowcaseEpisode(),
        ]);
        if (isMounted) {
          setLimits(limitsData);
          setEpisode(showcaseData);
          setSelectedStepIdx(0);
        }
      } catch (err) {
        if (isMounted) setError(err.message || 'Failed to load control episode data');
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    init();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleRunLiveEpisode = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await controlApi.runEpisode({
        initial_soc: parseFloat(initialSoc),
        inject_error: injectError,
        inject_error_step: 2,
        force_infeasible: forceInfeasible,
        force_infeasible_step: 5,
        run_id: 'live_interactive_run',
      });
      setEpisode(res);
      setSelectedStepIdx(0);
    } catch (err) {
      setError(err.message || 'Episode execution failed');
    } finally {
      setLoading(false);
    }
  };

  const handleReloadShowcase = async () => {
    try {
      setLoading(true);
      setError(null);
      const showcaseData = await controlApi.getShowcaseEpisode();
      setEpisode(showcaseData);
      setSelectedStepIdx(0);
    } catch (err) {
      setError(err.message || 'Failed to reload showcase episode');
    } finally {
      setLoading(false);
    }
  };

  if (!episode && loading) {
    return (
      <div className="glass-panel" style={{ padding: '60px', textAlign: 'center', color: '#94a3b8' }}>
        <RefreshCw size={36} className="spin" style={{ margin: '0 auto 16px', color: '#10b981' }} />
        <div style={{ fontSize: '1.1rem', fontWeight: 600, color: '#f1f5f9' }}>
          Loading Multi-Step Control Engine...
        </div>
        <div style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '6px' }}>
          Connecting with pandapower AC Power Flow physical solver
        </div>
      </div>
    );
  }

  const steps = episode?.steps || [];
  const activeStep = steps[selectedStepIdx] || steps[0];
  const batteryCap = limits?.battery?.capacity_mwh || 2.0;
  const socMinPct = (limits?.battery?.soc_min ?? 0.1) * 100;
  const socMaxPct = (limits?.battery?.soc_max ?? 0.9) * 100;
  const finalSoc = steps.length > 0 ? steps[steps.length - 1].soc : 0.5;
  const replanSteps = episode?.replan_steps || [];
  const infeasibleSteps = episode?.infeasible_steps || [];

  // Transform data for charts
  const chartData = steps.map((s) => ({
    name: `T${s.step}`,
    step: s.step,
    hour: s.forecast?.hour ?? 10 + s.step,
    soc: Math.round(s.soc * 1000) / 10,
    socMwh: Math.round(s.soc * batteryCap * 100) / 100,
    batteryMw: s.chosen_action?.battery_mw ?? 0,
    curtailPct: s.chosen_action?.curtail_pct ?? 0,
    solarFc: Math.round((s.forecast?.solar_scale ?? 0) * 100) / 100,
    solarObs: Math.round((s.observed?.solar_scale ?? 0) * 100) / 100,
    loadFc: Math.round((s.forecast?.load_scale ?? 0) * 100) / 100,
    loadObs: Math.round((s.observed?.load_scale ?? 0) * 100) / 100,
    replan: s.replan_flag,
    errorLabel: s.error_label,
    minMargin: s.verification_result?.min_margin ?? 0,
  }));

  const CustomChartTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div
          style={{
            backgroundColor: '#090d16',
            border: '1px solid rgba(255,255,255,0.15)',
            padding: '10px 14px',
            borderRadius: '8px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
          }}
        >
          <div
            style={{
              fontSize: '0.78rem',
              color: '#94a3b8',
              marginBottom: '6px',
              fontFamily: 'var(--font-mono)',
              borderBottom: '1px solid rgba(255,255,255,0.08)',
              paddingBottom: '4px',
            }}
          >
            Step {label}
          </div>
          {payload.map((entry, idx) => (
            <div
              key={idx}
              style={{
                fontSize: '0.82rem',
                color: entry.color || '#e2e8f0',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginTop: '3px',
              }}
            >
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: entry.color || '#e2e8f0',
                }}
              />
              <span style={{ color: '#cbd5e1' }}>{entry.name}:</span>
              <strong style={{ fontFamily: 'var(--font-mono)' }}>{entry.value}</strong>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginBottom: '24px' }}>
      {/* Header Banner */}
      <div
        className="glass-panel"
        style={{
          padding: '24px',
          background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(15, 23, 42, 0.6) 100%)',
          borderColor: 'rgba(16, 185, 129, 0.25)',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            flexWrap: 'wrap',
            gap: '16px',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span
                style={{
                  backgroundColor: 'rgba(16, 185, 129, 0.2)',
                  color: '#10b981',
                  padding: '4px 10px',
                  borderRadius: '6px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  letterSpacing: '0.05em',
                  textTransform: 'uppercase',
                }}
              >
                Checkpoint 5 Multi-Step Control
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
                AC Newton-Raphson Verified
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
              ⏱️ Rolling-Horizon Time Plan & Physical Solver Verification
            </h2>
            <p style={{ color: '#94a3b8', fontSize: '0.88rem', margin: 0, maxWidth: '820px' }}>
              Autonomous 8-step rolling-horizon beam-search controller over CIGRE MV grid. Enforces battery SOC
              admissibility, handles forecast drifts with online replanning, and executes the 4-step Fallback Ladder
              with AC power flow verification at every step.
            </p>
          </div>

          {/* Action Buttons & Config Toggles */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
              background: 'rgba(15, 23, 42, 0.7)',
              padding: '14px 16px',
              borderRadius: '10px',
              border: '1px solid rgba(255,255,255,0.08)',
              minWidth: '280px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
              <label
                style={{
                  fontSize: '0.8rem',
                  color: '#cbd5e1',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: 'pointer',
                }}
              >
                <input
                  type="checkbox"
                  checked={injectError}
                  onChange={(e) => setInjectError(e.target.checked)}
                  style={{ cursor: 'pointer', accentColor: '#10b981' }}
                />
                <span>Inject Forecast Error at T2</span>
              </label>
              <label
                style={{
                  fontSize: '0.8rem',
                  color: '#cbd5e1',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: 'pointer',
                }}
              >
                <input
                  type="checkbox"
                  checked={forceInfeasible}
                  onChange={(e) => setForceInfeasible(e.target.checked)}
                  style={{ cursor: 'pointer', accentColor: '#ef4444' }}
                />
                <span title="Inject severe contingency to test fallback ladder">Stress Test (Infeasible)</span>
              </label>
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={handleRunLiveEpisode}
                disabled={loading}
                style={{
                  flex: 1,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  padding: '9px 14px',
                  borderRadius: '7px',
                  backgroundColor: '#10b981',
                  color: '#042f2e',
                  fontWeight: 700,
                  fontSize: '0.84rem',
                  border: 'none',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  boxShadow: '0 2px 10px rgba(16, 185, 129, 0.35)',
                }}
              >
                {loading ? <RefreshCw size={15} className="spin" /> : <Play size={15} />}
                <span>{loading ? 'Running...' : 'Run Live 8-Step Episode'}</span>
              </button>
              <button
                onClick={handleReloadShowcase}
                disabled={loading}
                title="Reset to showcase benchmark"
                style={{
                  padding: '9px 12px',
                  borderRadius: '7px',
                  backgroundColor: 'rgba(255,255,255,0.06)',
                  color: '#cbd5e1',
                  fontWeight: 600,
                  fontSize: '0.84rem',
                  border: '1px solid rgba(255,255,255,0.12)',
                  cursor: 'pointer',
                }}
              >
                <RefreshCw size={14} />
              </button>
            </div>
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

      {/* Metric Cards Row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '14px',
        }}
      >
        <div
          className="glass-panel"
          style={{
            padding: '16px',
            borderLeft: '4px solid #38bdf8',
          }}
        >
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Horizon Steps
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f8fafc', marginTop: '4px' }}>
            {episode?.total_steps || 8} <span style={{ fontSize: '0.85rem', color: '#64748b' }}>steps (1h dt)</span>
          </div>
          <div style={{ fontSize: '0.78rem', color: '#38bdf8', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Clock size={12} />
            <span>Deterministic lookahead</span>
          </div>
        </div>

        <div
          className="glass-panel"
          style={{
            padding: '16px',
            borderLeft: '4px solid #10b981',
          }}
        >
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Battery Capacity
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f8fafc', marginTop: '4px' }}>
            {batteryCap.toFixed(1)} <span style={{ fontSize: '0.85rem', color: '#64748b' }}>MWh (1.0 MW)</span>
          </div>
          <div style={{ fontSize: '0.78rem', color: '#10b981', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <BatteryCharging size={12} />
            <span>Bus 5 • η = 95%</span>
          </div>
        </div>

        <div
          className="glass-panel"
          style={{
            padding: '16px',
            borderLeft: `4px solid ${replanSteps.length > 0 ? '#ec4899' : '#64748b'}`,
          }}
        >
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Replans Triggered
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f8fafc', marginTop: '4px' }}>
            {replanSteps.length}{' '}
            <span style={{ fontSize: '0.85rem', color: replanSteps.length > 0 ? '#ec4899' : '#64748b' }}>
              {replanSteps.length > 0 ? `at ${replanSteps.map((s) => `T${s}`).join(', ')}` : 'zero drift'}
            </span>
          </div>
          <div style={{ fontSize: '0.78rem', color: replanSteps.length > 0 ? '#ec4899' : '#94a3b8', marginTop: '4px' }}>
            {replanSteps.length > 0 ? '⚡ Dynamic plan adjustment' : 'Nominal plan executed'}
          </div>
        </div>

        <div
          className="glass-panel"
          style={{
            padding: '16px',
            borderLeft: `4px solid ${infeasibleSteps.length > 0 ? '#ef4444' : '#10b981'}`,
          }}
        >
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Infeasible Periods
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f8fafc', marginTop: '4px' }}>
            {infeasibleSteps.length}{' '}
            <span style={{ fontSize: '0.85rem', color: infeasibleSteps.length > 0 ? '#ef4444' : '#10b981' }}>
              {infeasibleSteps.length > 0 ? `at ${infeasibleSteps.map((s) => `T${s}`).join(', ')}` : 'fully feasible'}
            </span>
          </div>
          <div style={{ fontSize: '0.78rem', color: infeasibleSteps.length > 0 ? '#ef4444' : '#10b981', marginTop: '4px' }}>
            {infeasibleSteps.length > 0 ? 'Fallback ladder active' : 'All constraints satisfied'}
          </div>
        </div>

        <div
          className="glass-panel"
          style={{
            padding: '16px',
            borderLeft: '4px solid #a855f7',
          }}
        >
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Final Battery SOC
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#f8fafc', marginTop: '4px' }}>
            {(finalSoc * 100).toFixed(1)}%{' '}
            <span style={{ fontSize: '0.85rem', color: '#64748b' }}>
              {(finalSoc * batteryCap).toFixed(2)} MWh
            </span>
          </div>
          <div style={{ fontSize: '0.78rem', color: '#a855f7', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Battery size={12} />
            <span>Safe within [{socMinPct}% - {socMaxPct}%]</span>
          </div>
        </div>
      </div>

      {/* Infeasible Callout Banner (if any) */}
      {infeasibleSteps.length > 0 && (
        <div
          className="glass-panel"
          style={{
            padding: '16px 20px',
            backgroundColor: 'rgba(239, 68, 68, 0.12)',
            border: '1px solid rgba(239, 68, 68, 0.35)',
            borderRadius: '10px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#ef4444', fontWeight: 700, fontSize: '0.98rem' }}>
            <AlertTriangle size={20} />
            <span>Deliberate Infeasible Stress Test Period Detected: Steps {infeasibleSteps.map((s) => `T${s}`).join(', ')}</span>
          </div>
          <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {infeasibleSteps.map((stepIdx) => {
              const rec = steps[stepIdx];
              return (
                <div
                  key={stepIdx}
                  style={{
                    backgroundColor: 'rgba(15, 23, 42, 0.8)',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    fontSize: '0.84rem',
                    color: '#e2e8f0',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: '10px',
                    borderLeft: '4px solid #ef4444',
                  }}
                >
                  <div>
                    <strong>Step T{stepIdx}:</strong> Fallback Ladder Invoked:{' '}
                    <code
                      style={{
                        backgroundColor: 'rgba(239, 68, 68, 0.2)',
                        color: '#fca5a5',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      {rec?.fallback_used || 'infeasible_residual'}
                    </code>
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                    Residual Violations: <strong style={{ color: '#ef4444' }}>{rec?.verification_result?.violations?.length ?? 0}</strong>{' '}
                    | Margin:{' '}
                    <strong style={{ color: '#ef4444', fontFamily: 'var(--font-mono)' }}>
                      {(rec?.verification_result?.min_margin ?? 0).toFixed(4)}
                    </strong>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Main Charts Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '20px' }}>
        {/* 1. Battery State of Charge (SOC) Trajectory */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '16px',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#10b981', fontWeight: 600, fontSize: '1.02rem' }}>
              <BatteryCharging size={20} />
              <span>1. Battery State of Charge (SOC) Trajectory & Operating Envelope</span>
            </div>
            <div style={{ display: 'flex', gap: '14px', fontSize: '0.78rem', color: '#94a3b8' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '10px', height: '2px', backgroundColor: '#ef4444', borderTop: '2px dashed #ef4444' }} />
                <span>SOC Max ({socMaxPct}%)</span>
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: '10px', height: '2px', backgroundColor: '#f59e0b', borderTop: '2px dashed #f59e0b' }} />
                <span>SOC Min ({socMinPct}%)</span>
              </span>
            </div>
          </div>

          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 15, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="socGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.06)" />
                <XAxis dataKey="name" stroke="#64748b" fontSize={11} tickLine={false} />
                <YAxis domain={[0, 100]} stroke="#64748b" fontSize={11} tickLine={false} unit="%" />
                <Tooltip content={<CustomChartTooltip />} />
                <ReferenceLine
                  y={socMaxPct}
                  stroke="#ef4444"
                  strokeDasharray="4 4"
                  label={{ value: `Max ${socMaxPct}%`, fill: '#ef4444', fontSize: 10, position: 'insideTopRight' }}
                />
                <ReferenceLine
                  y={socMinPct}
                  stroke="#f59e0b"
                  strokeDasharray="4 4"
                  label={{ value: `Min ${socMinPct}%`, fill: '#f59e0b', fontSize: 10, position: 'insideBottomRight' }}
                />
                <Area
                  type="monotone"
                  dataKey="soc"
                  name="Battery SOC (%)"
                  stroke="#10b981"
                  strokeWidth={3}
                  fillOpacity={1}
                  fill="url(#socGradient)"
                  dot={{ r: 5, fill: '#047857', stroke: '#10b981', strokeWidth: 2 }}
                  activeDot={{ r: 7, fill: '#34d399' }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 2. Action Dispatch Timeline */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '16px',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#38bdf8', fontWeight: 600, fontSize: '1.02rem' }}>
              <Zap size={20} />
              <span>2. Action Dispatch Timeline: Battery Active Power & Solar Curtailment</span>
            </div>
            <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
              <span style={{ color: '#38bdf8' }}>Positive: Discharge (+MW)</span> •{' '}
              <span style={{ color: '#818cf8' }}>Negative: Charge (-MW)</span> •{' '}
              <span style={{ color: '#f43f5e' }}>Line: Curtailment (%)</span>
            </div>
          </div>

          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 15, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.06)" />
                <XAxis dataKey="name" stroke="#64748b" fontSize={11} tickLine={false} />
                <YAxis
                  yAxisId="power"
                  domain={[-1.2, 1.2]}
                  stroke="#38bdf8"
                  fontSize={11}
                  tickLine={false}
                  unit=" MW"
                />
                <YAxis
                  yAxisId="curtail"
                  orientation="right"
                  domain={[0, 100]}
                  stroke="#f43f5e"
                  fontSize={11}
                  tickLine={false}
                  unit="%"
                />
                <Tooltip content={<CustomChartTooltip />} />
                <Legend verticalAlign="top" height={32} />
                <ReferenceLine yAxisId="power" y={0} stroke="rgba(255,255,255,0.2)" />
                <Bar
                  yAxisId="power"
                  dataKey="batteryMw"
                  name="Battery Dispatch (MW)"
                  fill="#38bdf8"
                  radius={[4, 4, 0, 0]}
                />
                <Line
                  yAxisId="curtail"
                  type="monotone"
                  dataKey="curtailPct"
                  name="Solar Curtailment (%)"
                  stroke="#f43f5e"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: '#f43f5e' }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 3. Forecast vs Observed Conditions & Replan Markers */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '16px',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#facc15', fontWeight: 600, fontSize: '1.02rem' }}>
              <TrendingUp size={20} />
              <span>3. Forecast vs Observed Operating Scales & Replan Markers</span>
            </div>
            <div style={{ fontSize: '0.78rem', color: '#94a3b8' }}>
              Dashed lines: Forecast • Solid lines: Actual Observed • Pink vertical lines: Replan triggers
            </div>
          </div>

          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 15, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.06)" />
                <XAxis dataKey="name" stroke="#64748b" fontSize={11} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
                <Tooltip content={<CustomChartTooltip />} />
                <Legend verticalAlign="top" height={32} />

                {/* Replan markers */}
                {chartData
                  .filter((d) => d.replan)
                  .map((d) => (
                    <ReferenceLine
                      key={`replan-${d.step}`}
                      x={d.name}
                      stroke="#ec4899"
                      strokeWidth={2}
                      strokeDasharray="4 4"
                      label={{
                        value: `Replan: ${d.errorLabel || 'Forecast Drift'}`,
                        fill: '#ec4899',
                        fontSize: 10,
                        position: 'insideTopLeft',
                      }}
                    />
                  ))}

                <Line
                  type="monotone"
                  dataKey="solarFc"
                  name="Solar Forecast"
                  stroke="#facc15"
                  strokeDasharray="4 4"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="solarObs"
                  name="Solar Observed"
                  stroke="#eab308"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: '#eab308' }}
                />
                <Line
                  type="monotone"
                  dataKey="loadFc"
                  name="Demand Forecast"
                  stroke="#c084fc"
                  strokeDasharray="4 4"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="loadObs"
                  name="Demand Observed"
                  stroke="#9333ea"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: '#9333ea' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* 4. Step-by-Step Solver Verification Inspector */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '18px',
            flexWrap: 'wrap',
            gap: '14px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#38bdf8', fontWeight: 600, fontSize: '1.05rem' }}>
            <Cpu size={20} />
            <span>4. Step-by-Step AC Power Flow Solver Verification Inspector</span>
          </div>

          {/* Step Selector Pills */}
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {steps.map((s, idx) => {
              const isSelected = selectedStepIdx === idx;
              const isReplan = s.replan_flag;
              const isInfeasible = s.infeasible_flag;
              return (
                <button
                  key={idx}
                  onClick={() => setSelectedStepIdx(idx)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '7px',
                    fontSize: '0.8rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    backgroundColor: isSelected
                      ? 'rgba(56, 189, 248, 0.25)'
                      : 'rgba(255, 255, 255, 0.04)',
                    color: isSelected ? '#38bdf8' : '#94a3b8',
                    border: isSelected ? '1px solid #38bdf8' : '1px solid rgba(255, 255, 255, 0.08)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                  }}
                >
                  <span>Step T{s.step}</span>
                  {isReplan && (
                    <span
                      style={{
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        backgroundColor: '#ec4899',
                      }}
                      title="Replan triggered"
                    />
                  )}
                  {isInfeasible && (
                    <span
                      style={{
                        width: '6px',
                        height: '6px',
                        borderRadius: '50%',
                        backgroundColor: '#ef4444',
                      }}
                      title="Infeasible period"
                    />
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {activeStep && (
          <div>
            {/* Step Status Summary Cards */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
                gap: '12px',
                marginBottom: '20px',
              }}
            >
              <div
                style={{
                  padding: '12px 14px',
                  backgroundColor: 'rgba(15, 23, 42, 0.6)',
                  borderRadius: '8px',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                }}
              >
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase' }}>
                  AC Newton-Raphson Solver
                </div>
                <div
                  style={{
                    fontSize: '1.05rem',
                    fontWeight: 700,
                    marginTop: '4px',
                    color: activeStep.verification_result?.converged ? '#10b981' : '#ef4444',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  {activeStep.verification_result?.converged ? (
                    <>
                      <CheckCircle2 size={16} />
                      <span>Converged</span>
                    </>
                  ) : (
                    <>
                      <AlertTriangle size={16} />
                      <span>Diverged</span>
                    </>
                  )}
                </div>
              </div>

              <div
                style={{
                  padding: '12px 14px',
                  backgroundColor: 'rgba(15, 23, 42, 0.6)',
                  borderRadius: '8px',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                }}
              >
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase' }}>
                  Physical Safety Verdict
                </div>
                <div
                  style={{
                    fontSize: '1.05rem',
                    fontWeight: 700,
                    marginTop: '4px',
                    color: activeStep.verification_result?.is_safe ? '#10b981' : '#f59e0b',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  {activeStep.verification_result?.is_safe ? (
                    <>
                      <ShieldCheck size={16} />
                      <span>PHYSICALLY SAFE</span>
                    </>
                  ) : (
                    <>
                      <AlertTriangle size={16} />
                      <span>CONSTRAINTS REMAIN</span>
                    </>
                  )}
                </div>
              </div>

              <div
                style={{
                  padding: '12px 14px',
                  backgroundColor: 'rgba(15, 23, 42, 0.6)',
                  borderRadius: '8px',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                }}
              >
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase' }}>
                  Min Distance to Limit
                </div>
                <div
                  style={{
                    fontSize: '1.05rem',
                    fontWeight: 700,
                    marginTop: '4px',
                    fontFamily: 'var(--font-mono)',
                    color:
                      (activeStep.verification_result?.min_margin ?? 0) >= 0 ? '#10b981' : '#ef4444',
                  }}
                >
                  {((activeStep.verification_result?.min_margin ?? 0) * 100).toFixed(2)}%{' '}
                  <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                    ({(activeStep.verification_result?.min_margin ?? 0) >= 0 ? '+' : ''}
                    {(activeStep.verification_result?.min_margin ?? 0).toFixed(4)} p.u.)
                  </span>
                </div>
              </div>

              <div
                style={{
                  padding: '12px 14px',
                  backgroundColor: 'rgba(15, 23, 42, 0.6)',
                  borderRadius: '8px',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                }}
              >
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase' }}>
                  Physical Solve Latency
                </div>
                <div
                  style={{
                    fontSize: '1.05rem',
                    fontWeight: 700,
                    marginTop: '4px',
                    color: '#38bdf8',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {(activeStep.verification_result?.solve_ms ?? 0).toFixed(2)} ms
                </div>
              </div>
            </div>

            {/* Action & State Detail Pills */}
            <div
              style={{
                display: 'flex',
                gap: '12px',
                flexWrap: 'wrap',
                backgroundColor: 'rgba(15, 23, 42, 0.5)',
                padding: '12px 16px',
                borderRadius: '8px',
                border: '1px solid rgba(255,255,255,0.06)',
                marginBottom: '20px',
                fontSize: '0.82rem',
                color: '#cbd5e1',
              }}
            >
              <div>
                <span style={{ color: '#94a3b8' }}>Dispatched Action:</span>{' '}
                <strong style={{ color: '#38bdf8' }}>
                  {activeStep.chosen_action?.battery_mw > 0 ? '+' : ''}
                  {activeStep.chosen_action?.battery_mw ?? 0} MW Battery
                </strong>
                , Curtail: <strong style={{ color: '#f43f5e' }}>{activeStep.chosen_action?.curtail_pct ?? 0}%</strong>
                {activeStep.chosen_action?.switch_toggle !== null && (
                  <span>
                    , Toggle Switch: <strong style={{ color: '#a855f7' }}>S{activeStep.chosen_action.switch_toggle}</strong>
                  </span>
                )}
              </div>
              <div style={{ borderLeft: '1px solid rgba(255,255,255,0.1)', paddingLeft: '12px' }}>
                <span style={{ color: '#94a3b8' }}>Resulting SOC:</span>{' '}
                <strong style={{ color: '#10b981', fontFamily: 'var(--font-mono)' }}>
                  {((activeStep.soc ?? 0) * 100).toFixed(2)}%
                </strong>{' '}
                ({((activeStep.soc ?? 0) * batteryCap).toFixed(3)} MWh)
              </div>
              {activeStep.fallback_used && (
                <div style={{ borderLeft: '1px solid rgba(255,255,255,0.1)', paddingLeft: '12px' }}>
                  <span style={{ color: '#94a3b8' }}>Fallback Invoked:</span>{' '}
                  <span style={{ color: '#ef4444', fontWeight: 700 }}>{activeStep.fallback_used}</span>
                </div>
              )}
            </div>

            {/* Bus Voltages & Line Loading Tables */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '16px' }}>
              {/* Bus Voltages Table */}
              <div
                style={{
                  backgroundColor: 'rgba(15, 23, 42, 0.65)',
                  borderRadius: '8px',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  padding: '14px',
                }}
              >
                <div
                  style={{
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    color: '#f8fafc',
                    marginBottom: '10px',
                    display: 'flex',
                    justifyContent: 'space-between',
                  }}
                >
                  <span>Bus Voltages (p.u.)</span>
                  <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                    Tolerance: [{limits?.grid?.v_min ?? 0.95} - {limits?.grid?.v_max ?? 1.05}]
                  </span>
                </div>
                <div style={{ maxHeight: '240px', overflowY: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                    <thead>
                      <tr style={{ color: '#94a3b8', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                        <th style={{ textAlign: 'left', padding: '6px 8px' }}>Bus ID</th>
                        <th style={{ textAlign: 'right', padding: '6px 8px' }}>Voltage (p.u.)</th>
                        <th style={{ textAlign: 'center', padding: '6px 8px' }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(activeStep.verification_result?.bus_vm || {})
                        .sort(([a], [b]) => parseInt(a, 10) - parseInt(b, 10))
                        .map(([bus, vm]) => {
                          const vMin = limits?.grid?.v_min ?? 0.95;
                          const vMax = limits?.grid?.v_max ?? 1.05;
                          const isNormal = vm >= vMin && vm <= vMax;
                          return (
                            <tr
                              key={bus}
                              style={{
                                borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                                color: isNormal ? '#e2e8f0' : '#ef4444',
                              }}
                            >
                              <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>Bus {bus}</td>
                              <td style={{ textAlign: 'right', padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>
                                {Number(vm).toFixed(4)}
                              </td>
                              <td style={{ textAlign: 'center', padding: '6px 8px' }}>
                                <span
                                  style={{
                                    fontSize: '0.72rem',
                                    padding: '2px 8px',
                                    borderRadius: '4px',
                                    fontWeight: 600,
                                    backgroundColor: isNormal
                                      ? 'rgba(16, 185, 129, 0.15)'
                                      : 'rgba(239, 68, 68, 0.2)',
                                    color: isNormal ? '#10b981' : '#f87171',
                                  }}
                                >
                                  {isNormal ? 'Normal' : 'VIOLATION'}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Line Loading Table */}
              <div
                style={{
                  backgroundColor: 'rgba(15, 23, 42, 0.65)',
                  borderRadius: '8px',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  padding: '14px',
                }}
              >
                <div
                  style={{
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    color: '#f8fafc',
                    marginBottom: '10px',
                    display: 'flex',
                    justifyContent: 'space-between',
                  }}
                >
                  <span>Line Loading (%)</span>
                  <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                    Limit: ≤ {limits?.grid?.max_loading_pct ?? 100}%
                  </span>
                </div>
                <div style={{ maxHeight: '240px', overflowY: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                    <thead>
                      <tr style={{ color: '#94a3b8', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                        <th style={{ textAlign: 'left', padding: '6px 8px' }}>Line ID</th>
                        <th style={{ textAlign: 'right', padding: '6px 8px' }}>Loading (%)</th>
                        <th style={{ textAlign: 'center', padding: '6px 8px' }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(activeStep.verification_result?.line_loading || {})
                        .sort(([a], [b]) => parseInt(a, 10) - parseInt(b, 10))
                        .map(([line, loadingPct]) => {
                          const maxLoad = limits?.grid?.max_loading_pct ?? 100;
                          const isNormal = loadingPct <= maxLoad;
                          return (
                            <tr
                              key={line}
                              style={{
                                borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                                color: isNormal ? '#e2e8f0' : '#ef4444',
                              }}
                            >
                              <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>Line {line}</td>
                              <td style={{ textAlign: 'right', padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>
                                {Number(loadingPct).toFixed(2)}%
                              </td>
                              <td style={{ textAlign: 'center', padding: '6px 8px' }}>
                                <span
                                  style={{
                                    fontSize: '0.72rem',
                                    padding: '2px 8px',
                                    borderRadius: '4px',
                                    fontWeight: 600,
                                    backgroundColor: isNormal
                                      ? 'rgba(16, 185, 129, 0.15)'
                                      : 'rgba(239, 68, 68, 0.2)',
                                    color: isNormal ? '#10b981' : '#f87171',
                                  }}
                                >
                                  {isNormal ? 'Normal' : 'OVERLOAD'}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
