import React, { useState } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid
} from 'recharts';
import { TrendingUp, Sun, Activity } from 'lucide-react';

export default function TimeSeriesChart({ data, startDate, endDate }) {
  const [metricMode, setMetricMode] = useState('pu'); // 'pu' or 'raw'

  if (!data || data.length === 0) {
    return (
      <div className="glass-panel" style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
        Loading Time-Series Solar & Demand Data...
      </div>
    );
  }

  // Downsample data if large date range selected (e.g. > 500 points) to keep SVG chart smooth
  const sampledData = data.length > 500 
    ? data.filter((_, idx) => idx % Math.ceil(data.length / 500) === 0)
    : data;

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div style={{ backgroundColor: '#090d16', border: '1px solid rgba(255,255,255,0.15)', padding: '10px 14px', borderRadius: '8px', boxShadow: '0 4px 20px rgba(0,0,0,0.5)' }}>
          <p style={{ fontSize: '0.78rem', color: '#94a3b8', marginBottom: '6px', fontFamily: 'var(--font-mono)' }}>{label}</p>
          {payload.map((entry, idx) => (
            <div key={idx} style={{ fontSize: '0.84rem', color: entry.color, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: entry.color }} />
              <span>{entry.name}:</span>
              <strong style={{ fontFamily: 'var(--font-mono)' }}>
                {metricMode === 'pu' ? `${entry.value.toFixed(4)} p.u.` : `${entry.value.toFixed(2)} ${entry.dataKey.includes('solar') ? 'W/m²' : 'kW'}`}
              </strong>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="glass-panel" style={{ padding: '20px', marginBottom: '24px' }}>
      
      {/* Chart Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#06b6d4', fontWeight: 600, fontSize: '1.02rem' }}>
          <TrendingUp size={20} />
          <span>Hourly Solar Generation (PVGIS Pune) vs. Customer Load Demand</span>
        </div>

        {/* Toggle Mode Button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>Units:</span>
          <button
            onClick={() => setMetricMode('pu')}
            style={{
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '0.78rem',
              fontWeight: 500,
              backgroundColor: metricMode === 'pu' ? '#06b6d4' : 'rgba(255,255,255,0.05)',
              color: metricMode === 'pu' ? '#ffffff' : '#94a3b8'
            }}
          >
            Per Unit (p.u.)
          </button>
          <button
            onClick={() => setMetricMode('raw')}
            style={{
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '0.78rem',
              fontWeight: 500,
              backgroundColor: metricMode === 'raw' ? '#06b6d4' : 'rgba(255,255,255,0.05)',
              color: metricMode === 'raw' ? '#ffffff' : '#94a3b8'
            }}
          >
            Raw (W/m² & kW)
          </button>
        </div>
      </div>

      {/* Chart Canvas */}
      <div style={{ width: '100%', height: 380 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={sampledData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="solarGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.0} />
              </linearGradient>
              <linearGradient id="loadGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" />
            <XAxis dataKey="timestamp" stroke="#64748b" fontSize={11} tickLine={false} />
            <YAxis stroke="#64748b" fontSize={11} tickLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Legend verticalAlign="top" height={36} />

            {/* Solar Generation Trace */}
            <Area
              type="monotone"
              dataKey={metricMode === 'pu' ? 'solar_pu' : 'solar_ghi'}
              name="Solar Generation (Pune PVGIS)"
              stroke="#f59e0b"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#solarGrad)"
            />

            {/* Demand Load Trace */}
            <Area
              type="monotone"
              dataKey={metricMode === 'pu' ? 'load_pu' : 'load_kw'}
              name="Customer Load Demand"
              stroke="#3b82f6"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#loadGrad)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

    </div>
  );
}
