import React, { useState, useEffect } from 'react';
import { Calendar, Clock, RefreshCw, Layers } from 'lucide-react';

export default function DateRangePicker({ startDate, endDate, onApply, loading }) {
  const [start, setStart] = useState(startDate);
  const [end, setEnd] = useState(endDate);

  useEffect(() => {
    setStart(startDate);
    setEnd(endDate);
  }, [startDate, endDate]);

  // Calculate day and month duration count
  const calculateDuration = (sDate, eDate) => {
    const d1 = new Date(sDate);
    const d2 = new Date(eDate);
    const diffTime = Math.abs(d2 - d1);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
    const approxMonths = (diffDays / 30.4).toFixed(1);
    return { days: diffDays, months: approxMonths };
  };

  const duration = calculateDuration(start, end);

  // Preset handlers
  const setPreset = (months) => {
    const s = '2023-01-01';
    let e = '2023-01-31';
    if (months === 2) e = '2023-02-28';
    if (months === 3) e = '2023-03-31';
    if (months === 6) e = '2023-06-30';

    setStart(s);
    setEnd(e);
    onApply(s, e);
  };

  const handleApply = (e) => {
    e.preventDefault();
    if (start && end) {
      onApply(start, end);
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '20px 24px', marginBottom: '24px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        
        {/* Section Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#06b6d4', fontWeight: 600, fontSize: '0.95rem' }}>
            <Calendar size={18} />
            <span>Select Simulation Date Window</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Presets:</span>
            {[
              { label: '1 Month', months: 1 },
              { label: '2 Months', months: 2 },
              { label: '3 Months', months: 3 },
              { label: '6 Months', months: 6 },
            ].map((p) => (
              <button
                key={p.months}
                type="button"
                onClick={() => setPreset(p.months)}
                style={{
                  padding: '4px 10px',
                  borderRadius: '6px',
                  fontSize: '0.78rem',
                  fontWeight: 500,
                  backgroundColor: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  color: '#e2e8f0',
                  transition: 'all 0.2s ease'
                }}
                onMouseEnter={(e) => (e.target.style.borderColor = '#06b6d4')}
                onMouseLeave={(e) => (e.target.style.borderColor = 'rgba(255, 255, 255, 0.1)')}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {/* Date Inputs Form */}
        <form onSubmit={handleApply} style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          
          {/* Start Date Calendar Input */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: '1 1 200px' }}>
            <label style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: 500 }}>Start Date (Calendar)</label>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <input
                type="date"
                value={start}
                min="2020-01-01"
                max="2023-12-31"
                onChange={(e) => setStart(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  backgroundColor: '#0f172a',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#f8fafc',
                  fontSize: '0.9rem',
                  outline: 'none'
                }}
              />
            </div>
          </div>

          {/* End Date Calendar Input */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: '1 1 200px' }}>
            <label style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: 500 }}>End Date (Calendar)</label>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <input
                type="date"
                value={end}
                min={start || "2020-01-01"}
                max="2023-12-31"
                onChange={(e) => setEnd(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  backgroundColor: '#0f172a',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#f8fafc',
                  fontSize: '0.9rem',
                  outline: 'none'
                }}
              />
            </div>
          </div>

          {/* Duration Badge */}
          <div 
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px', 
              padding: '10px 14px', 
              borderRadius: '8px', 
              backgroundColor: 'rgba(6, 182, 212, 0.08)',
              border: '1px solid rgba(6, 182, 212, 0.2)',
              marginTop: '18px'
            }}
          >
            <Clock size={16} color="#06b6d4" />
            <span style={{ fontSize: '0.85rem', color: '#cbd5e1', fontWeight: 500 }}>
              <strong style={{ color: '#06b6d4' }}>{duration.days} Days</strong> ({duration.months} Months)
            </span>
          </div>

          {/* Apply Button */}
          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: '18px',
              padding: '10px 22px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)',
              color: '#ffffff',
              fontWeight: 600,
              fontSize: '0.88rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              boxShadow: '0 0 15px rgba(6, 182, 212, 0.3)',
              opacity: loading ? 0.7 : 1,
              transition: 'transform 0.15s ease'
            }}
          >
            <RefreshCw size={16} className={loading ? 'animated-pulse' : ''} />
            <span>{loading ? 'Fetching...' : 'Update Simulation Data'}</span>
          </button>

        </form>

      </div>
    </div>
  );
}
