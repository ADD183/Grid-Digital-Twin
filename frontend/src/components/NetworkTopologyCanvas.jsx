import React, { useState } from 'react';
import { Network, Zap, Info, ShieldAlert, CheckCircle, Flame } from 'lucide-react';

export default function NetworkTopologyCanvas({ topology }) {
  const [selectedBus, setSelectedBus] = useState(null);
  const [hoveredBus, setHoveredBus] = useState(null);

  if (!topology || !topology.buses || topology.buses.length === 0) {
    return (
      <div className="glass-panel" style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
        Loading Network Topology...
      </div>
    );
  }

  const { buses, lines } = topology;

  // Scale bus (x, y) coordinates to SVG viewBox space (width: 860, height: 420)
  const minX = Math.min(...buses.map((b) => b.x));
  const maxX = Math.max(...buses.map((b) => b.x));
  const minY = Math.min(...buses.map((b) => b.y));
  const maxY = Math.max(...buses.map((b) => b.y));

  const mapX = (x) => {
    if (maxX === minX) return 430;
    return 80 + ((x - minX) / (maxX - minX)) * 700;
  };

  const mapY = (y) => {
    if (maxY === minY) return 210;
    // Note: invert Y since SVG origin is top-left
    return 60 + ((y - minY) / (maxY - minY)) * 300;
  };

  // Node color helper
  const getNodeColor = (vm_pu) => {
    if (vm_pu >= 0.95 && vm_pu <= 1.05) return '#10b981'; // Green (Safe)
    if ((vm_pu >= 0.90 && vm_pu < 0.95) || (vm_pu > 1.05 && vm_pu <= 1.10)) return '#f59e0b'; // Amber (Warning)
    return '#ef4444'; // Red (Violation)
  };

  // Line color helper
  const getLineColor = (loading) => {
    if (loading <= 70) return '#06b6d4'; // Cyan
    if (loading <= 100) return '#f59e0b'; // Amber
    return '#ef4444'; // Red Overload
  };

  const activeBus = selectedBus || hoveredBus || buses[0];

  return (
    <div className="glass-panel" style={{ padding: '20px', marginBottom: '24px' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#06b6d4', fontWeight: 600, fontSize: '1.02rem' }}>
          <Network size={20} />
          <span>CIGRE MV Distribution Grid Topology Map</span>
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', fontSize: '0.78rem', color: '#94a3b8' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#10b981', display: 'inline-block' }} />
            <span>Safe (0.95-1.05 p.u.)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#f59e0b', display: 'inline-block' }} />
            <span>Warning</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#ef4444', display: 'inline-block' }} />
            <span>Violation</span>
          </div>
        </div>
      </div>

      {/* Main Canvas + Telemetry Sidebar Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 260px', gap: '16px' }}>
        
        {/* SVG Canvas Container */}
        <div style={{ backgroundColor: '#090d16', borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.08)', position: 'relative', overflow: 'hidden' }}>
          
          <svg viewBox="0 0 860 420" style={{ width: '100%', height: '100%', display: 'block' }}>
            <defs>
              <linearGradient id="gridBg" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#0b1329" />
                <stop offset="100%" stopColor="#070b14" />
              </linearGradient>
            </defs>

            <rect width="860" height="420" fill="url(#gridBg)" />

            {/* Subtle Background Grid Lines */}
            <g stroke="rgba(255, 255, 255, 0.03)" strokeWidth="1">
              {[...Array(10)].map((_, i) => (
                <line key={`v-${i}`} x1={i * 86} y1="0" x2={i * 86} y2="420" />
              ))}
              {[...Array(6)].map((_, i) => (
                <line key={`h-${i}`} x1="0" y1={i * 70} x2="860" y2={i * 70} />
              ))}
            </g>

            {/* Network Lines */}
            {lines.map((line) => {
              const fromBus = buses.find((b) => b.id === line.from_bus) || { x: line.from_x, y: line.from_y };
              const toBus = buses.find((b) => b.id === line.to_bus) || { x: line.to_x, y: line.to_y };

              const x1 = mapX(fromBus.x);
              const y1 = mapY(fromBus.y);
              const x2 = mapX(toBus.x);
              const y2 = mapY(toBus.y);

              const strokeColor = getLineColor(line.loading_percent);

              return (
                <g key={`line-${line.id}`}>
                  {/* Outer line shadow */}
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke={strokeColor}
                    strokeWidth="4"
                    strokeOpacity="0.3"
                  />
                  {/* Inner line */}
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke={strokeColor}
                    strokeWidth="2"
                    className="flow-line"
                  />
                </g>
              );
            })}

            {/* Network Bus Nodes */}
            {buses.map((bus) => {
              const cx = mapX(bus.x);
              const cy = mapY(bus.y);
              const color = getNodeColor(bus.vm_pu);
              const isSelected = selectedBus && selectedBus.id === bus.id;
              const isHovered = hoveredBus && hoveredBus.id === bus.id;

              return (
                <g
                  key={`bus-${bus.id}`}
                  onClick={() => setSelectedBus(bus)}
                  onMouseEnter={() => setHoveredBus(bus)}
                  onMouseLeave={() => setHoveredBus(null)}
                  style={{ cursor: 'pointer' }}
                >
                  {/* Outer pulse ring */}
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isSelected || isHovered ? 20 : 15}
                    fill="transparent"
                    stroke={color}
                    strokeWidth="2"
                    strokeOpacity={isSelected || isHovered ? "0.9" : "0.4"}
                    className={isSelected || isHovered ? "animated-pulse" : ""}
                  />

                  {/* Core filled node */}
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isSelected || isHovered ? 12 : 10}
                    fill={color}
                    stroke="#090d16"
                    strokeWidth="2"
                  />

                  {/* Bus ID Text */}
                  <text
                    x={cx}
                    y={cy + 4}
                    textAnchor="middle"
                    fill="#ffffff"
                    fontSize="10"
                    fontWeight="bold"
                    fontFamily="var(--font-mono)"
                    pointerEvents="none"
                  >
                    {bus.id}
                  </text>

                  {/* Label below */}
                  <text
                    x={cx}
                    y={cy + 24}
                    textAnchor="middle"
                    fill="#94a3b8"
                    fontSize="9"
                    fontFamily="var(--font-sans)"
                    pointerEvents="none"
                  >
                    {bus.vm_pu.toFixed(3)} p.u.
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* Telemetry Inspector Panel */}
        <div style={{ backgroundColor: '#0f172a', borderRadius: '10px', padding: '16px', border: '1px solid rgba(255, 255, 255, 0.08)', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '10px' }}>
            <Zap size={16} color="#06b6d4" />
            <span style={{ fontSize: '0.88rem', fontWeight: 600, color: '#f8fafc' }}>
              Bus Telemetry Inspector
            </span>
          </div>

          {activeBus ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Target Node</span>
                <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc' }}>
                  {activeBus.name} (Bus {activeBus.id})
                </div>
              </div>

              <div style={{ padding: '10px', borderRadius: '8px', backgroundColor: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Voltage Level</span>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: getNodeColor(activeBus.vm_pu), fontFamily: 'var(--font-mono)' }}>
                  {activeBus.vm_pu.toFixed(4)} p.u.
                </div>
                <span style={{ fontSize: '0.72rem', color: '#64748b' }}>Nominal: {activeBus.vn_kv} kV</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div style={{ padding: '8px', borderRadius: '6px', backgroundColor: 'rgba(255, 255, 255, 0.03)' }}>
                  <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Active Power (P)</span>
                  <div style={{ fontSize: '0.92rem', fontWeight: 600, color: '#e2e8f0', fontFamily: 'var(--font-mono)' }}>
                    {activeBus.p_mw.toFixed(3)} MW
                  </div>
                </div>

                <div style={{ padding: '8px', borderRadius: '6px', backgroundColor: 'rgba(255, 255, 255, 0.03)' }}>
                  <span style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Reactive Power (Q)</span>
                  <div style={{ fontSize: '0.92rem', fontWeight: 600, color: '#e2e8f0', fontFamily: 'var(--font-mono)' }}>
                    {activeBus.q_mvar.toFixed(3)} MVar
                  </div>
                </div>
              </div>

              <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '6px' }}>
                💡 Click any node on the diagram to pin telemetry data.
              </div>
            </div>
          ) : (
            <div style={{ fontSize: '0.82rem', color: '#94a3b8' }}>Hover or click a node to view real-time AC power flow results.</div>
          )}

        </div>

      </div>
    </div>
  );
}
