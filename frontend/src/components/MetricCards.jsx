import React from 'react';
import { Cpu, Sun, Activity, Gauge, CheckCircle2, AlertTriangle } from 'lucide-react';

export default function MetricCards({ summary }) {
  if (!summary) return null;

  const {
    bus_count = 15,
    der_count = 13,
    vm_pu_min,
    vm_pu_max,
    max_line_loading_percent,
    converged
  } = summary;

  const isVoltageSafe = converged && vm_pu_min != null && vm_pu_max != null && vm_pu_min >= 0.95 && vm_pu_max <= 1.05;
  const isLineSafe = max_line_loading_percent != null ? max_line_loading_percent <= 100 : true;

  const cards = [
    {
      title: 'Network locations',
      value: `${bus_count} locations`,
      sub: 'Across the distribution grid',
      icon: Cpu,
      tone: 'info'
    },
    {
      title: 'Local energy sources',
      value: `${der_count} sources`,
      sub: 'Solar and distributed generation',
      icon: Sun,
      tone: 'info'
    },
    {
      title: 'Voltage health',
      value: vm_pu_min != null && vm_pu_max != null ? `${vm_pu_min.toFixed(4)} - ${vm_pu_max.toFixed(4)} p.u.` : '1.0000 - 1.0500 p.u.',
      sub: isVoltageSafe ? 'Within normal limits' : 'Needs attention',
      icon: Activity,
      tone: isVoltageSafe ? 'ok' : 'danger'
    },
    {
      title: 'Line use',
      value: max_line_loading_percent != null ? `${max_line_loading_percent.toFixed(1)}%` : '0.0%',
      sub: isLineSafe ? 'Within normal limits' : 'Needs attention',
      icon: Gauge,
      tone: isLineSafe ? 'ok' : 'danger'
    }
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '24px' }}>
      {cards.map((card, idx) => {
        const IconComponent = card.icon;
        const SubIcon = card.tone === 'danger' ? AlertTriangle : CheckCircle2;
        return (
          <div key={idx} className="vp-kpi-tile" data-tone={card.tone}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span className="vp-kpi-label">{card.title}</span>
              <IconComponent size={18} style={{ color: 'var(--text-muted)' }} />
            </div>

            <div className="vp-kpi-value">
              {card.value}
            </div>

            <div 
              className="vp-kpi-subtext"
              style={{ 
                marginTop: '6px', 
                display: 'flex', 
                alignItems: 'center', 
                gap: '4px',
                color: card.tone === 'ok' ? 'var(--ok)' : card.tone === 'danger' ? 'var(--danger)' : 'var(--text-faint)'
              }}
            >
              <SubIcon size={13} />
              <span>{card.sub}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

