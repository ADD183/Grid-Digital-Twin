import React, { useEffect, useState } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line,
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
  Cpu,
} from 'lucide-react';
import { controlApi } from '../api/client';
import ChartDisclosure from './ui/ChartDisclosure';

function CustomChartTooltip({ active, payload, label }) {
  if (active && payload && payload.length) {
    return (
      <div className="vp-chart-tooltip">
        <div className="vp-chart-tooltip-title">Step {label}</div>
        {payload.map((entry, idx) => (
          <div key={idx} className="vp-chart-tooltip-item">
            <span
              className="vp-chart-tooltip-dot"
              style={{ backgroundColor: entry.color || 'var(--color-fg-muted)' }}
            />
            <span className="vp-chart-tooltip-label">{entry.name}:</span>
            <strong className="vp-chart-tooltip-val">{entry.value}</strong>
          </div>
        ))}
      </div>
    );
  }
  return null;
}

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
        const limitsData = await controlApi.getLimits();
        const showcaseData = await controlApi.getShowcaseEpisode();
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
      <div className="vp-card vp-text-center" style={{ padding: 'var(--space-8)' }}>
        <RefreshCw size={36} className="spin vp-text-accent" style={{ margin: '0 auto var(--space-3)' }} />
        <div style={{ fontSize: 'var(--font-lg)', fontWeight: 'var(--font-semibold)', color: 'var(--color-fg-primary)' }}>
          Loading Multi-Step Control Engine...
        </div>
        <div style={{ fontSize: 'var(--font-sm)', color: 'var(--color-fg-muted)', marginTop: 'var(--space-1)' }}>
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-5)', marginBottom: 'var(--space-6)' }}>
      {/* Header Banner */}
      <div className="vp-card vp-card-gradient">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 'var(--space-4)' }}>
          <div>
            <div className="vp-flex vp-gap-2 vp-mb-2">
              <span className="vp-badge vp-badge-accent">Planning</span>
            </div>
            <h2 className="vp-page-title vp-flex vp-items-center vp-gap-2">
              <span>Plan battery and grid actions</span>
            </h2>
            <p className="vp-page-description" style={{ maxWidth: '820px' }}>
              Review an eight-period plan, adjust the starting battery charge, or test how the plan responds to changing conditions.
            </p>
          </div>

          {/* Action Buttons & Config Toggles */}
          <div
            className="vp-card"
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--space-3)',
              padding: 'var(--space-3) var(--space-4)',
              minWidth: '290px',
              backgroundColor: 'var(--color-bg-tertiary)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--space-2)' }}>
              <span style={{ fontSize: 'var(--font-xs)', color: 'var(--color-fg-secondary)', fontWeight: 'var(--font-semibold)' }}>Starting battery charge:</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                <input
                  type="range"
                  min="0.1"
                  max="0.9"
                  step="0.05"
                  value={initialSoc}
                  onChange={(e) => setInitialSoc(parseFloat(e.target.value))}
                  style={{ cursor: 'pointer', accentColor: 'var(--c-soc)', width: '100px' }}
                />
                <span style={{ fontSize: 'var(--font-xs)', fontFamily: 'var(--font-mono)', color: 'var(--c-soc)', fontWeight: 'var(--font-bold)', minWidth: '36px' }}>
                  {(initialSoc * 100).toFixed(0)}%
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
              <label style={{ fontSize: 'var(--font-xs)', color: 'var(--color-fg-secondary)', display: 'flex', alignItems: 'center', gap: 'var(--space-2)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={injectError}
                  onChange={(e) => setInjectError(e.target.checked)}
                  style={{ cursor: 'pointer', accentColor: 'var(--c-soc)' }}
                />
                <span>Test a sudden forecast change at T2</span>
              </label>
              <label style={{ fontSize: 'var(--font-xs)', color: 'var(--color-fg-secondary)', display: 'flex', alignItems: 'center', gap: 'var(--space-2)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={forceInfeasible}
                  onChange={(e) => setForceInfeasible(e.target.checked)}
                  style={{ cursor: 'pointer', accentColor: 'var(--color-danger)' }}
                />
                <span title="Test a high-demand situation">Test high demand</span>
              </label>
            </div>

            <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
              <button
                onClick={handleRunLiveEpisode}
                disabled={loading}
                className="vp-btn vp-btn-primary"
                style={{ flex: 1 }}
              >
                {loading ? <RefreshCw size={15} className="spin" /> : <Play size={15} />}
                <span>{loading ? 'Running...' : 'Run plan'}</span>
              </button>
              <button
                onClick={handleReloadShowcase}
                disabled={loading}
                title="Reset to saved plan"
                className="vp-btn vp-btn-secondary"
              >
                <RefreshCw size={14} />
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div className="vp-alert vp-alert-danger vp-mt-3">
            <AlertTriangle size={16} />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Metric Cards Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-3)' }}>
        <div className="vp-kpi-tile" style={{ borderLeft: '4px solid var(--color-info)' }}>
          <div className="vp-kpi-label">Periods in plan</div>
          <div className="vp-kpi-value">
            {episode?.total_steps || 8} <span style={{ fontSize: 'var(--font-xs)', color: 'var(--color-fg-muted)' }}>steps (1h dt)</span>
          </div>
          <div className="vp-kpi-subtext vp-flex vp-items-center vp-gap-1" style={{ color: 'var(--color-info)' }}>
            <Clock size={12} />
            <span>Time covered by this plan</span>
          </div>
        </div>

        <div className="vp-kpi-tile" style={{ borderLeft: '4px solid var(--c-soc)' }}>
          <div className="vp-kpi-label">Battery Capacity</div>
          <div className="vp-kpi-value">
            {batteryCap.toFixed(1)} <span style={{ fontSize: 'var(--font-xs)', color: 'var(--color-fg-muted)' }}>MWh (1.0 MW)</span>
          </div>
          <div className="vp-kpi-subtext vp-flex vp-items-center vp-gap-1" style={{ color: 'var(--c-soc)' }}>
            <BatteryCharging size={12} />
            <span>Bus 5 • η = 95%</span>
          </div>
        </div>

        <div className="vp-kpi-tile" style={{ borderLeft: `4px solid ${replanSteps.length > 0 ? '#ec4899' : 'var(--color-border)'}` }}>
          <div className="vp-kpi-label">Plan updates</div>
          <div className="vp-kpi-value">
            {replanSteps.length}{' '}
            <span style={{ fontSize: 'var(--font-xs)', color: replanSteps.length > 0 ? '#ec4899' : 'var(--color-fg-muted)' }}>
              {replanSteps.length > 0 ? `at ${replanSteps.map((s) => `T${s}`).join(', ')}` : 'zero drift'}
            </span>
          </div>
          <div className="vp-kpi-subtext" style={{ color: replanSteps.length > 0 ? '#ec4899' : 'var(--color-fg-muted)' }}>
              {replanSteps.length > 0 ? 'Plan adjusted to new conditions' : 'Original plan followed'}
          </div>
        </div>

        <div className="vp-kpi-tile" style={{ borderLeft: `4px solid ${infeasibleSteps.length > 0 ? 'var(--color-danger)' : 'var(--color-success)'}` }}>
          <div className="vp-kpi-label">High-stress periods</div>
          <div className="vp-kpi-value">
            {infeasibleSteps.length}{' '}
            <span style={{ fontSize: 'var(--font-xs)', color: infeasibleSteps.length > 0 ? 'var(--color-danger)' : 'var(--color-success)' }}>
              {infeasibleSteps.length > 0 ? `at ${infeasibleSteps.map((s) => `T${s}`).join(', ')}` : 'fully feasible'}
            </span>
          </div>
          <div className="vp-kpi-subtext" style={{ color: infeasibleSteps.length > 0 ? 'var(--color-danger)' : 'var(--color-success)' }}>
            {infeasibleSteps.length > 0 ? 'Fallback ladder active' : 'All constraints satisfied'}
          </div>
        </div>

        <div className="vp-kpi-tile" style={{ borderLeft: '4px solid #a855f7' }}>
          <div className="vp-kpi-label">Battery charge at the end</div>
          <div className="vp-kpi-value">
            {(finalSoc * 100).toFixed(1)}%{' '}
            <span style={{ fontSize: 'var(--font-xs)', color: 'var(--color-fg-muted)' }}>
              {(finalSoc * batteryCap).toFixed(2)} MWh
            </span>
          </div>
          <div className="vp-kpi-subtext vp-flex vp-items-center vp-gap-1" style={{ color: '#a855f7' }}>
            <Battery size={12} />
            <span>Safe within [{socMinPct}% - {socMaxPct}%]</span>
          </div>
        </div>
      </div>

      {/* Infeasible Callout Banner (if any) */}
      {infeasibleSteps.length > 0 && (
        <div className="vp-alert vp-alert-danger" style={{ display: 'block' }}>
          <div className="vp-flex vp-items-center vp-gap-2" style={{ fontWeight: 'var(--font-bold)' }}>
            <AlertTriangle size={18} />
            <span>Deliberate Infeasible Stress Test Period Detected: Steps {infeasibleSteps.map((s) => `T${s}`).join(', ')}</span>
          </div>
          <div className="vp-mt-2 vp-flex vp-flex-col vp-gap-2">
            {infeasibleSteps.map((stepIdx) => {
              const rec = steps[stepIdx];
              return (
                <div
                  key={stepIdx}
                  className="vp-card"
                  style={{
                    padding: 'var(--space-2) var(--space-3)',
                    backgroundColor: 'var(--color-bg-secondary)',
                    fontSize: 'var(--font-xs)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: 'var(--space-2)',
                    borderLeft: '4px solid var(--color-danger)',
                  }}
                >
                  <div>
                    <strong>Step T{stepIdx}:</strong> Fallback Ladder Invoked:{' '}
                    <code className="vp-badge vp-badge-danger" style={{ fontFamily: 'var(--font-mono)' }}>
                      {rec?.fallback_used || 'infeasible_residual'}
                    </code>
                  </div>
                  <div style={{ color: 'var(--color-fg-muted)' }}>
                    Residual Violations: <strong style={{ color: 'var(--color-danger)' }}>{rec?.verification_result?.violations?.length ?? 0}</strong>{' '}
                    | Margin:{' '}
                    <strong style={{ color: 'var(--color-danger)', fontFamily: 'var(--font-mono)' }}>
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
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 'var(--space-4)' }}>
        {/* 1. Battery State of Charge (SOC) Trajectory */}
        <div className="vp-card">
          <div className="vp-card-header vp-flex vp-justify-between vp-items-center vp-flex-wrap vp-gap-2">
            <div className="vp-card-title vp-flex vp-items-center vp-gap-2" style={{ color: 'var(--c-soc)' }}>
              <BatteryCharging size={18} />
              <span>Battery charge over time</span>
            </div>
            <div className="vp-flex vp-gap-3" style={{ fontSize: 'var(--font-xs)', color: 'var(--color-fg-muted)' }}>
              <span className="vp-flex vp-items-center vp-gap-1">
                <span style={{ width: '10px', height: '2px', backgroundColor: 'var(--color-danger)', borderTop: '2px dashed var(--color-danger)' }} />
                <span>Upper charge limit ({socMaxPct}%)</span>
              </span>
              <span className="vp-flex vp-items-center vp-gap-1">
                <span style={{ width: '10px', height: '2px', backgroundColor: 'var(--color-warning)', borderTop: '2px dashed var(--color-warning)' }} />
                <span>Reserve limit ({socMinPct}%)</span>
              </span>
            </div>
          </div>

          <ChartDisclosure title="Show battery level" summary="See how much stored energy remains during the plan.">
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 15, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="socGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--c-soc)" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="var(--c-soc)" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle)" />
                <XAxis dataKey="name" stroke="var(--color-fg-muted)" fontSize={11} tickLine={false} />
                <YAxis domain={[0, 100]} stroke="var(--color-fg-muted)" fontSize={11} tickLine={false} unit="%" />
                <Tooltip content={<CustomChartTooltip />} />
                <ReferenceLine
                  y={socMaxPct}
                  stroke="var(--color-danger)"
                  strokeDasharray="4 4"
                  label={{ value: `Max ${socMaxPct}%`, fill: 'var(--color-danger)', fontSize: 10, position: 'insideTopRight' }}
                />
                <ReferenceLine
                  y={socMinPct}
                  stroke="var(--color-warning)"
                  strokeDasharray="4 4"
                  label={{ value: `Min ${socMinPct}%`, fill: 'var(--color-warning)', fontSize: 10, position: 'insideBottomRight' }}
                />
                <Area
                  type="monotone"
                  dataKey="soc"
                  name="Battery SOC (%)"
                  stroke="var(--c-soc)"
                  strokeWidth={3}
                  fillOpacity={1}
                  fill="url(#socGradient)"
                  dot={{ r: 5, fill: '#047857', stroke: 'var(--c-soc)', strokeWidth: 2 }}
                  activeDot={{ r: 7, fill: '#34d399' }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          </ChartDisclosure>
        </div>

        {/* 2. Action Dispatch Timeline */}
        <div className="vp-card">
          <div className="vp-card-header vp-flex vp-justify-between vp-items-center vp-flex-wrap vp-gap-2">
            <div className="vp-card-title vp-flex vp-items-center vp-gap-2" style={{ color: 'var(--c-battery)' }}>
              <Zap size={18} />
              <span>Planned battery and solar actions</span>
            </div>
            <div style={{ fontSize: 'var(--font-xs)', color: 'var(--color-fg-muted)' }}>
              <span style={{ color: 'var(--c-battery)' }}>Positive: Discharge (+MW)</span> •{' '}
              <span style={{ color: '#818cf8' }}>Negative: Charge (-MW)</span> •{' '}
              <span style={{ color: 'var(--c-curtail)' }}>Line: Curtailment (%)</span>
            </div>
          </div>

          <ChartDisclosure title="Show planned actions" summary="Review battery output and solar adjustments over time.">
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 15, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle)" />
                <XAxis dataKey="name" stroke="var(--color-fg-muted)" fontSize={11} tickLine={false} />
                <YAxis
                  yAxisId="power"
                  domain={[-1.2, 1.2]}
                  stroke="var(--c-battery)"
                  fontSize={11}
                  tickLine={false}
                  unit=" MW"
                />
                <YAxis
                  yAxisId="curtail"
                  orientation="right"
                  domain={[0, 100]}
                  stroke="var(--c-curtail)"
                  fontSize={11}
                  tickLine={false}
                  unit="%"
                />
                <Tooltip content={<CustomChartTooltip />} />
                <Legend verticalAlign="top" height={32} />
                <ReferenceLine yAxisId="power" y={0} stroke="var(--color-border)" />
                <Bar
                  yAxisId="power"
                  dataKey="batteryMw"
                  name="Battery Dispatch (MW)"
                  fill="var(--c-battery)"
                  radius={[4, 4, 0, 0]}
                />
                <Line
                  yAxisId="curtail"
                  type="monotone"
                  dataKey="curtailPct"
                  name="Solar Curtailment (%)"
                  stroke="var(--c-curtail)"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: 'var(--c-curtail)' }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          </ChartDisclosure>
        </div>

        {/* 3. Forecast vs Observed Conditions & Replan Markers */}
        <div className="vp-card">
          <div className="vp-card-header vp-flex vp-justify-between vp-items-center vp-flex-wrap vp-gap-2">
            <div className="vp-card-title vp-flex vp-items-center vp-gap-2" style={{ color: 'var(--c-solar)' }}>
              <TrendingUp size={18} />
              <span>Expected and observed conditions</span>
            </div>
            <div style={{ fontSize: 'var(--font-xs)', color: 'var(--color-fg-muted)' }}>
              Compare expected with observed conditions; markers show when the plan changed.
            </div>
          </div>

          <ChartDisclosure title="Show forecast and observed conditions" summary="Compare expected conditions with what the system observed.">
          <div style={{ width: '100%', height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 15, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle)" />
                <XAxis dataKey="name" stroke="var(--color-fg-muted)" fontSize={11} tickLine={false} />
                <YAxis stroke="var(--color-fg-muted)" fontSize={11} tickLine={false} />
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
                  stroke="var(--c-solar)"
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
                  stroke="var(--c-load)"
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
          </ChartDisclosure>
        </div>
      </div>

      {/* 4. Step-by-Step Solver Verification Inspector */}
      <div className="vp-card">
        <div className="vp-card-header vp-flex vp-justify-between vp-items-center vp-flex-wrap vp-gap-3">
          <div className="vp-card-title vp-flex vp-items-center vp-gap-2" style={{ color: 'var(--c-battery)' }}>
            <Cpu size={18} />
            <span>Details for each period</span>
          </div>

          {/* Step Selector Segmented Controls */}
          <div className="vp-segmented" style={{ flexWrap: 'wrap' }}>
            {steps.map((s, idx) => {
              const isSelected = selectedStepIdx === idx;
              const isReplan = s.replan_flag;
              const isInfeasible = s.infeasible_flag;
              return (
                <button
                  key={idx}
                  onClick={() => setSelectedStepIdx(idx)}
                  className={`vp-segmented-btn ${isSelected ? 'active' : ''}`}
                  style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
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
                        backgroundColor: 'var(--color-danger)',
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
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: 'var(--space-3)',
                marginBottom: 'var(--space-4)',
              }}
            >
              <div className="vp-kpi-tile">
                <div className="vp-kpi-label">Grid check</div>
                <div
                  className="vp-kpi-value"
                  style={{
                    color: activeStep.verification_result?.converged ? 'var(--color-success)' : 'var(--color-danger)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-2)',
                  }}
                >
                  {activeStep.verification_result?.converged ? (
                    <>
                      <CheckCircle2 size={18} />
                      <span>Converged</span>
                    </>
                  ) : (
                    <>
                      <AlertTriangle size={18} />
                      <span>Diverged</span>
                    </>
                  )}
                </div>
              </div>

              <div className="vp-kpi-tile">
                <div className="vp-kpi-label">Physical Safety Verdict</div>
                <div
                  className="vp-kpi-value"
                  style={{
                    color: activeStep.verification_result?.is_safe ? 'var(--color-success)' : 'var(--color-warning)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-2)',
                  }}
                >
                  {activeStep.verification_result?.is_safe ? (
                    <>
                      <ShieldCheck size={18} />
                      <span>PHYSICALLY SAFE</span>
                    </>
                  ) : (
                    <>
                      <AlertTriangle size={18} />
                      <span>CONSTRAINTS REMAIN</span>
                    </>
                  )}
                </div>
              </div>

              <div className="vp-kpi-tile">
                <div className="vp-kpi-label">Min Distance to Limit</div>
                <div
                  className="vp-kpi-value"
                  style={{
                    fontFamily: 'var(--font-mono)',
                    color: (activeStep.verification_result?.min_margin ?? 0) >= 0 ? 'var(--color-success)' : 'var(--color-danger)',
                  }}
                >
                  {((activeStep.verification_result?.min_margin ?? 0) * 100).toFixed(2)}%{' '}
                  <span style={{ fontSize: 'var(--font-xs)', color: 'var(--color-fg-muted)' }}>
                    ({(activeStep.verification_result?.min_margin ?? 0) >= 0 ? '+' : ''}
                    {(activeStep.verification_result?.min_margin ?? 0).toFixed(4)} p.u.)
                  </span>
                </div>
              </div>

              <div className="vp-kpi-tile">
                <div className="vp-kpi-label">Physical Solve Latency</div>
                <div
                  className="vp-kpi-value"
                  style={{
                    color: 'var(--color-info)',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {(activeStep.verification_result?.solve_ms ?? 0).toFixed(2)} ms
                </div>
              </div>
            </div>

            {/* Action & State Detail Pills */}
            <div
              className="vp-card"
              style={{
                display: 'flex',
                gap: 'var(--space-4)',
                flexWrap: 'wrap',
                backgroundColor: 'var(--color-bg-secondary)',
                padding: 'var(--space-3) var(--space-4)',
                marginBottom: 'var(--space-4)',
                fontSize: 'var(--font-xs)',
                color: 'var(--color-fg-secondary)',
              }}
            >
              <div>
                <span style={{ color: 'var(--color-fg-muted)' }}>Dispatched Action:</span>{' '}
                <strong style={{ color: 'var(--c-battery)' }}>
                  {activeStep.chosen_action?.battery_mw > 0 ? '+' : ''}
                  {activeStep.chosen_action?.battery_mw ?? 0} MW Battery
                </strong>
                , Curtail: <strong style={{ color: 'var(--c-curtail)' }}>{activeStep.chosen_action?.curtail_pct ?? 0}%</strong>
                {activeStep.chosen_action?.switch_toggle !== null && (
                  <span>
                    , Toggle Switch: <strong style={{ color: '#a855f7' }}>S{activeStep.chosen_action.switch_toggle}</strong>
                  </span>
                )}
              </div>
              <div style={{ borderLeft: '1px solid var(--color-border-subtle)', paddingLeft: 'var(--space-3)' }}>
                <span style={{ color: 'var(--color-fg-muted)' }}>Resulting SOC:</span>{' '}
                <strong style={{ color: 'var(--c-soc)', fontFamily: 'var(--font-mono)' }}>
                  {((activeStep.soc ?? 0) * 100).toFixed(2)}%
                </strong>{' '}
                ({((activeStep.soc ?? 0) * batteryCap).toFixed(3)} MWh)
              </div>
              {activeStep.fallback_used && (
                <div style={{ borderLeft: '1px solid var(--color-border-subtle)', paddingLeft: 'var(--space-3)' }}>
                  <span style={{ color: 'var(--color-fg-muted)' }}>Fallback Invoked:</span>{' '}
                  <span className="vp-badge vp-badge-danger">{activeStep.fallback_used}</span>
                </div>
              )}
            </div>

            {/* Bus Voltages & Line Loading Tables */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: 'var(--space-4)' }}>
              {/* Bus Voltages Table */}
              <div className="vp-card" style={{ padding: 'var(--space-3)' }}>
                <div
                  style={{
                    fontSize: 'var(--font-sm)',
                    fontWeight: 'var(--font-semibold)',
                    color: 'var(--color-fg-primary)',
                    marginBottom: 'var(--space-2)',
                    display: 'flex',
                    justifyContent: 'space-between',
                  }}
                >
                  <span>Bus Voltages (p.u.)</span>
                  <span style={{ fontSize: 'var(--font-xs)', color: 'var(--color-fg-muted)' }}>
                    Tolerance: [{limits?.grid?.v_min ?? 0.95} - {limits?.grid?.v_max ?? 1.05}]
                  </span>
                </div>
                <div className="vp-table-container" style={{ maxHeight: '240px', overflowY: 'auto' }}>
                  <table className="vp-table">
                    <thead>
                      <tr>
                        <th>Bus ID</th>
                        <th className="vp-text-right">Voltage (p.u.)</th>
                        <th className="vp-text-center">Status</th>
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
                            <tr key={bus}>
                              <td style={{ fontFamily: 'var(--font-mono)' }}>Bus {bus}</td>
                              <td className="vp-text-right" style={{ fontFamily: 'var(--font-mono)' }}>
                                {Number(vm).toFixed(4)}
                              </td>
                              <td className="vp-text-center">
                                <span className={`vp-badge ${isNormal ? 'vp-badge-success' : 'vp-badge-danger'}`}>
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
              <div className="vp-card" style={{ padding: 'var(--space-3)' }}>
                <div
                  style={{
                    fontSize: 'var(--font-sm)',
                    fontWeight: 'var(--font-semibold)',
                    color: 'var(--color-fg-primary)',
                    marginBottom: 'var(--space-2)',
                    display: 'flex',
                    justifyContent: 'space-between',
                  }}
                >
                  <span>Line Loading (%)</span>
                  <span style={{ fontSize: 'var(--font-xs)', color: 'var(--color-fg-muted)' }}>
                    Limit: ≤ {limits?.grid?.max_loading_pct ?? 100}%
                  </span>
                </div>
                <div className="vp-table-container" style={{ maxHeight: '240px', overflowY: 'auto' }}>
                  <table className="vp-table">
                    <thead>
                      <tr>
                        <th>Line ID</th>
                        <th className="vp-text-right">Loading (%)</th>
                        <th className="vp-text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(activeStep.verification_result?.line_loading || {})
                        .sort(([a], [b]) => parseInt(a, 10) - parseInt(b, 10))
                        .map(([line, loadingPct]) => {
                          const maxLoad = limits?.grid?.max_loading_pct ?? 100;
                          const isNormal = loadingPct <= maxLoad;
                          return (
                            <tr key={line}>
                              <td style={{ fontFamily: 'var(--font-mono)' }}>Line {line}</td>
                              <td className="vp-text-right" style={{ fontFamily: 'var(--font-mono)' }}>
                                {Number(loadingPct).toFixed(2)}%
                              </td>
                              <td className="vp-text-center">
                                <span className={`vp-badge ${isNormal ? 'vp-badge-success' : 'vp-badge-danger'}`}>
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

