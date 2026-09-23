import React from 'react';
import { Activity, Zap, MapPin, ShieldCheck } from 'lucide-react';

export default function Header({ apiOnline }) {
  return (
    <header className="glass-panel" style={{ padding: '16px 24px', marginBottom: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        
        {/* Brand & Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div 
            style={{
              width: '44px',
              height: '44px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 15px rgba(6, 182, 212, 0.4)'
            }}
          >
            <Zap size={24} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h1 style={{ fontSize: '1.35rem', fontWeight: 700, color: '#f8fafc', letterSpacing: '-0.02em' }}>
                Renewable Distribution Grid Digital Twin
              </h1>
              <span 
                style={{ 
                  backgroundColor: 'rgba(6, 182, 212, 0.15)', 
                  color: '#06b6d4', 
                  border: '1px solid rgba(6, 182, 212, 0.3)',
                  padding: '2px 8px', 
                  borderRadius: '6px', 
                  fontSize: '0.75rem',
                  fontWeight: 600
                }}
              >
                Checkpoint 1
              </span>
            </div>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: '2px' }}>
              AC Power Flow Simulation & PVGIS Solar Irradiance Integration
            </p>
          </div>
        </div>

        {/* Badges & Meta Info */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', color: '#cbd5e1' }}>
            <MapPin size={15} color="#06b6d4" />
            <span>Pune, India (18.52° N, 73.85° E)</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', color: '#cbd5e1' }}>
            <ShieldCheck size={15} color="#10b981" />
            <span>CIGRE MV 15-Bus DER Grid</span>
          </div>

          {/* API Status Badge */}
          <div 
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px', 
              padding: '6px 12px', 
              borderRadius: '20px',
              backgroundColor: apiOnline ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
              border: `1px solid ${apiOnline ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
              fontSize: '0.8rem',
              fontWeight: 500,
              color: apiOnline ? '#10b981' : '#ef4444'
            }}
          >
            <span 
              style={{ 
                width: '8px', 
                height: '8px', 
                borderRadius: '50%', 
                backgroundColor: apiOnline ? '#10b981' : '#ef4444',
                boxShadow: apiOnline ? '0 0 8px #10b981' : '0 0 8px #ef4444'
              }} 
            />
            {apiOnline ? 'Backend Online (FastAPI)' : 'Connecting to API...'}
          </div>

        </div>

      </div>
    </header>
  );
}
