import React from 'react';
import {
  ArrowRight,
  Brain,
  ChartNoAxesCombined,
  Clock,
  Gauge,
  PanelsTopLeft,
  SlidersHorizontal,
} from 'lucide-react';
import MetricCards from '../MetricCards';

const WORKSPACE_LINKS = [
  {
    id: 'showcase',
    title: 'Daily story',
    description: 'Follow a full-day grid run and its key events.',
    icon: Clock,
  },
  {
    id: 'grid',
    title: 'Grid status',
    description: 'Review current conditions, connections, and energy use.',
    icon: Gauge,
  },
  {
    id: 'forecast',
    title: 'Forecasts',
    description: 'Compare expected generation and demand.',
    icon: ChartNoAxesCombined,
  },
  {
    id: 'engine',
    title: 'Grid actions',
    description: 'Explore grid situations and possible responses.',
    icon: SlidersHorizontal,
  },
  {
    id: 'time_plan',
    title: 'Plan over time',
    description: 'Review how planned actions change across periods.',
    icon: Clock,
  },
  {
    id: 'mpc',
    title: 'Plan settings',
    description: 'Set starting conditions and run a plan.',
    icon: PanelsTopLeft,
  },
  {
    id: 'surrogate',
    title: 'Prediction quality',
    description: 'Review where estimates are reliable and where they differ.',
    icon: Brain,
  },
];

export default function DashboardOverview({ summary, apiOnline, onNavigate }) {
  return (
    <div className="vp-dashboard">
      <header className="vp-dashboard-header">
        <div>
          <span className="vp-dashboard-eyebrow">VoltPredict</span>
          <h2>Grid overview</h2>
          <p>See current conditions or open a workspace to explore a specific question.</p>
        </div>
        <span className="vp-dashboard-status" data-status={apiOnline ? 'online' : 'offline'}>
          <span aria-hidden="true" />
          {apiOnline ? 'Connected' : 'Not connected'}
        </span>
      </header>

      <section className="vp-dashboard-section" aria-labelledby="dashboard-grid-title">
        <div className="vp-dashboard-section-heading">
          <div>
            <h3 id="dashboard-grid-title">Current grid conditions</h3>
            <p>A quick read on network health and local energy sources.</p>
          </div>
          <button type="button" className="vp-btn vp-btn-secondary" onClick={() => onNavigate('grid')}>
            Open grid status <ArrowRight size={15} />
          </button>
        </div>
        {summary ? (
          <MetricCards summary={summary} />
        ) : (
          <div className="vp-dashboard-empty" role="status">Grid conditions are loading.</div>
        )}
      </section>

      <section className="vp-dashboard-section" aria-labelledby="dashboard-workspaces-title">
        <div className="vp-dashboard-section-heading">
          <div>
            <h3 id="dashboard-workspaces-title">Explore a workspace</h3>
            <p>Each area focuses on one part of grid operation and planning.</p>
          </div>
        </div>
        <div className="vp-dashboard-links">
          {WORKSPACE_LINKS.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                type="button"
                className="vp-dashboard-link"
                onClick={() => onNavigate(item.id)}
              >
                <Icon size={19} aria-hidden="true" />
                <span className="vp-dashboard-link-copy">
                  <strong>{item.title}</strong>
                  <small>{item.description}</small>
                </span>
                <ArrowRight className="vp-dashboard-link-arrow" size={17} aria-hidden="true" />
              </button>
            );
          })}
        </div>
      </section>
    </div>
  );
}
