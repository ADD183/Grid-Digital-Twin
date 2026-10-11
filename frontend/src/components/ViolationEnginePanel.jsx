import React, { useState, useEffect } from 'react';
import { 
  ShieldAlert, 
  CheckCircle2, 
  AlertTriangle, 
  Zap, 
  BatteryCharging, 
  GitFork, 
  Sun, 
  Sliders, 
  Award, 
  Info,
  XCircle,
  Play
} from 'lucide-react';
import { API_BASE } from '../config';
import ChartDisclosure from './ui/ChartDisclosure';

export default function ViolationEnginePanel() {
  const [selectedScenario, setSelectedScenario] = useState('solar_spike');
  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState(null);

  // Simulation State
  const [scenarioData, setScenarioData] = useState(null);
  const [evaluationData, setEvaluationData] = useState(null);
  const [activeViewMode, setActiveViewMode] = useState('before'); // 'before' | 'after' | 'custom'
  const [filterType, setFilterType] = useState('ALL');
  const [violationCategoryFilter, setViolationCategoryFilter] = useState('ALL');

  // Custom action sandbox inputs
  const [customType, setCustomType] = useState('FEEDER_RECONFIGURATION');
  const [curtailPct, setCurtailPct] = useState(50);
  const [batteryMw, setBatteryMw] = useState(1.5);
  const [switchName, setSwitchName] = useState('S1');
  const [voltageSetpoint, setVoltageSetpoint] = useState(1.02);
  const [customResult, setCustomResult] = useState(null);
  const [applyingCustom, setApplyingCustom] = useState(false);

  // Trigger violation scenario
  const handleTriggerScenario = async (scenId = selectedScenario) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/violations/trigger`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: scenId }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setScenarioData(data);
      setActiveViewMode('before');
      setCustomResult(null);

      // Immediately run evaluation engine automatically for smooth demo
      handleRunEngine(scenId);
    } catch (err) {
      console.error('Trigger error:', err);
      setError('Failed to trigger grid constraint scenario.');
    } finally {
      setLoading(false);
    }
  };

  // Run Propose -> Verify -> Repair engine
  const handleRunEngine = async (scenId = selectedScenario) => {
    setEvaluating(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/violations/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: scenId }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setEvaluationData(data);
    } catch (err) {
      console.error('Engine error:', err);
      setError('Engine evaluation failed to complete.');
    } finally {
      setEvaluating(false);
    }
  };

  // Trigger default scenario on component mount
  useEffect(() => {
    handleTriggerScenario('solar_spike');
  }, []);

  // Apply custom action in sandbox
  const handleApplyCustomAction = async () => {
    setApplyingCustom(true);
    setError(null);
    try {
      const body = {
        scenario_id: selectedScenario,
        action_type: customType,
        curtailment_pct: Number(curtailPct),
        battery_p_mw: Number(batteryMw),
        battery_bus: 5,
        switch_name: switchName,
        voltage_setpoint_pu: Number(voltageSetpoint),
      };
      const res = await fetch(`${API_BASE}/api/violations/apply-custom-action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setCustomResult(data);
      setActiveViewMode('custom');
    } catch (err) {
      console.error('Custom action error:', err);
      setError('Failed to simulate custom action.');
    } finally {
      setApplyingCustom(false);
    }
  };

  const currentTopology = 
    activeViewMode === 'after' && evaluationData?.after_topology
      ? evaluationData.after_topology
      : activeViewMode === 'custom' && customResult?.topology
      ? customResult.topology
      : scenarioData?.topology || evaluationData?.before_topology;

  const currentViolations = 
    activeViewMode === 'after'
      ? { 
          has_violations: !evaluationData?.fully_resolved, 
          total_violations: evaluationData?.recommended_action?.residual_violations_count || 0, 
          all_violations: evaluationData?.recommended_action?.violations_detail || [],
          voltage_violations: [], 
          loading_violations: [] 
        }
      : activeViewMode === 'custom' && customResult?.violations
      ? customResult.violations
      : scenarioData?.violations || evaluationData?.initial_violations;

  const winner = evaluationData?.recommended_action;
  const afterResolved = Boolean(evaluationData?.fully_resolved && winner?.resolved);
  const residualCount = winner?.residual_violations_count ?? 0;
  const activeSummary = activeViewMode === 'after'
    ? evaluationData?.after_grid_summary
    : evaluationData?.before_grid_summary;
  const rankedActions = evaluationData?.ranked_actions || [];

  const filteredActions = rankedActions.filter((act) => {
    if (filterType === 'ALL') return true;
    return act.action_type === filterType;
  });

  // Action type badge helper
  const getActionBadge = (type) => {
    switch (type) {
      case 'VOLTAGE_SETPOINT':
        return { label: 'Voltage Setpoint', tone: 'ok', icon: Sliders };
      case 'FEEDER_RECONFIGURATION':
        return { label: 'Feeder Switching', tone: 'info', icon: GitFork };
      case 'BATTERY_DISPATCH':
        return { label: 'Battery Dispatch', tone: 'info', icon: BatteryCharging };
      case 'CURTAILMENT':
        return { label: 'Solar Curtailment', tone: 'warn', icon: Sun };
      case 'HYBRID':
        return { label: 'Hybrid Action', tone: 'info', icon: Zap };
      default:
        return { label: type, tone: 'neutral', icon: Zap };
    }
  };

  // Node color helper with strict utility bounds [0.95, 1.05]
  const getNodeColor = (vm_pu) => {
    if (vm_pu > 1.05 || vm_pu < 0.95) return 'var(--danger)';
    return 'var(--ok)';
  };

  const getLineColor = (loading) => {
    if (loading > 100) return 'var(--danger)';
    if (loading > 75) return 'var(--warn)';
    return 'var(--accent)';
  };

  return (
    <div style={{ marginBottom: '24px' }}>
      
      {/* SECTION 1: HEADER & SCENARIO TRIGGER CONTROLS */}
      <div className="vp-card" style={{ marginBottom: '20px' }}>
        <div className="vp-page-header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <ShieldAlert size={22} color="var(--danger)" />
              <h2 className="vp-page-title">
                Grid actions and alerts
              </h2>
            </div>
            <p className="vp-page-desc">
              Choose a grid condition to explore, then compare actions that may improve it.
            </p>
          </div>

          {/* Quick Engine Status Indicator */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span className="vp-badge" data-tone={currentViolations?.has_violations ? 'danger' : 'ok'}>
              {currentViolations?.has_violations ? `${currentViolations.total_violations} items need attention` : 'Operating normally'}
            </span>
          </div>
        </div>

        {/* Scenario Selection Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px', marginBottom: '18px' }}>
          {[
            { id: 'solar_spike', icon: Sun, title: 'Sudden solar increase', desc: 'Explore what happens when generation rises quickly.' },
            { id: 'evening_peak', icon: BatteryCharging, title: 'High evening demand', desc: 'See how the grid responds when household use peaks.' },
            { id: 'line_congestion', icon: Zap, title: 'Busy power lines', desc: 'Review a situation where demand strains a connection.' },
            { id: 'cloudy_drop', icon: AlertTriangle, title: 'Sudden solar drop', desc: 'Explore how support actions respond when generation falls.' },
            { id: 'infeasible', icon: XCircle, title: 'Extreme demand', desc: 'Test a situation that available actions cannot fully resolve.' },
          ].map((scen) => {
            const Icon = scen.icon;
            const isSelected = selectedScenario === scen.id;
            return (
              <button
                key={scen.id}
                onClick={() => {
                  setSelectedScenario(scen.id);
                  handleTriggerScenario(scen.id);
                }}
                disabled={loading || evaluating}
                style={{
                  backgroundColor: isSelected ? 'var(--accent-soft)' : 'var(--surface-raised)',
                  border: isSelected ? '1px solid var(--accent)' : '1px solid var(--border)',
                  borderRadius: 'var(--r-md)',
                  padding: '14px 16px',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                  <Icon size={18} style={{ color: isSelected ? 'var(--accent)' : 'var(--text-muted)' }} />
                  <span style={{ fontWeight: 600, color: isSelected ? 'var(--text)' : 'var(--text-muted)', fontSize: '0.9rem' }}>
                    {scen.title}
                  </span>
                  {isSelected && (
                    <span className="vp-badge" data-tone="info" style={{ marginLeft: 'auto' }}>
                      Active
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-faint)', lineHeight: 1.4 }}>
                  {scen.desc}
                </div>
              </button>
            );
          })}
        </div>

        {/* Action Trigger Buttons */}
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <button
            onClick={() => handleTriggerScenario(selectedScenario)}
            disabled={loading || evaluating}
            className="vp-btn vp-btn-danger-outline"
          >
            <ShieldAlert size={16} />
            <span>{loading ? 'Loading situation...' : 'Explore this situation'}</span>
          </button>

          <button
            onClick={() => handleRunEngine(selectedScenario)}
            disabled={evaluating}
            className="vp-btn vp-btn-primary"
          >
            <Zap size={16} />
            <span>{evaluating ? 'Comparing actions...' : 'Compare possible actions'}</span>
          </button>
        </div>

        {error && (
          <div className="vp-alert" data-tone="danger" style={{ marginTop: '14px' }}>
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* SECTION 2: BEFORE / AFTER INTERACTIVE COMPARISON VIEW */}
      <div className="vp-card" style={{ marginBottom: '20px' }}>
        
        {/* View Switcher Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px', marginBottom: '18px' }}>
          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text)' }}>
              Conditions before and after an action
            </h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Compare the original grid conditions with the result after a recommended action.
            </p>
          </div>

          {/* Before / After Segmented Control */}
          <div className="vp-segmented">
            <button
              onClick={() => setActiveViewMode('before')}
              className={`vp-segmented-btn ${activeViewMode === 'before' ? 'active' : ''}`}
              aria-selected={activeViewMode === 'before'}
            >
              Before
            </button>
            <button
              onClick={() => setActiveViewMode('after')}
              className={`vp-segmented-btn ${activeViewMode === 'after' ? 'active' : ''}`}
              aria-selected={activeViewMode === 'after'}
            >
              After
            </button>
            {customResult && (
              <button
                onClick={() => setActiveViewMode('custom')}
                className={`vp-segmented-btn ${activeViewMode === 'custom' ? 'active' : ''}`}
                aria-selected={activeViewMode === 'custom'}
              >
                Custom action
              </button>
            )}
          </div>
        </div>

        {/* State Banner */}
        <div className="vp-alert" data-tone={activeViewMode === 'after' && afterResolved ? 'ok' : 'danger'} style={{ marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', width: '100%', justifyContent: 'space-between', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              {activeViewMode === 'after' && afterResolved ? (
                <CheckCircle2 size={20} style={{ color: 'var(--ok)' }} />
              ) : (
                <AlertTriangle size={20} style={{ color: 'var(--danger)' }} />
              )}
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>
                  {activeViewMode === 'after' && afterResolved
                    ? `Grid within limits: ${winner?.name || 'Corrective Action Applied'}`
                    : activeViewMode === 'after'
                    ? `Residual constraints remain after ${winner?.name || 'the best action'}`
                    : `Grid Under Stress: ${scenarioData?.scenario?.name || 'Constraint Active'}`}
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  {activeViewMode === 'after' && afterResolved
                    ? 'No remaining grid issues were found.'
                    : activeViewMode === 'after'
                    ? `${residualCount} residual violation(s) remain. This result is not fully resolved.`
                    : `${currentViolations?.total_violations || 0} active violation constraints detected. Voltage limits violated.`}
                </div>
              </div>
            </div>

            {/* Delta Metrics Badges */}
            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-faint)' }}>Voltage Range</div>
                <div className="mono" style={{ fontSize: '0.88rem', fontWeight: 600 }}>
                  {activeSummary?.vm_pu_min != null && activeSummary?.vm_pu_max != null
                    ? `${activeSummary.vm_pu_min}–${activeSummary.vm_pu_max} p.u.`
                    : 'N/A'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-faint)' }}>Max Line Loading</div>
                <div className="mono" style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--accent)' }}>
                  {activeSummary?.max_line_loading_percent != null
                    ? `${activeSummary.max_line_loading_percent}%`
                    : 'N/A'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-faint)' }}>Violations Count</div>
                <div className="mono" style={{ fontSize: '0.88rem', fontWeight: 600 }}>
                  {activeViewMode === 'after'
                    ? `${residualCount} residual`
                    : `${currentViolations?.total_violations ?? 'N/A'} active`}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ACTIVE VIOLATIONS DETAILED BREAKDOWN LOG */}
        {currentViolations?.has_violations ? (
          <div className="vp-card-raised" style={{ padding: '16px', marginBottom: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px', marginBottom: '14px' }}>
              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ShieldAlert size={18} />
                <span>Active Grid Violations Log ({currentViolations.total_violations} Constraints Flagged)</span>
              </div>

              {/* Category Filter Chips */}
              <div className="vp-segmented">
                {[
                  { id: 'ALL', label: `All (${currentViolations.total_violations})` },
                  { id: 'OVERVOLTAGE', label: 'Overvoltage' },
                  { id: 'UNDERVOLTAGE', label: 'Undervoltage' },
                  { id: 'LINE_OVERLOAD', label: 'Line Overload' },
                  { id: 'TRAFO_OVERLOAD', label: 'Trafo Overload' },
                ].map((cat) => {
                  const count = cat.id === 'ALL' 
                    ? currentViolations.total_violations 
                    : (currentViolations.all_violations || []).filter((v) => v.violation_type === cat.id).length;
                  if (cat.id !== 'ALL' && count === 0) return null;
                  return (
                    <button
                      key={cat.id}
                      onClick={() => setViolationCategoryFilter(cat.id)}
                      className={`vp-segmented-btn ${violationCategoryFilter === cat.id ? 'active' : ''}`}
                      aria-selected={violationCategoryFilter === cat.id}
                      style={{ fontSize: '0.74rem', padding: '4px 10px' }}
                    >
                      {cat.id === 'ALL' ? cat.label : `${cat.label} (${count})`}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Violation Items List */}
            <div style={{ display: 'grid', gap: '8px', maxHeight: '260px', overflowY: 'auto', paddingRight: '4px' }}>
              {(currentViolations.all_violations || [])
                .filter((v) => violationCategoryFilter === 'ALL' || v.violation_type === violationCategoryFilter)
                .map((v, i) => {
                  const isOver = v.violation_type.includes('OVERVOLTAGE') || v.violation_type.includes('OVERLOAD');
                  const tone = isOver ? 'danger' : 'warn';
                  return (
                    <div
                      key={i}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 14px',
                        backgroundColor: 'var(--surface)',
                        borderRadius: 'var(--r-sm)',
                        borderLeft: `3px solid var(--${tone})`,
                        border: '1px solid var(--border)',
                        fontSize: '0.82rem',
                        gap: '12px'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1 }}>
                        <span className="vp-badge" data-tone={tone}>
                          {v.violation_type.replace('_', ' ')}
                        </span>
                        <div>
                          <strong style={{ color: 'var(--text)', fontSize: '0.86rem' }}>{v.element_name}</strong>
                          <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                            {v.description}
                          </div>
                        </div>
                      </div>

                      <div className="num mono" style={{ textAlign: 'right', minWidth: '130px' }}>
                        <div style={{ color: `var(--${tone})`, fontWeight: 600, fontSize: '0.88rem' }}>
                          {v.actual_value} {v.unit}
                        </div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-faint)' }}>
                          Limit: {v.limit_value} {v.unit} (+{v.margin} margin)
                        </div>
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        ) : (
          <div className="vp-alert" data-tone="ok" style={{ marginBottom: '16px' }}>
            <span>✓ All 15 buses and feeder lines are operating within safe tolerances [0.95–1.05 p.u., ≤ 100% load]. 0 active violations.</span>
          </div>
        )}

        {/* Embedded SVG Topology Canvas */}
        {currentTopology && currentTopology.buses && (
          <ChartDisclosure title="Show the affected network" summary="Open the map to inspect where grid conditions changed.">
          <div style={{ backgroundColor: 'var(--surface-raised)', borderRadius: 'var(--r-md)', border: '1px solid var(--border)', overflow: 'hidden' }}>
            <svg viewBox="0 0 860 380" style={{ width: '100%', height: 'auto', display: 'block', maxHeight: '420px' }}>
              {/* Background Grid Lines */}
              <g stroke="var(--border)" strokeWidth="1" strokeDasharray="2 4">
                {[...Array(10)].map((_, i) => (
                  <line key={`gv-${i}`} x1={i * 86} y1="0" x2={i * 86} y2="380" />
                ))}
                {[...Array(6)].map((_, i) => (
                  <line key={`gh-${i}`} x1="0" y1={i * 63} x2="860" y2={i * 63} />
                ))}
              </g>

              {/* Render Lines */}
              {currentTopology.lines.map((line) => {
                const b1 = currentTopology.buses.find((b) => b.id === line.from_bus) || { x: line.from_x, y: line.from_y };
                const b2 = currentTopology.buses.find((b) => b.id === line.to_bus) || { x: line.to_x, y: line.to_y };
                
                const minX = Math.min(...currentTopology.buses.map((b) => b.x));
                const maxX = Math.max(...currentTopology.buses.map((b) => b.x));
                const minY = Math.min(...currentTopology.buses.map((b) => b.y));
                const maxY = Math.max(...currentTopology.buses.map((b) => b.y));

                const mapX = (x) => 80 + ((x - minX) / (maxX - minX || 1)) * 700;
                const mapY = (y) => 50 + ((y - minY) / (maxY - minY || 1)) * 270;

                const x1 = mapX(b1.x);
                const y1 = mapY(b1.y);
                const x2 = mapX(b2.x);
                const y2 = mapY(b2.y);

                const strokeColor = getLineColor(line.loading_percent);

                return (
                  <g key={`l-${line.id}`}>
                    <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={strokeColor} strokeWidth="2" strokeOpacity="0.85" />
                  </g>
                );
              })}

              {/* Render Buses */}
              {currentTopology.buses.map((bus) => {
                const minX = Math.min(...currentTopology.buses.map((b) => b.x));
                const maxX = Math.max(...currentTopology.buses.map((b) => b.x));
                const minY = Math.min(...currentTopology.buses.map((b) => b.y));
                const maxY = Math.max(...currentTopology.buses.map((b) => b.y));

                const mapX = (x) => 80 + ((x - minX) / (maxX - minX || 1)) * 700;
                const mapY = (y) => 50 + ((y - minY) / (maxY - minY || 1)) * 270;

                const cx = mapX(bus.x);
                const cy = mapY(bus.y);
                const color = getNodeColor(bus.vm_pu);
                const isViolation = bus.vm_pu > 1.05 || bus.vm_pu < 0.95;

                return (
                  <g key={`b-${bus.id}`}>
                    {isViolation && (
                      <circle
                        cx={cx}
                        cy={cy}
                        r="16"
                        fill="transparent"
                        stroke="var(--danger)"
                        strokeWidth="2"
                        strokeOpacity="0.6"
                      />
                    )}

                    <circle cx={cx} cy={cy} r="10" fill={color} stroke="var(--surface-raised)" strokeWidth="2" />
                    
                    <text x={cx} y={cy + 4} textAnchor="middle" fill="#ffffff" fontSize="9" fontWeight="600" fontFamily="var(--font-mono)">
                      {bus.id}
                    </text>
                    
                    <text x={cx} y={cy + 22} textAnchor="middle" fill="var(--text-muted)" fontSize="9" fontFamily="var(--font-sans)">
                      {bus.vm_pu.toFixed(3)}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
          </ChartDisclosure>
        )}
      </div>

      {/* SECTION 3: WINNER RECOMMENDATION & EXPLAINABILITY */}
      {winner && (
        <div className="vp-card" style={{ marginBottom: '20px', borderColor: 'var(--accent)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent)', fontSize: '0.81rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '8px' }}>
            <Award size={18} />
            <span>Recommended action</span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px', marginBottom: '16px' }}>
            <div>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text)', marginBottom: '6px' }}>
                {winner.name}
              </h3>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                {(() => {
                  const badge = getActionBadge(winner.action_type);
                  const Icon = badge.icon;
                  return (
                    <span className="vp-badge" data-tone={badge.tone}>
                      <Icon size={12} />
                      {badge.label}
                    </span>
                  );
                })()}
                <span className="vp-badge" data-tone={winner.resolved ? 'ok' : 'danger'}>
                  {winner.resolved ? 'Fully resolved · 0 residual violations' : `Best partial action · ${winner.residual_violations_count} residual violations`}
                </span>
                <span className="vp-badge" data-tone="info">
                  Score: {winner.score} pts
                </span>
              </div>
            </div>

            {/* Quick Metrics */}
            <div style={{ display: 'flex', gap: '12px' }}>
              <div className="vp-kpi-tile" style={{ padding: '8px 14px', minWidth: '130px' }}>
                <div className="vp-kpi-label">Clean Energy Retained</div>
                <div className="vp-kpi-value" style={{ fontSize: '1.25rem', color: 'var(--ok)' }}>{winner.renewable_retained_pct}%</div>
              </div>
              <div className="vp-kpi-tile" style={{ padding: '8px 14px', minWidth: '110px' }}>
                <div className="vp-kpi-label">Cost Proxy</div>
                <div className="vp-kpi-value" style={{ fontSize: '1.25rem', color: 'var(--accent)' }}>{winner.cost_proxy}/3</div>
              </div>
            </div>
          </div>

          {/* Decision Rationale Explanation Box */}
          <div className="vp-alert" data-tone="info">
            <div>
              <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--accent)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Info size={15} />
                <span>Why This Action Was Selected (Multi-Objective Decision Rationale):</span>
              </div>
              <p style={{ fontSize: '0.85rem', color: 'var(--text)', lineHeight: 1.5 }}>
                {evaluationData.explanation}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* SECTION 4: ACTION COMPARISON MATRIX TABLE */}
      <div className="vp-card" style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text)' }}>
              Other actions considered ({rankedActions.length})
            </h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Options ranked by their expected effect on grid conditions
            </p>
          </div>

          {/* Action Family Filter Buttons */}
          <div className="vp-segmented">
            {['ALL', 'VOLTAGE_SETPOINT', 'FEEDER_RECONFIGURATION', 'BATTERY_DISPATCH', 'CURTAILMENT', 'HYBRID'].map((type) => (
              <button
                key={type}
                onClick={() => setFilterType(type)}
                className={`vp-segmented-btn ${filterType === type ? 'active' : ''}`}
                aria-selected={filterType === type}
                style={{ fontSize: '0.74rem', padding: '4px 10px' }}
              >
                {type === 'ALL' ? 'All Types' : type.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Comparison Table */}
        <div className="vp-table-container">
          <table className="vp-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Action Name</th>
                <th>Action Family</th>
                <th>Resolved?</th>
                <th className="num">Residual Viols</th>
                <th className="num">Clean Energy</th>
                <th className="num">Cost Proxy</th>
                <th className="num">Score</th>
              </tr>
            </thead>
            <tbody>
              {filteredActions.map((act) => {
                const badge = getActionBadge(act.action_type);
                const Icon = badge.icon;
                const isWinner = act.rank === 1;

                return (
                  <tr
                    key={act.action_id}
                    style={{
                      backgroundColor: isWinner ? 'var(--surface-hover)' : 'transparent',
                    }}
                  >
                    <td className="mono" style={{ fontWeight: 600, color: isWinner ? 'var(--accent)' : 'var(--text)' }}>
                      {isWinner ? '#1 Winner' : `#${act.rank}`}
                    </td>
                    <td style={{ fontWeight: 500, color: 'var(--text)' }}>
                      {act.name}
                    </td>
                    <td>
                      <span className="vp-badge" data-tone={badge.tone}>
                        <Icon size={11} />
                        {badge.label}
                      </span>
                    </td>
                    <td>
                      <span className="vp-badge" data-tone={act.resolved ? 'ok' : 'danger'}>
                        {act.resolved ? 'Full' : 'Partial'}
                      </span>
                    </td>
                    <td className="num mono">
                      {act.residual_violations_count}
                    </td>
                    <td className="num mono" style={{ color: act.renewable_retained_pct === 100 ? 'var(--ok)' : 'var(--warn)' }}>
                      {act.renewable_retained_pct}%
                    </td>
                    <td className="num mono">
                      {act.cost_proxy}/3
                    </td>
                    <td className="num mono" style={{ fontWeight: 600, color: isWinner ? 'var(--accent)' : 'var(--text)' }}>
                      {act.score.toFixed(1)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* SECTION 5: INTERACTIVE CUSTOM ACTION SANDBOX */}
      <div className="vp-card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <Sliders size={20} color="var(--accent)" />
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text)' }}>
            Interactive Action Sandbox & Custom Dispatch
          </h3>
        </div>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '18px' }}>
          Manually test specific operational adjustments on the current constraint scenario and observe the physics response.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px', marginBottom: '18px' }}>
          {/* Action Type Picker */}
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '6px' }}>Select Action Type:</label>
            <select
              value={customType}
              onChange={(e) => setCustomType(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--r-sm)',
                backgroundColor: 'var(--surface-raised)',
                border: '1px solid var(--border)',
                color: 'var(--text)',
                fontSize: '0.85rem',
                outline: 'none'
              }}
            >
              <option value="VOLTAGE_SETPOINT">Substation Voltage Setpoint (p.u.)</option>
              <option value="FEEDER_RECONFIGURATION">Feeder Reconfiguration (Tie Switch)</option>
              <option value="BATTERY_DISPATCH">Battery Storage Dispatch (MW)</option>
              <option value="CURTAILMENT">Solar Generation Curtailment (%)</option>
            </select>
          </div>

          {/* Conditional Parameter Input */}
          {customType === 'VOLTAGE_SETPOINT' && (
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
                Slack Bus Voltage Setpoint: <strong className="tabular-nums">{Number(voltageSetpoint).toFixed(3)} p.u.</strong> (0.980–1.050 p.u.)
              </label>
              <input
                type="range"
                min="0.980"
                max="1.050"
                step="0.005"
                value={voltageSetpoint}
                onChange={(e) => setVoltageSetpoint(e.target.value)}
                style={{ width: '100%', accentColor: 'var(--accent)' }}
              />
            </div>
          )}

          {customType === 'FEEDER_RECONFIGURATION' && (
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '6px' }}>Select Tie Switch:</label>
              <select
                value={switchName}
                onChange={(e) => setSwitchName(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 'var(--r-sm)',
                  backgroundColor: 'var(--surface-raised)',
                  border: '1px solid var(--border)',
                  color: 'var(--text)',
                  fontSize: '0.85rem',
                  outline: 'none'
                }}
              >
                <option value="S1">Switch S1 (Line 14 — Feeder 1 & 2 Tie)</option>
                <option value="S2">Switch S2 (Line 12 — Bus 6 & 7 Loop Tie)</option>
                <option value="S3">Switch S3 (Line 13 — Bus 4 & 11 Cross Tie)</option>
              </select>
            </div>
          )}

          {customType === 'BATTERY_DISPATCH' && (
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
                Battery Dispatch Power: <strong className="tabular-nums">{batteryMw} MW</strong> ({batteryMw > 0 ? 'Charging/Absorption' : 'Discharging/Injection'})
              </label>
              <input
                type="range"
                min="-2.0"
                max="2.0"
                step="0.25"
                value={batteryMw}
                onChange={(e) => setBatteryMw(e.target.value)}
                style={{ width: '100%', accentColor: 'var(--accent)' }}
              />
            </div>
          )}

          {customType === 'CURTAILMENT' && (
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
                Curtailment Percentage: <strong className="tabular-nums">{curtailPct}%</strong>
              </label>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={curtailPct}
                onChange={(e) => setCurtailPct(e.target.value)}
                style={{ width: '100%', accentColor: 'var(--accent)' }}
              />
            </div>
          )}
        </div>

        <button
          onClick={handleApplyCustomAction}
          disabled={applyingCustom}
          className="vp-btn vp-btn-primary"
        >
          <Play size={16} />
          <span>{applyingCustom ? 'Simulating Physics...' : 'Simulate Custom Action'}</span>
        </button>

        {customResult && (
          <div className="vp-alert" data-tone={customResult.resolved ? 'ok' : 'danger'} style={{ marginTop: '16px' }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.88rem', marginBottom: '4px' }}>
                {customResult.resolved ? '✓ Custom Action Fully Resolved Grid Constraints!' : `⚠️ Residual Violations: ${customResult.violations.total_violations}`}
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                {customResult.action.description}
              </div>
            </div>
          </div>
        )}
      </div>

    </div>
  );
}

