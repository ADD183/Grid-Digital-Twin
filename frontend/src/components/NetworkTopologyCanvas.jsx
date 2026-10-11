import React, { useState, useMemo } from 'react';
import { Network, Zap } from 'lucide-react';
import ChartDisclosure from './ui/ChartDisclosure';

export default function NetworkTopologyCanvas({ topology }) {
  const [selectedBus, setSelectedBus] = useState(null);
  const [hoveredBus, setHoveredBus] = useState(null);

  const buses = topology?.buses || [];
  const lines = topology?.lines || [];

  // Tidy schematic layout computation with fallback (PRD Section 4 item 5)
  const busCoordinates = useMemo(() => {
    try {
      if (!buses.length || !lines.length) return null;
      const adj = new Map();
      buses.forEach((b) => adj.set(b.id, []));
      lines.forEach((l) => {
        if (adj.has(l.from_bus)) adj.get(l.from_bus).push(l.to_bus);
        if (adj.has(l.to_bus)) adj.get(l.to_bus).push(l.from_bus);
      });

      const rootId = buses.find((b) => b.id === 1)?.id || buses[0].id;
      const depth = new Map();
      const queue = [rootId];
      depth.set(rootId, 0);

      while (queue.length > 0) {
        const u = queue.shift();
        const neighbors = adj.get(u) || [];
        for (const v of neighbors) {
          if (!depth.has(v)) {
            depth.set(v, depth.get(u) + 1);
            queue.push(v);
          }
        }
      }

      if (depth.size !== buses.length) return null; // Disconnected graph fallback

      const maxDepth = Math.max(...Array.from(depth.values()));
      const levels = Array.from({ length: maxDepth + 1 }, () => []);
      buses.forEach((b) => {
        const d = depth.get(b.id);
        levels[d].push(b);
      });

      const coords = new Map();
      const xStep = 700 / Math.max(maxDepth, 1);

      levels.forEach((levelBuses, d) => {
        const x = 80 + d * xStep;
        const yStep = 300 / (levelBuses.length + 1);
        levelBuses.forEach((b, idx) => {
          const y = 60 + (idx + 1) * yStep;
          coords.set(b.id, { x, y });
        });
      });

      return coords;
    } catch {
      return null;
    }
  }, [buses, lines]);

  if (!topology || !topology.buses || topology.buses.length === 0) {
    return (
      <div className="vp-card" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        Loading Network Topology...
      </div>
    );
  }


  // Fallback map helper scaling raw (x, y) coordinates
  const minX = Math.min(...buses.map((b) => b.x));
  const maxX = Math.max(...buses.map((b) => b.x));
  const minY = Math.min(...buses.map((b) => b.y));
  const maxY = Math.max(...buses.map((b) => b.y));

  const getBusPos = (bus) => {
    if (busCoordinates && busCoordinates.has(bus.id)) {
      return busCoordinates.get(bus.id);
    }
    const x = maxX === minX ? 430 : 80 + ((bus.x - minX) / (maxX - minX)) * 700;
    const y = maxY === minY ? 210 : 60 + ((bus.y - minY) / (maxY - minY)) * 300;
    return { x, y };
  };

  // Node color helper
  const getNodeColor = (vm_pu) => {
    if (vm_pu >= 0.95 && vm_pu <= 1.05) return 'var(--ok)';
    if ((vm_pu >= 0.90 && vm_pu < 0.95) || (vm_pu > 1.05 && vm_pu <= 1.10)) return 'var(--warn)';
    return 'var(--danger)';
  };

  // Line color helper
  const getLineColor = (loading) => {
    if (loading <= 70) return 'var(--accent)';
    if (loading <= 100) return 'var(--warn)';
    return 'var(--danger)';
  };

  const activeBus = selectedBus || hoveredBus || buses[0];

  return (
    <div className="vp-card" style={{ marginBottom: '24px' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent)', fontWeight: 600, fontSize: '1.02rem' }}>
          <Network size={20} />
          <span>Grid map</span>
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--ok)', display: 'inline-block' }} />
            <span>Normal</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--warn)', display: 'inline-block' }} />
            <span>Warning</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--danger)', display: 'inline-block' }} />
            <span>Needs attention</span>
          </div>
        </div>
      </div>

      <ChartDisclosure title="Open the network map" summary="Select a bus to inspect its current reading and connected lines.">
      {/* Main Canvas + Telemetry Sidebar Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr minmax(240px, 280px)', gap: '16px' }}>
        
        {/* SVG Canvas Container */}
        <div 
          style={{ 
            backgroundColor: 'var(--surface-raised)', 
            borderRadius: 'var(--r-md)', 
            border: '1px solid var(--border)', 
            position: 'relative', 
            overflowX: 'auto' 
          }}
        >
          <svg viewBox="0 0 860 420" style={{ width: '100%', height: '100%', minWidth: '500px', display: 'block' }}>
            {/* Background Grid Lines */}
            <g stroke="var(--border)" strokeWidth="1" strokeDasharray="2 4">
              {[...Array(10)].map((_, i) => (
                <line key={`v-${i}`} x1={i * 86} y1="0" x2={i * 86} y2="420" />
              ))}
              {[...Array(6)].map((_, i) => (
                <line key={`h-${i}`} x1="0" y1={i * 70} x2="860" y2={i * 70} />
              ))}
            </g>

            {/* Network Lines */}
            {lines.map((line) => {
              const fromBusObj = buses.find((b) => b.id === line.from_bus);
              const toBusObj = buses.find((b) => b.id === line.to_bus);
              const p1 = fromBusObj ? getBusPos(fromBusObj) : { x: 0, y: 0 };
              const p2 = toBusObj ? getBusPos(toBusObj) : { x: 0, y: 0 };

              const strokeColor = getLineColor(line.loading_percent);

              return (
                <g key={`line-${line.id}`}>
                  <line
                    x1={p1.x}
                    y1={p1.y}
                    x2={p2.x}
                    y2={p2.y}
                    stroke={strokeColor}
                    strokeWidth="2"
                    strokeOpacity="0.85"
                  />
                </g>
              );
            })}

            {/* Network Bus Nodes */}
            {buses.map((bus) => {
              const pos = getBusPos(bus);
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
                  {/* Outer selection ring */}
                  {(isSelected || isHovered) && (
                    <circle
                      cx={pos.x}
                      cy={pos.y}
                      r={18}
                      fill="transparent"
                      stroke={color}
                      strokeWidth="2"
                      strokeOpacity="0.6"
                    />
                  )}

                  {/* Core filled node */}
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={isSelected || isHovered ? 11 : 9}
                    fill={color}
                    stroke="var(--surface-raised)"
                    strokeWidth="2"
                  />

                  {/* Bus ID Text */}
                  <text
                    x={pos.x}
                    y={pos.y + 4}
                    textAnchor="middle"
                    fill="#ffffff"
                    fontSize="10"
                    fontWeight="600"
                    fontFamily="var(--font-mono)"
                    pointerEvents="none"
                  >
                    {bus.id}
                  </text>

                  {/* Label below */}
                  <text
                    x={pos.x}
                    y={pos.y + 22}
                    textAnchor="middle"
                    fill="var(--text-muted)"
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
        <div 
          className="vp-card-raised"
          style={{ 
            borderRadius: 'var(--r-md)', 
            padding: '16px', 
            display: 'flex', 
            flexDirection: 'column', 
            gap: '12px' 
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid var(--border)', paddingBottom: '10px' }}>
            <Zap size={16} color="var(--accent)" />
            <span style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--text)' }}>
              Selected location
            </span>
          </div>

          {activeBus ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Location</span>
                <div style={{ fontSize: '1.02rem', fontWeight: 600, color: 'var(--text)' }}>
                  {activeBus.name} (Bus {activeBus.id})
                </div>
              </div>

              <div style={{ padding: '10px', borderRadius: 'var(--r-sm)', backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Voltage</span>
                <div style={{ fontSize: '1.25rem', fontWeight: 600, color: getNodeColor(activeBus.vm_pu), fontFamily: 'var(--font-mono)' }}>
                  {activeBus.vm_pu.toFixed(4)} p.u.
                </div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-faint)' }}>Nominal: {activeBus.vn_kv} kV</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div style={{ padding: '8px', borderRadius: 'var(--r-sm)', backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Active Power (P)</span>
                  <div style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--text)', fontFamily: 'var(--font-mono)' }}>
                    {activeBus.p_mw.toFixed(3)} MW
                  </div>
                </div>

                <div style={{ padding: '8px', borderRadius: 'var(--r-sm)', backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Reactive Power (Q)</span>
                  <div style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--text)', fontFamily: 'var(--font-mono)' }}>
                    {activeBus.q_mvar.toFixed(3)} MVar
                  </div>
                </div>
              </div>

              <div style={{ fontSize: '0.75rem', color: 'var(--text-faint)', marginTop: '4px' }}>
                💡 Click any node on the diagram to pin telemetry data.
              </div>
            </div>
          ) : (
            <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>Open the map and select a location to view current readings.</div>
          )}

        </div>

      </div>
      </ChartDisclosure>
    </div>
  );
}

