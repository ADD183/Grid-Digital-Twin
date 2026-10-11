import React, { useState } from 'react';
import {
  Trophy,
  Layers,
  Zap,
  TrendingUp,
  Sliders,
  Clock,
  Cpu,
  Brain,
  Menu,
  X,
} from 'lucide-react';
import ThemeToggle from './ThemeToggle';

const NAV_GROUPS = [
  {
    group: 'Overview',
    items: [
      { id: 'showcase', label: 'Daily story', icon: Trophy, tooltip: 'Full-day grid scenario and evidence' },
      { id: 'all', label: 'Dashboard', icon: Layers, tooltip: 'All available views' },
    ],
  },
  {
    group: 'Network',
    items: [
      { id: 'grid', label: 'Grid status', icon: Zap, tooltip: 'Network and power-flow detail' },
      { id: 'forecast', label: 'Forecasts', icon: TrendingUp, tooltip: 'Generation and demand forecast detail' },
    ],
  },
  {
    group: 'Planning',
    items: [
      { id: 'engine', label: 'Grid actions', icon: Sliders, tooltip: 'Action selection and constraint scenarios' },
      { id: 'time_plan', label: 'Plan over time', icon: Clock, tooltip: 'Multi-step control episode' },
      { id: 'mpc', label: 'Plan settings', icon: Cpu, tooltip: 'Predictive control settings and results' },
    ],
  },
  {
    group: 'Models',
    items: [
      { id: 'surrogate', label: 'Prediction quality', icon: Brain, tooltip: 'Model screening and evaluation detail' },
    ],
  },
];

const GRID_VIEW_SUMMARY = 'Check whether the network is operating normally and compare local generation with customer demand.';

export default function AppShell({
  activeTab,
  onSelectTab,
  apiOnline,
  children,
}) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Find active nav item title for top bar
  let activeTitle = 'VoltPredict Digital Twin';
  NAV_GROUPS.forEach((g) => {
    g.items.forEach((item) => {
      if (item.id === activeTab) {
        activeTitle = item.label;
      }
    });
  });

  const renderNavItems = () =>
    NAV_GROUPS.map((g) => (
      <div key={g.group} style={{ marginBottom: '20px' }}>
        <div
          style={{
            fontSize: '0.72rem',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            color: 'var(--text-faint)',
            padding: '0 12px 6px',
          }}
        >
          {g.group}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {g.items.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                type="button"
                title={item.tooltip}
                aria-current={isActive ? 'page' : undefined}
                onClick={() => {
                  onSelectTab(item.id);
                  setMobileMenuOpen(false);
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: 'var(--r-sm)',
                  border: 'none',
                  backgroundColor: isActive ? 'var(--accent-soft)' : 'transparent',
                  color: isActive ? 'var(--accent)' : 'var(--text-muted)',
                  fontSize: '0.86rem',
                  fontWeight: isActive ? 600 : 500,
                  cursor: 'pointer',
                  textAlign: 'left',
                  position: 'relative',
                  transition: 'all 0.15s ease',
                }}
              >
                {isActive && (
                  <div
                    style={{
                      position: 'absolute',
                      left: 0,
                      top: '6px',
                      bottom: '6px',
                      width: '3px',
                      borderRadius: '0 2px 2px 0',
                      backgroundColor: 'var(--accent)',
                    }}
                  />
                )}
                <Icon size={18} style={{ flexShrink: 0, color: isActive ? 'var(--accent)' : 'var(--text-faint)' }} />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {item.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    ));

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--bg)' }}>
      {/* Desktop Sidebar (>= 1024px) */}
      <aside
        className="desktop-sidebar"
        style={{
          width: '248px',
          flexShrink: 0,
          backgroundColor: 'var(--surface)',
          borderRight: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
          position: 'sticky',
          top: 0,
          height: '100vh',
          zIndex: 20,
        }}
      >
        {/* Brand Header */}
        <div
          style={{
            padding: '20px 16px',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              backgroundColor: 'var(--accent-solid)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              fontWeight: 700,
              fontSize: '1rem',
            }}
          >
            VP
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '1.05rem', color: 'var(--text)', lineHeight: 1.2 }}>
              VoltPredict
            </div>
            <div style={{ fontSize: '0.74rem', color: 'var(--text-faint)' }}>
              Grid operations workspace
            </div>
          </div>
        </div>

        {/* Grouped Navigation */}
        <nav style={{ flex: 1, padding: '16px 12px', overflowY: 'auto' }}>
          {renderNavItems()}
        </nav>

        {/* Sidebar Footer */}
        <div
          style={{
            padding: '14px 16px',
            borderTop: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: 'var(--surface-raised)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem' }}>
            <div
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '999px',
                backgroundColor: apiOnline ? 'var(--ok)' : 'var(--danger)',
              }}
            />
            <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>
              {apiOnline ? 'API Online' : 'Offline'}
            </span>
          </div>
          <ThemeToggle />
        </div>
      </aside>

      {/* Main Content Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Sticky Top Bar (56px) */}
        <header
          style={{
            height: '56px',
            backgroundColor: 'var(--surface)',
            borderBottom: '1px solid var(--border)',
            position: 'sticky',
            top: 0,
            zIndex: 15,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 24px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {/* Mobile Menu Button */}
            <button
              type="button"
              className="mobile-menu-btn"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Toggle navigation menu"
              style={{
                display: 'none',
                background: 'transparent',
                border: 'none',
                color: 'var(--text)',
                cursor: 'pointer',
                padding: '4px',
              }}
            >
              {mobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
            </button>

            <h1 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text)' }}>
              {activeTitle}
            </h1>
          </div>

          {/* Theme control remains in the top bar on smaller screens. */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div className="mobile-theme-toggle" style={{ display: 'none' }}>
              <ThemeToggle />
            </div>
          </div>
        </header>

        {/* View Container */}
        <main
          style={{
            flex: 1,
            padding: '24px',
            maxWidth: '1200px',
            width: '100%',
            margin: '0 auto',
          }}
        >
          {activeTab === 'grid' && <p className="vp-view-summary">{GRID_VIEW_SUMMARY}</p>}
          {children}
        </main>

        {/* Quiet Page Footer */}
        <footer
          style={{
            padding: '16px 24px',
            borderTop: '1px solid var(--border)',
            textAlign: 'center',
            fontSize: '0.8rem',
            color: 'var(--text-faint)',
          }}
        >
          VoltPredict · Grid operations workspace
        </footer>
      </div>

      {/* Mobile Slide-Over Drawer (< 1024px) */}
      {mobileMenuOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 50,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
          }}
          onClick={() => setMobileMenuOpen(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Primary navigation"
            style={{
              width: '280px',
              backgroundColor: 'var(--surface)',
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              padding: '16px',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '20px',
                paddingBottom: '12px',
                borderBottom: '1px solid var(--border)',
              }}
            >
              <div style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--text)' }}>
                VoltPredict
              </div>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)' }}
              >
                <X size={20} />
              </button>
            </div>
            <nav style={{ flex: 1, overflowY: 'auto' }}>{renderNavItems()}</nav>
            <div style={{ paddingTop: '12px', borderTop: '1px solid var(--border)' }}>
              <ThemeToggle />
            </div>
          </div>
        </div>
      )}

      {/* Responsive Layout CSS */}
      <style>{`
        @media (max-width: 1023px) {
          .desktop-sidebar {
            display: none !important;
          }
          .mobile-menu-btn {
            display: flex !important;
          }
          .mobile-theme-toggle {
            display: flex !important;
          }
          .header-chips {
            display: none !important;
          }
        }
      `}</style>
    </div>
  );
}
