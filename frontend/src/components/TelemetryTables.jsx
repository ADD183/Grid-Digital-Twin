import React, { useState } from 'react';
import { Table } from 'lucide-react';

export default function TelemetryTables({ topology }) {
  const [activeTab, setActiveTab] = useState('buses');

  if (!topology || !topology.buses) return null;

  const { buses = [], lines = [] } = topology;

  return (
    <div className="vp-card" style={{ marginBottom: '24px' }}>
      
      {/* Header & Tabs */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent)', fontWeight: 600, fontSize: '1.02rem' }}>
          <Table size={20} />
          <span>Grid Telemetry & Thermal Load Inspection</span>
        </div>

        {/* Tab Buttons */}
        <div className="vp-segmented">
          <button
            onClick={() => setActiveTab('buses')}
            className={`vp-segmented-btn ${activeTab === 'buses' ? 'active' : ''}`}
            aria-selected={activeTab === 'buses'}
          >
            Bus Voltages ({buses.length})
          </button>
          <button
            onClick={() => setActiveTab('lines')}
            className={`vp-segmented-btn ${activeTab === 'lines' ? 'active' : ''}`}
            aria-selected={activeTab === 'lines'}
          >
            Line Thermal Loading ({lines.length})
          </button>
        </div>
      </div>

      {/* Tab 1: Bus Table */}
      {activeTab === 'buses' && (
        <div className="vp-table-container">
          <table className="vp-table">
            <thead>
              <tr>
                <th>Bus ID</th>
                <th>Name</th>
                <th className="num">Voltage (p.u.)</th>
                <th className="num">Nominal (kV)</th>
                <th className="num">Active Power P (MW)</th>
                <th className="num">Reactive Power Q (MVar)</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {buses.map((bus) => {
                const isSafe = bus.vm_pu >= 0.95 && bus.vm_pu <= 1.05;
                return (
                  <tr key={bus.id}>
                    <td className="mono" style={{ fontWeight: 600, color: 'var(--accent)' }}>{bus.id}</td>
                    <td>{bus.name}</td>
                    <td className="num mono" style={{ fontWeight: 600, color: isSafe ? 'var(--ok)' : 'var(--danger)' }}>
                      {bus.vm_pu.toFixed(4)}
                    </td>
                    <td className="num">{bus.vn_kv} kV</td>
                    <td className="num mono">{bus.p_mw.toFixed(3)}</td>
                    <td className="num mono">{bus.q_mvar.toFixed(3)}</td>
                    <td>
                      <span className="vp-badge" data-tone={isSafe ? 'ok' : 'danger'}>
                        {isSafe ? 'Normal' : 'Violation'}
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
        <div className="vp-table-container">
          <table className="vp-table">
            <thead>
              <tr>
                <th>Line ID</th>
                <th>Name</th>
                <th>Endpoints</th>
                <th className="num">Length (km)</th>
                <th className="num">Thermal Loading (%)</th>
                <th>Load Visual</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line) => {
                const load = line.loading_percent;
                const tone = load <= 70 ? 'ok' : load <= 100 ? 'warn' : 'danger';
                const barColor = tone === 'ok' ? 'var(--ok)' : tone === 'warn' ? 'var(--warn)' : 'var(--danger)';
                return (
                  <tr key={line.id}>
                    <td className="mono" style={{ fontWeight: 600, color: 'var(--accent)' }}>{line.id}</td>
                    <td>{line.name}</td>
                    <td>Bus {line.from_bus} → Bus {line.to_bus}</td>
                    <td className="num">{line.length_km} km</td>
                    <td className="num mono" style={{ fontWeight: 600, color: barColor }}>
                      {load.toFixed(2)}%
                    </td>
                    <td style={{ width: '180px' }}>
                      <div style={{ height: '6px', width: '100%', backgroundColor: 'var(--surface-raised)', borderRadius: '999px', overflow: 'hidden', border: '1px solid var(--border)' }}>
                        <div style={{ height: '100%', width: `${Math.min(load, 100)}%`, backgroundColor: barColor, borderRadius: '999px', transition: 'width 0.3s ease' }} />
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

