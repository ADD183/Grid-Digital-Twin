import React, { useState } from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid
} from 'recharts';
import { TrendingUp } from 'lucide-react';

export default function TimeSeriesChart({ data, startDate, endDate }) {
  const [metricMode, setMetricMode] = useState('pu'); // 'pu' or 'raw'

  if (!data || data.length === 0) {
    return (
      <div className="vp-card" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
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
        <div 
          style={{ 
            backgroundColor: 'var(--surface-raised)', 
            border: '1px solid var(--border-strong)', 
            padding: '10px 14px', 
            borderRadius: 'var(--r-sm)', 
            boxShadow: 'var(--shadow-card)' 
          }}
        >
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '6px', fontFamily: 'var(--font-mono)' }}>{label}</p>
          {payload.map((entry, idx) => (
            <div key={idx} style={{ fontSize: '0.84rem', color: entry.color, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: entry.color }} />
              <span>{entry.name}:</span>
              <strong style={{ fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}>
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
    <div className="vp-card" style={{ marginBottom: '24px' }}>
      
      {/* Chart Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent)', fontWeight: 600, fontSize: '1.02rem' }}>
          <TrendingUp size={20} />
          <span>Hourly Solar Generation (PVGIS Pune) vs. Customer Load Demand</span>
        </div>

        {/* Toggle Mode Button */}
        <div className="vp-segmented">
          <button
            onClick={() => setMetricMode('pu')}
            className={`vp-segmented-btn ${metricMode === 'pu' ? 'active' : ''}`}
            aria-selected={metricMode === 'pu'}
          >
            Per Unit (p.u.)
          </button>
          <button
            onClick={() => setMetricMode('raw')}
            className={`vp-segmented-btn ${metricMode === 'raw' ? 'active' : ''}`}
            aria-selected={metricMode === 'raw'}
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
                <stop offset="5%" stopColor="var(--c-solar)" stopOpacity={0.25} />
                <stop offset="95%" stopColor="var(--c-solar)" stopOpacity={0.0} />
              </linearGradient>
              <linearGradient id="loadGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--c-load)" stopOpacity={0.2} />
                <stop offset="95%" stopColor="var(--c-load)" stopOpacity={0.0} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="timestamp" stroke="var(--text-faint)" fontSize={11} tickLine={false} />
            <YAxis stroke="var(--text-faint)" fontSize={11} tickLine={false} />
            <Tooltip content={<CustomTooltip />} />
            <Legend verticalAlign="top" height={36} />

            {/* Solar Generation Trace */}
            <Area
              type="monotone"
              dataKey={metricMode === 'pu' ? 'solar_pu' : 'solar_ghi'}
              name="Solar Generation (Pune PVGIS)"
              stroke="var(--c-solar)"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#solarGrad)"
            />

            {/* Demand Load Trace */}
            <Area
              type="monotone"
              dataKey={metricMode === 'pu' ? 'load_pu' : 'load_kw'}
              name="Customer Load Demand"
              stroke="var(--c-load)"
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

