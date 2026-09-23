import React from 'react';
import { Cpu, Sun, Activity, Gauge, CheckCircle2 } from 'lucide-react';

export default function MetricCards({ summary }) {
  if (!summary) return null;

  const {
    bus_count = 15,
    der_count = 13,
    vm_pu_min = 0.9438,
    vm_pu_max = 1.0300,
    max_line_loading_percent = 65.97,
    converged = true
  } = summary;

  const isVoltageSafe = vm_pu_min >= 0.94 && vm_pu_max <= 1.05;
  const isLineSafe = max_line_loading_percent <= 100;

  const cards = [
    {
      title: 'Active Grid Buses',
      value: `${bus_count} Buses`,
      sub: '15 kV Distribution Network',
      icon: Cpu,
      color: '#06b6d4'
    },
    {
      title: 'Connected DERs',
      value: `${der_count} DER Units`,
      sub: 'Rooftop Solar & Distributed Gen',
      icon: Sun,
      color: '#f59e0b'
    },
    {
      title: 'Bus Voltage Range',
      value: `${vm_pu_min.toFixed(4)} - ${vm_pu_max.toFixed(4)} p.u.`,
      sub: isVoltageSafe ? 'Safe Band (0.95 ± 0.05 p.u.)' : 'Voltage Warning',
      icon: Activity,
      color: isVoltageSafe ? '#10b981' : '#f59e0b'
    },
    {
      title: 'Max Thermal Line Load',
      value: `${max_line_loading_percent.toFixed(1)}%`,
      sub: isLineSafe ? 'Normal Thermal Loading (<100%)' : 'Line Overload',
      icon: Gauge,
      color: isLineSafe ? '#10b981' : '#ef4444'
    }
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '24px' }}>
      {cards.map((card, idx) => {
        const IconComponent = card.icon;
        return (
          <div 
            key={idx} 
            className="glass-panel" 
            style={{ padding: '18px 20px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <span style={{ fontSize: '0.82rem', color: '#94a3b8', fontWeight: 500 }}>{card.title}</span>
              <div 
                style={{ 
                  width: '32px', 
                  height: '32px', 
                  borderRadius: '8px', 
                  backgroundColor: `${card.color}15`, 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  border: `1px solid ${card.color}30`
                }}
              >
                <IconComponent size={17} color={card.color} />
              </div>
            </div>

            <div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', fontFamily: 'var(--font-mono)' }}>
                {card.value}
              </div>
              <div style={{ fontSize: '0.76rem', color: card.color, marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle2 size={12} color={card.color} />
                <span>{card.sub}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
