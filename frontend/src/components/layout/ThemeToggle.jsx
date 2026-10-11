import React from 'react';
import { Sun, Moon, Monitor } from 'lucide-react';
import { useTheme } from '../../theme/ThemeProvider';

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <div
      aria-label="Theme selection"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        backgroundColor: 'var(--surface-raised)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--r-pill)',
        padding: '3px',
        gap: '2px',
      }}
    >
      <button
        type="button"
        onClick={() => setTheme('light')}
        title="Light theme"
        aria-label="Set light theme"
        aria-pressed={theme === 'light'}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '26px',
          height: '26px',
          borderRadius: '999px',
          border: 'none',
          backgroundColor: theme === 'light' ? 'var(--surface)' : 'transparent',
          color: theme === 'light' ? 'var(--accent)' : 'var(--text-faint)',
          cursor: 'pointer',
          transition: 'all 0.15s ease',
          boxShadow: theme === 'light' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
        }}
      >
        <Sun size={14} />
      </button>

      <button
        type="button"
        onClick={() => setTheme('dark')}
        title="Dark theme"
        aria-label="Set dark theme"
        aria-pressed={theme === 'dark'}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '26px',
          height: '26px',
          borderRadius: '999px',
          border: 'none',
          backgroundColor: theme === 'dark' ? 'var(--surface)' : 'transparent',
          color: theme === 'dark' ? 'var(--accent)' : 'var(--text-faint)',
          cursor: 'pointer',
          transition: 'all 0.15s ease',
          boxShadow: theme === 'dark' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
        }}
      >
        <Moon size={14} />
      </button>

      <button
        type="button"
        onClick={() => setTheme('system')}
        title="System preference"
        aria-label="Set system theme"
        aria-pressed={theme === 'system'}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '26px',
          height: '26px',
          borderRadius: '999px',
          border: 'none',
          backgroundColor: theme === 'system' ? 'var(--surface)' : 'transparent',
          color: theme === 'system' ? 'var(--accent)' : 'var(--text-faint)',
          cursor: 'pointer',
          transition: 'all 0.15s ease',
          boxShadow: theme === 'system' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
        }}
      >
        <Monitor size={14} />
      </button>
    </div>
  );
}
