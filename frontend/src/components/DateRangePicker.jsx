import React, { useState, useEffect } from 'react';
import { Calendar, Clock, RefreshCw } from 'lucide-react';

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
    <div className="vp-card" style={{ marginBottom: '24px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        
        {/* Section Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent)', fontWeight: 600, fontSize: '0.95rem' }}>
            <Calendar size={18} />
            <span>Select Simulation Date Window</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginRight: '4px' }}>Presets:</span>
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
                className="vp-btn vp-btn-secondary"
                style={{ height: '30px', padding: '0 10px', fontSize: '0.78rem' }}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {/* Date Inputs Form */}
        <form onSubmit={handleApply} style={{ display: 'flex', alignItems: 'flex-end', gap: '16px', flexWrap: 'wrap' }}>
          
          {/* Start Date Calendar Input */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: '1 1 200px' }}>
            <label style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 500 }}>Start Date</label>
            <input
              type="date"
              value={start}
              min="2020-01-01"
              max="2023-12-31"
              onChange={(e) => setStart(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--r-sm)',
                backgroundColor: 'var(--surface-raised)',
                border: '1px solid var(--border)',
                color: 'var(--text)',
                fontSize: '0.88rem',
                outline: 'none',
                colorScheme: 'inherit'
              }}
            />
          </div>

          {/* End Date Calendar Input */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: '1 1 200px' }}>
            <label style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 500 }}>End Date</label>
            <input
              type="date"
              value={end}
              min={start || "2020-01-01"}
              max="2023-12-31"
              onChange={(e) => setEnd(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--r-sm)',
                backgroundColor: 'var(--surface-raised)',
                border: '1px solid var(--border)',
                color: 'var(--text)',
                fontSize: '0.88rem',
                outline: 'none',
                colorScheme: 'inherit'
              }}
            />
          </div>

          {/* Duration Badge */}
          <div 
            className="vp-badge" 
            data-tone="info"
            style={{ 
              padding: '8px 12px', 
              borderRadius: 'var(--r-sm)', 
              fontSize: '0.82rem',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Clock size={15} />
            <span>
              <strong>{duration.days} Days</strong> ({duration.months} Months)
            </span>
          </div>

          {/* Apply Button */}
          <button
            type="submit"
            disabled={loading}
            className="vp-btn vp-btn-primary"
          >
            <RefreshCw size={16} className={loading ? 'animated-spin' : ''} />
            <span>{loading ? 'Fetching...' : 'Update Data'}</span>
          </button>

        </form>

      </div>
    </div>
  );
}

