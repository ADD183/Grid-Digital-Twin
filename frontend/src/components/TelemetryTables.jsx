import React, { useState } from 'react';
import { Table, Server, Cpu, Activity } from 'lucide-react';

export default function TelemetryTables({ topology }) {
  const [activeTab, setActiveTab] = useState('buses');

  if (!topology || !topology.buses) return null;

  const { buses = [], lines = [] } = topology;

  return (
    <div className="glass-panel" style={{ padding: '20px', marginBottom: '24px' }}>
      
      {/* Header & Tabs */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#06b6d4', fontWeight: 600, fontSize: '1.02rem' }}>
          <Table size={20} />
          <span>Grid Telemetry & Thermal Load Inspection</span>
        </div>

        {/* Tab Buttons */}
        <div style={{ display: 'flex', backgroundColor: '#0f172a', padding: '4px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.08)' }}>
          <button
            onClick={() => setActiveTab('buses')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              fontSize: '0.8rem',
              fontWeight: 600,
              backgroundColor: activeTab === 'buses' ? '#06b6d4' : 'transparent',
              color: activeTab === 'buses' ? '#ffffff' : '#94a3b8'
            }}
          >
            Bus Voltages ({buses.length})
          </button>
          <button
            onClick={() => setActiveTab('lines')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              fontSize: '0.8rem',
              fontWeight: 600,
              backgroundColor: activeTab === 'lines' ? '#06b6d4' : 'transparent',
              color: activeTab === 'lines' ? '#ffffff' : '#94a3b8'
            }}
          >
            Line Thermal Loading ({lines.length})
          </button>
        </div>
      </div>

      {/* Tab 1: Bus Table */}
      {activeTab === 'buses' && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
            <thead>
              <tr style={{ backgroundColor: 'rgba(255,255,255,0.03)', color: '#94a3b8', textAlign: 'left', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                <th style={{ padding: '10px 14px' }}>Bus ID</th>
                <th style={{ padding: '10px 14px' }}>Name</th>
                <th style={{ padding: '10px 14px' }}>Voltage (p.u.)</th>
                <th style={{ padding: '10px 14px' }}>Nominal (kV)</th>
                <th style={{ padding: '10px 14px' }}>Active Power P (MW)</th>
                <th style={{ padding: '10px 14px' }}>Reactive Power Q (MVar)</th>
                <th style={{ padding: '10px 14px' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {buses.map((bus) => {
                const isSafe = bus.vm_pu >= 0.94 && bus.vm_pu <= 1.05;
                const statusColor = isSafe ? '#10b981' : '#f59e0b';
                return (
                  <tr key={bus.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#06b6d4' }}>{bus.id}</td>
                    <td style={{ padding: '10px 14px', color: '#f8fafc' }}>{bus.name}</td>
                    <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontWeight: 700, color: statusColor }}>
                      {bus.vm_pu.toFixed(4)}
                    </td>
                    <td style={{ padding: '10px 14px', color: '#cbd5e1' }}>{bus.vn_kv} kV</td>
                    <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', color: '#cbd5e1' }}>{bus.p_mw.toFixed(3)}</td>
                    <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', color: '#cbd5e1' }}>{bus.q_mvar.toFixed(3)}</td>
                    <td style={{ padding: '10px 14px' }}>
                      <span style={{ padding: '2px 8px', borderRadius: '12px', fontSize: '0.74rem', backgroundColor: `${statusColor}15`, color: statusColor, border: `1px solid ${statusColor}30` }}>
                        {isSafe ? 'Normal' : 'Warning'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 2: Line Table */}
      {activeTab === 'lines' && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem' }}>
            <thead>
              <tr style={{ backgroundColor: 'rgba(255,255,255,0.03)', color: '#94a3b8', textAlign: 'left', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                <th style={{ padding: '10px 14px' }}>Line ID</th>
                <th style={{ padding: '10px 14px' }}>Name</th>
                <th style={{ padding: '10px 14px' }}>Endpoints</th>
                <th style={{ padding: '10px 14px' }}>Length (km)</th>
                <th style={{ padding: '10px 14px' }}>Thermal Loading (%)</th>
                <th style={{ padding: '10px 14px' }}>Load Visual</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line) => {
                const load = line.loading_percent;
                const barColor = load <= 70 ? '#06b6d4' : (load <= 100 ? '#f59e0b' : '#ef4444');
                return (
                  <tr key={line.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#06b6d4' }}>{line.id}</td>
                    <td style={{ padding: '10px 14px', color: '#f8fafc' }}>{line.name}</td>
                    <td style={{ padding: '10px 14px', color: '#cbd5e1' }}>Bus {line.from_bus} → Bus {line.to_bus}</td>
                    <td style={{ padding: '10px 14px', color: '#cbd5e1' }}>{line.length_km} km</td>
                    <td style={{ padding: '10px 14px', fontFamily: 'var(--font-mono)', fontWeight: 700, color: barColor }}>
                      {load.toFixed(2)}%
                    </td>
                    <td style={{ padding: '10px 14px', width: '180px' }}>
                      <div style={{ height: '8px', width: '100%', backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: '4px', overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${Math.min(load, 100)}%`, backgroundColor: barColor, borderRadius: '4px' }} />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

    </div>
  );
}
