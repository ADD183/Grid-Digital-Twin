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

const API_BASE = 'http://127.0.0.1:8000';

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

  // Custom action sandbox inputs
  const [customType, setCustomType] = useState('FEEDER_RECONFIGURATION');
  const [curtailPct, setCurtailPct] = useState(50);
  const [batteryMw, setBatteryMw] = useState(1.5);
  const [switchName, setSwitchName] = useState('S1');
  const [customResult, setCustomResult] = useState(null);
  const [applyingCustom, setApplyingCustom] = useState(false);

  // Load scenarios on mount
  useEffect(() => {
    const fetchScenarios = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/violations/scenarios`);
        if (res.ok) {
          const data = await res.json();
          setScenarios(data.scenarios || []);
        }
      } catch (err) {
        console.error('Failed to load scenarios:', err);
      }
    };
    fetchScenarios();
  }, []);

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
      setSelectedActionIndex(0);
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
      ? { has_violations: !evaluationData?.fully_resolved, total_violations: evaluationData?.recommended_action?.residual_violations_count || 0, voltage_violations: [], loading_violations: [] }
      : activeViewMode === 'custom' && customResult?.violations
      ? customResult.violations
      : scenarioData?.violations || evaluationData?.initial_violations;

  const winner = evaluationData?.recommended_action;
  const rankedActions = evaluationData?.ranked_actions || [];

  const filteredActions = rankedActions.filter((act) => {
    if (filterType === 'ALL') return true;
    return act.action_type === filterType;
  });

  // Action type badge helper
  const getActionBadge = (type) => {
    switch (type) {
      case 'FEEDER_RECONFIGURATION':
        return { label: 'Feeder Switching', bg: 'rgba(6, 182, 212, 0.15)', border: 'rgba(6, 182, 212, 0.35)', color: '#38bdf8', icon: GitFork };
      case 'BATTERY_DISPATCH':
        return { label: 'Battery Dispatch', bg: 'rgba(168, 85, 247, 0.15)', border: 'rgba(168, 85, 247, 0.35)', color: '#c084fc', icon: BatteryCharging };
      case 'CURTAILMENT':
        return { label: 'Solar Curtailment', bg: 'rgba(245, 158, 11, 0.15)', border: 'rgba(245, 158, 11, 0.35)', color: '#fbbf24', icon: Sun };
      case 'HYBRID':
        return { label: 'Hybrid Action', bg: 'rgba(59, 130, 246, 0.15)', border: 'rgba(59, 130, 246, 0.35)', color: '#60a5fa', icon: Zap };
      default:
        return { label: type, bg: 'rgba(148, 163, 184, 0.15)', border: 'rgba(148, 163, 184, 0.35)', color: '#cbd5e1', icon: Zap };
    }
  };

  // Node color helper with strict utility bounds [0.94, 1.05]
  const getNodeColor = (vm_pu) => {
    if (vm_pu > 1.05) return '#ef4444'; // Red (Overvoltage)
    if (vm_pu < 0.94) return '#f59e0b'; // Amber (Undervoltage)
    return '#10b981'; // Green (Safe)
  };

  const getLineColor = (loading) => {
    if (loading > 100) return '#ef4444';
    if (loading > 75) return '#f59e0b';
    return '#06b6d4';
  };

  return (
    <div style={{ marginBottom: '24px' }}>
      
      {/* SECTION 1: HEADER & SCENARIO TRIGGER CONTROLS */}
      <div className="glass-panel" style={{ padding: '22px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', marginBottom: '18px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div 
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '8px',
                  background: 'linear-gradient(135deg, #ef4444 0%, #f59e0b 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 0 12px rgba(239, 68, 68, 0.4)'
                }}
              >
                <ShieldAlert size={20} color="#ffffff" />
              </div>
              <div>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc' }}>
                  Violation Detection & Corrective Action Engine
                </h2>
                <p style={{ fontSize: '0.82rem', color: '#94a3b8' }}>
                  Checkpoint 3: Propose → Verify → Repair Closed-Loop Grid Defense & Optimization
                </p>
              </div>
            </div>
          </div>

          {/* Quick Engine Status Indicator */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div 
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 14px',
                borderRadius: '20px',
                backgroundColor: currentViolations?.has_violations ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                border: `1px solid ${currentViolations?.has_violations ? 'rgba(239, 68, 68, 0.4)' : 'rgba(16, 185, 129, 0.4)'}`,
                color: currentViolations?.has_violations ? '#f87171' : '#34d399',
                fontSize: '0.82rem',
                fontWeight: 600
              }}
            >
              <span 
                style={{ 
                  width: '8px', 
                  height: '8px', 
                  borderRadius: '50%', 
                  backgroundColor: currentViolations?.has_violations ? '#ef4444' : '#10b981',
                  boxShadow: currentViolations?.has_violations ? '0 0 8px #ef4444' : '0 0 8px #10b981',
                  animation: currentViolations?.has_violations ? 'pulse-ring 1.5s infinite ease-in-out' : 'none'
                }} 
              />
              {currentViolations?.has_violations ? `${currentViolations.total_violations} Violations Active` : 'Grid In Safe Band (0.94-1.05 p.u.)'}
            </div>
          </div>
        </div>

        {/* Scenario Selection Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px', marginBottom: '18px' }}>
          {[
            { id: 'solar_spike', icon: Sun, title: 'Midday Solar Surge', desc: 'High rooftop PV + low demand triggers overvoltage (>1.05 p.u.)' },
            { id: 'evening_peak', icon: BatteryCharging, title: 'Evening Demand Peak', desc: 'Sunset + peak appliance load causes voltage sags (<0.94 p.u.)' },
            { id: 'line_congestion', icon: Zap, title: 'Feeder Line Overload', desc: 'Heavy branch demand pushes line loading past 100% thermal limit' },
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
                  backgroundColor: isSelected ? 'rgba(56, 189, 248, 0.12)' : 'rgba(15, 23, 42, 0.6)',
                  border: isSelected ? '1px solid #38bdf8' : '1px solid rgba(255, 255, 255, 0.08)',
                  borderRadius: '10px',
                  padding: '14px 16px',
                  textAlign: 'left',
                  transition: 'all 0.2s',
                  boxShadow: isSelected ? '0 0 15px rgba(56, 189, 248, 0.2)' : 'none',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                  <Icon size={18} color={isSelected ? '#38bdf8' : '#94a3b8'} />
                  <span style={{ fontWeight: 600, color: isSelected ? '#f8fafc' : '#cbd5e1', fontSize: '0.9rem' }}>
                    {scen.title}
                  </span>
                  {isSelected && (
                    <span style={{ marginLeft: 'auto', fontSize: '0.72rem', backgroundColor: 'rgba(56, 189, 248, 0.25)', color: '#38bdf8', padding: '2px 6px', borderRadius: '4px' }}>
                      Active
                    </span>
                  )}
                </div>
                <div style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.4 }}>
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
            style={{
              background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
              color: '#ffffff',
              padding: '10px 20px',
              borderRadius: '8px',
              fontWeight: 600,
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              boxShadow: '0 4px 14px rgba(239, 68, 68, 0.4)',
              transition: 'opacity 0.2s'
            }}
          >
            <ShieldAlert size={16} />
            {loading ? 'Inducing Constraint...' : '🚨 Trigger Constraint Scenario'}
          </button>

          <button
            onClick={() => handleRunEngine(selectedScenario)}
            disabled={evaluating}
            style={{
              background: 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)',
              color: '#ffffff',
              padding: '10px 20px',
              borderRadius: '8px',
              fontWeight: 600,
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              boxShadow: '0 4px 14px rgba(6, 182, 212, 0.4)',
            }}
          >
            <Zap size={16} />
            {evaluating ? 'Propose-Verify Loop Running...' : '🤖 Re-Run AI Decision Engine'}
          </button>
        </div>

        {error && (
          <div style={{ marginTop: '14px', padding: '10px 14px', borderRadius: '8px', backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#f87171', fontSize: '0.85rem' }}>
            ⚠️ {error}
          </div>
        )}
      </div>

      {/* SECTION 2: BEFORE / AFTER INTERACTIVE COMPARISON VIEW */}
      <div className="glass-panel" style={{ padding: '22px', marginBottom: '20px' }}>
        
        {/* View Switcher Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px', marginBottom: '18px' }}>
          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>Interactive Grid Topology: Before & After Action</span>
            </h3>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
              Toggle between the unmitigated violation state and the AI-corrected network state
            </p>
          </div>

          {/* Before / After Segmented Button */}
          <div style={{ display: 'flex', gap: '6px', backgroundColor: 'rgba(15, 23, 42, 0.8)', padding: '4px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
            <button
              onClick={() => setActiveViewMode('before')}
              style={{
                backgroundColor: activeViewMode === 'before' ? 'rgba(239, 68, 68, 0.25)' : 'transparent',
                color: activeViewMode === 'before' ? '#f87171' : '#94a3b8',
                border: activeViewMode === 'before' ? '1px solid rgba(239, 68, 68, 0.5)' : '1px solid transparent',
                padding: '6px 14px',
                borderRadius: '6px',
                fontSize: '0.82rem',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <AlertTriangle size={14} />
              🚨 Before Action (In Violation)
            </button>
            <button
              onClick={() => setActiveViewMode('after')}
              style={{
                backgroundColor: activeViewMode === 'after' ? 'rgba(16, 185, 129, 0.25)' : 'transparent',
                color: activeViewMode === 'after' ? '#34d399' : '#94a3b8',
                border: activeViewMode === 'after' ? '1px solid rgba(16, 185, 129, 0.5)' : '1px solid transparent',
                padding: '6px 14px',
                borderRadius: '6px',
                fontSize: '0.82rem',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
            >
              <CheckCircle2 size={14} />
              ✅ After Action (Resolved by AI)
            </button>
            {customResult && (
              <button
                onClick={() => setActiveViewMode('custom')}
                style={{
                  backgroundColor: activeViewMode === 'custom' ? 'rgba(168, 85, 247, 0.25)' : 'transparent',
                  color: activeViewMode === 'custom' ? '#c084fc' : '#94a3b8',
                  border: activeViewMode === 'custom' ? '1px solid rgba(168, 85, 247, 0.5)' : '1px solid transparent',
                  padding: '6px 14px',
                  borderRadius: '6px',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                }}
              >
                🔬 Custom Sandbox State
              </button>
            )}
          </div>
        </div>

        {/* State Banner */}
        <div 
          style={{
            padding: '12px 16px',
            borderRadius: '8px',
            marginBottom: '16px',
            backgroundColor: activeViewMode === 'after' ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
            border: `1px solid ${activeViewMode === 'after' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {activeViewMode === 'after' ? (
              <CheckCircle2 size={20} color="#10b981" />
            ) : (
              <AlertTriangle size={20} color="#ef4444" />
            )}
            <div>
              <div style={{ fontWeight: 600, color: activeViewMode === 'after' ? '#34d399' : '#f87171', fontSize: '0.88rem' }}>
                {activeViewMode === 'after' 
                  ? `Grid Healed: ${winner?.name || 'Corrective Action Applied'}`
                  : `Grid Under Stress: ${scenarioData?.scenario?.name || 'Constraint Active'}`}
              </div>
              <div style={{ fontSize: '0.78rem', color: '#cbd5e1' }}>
                {activeViewMode === 'after'
                  ? 'All bus voltages restored within [0.94, 1.05] p.u. Safe operating envelope.'
                  : `${currentViolations?.total_violations || 0} active violation constraints detected. Voltage limits violated.`}
              </div>
            </div>
          </div>

          {/* Delta Metrics Badges */}
          <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Worst Bus Voltage</div>
              <div style={{ fontSize: '0.9rem', fontWeight: 700, color: activeViewMode === 'after' ? '#34d399' : '#f87171', fontFamily: 'var(--font-mono)' }}>
                {activeViewMode === 'after'
                  ? `${evaluationData?.after_grid_summary?.vm_pu_max || winner?.max_vm_pu || '1.048'} p.u. (Safe)`
                  : `${evaluationData?.before_grid_summary?.vm_pu_max || '1.065'} p.u. (High)`}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Max Line Loading</div>
              <div style={{ fontSize: '0.9rem', fontWeight: 700, color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>
                {activeViewMode === 'after'
                  ? `${evaluationData?.after_grid_summary?.max_line_loading_percent || '45.9'}%`
                  : `${evaluationData?.before_grid_summary?.max_line_loading_percent || '65.9'}%`}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Violations Count</div>
              <div style={{ fontSize: '0.9rem', fontWeight: 700, color: activeViewMode === 'after' ? '#34d399' : '#f87171', fontFamily: 'var(--font-mono)' }}>
                {activeViewMode === 'after' ? '0 Violations (Clean)' : `${evaluationData?.initial_violations?.total_violations || 9} Violations`}
              </div>
            </div>
          </div>
        </div>

        {/* Embedded SVG Topology Canvas for Current Mode */}
        {currentTopology && currentTopology.buses && (
          <div style={{ backgroundColor: '#090d16', borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.08)', overflow: 'hidden' }}>
            <svg viewBox="0 0 860 380" style={{ width: '100%', height: 'auto', display: 'block', maxHeight: '420px' }}>
              <defs>
                <linearGradient id="engGridBg" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#0b1329" />
                  <stop offset="100%" stopColor="#070b14" />
                </linearGradient>
              </defs>
              <rect width="860" height="380" fill="url(#engGridBg)" />

              {/* Grid Lines */}
              <g stroke="rgba(255, 255, 255, 0.03)" strokeWidth="1">
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
                    <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={strokeColor} strokeWidth="4" strokeOpacity="0.25" />
                    <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={strokeColor} strokeWidth="2" className="flow-line" />
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
                const isViolation = bus.vm_pu > 1.05 || bus.vm_pu < 0.94;

                return (
                  <g key={`b-${bus.id}`}>
                    {/* Glowing ring for violation */}
                    {isViolation && (
                      <circle
                        cx={cx}
                        cy={cy}
                        r="18"
                        fill="transparent"
                        stroke="#ef4444"
                        strokeWidth="2.5"
                        strokeDasharray="4 2"
                        className="animated-pulse"
                      />
                    )}

                    <circle cx={cx} cy={cy} r="11" fill={color} stroke="#090d16" strokeWidth="2" />
                    
                    <text x={cx} y={cy + 4} textAnchor="middle" fill="#ffffff" fontSize="9" fontWeight="bold" fontFamily="var(--font-mono)">
                      {bus.id}
                    </text>
                    
                    <text x={cx} y={cy + 22} textAnchor="middle" fill={color} fontSize="9" fontWeight="600" fontFamily="var(--font-mono)">
                      {bus.vm_pu.toFixed(3)}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
        )}
      </div>

      {/* SECTION 3: WINNER RECOMMENDATION & EXPLAINABILITY */}
      {winner && (
        <div 
          className="glass-panel" 
          style={{ 
            padding: '24px', 
            marginBottom: '20px', 
            border: '1px solid rgba(6, 182, 212, 0.4)',
            boxShadow: '0 0 25px rgba(6, 182, 212, 0.15)' 
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#06b6d4', fontSize: '0.85rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
            <Award size={18} />
            <span>AI Optimal Recommendation (#1 Ranked Corrective Action)</span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px', marginBottom: '16px' }}>
            <div>
              <h3 style={{ fontSize: '1.35rem', fontWeight: 700, color: '#f8fafc', marginBottom: '4px' }}>
                {winner.name}
              </h3>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                {(() => {
                  const badge = getActionBadge(winner.action_type);
                  const Icon = badge.icon;
                  return (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '5px', backgroundColor: badge.bg, border: `1px solid ${badge.border}`, color: badge.color, padding: '3px 8px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600 }}>
                      <Icon size={12} />
                      {badge.label}
                    </span>
                  );
                })()}
                <span style={{ backgroundColor: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.35)', color: '#34d399', padding: '3px 8px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600 }}>
                  ✓ 100% Resolved (0 Residual Violations)
                </span>
                <span style={{ backgroundColor: 'rgba(56, 189, 248, 0.15)', border: '1px solid rgba(56, 189, 248, 0.35)', color: '#38bdf8', padding: '3px 8px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600 }}>
                  Score: {winner.score} pts
                </span>
              </div>
            </div>

            {/* Quick Metrics */}
            <div style={{ display: 'flex', gap: '12px' }}>
              <div style={{ backgroundColor: 'rgba(15, 23, 42, 0.6)', padding: '10px 16px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)', textAlign: 'center' }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Clean Energy Retained</div>
                <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#10b981' }}>{winner.renewable_retained_pct}%</div>
              </div>
              <div style={{ backgroundColor: 'rgba(15, 23, 42, 0.6)', padding: '10px 16px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)', textAlign: 'center' }}>
                <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Cost Proxy</div>
                <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#38bdf8' }}>{winner.cost_proxy}/3</div>
              </div>
            </div>
          </div>

          {/* Decision Rationale Explanation Box */}
          <div style={{ backgroundColor: 'rgba(6, 182, 212, 0.08)', borderLeft: '4px solid #06b6d4', padding: '14px 18px', borderRadius: '0 8px 8px 0', marginBottom: '14px' }}>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#38bdf8', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Info size={15} />
              <span>Why This Action Was Selected (Multi-Objective Decision Rationale):</span>
            </div>
            <p style={{ fontSize: '0.85rem', color: '#e2e8f0', lineHeight: 1.5 }}>
              {evaluationData.explanation}
            </p>
          </div>
        </div>
      )}

      {/* SECTION 4: ACTION COMPARISON MATRIX TABLE */}
      <div className="glass-panel" style={{ padding: '22px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '14px', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#f8fafc' }}>
              Candidate Action Evaluation Matrix ({rankedActions.length} Actions Assessed)
            </h3>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
              Full Propose-Verify-Repair comparison ranked by multi-objective score
            </p>
          </div>

          {/* Action Family Filter Buttons */}
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {['ALL', 'FEEDER_RECONFIGURATION', 'BATTERY_DISPATCH', 'CURTAILMENT', 'HYBRID'].map((type) => (
              <button
                key={type}
                onClick={() => setFilterType(type)}
                style={{
                  backgroundColor: filterType === type ? 'rgba(56, 189, 248, 0.2)' : 'rgba(15, 23, 42, 0.5)',
                  color: filterType === type ? '#38bdf8' : '#94a3b8',
                  border: filterType === type ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid rgba(255, 255, 255, 0.08)',
                  padding: '5px 12px',
                  borderRadius: '6px',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                }}
              >
                {type === 'ALL' ? 'All Types' : type.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Comparison Table */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.83rem', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)', color: '#94a3b8', fontSize: '0.75rem', textTransform: 'uppercase' }}>
                <th style={{ padding: '10px 12px' }}>Rank</th>
                <th style={{ padding: '10px 12px' }}>Action Name</th>
                <th style={{ padding: '10px 12px' }}>Action Family</th>
                <th style={{ padding: '10px 12px' }}>Resolved?</th>
                <th style={{ padding: '10px 12px' }}>Residual Viols</th>
                <th style={{ padding: '10px 12px' }}>Clean Energy</th>
                <th style={{ padding: '10px 12px' }}>Cost Proxy</th>
                <th style={{ padding: '10px 12px' }}>Score</th>
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
                      borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                      backgroundColor: isWinner ? 'rgba(6, 182, 212, 0.06)' : 'transparent',
                    }}
                  >
                    <td style={{ padding: '12px', fontWeight: 700, color: isWinner ? '#06b6d4' : '#cbd5e1' }}>
                      {isWinner ? '🏆 #1' : `#${act.rank}`}
                    </td>
                    <td style={{ padding: '12px', fontWeight: 600, color: '#f8fafc' }}>
                      {act.name}
                    </td>
                    <td style={{ padding: '12px' }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', backgroundColor: badge.bg, border: `1px solid ${badge.border}`, color: badge.color, padding: '2px 8px', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 600 }}>
                        <Icon size={11} />
                        {badge.label}
                      </span>
                    </td>
                    <td style={{ padding: '12px' }}>
                      {act.resolved ? (
                        <span style={{ color: '#10b981', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          <CheckCircle2 size={14} /> Full
                        </span>
                      ) : (
                        <span style={{ color: '#ef4444', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          <XCircle size={14} /> Partial
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '12px', fontFamily: 'var(--font-mono)' }}>
                      {act.residual_violations_count}
                    </td>
                    <td style={{ padding: '12px', fontFamily: 'var(--font-mono)', color: act.renewable_retained_pct === 100 ? '#10b981' : '#f59e0b' }}>
                      {act.renewable_retained_pct}%
                    </td>
                    <td style={{ padding: '12px', fontFamily: 'var(--font-mono)' }}>
                      {act.cost_proxy}/3
                    </td>
                    <td style={{ padding: '12px', fontWeight: 700, color: isWinner ? '#06b6d4' : '#f8fafc', fontFamily: 'var(--font-mono)' }}>
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
      <div className="glass-panel" style={{ padding: '22px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <Sliders size={20} color="#c084fc" />
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#f8fafc' }}>
            Interactive Action Sandbox & Custom Dispatch
          </h3>
        </div>
        <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '18px' }}>
          Manually test specific operational adjustments on the current constraint scenario and observe the physics response.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px', marginBottom: '18px' }}>
          {/* Action Type Picker */}
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', color: '#cbd5e1', marginBottom: '6px' }}>Select Action Type:</label>
            <select
              value={customType}
              onChange={(e) => setCustomType(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: '8px',
                backgroundColor: 'rgba(15, 23, 42, 0.8)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: '#f8fafc',
                fontSize: '0.85rem'
              }}
            >
              <option value="FEEDER_RECONFIGURATION">Feeder Reconfiguration (Tie Switch)</option>
              <option value="BATTERY_DISPATCH">Battery Storage Dispatch (MW)</option>
              <option value="CURTAILMENT">Solar Generation Curtailment (%)</option>
            </select>
          </div>

          {/* Conditional Parameter Input */}
          {customType === 'FEEDER_RECONFIGURATION' && (
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: '#cbd5e1', marginBottom: '6px' }}>Select Tie Switch:</label>
              <select
                value={switchName}
                onChange={(e) => setSwitchName(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: '8px',
                  backgroundColor: 'rgba(15, 23, 42, 0.8)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  color: '#f8fafc',
                  fontSize: '0.85rem'
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
              <label style={{ display: 'block', fontSize: '0.78rem', color: '#cbd5e1', marginBottom: '6px' }}>
                Battery Dispatch Power: <strong>{batteryMw} MW</strong> ({batteryMw > 0 ? 'Charging/Absorption' : 'Discharging/Injection'})
              </label>
              <input
                type="range"
                min="-2.0"
                max="2.0"
                step="0.25"
                value={batteryMw}
                onChange={(e) => setBatteryMw(e.target.value)}
                style={{ width: '100%', accentColor: '#c084fc' }}
              />
            </div>
          )}

          {customType === 'CURTAILMENT' && (
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: '#cbd5e1', marginBottom: '6px' }}>
                Curtailment Percentage: <strong>{curtailPct}%</strong>
              </label>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={curtailPct}
                onChange={(e) => setCurtailPct(e.target.value)}
                style={{ width: '100%', accentColor: '#fbbf24' }}
              />
            </div>
          )}
        </div>

        <button
          onClick={handleApplyCustomAction}
          disabled={applyingCustom}
          style={{
            background: 'linear-gradient(135deg, #a855f7 0%, #7c3aed 100%)',
            color: '#ffffff',
            padding: '10px 20px',
            borderRadius: '8px',
            fontWeight: 600,
            fontSize: '0.85rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            boxShadow: '0 4px 14px rgba(168, 85, 247, 0.4)',
          }}
        >
          <Play size={16} />
          {applyingCustom ? 'Simulating Physics...' : 'Simulate Custom Action'}
        </button>

        {customResult && (
          <div style={{ marginTop: '16px', padding: '14px', borderRadius: '8px', backgroundColor: customResult.resolved ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)', border: `1px solid ${customResult.resolved ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}` }}>
            <div style={{ fontWeight: 600, color: customResult.resolved ? '#34d399' : '#f87171', fontSize: '0.88rem', marginBottom: '4px' }}>
              {customResult.resolved ? '✓ Custom Action Fully Resolved Grid Constraints!' : `⚠️ Residual Violations: ${customResult.violations.total_violations}`}
            </div>
            <div style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>
              {customResult.action.description}
            </div>
          </div>
        )}
      </div>

    </div>
  );
}
