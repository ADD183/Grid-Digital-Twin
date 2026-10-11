import React, { useState, useEffect } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Brush
} from 'recharts';
import { RefreshCw, Brain } from 'lucide-react';
import { API_BASE } from '../config';

export default function ForecastPanel() {
  const [metrics, setMetrics] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [activeSeries, setActiveSeries] = useState('solar'); // 'solar' | 'load'
  const [showIntervals, setShowIntervals] = useState(true);
  const [windowHours, setWindowHours] = useState(168); // 48, 168, 336
  const [loading, setLoading] = useState(true);
  const [retraining, setRetraining] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');
  const [error, setError] = useState('');

  const fetchForecastData = async (hours = windowHours) => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/api/forecast/chart?points=${hours}`);
      if (!res.ok) {
        throw new Error(`Forecast service returned ${res.status}`);
      }
      const data = await res.json();
      if (!Array.isArray(data.points) || data.points.length === 0) {
        throw new Error('The forecast service returned no evaluation points.');
      }
      setMetrics(data.summary);
      setChartData(data.points);
    } catch (err) {
      console.error('Failed to fetch forecast chart data:', err);
      setError('Forecast data is unavailable. Check that the FastAPI backend is running and models can be loaded.');
      setChartData([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchForecastData(windowHours);
  }, [windowHours]);

  const handleRetrain = async () => {
    setRetraining(true);
    setStatusMsg('Retraining gradient boosting models with chronological split...');
    try {
      const res = await fetch(`${API_BASE}/api/forecast/train`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setMetrics(data.summary);
        setStatusMsg('Models retrained and serialized successfully!');
        await fetchForecastData(windowHours);
        setTimeout(() => setStatusMsg(''), 4000);
      } else {
        setStatusMsg(`Retraining failed (server returned ${res.status}).`);
      }
    } catch (err) {
      console.error('Retrain error:', err);
      setStatusMsg('Error communicating with backend API.');
    } finally {
      setRetraining(false);
    }
  };

  const currentMetrics = metrics ? metrics[activeSeries] : null;

  const actualColor = activeSeries === 'solar' ? 'var(--c-solar)' : 'var(--c-load)';
  const forecastColor = 'var(--c-forecast)';
  const baselineColor = 'var(--c-baseline)';

  return (
    <div className="vp-card" style={{ marginBottom: '24px' }}>
      
      {/* Header Section */}
      <div className="vp-page-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h2 className="vp-page-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Brain size={22} color="var(--accent)" />
              <span>AI Generation & Load Forecasting</span>
            </h2>
            <span className="vp-badge" data-tone="ok">
              {metrics?.engine_used || 'LightGBM GBDT'}
            </span>
          </div>
          <p className="vp-page-desc">
            Lagged features (t-1, t-2, t-3, t-24) + cyclical calendar features evaluated on chronological holdout test set vs. naive persistence benchmark.
          </p>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          
          {/* Target Toggle */}
          <div className="vp-segmented">
            <button
              onClick={() => setActiveSeries('solar')}
              className={`vp-segmented-btn ${activeSeries === 'solar' ? 'active' : ''}`}
              aria-selected={activeSeries === 'solar'}
            >
              Solar PV (p.u.)
            </button>
            <button
              onClick={() => setActiveSeries('load')}
              className={`vp-segmented-btn ${activeSeries === 'load' ? 'active' : ''}`}
              aria-selected={activeSeries === 'load'}
            >
              Grid Load (p.u.)
            </button>
          </div>

          {/* Window Length Select */}
          <select
            value={windowHours}
            onChange={(e) => setWindowHours(Number(e.target.value))}
            style={{
              backgroundColor: 'var(--surface-raised)',
              border: '1px solid var(--border)',
              color: 'var(--text)',
              padding: '6px 12px',
              borderRadius: 'var(--r-sm)',
              fontSize: '0.82rem',
              outline: 'none',
              cursor: 'pointer'
            }}
          >
            <option value={48}>Last 48 Hours</option>
            <option value={168}>Last 7 Days (168h)</option>
            <option value={336}>Last 14 Days (336h)</option>
          </select>

          {/* 90% Confidence Interval Toggle */}
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', color: 'var(--text-muted)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showIntervals}
              onChange={(e) => setShowIntervals(e.target.checked)}
              style={{ accentColor: 'var(--accent)', cursor: 'pointer' }}
            />
            <span>90% Confidence Interval</span>
          </label>

          {/* Retrain Button */}
          <button
            onClick={handleRetrain}
            disabled={retraining}
            className="vp-btn vp-btn-primary"
          >
            <RefreshCw size={15} className={retraining ? 'animated-spin' : ''} />
            <span>{retraining ? 'Retraining...' : 'Retrain Models'}</span>
          </button>
        </div>
      </div>

      {statusMsg && (
        <div className="vp-alert" data-tone="info" style={{ marginBottom: '16px' }}>
          <span>{statusMsg}</span>
        </div>
      )}

      {error && (
        <div className="vp-alert" data-tone="danger" style={{ marginBottom: '16px' }}>
          <span>{error}</span>
        </div>
      )}

      {/* Benchmark Metric Cards */}
      {currentMetrics && (
        <div 
          style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', 
            gap: '14px', 
            marginBottom: '20px' 
          }}
        >
          {/* MAE Comparison */}
          <div className="vp-kpi-tile" data-tone="ok">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="vp-kpi-label">Mean Absolute Error (MAE)</span>
              <span className="vp-badge" data-tone="ok">
                -{currentMetrics.mae_improvement_pct}% vs Naive
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', marginTop: '6px' }}>
              <span className="vp-kpi-value">
                {currentMetrics.model_metrics.mae} <span style={{ fontSize: '0.85rem', color: 'var(--text-faint)' }}>p.u.</span>
              </span>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Naive: <strong className="tabular-nums" style={{ color: 'var(--warn)' }}>{currentMetrics.naive_metrics.mae}</strong>
              </span>
            </div>
          </div>

          {/* RMSE Comparison */}
          <div className="vp-kpi-tile" data-tone="ok">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="vp-kpi-label">Root Mean Squared Error (RMSE)</span>
              <span className="vp-badge" data-tone="ok">
                -{currentMetrics.rmse_improvement_pct}% vs Naive
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', marginTop: '6px' }}>
              <span className="vp-kpi-value">
                {currentMetrics.model_metrics.rmse} <span style={{ fontSize: '0.85rem', color: 'var(--text-faint)' }}>p.u.</span>
              </span>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Naive: <strong className="tabular-nums" style={{ color: 'var(--warn)' }}>{currentMetrics.naive_metrics.rmse}</strong>
              </span>
            </div>
          </div>

          {/* R-Squared Metric */}
          <div className="vp-kpi-tile" data-tone="info">
            <span className="vp-kpi-label">Fit Quality (R² Score)</span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', marginTop: '6px' }}>
              <span className="vp-kpi-value" style={{ color: 'var(--accent)' }}>
                {(currentMetrics.model_metrics.r2 * 100).toFixed(1)}%
              </span>
              <span style={{ fontSize: '0.82rem', color: 'var(--text-faint)' }}>
                (Naive: {(currentMetrics.naive_metrics.r2 * 100).toFixed(1)}%)
              </span>
            </div>
          </div>

          {/* Dataset Info */}
          <div className="vp-kpi-tile" data-tone="info">
            <span className="vp-kpi-label">Chronological Holdout Split</span>
            <div style={{ marginTop: '6px', fontSize: '0.9rem', color: 'var(--text)' }}>
              Train: <strong className="tabular-nums">{currentMetrics.train_samples}h</strong> | Test: <strong className="tabular-nums">{currentMetrics.test_samples}h</strong>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-faint)', marginTop: '4px' }}>
              Holdout: {currentMetrics.test_start?.substring(0, 10)} to {currentMetrics.test_end?.substring(0, 10)}
            </div>
          </div>
        </div>
      )}

      {/* Chart Visualization */}
      <div style={{ height: '360px', width: '100%', marginTop: '10px' }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
            Loading forecasting comparison data...
          </div>
        ) : chartData.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
            No forecast evaluation data is available.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis 
                dataKey="timestamp" 
                stroke="var(--text-faint)" 
                tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                tickFormatter={(val) => val.substring(5, 16)}
              />
              <YAxis 
                stroke="var(--text-faint)" 
                tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                domain={[0, 'auto']}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--surface-raised)',
                  borderColor: 'var(--border-strong)',
                  borderRadius: 'var(--r-sm)',
                  color: 'var(--text)',
                  fontSize: '0.85rem',
                  boxShadow: 'var(--shadow-card)'
                }}
              />
              <Legend 
                verticalAlign="top" 
                height={36}
                wrapperStyle={{ fontSize: '0.85rem', paddingBottom: '10px' }}
              />

              {activeSeries === 'solar' ? (
                <>
                  <Line
                    type="monotone"
                    dataKey="solar_actual"
                    name="Actual Solar (p.u.)"
                    stroke={actualColor}
                    strokeWidth={2.5}
                    dot={false}
                    activeDot={{ r: 6 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="solar_pred"
                    name="LightGBM ML Forecast"
                    stroke={forecastColor}
                    strokeWidth={2}
                    dot={false}
                    strokeDasharray="4 2"
                  />
                  {showIntervals && (
                    <>
                      <Line
                        type="monotone"
                        dataKey="solar_upper"
                        name="90% Upper Bound (p.u.)"
                        stroke={forecastColor}
                        strokeWidth={1.2}
                        strokeDasharray="3 3"
                        dot={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="solar_lower"
                        name="90% Lower Bound (p.u.)"
                        stroke={forecastColor}
                        strokeWidth={1.2}
                        strokeDasharray="3 3"
                        dot={false}
                      />
                    </>
                  )}
                  <Line
                    type="monotone"
                    dataKey="solar_naive"
                    name="Naive Seasonal Baseline (t-24)"
                    stroke={baselineColor}
                    strokeWidth={1.5}
                    dot={false}
                    strokeDasharray="3 3"
                  />
                </>
              ) : (
                <>
                  <Line
                    type="monotone"
                    dataKey="load_actual"
                    name="Actual Load Demand (p.u.)"
                    stroke={actualColor}
                    strokeWidth={2.5}
                    dot={false}
                    activeDot={{ r: 6 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="load_pred"
                    name="LightGBM ML Forecast"
                    stroke={forecastColor}
                    strokeWidth={2}
                    dot={false}
                    strokeDasharray="4 2"
                  />
                  {showIntervals && (
                    <>
                      <Line
                        type="monotone"
                        dataKey="load_upper"
                        name="90% Upper Bound (p.u.)"
                        stroke={forecastColor}
                        strokeWidth={1.2}
                        strokeDasharray="3 3"
                        dot={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="load_lower"
                        name="90% Lower Bound (p.u.)"
                        stroke={forecastColor}
                        strokeWidth={1.2}
                        strokeDasharray="3 3"
                        dot={false}
                      />
                    </>
                  )}
                  <Line
                    type="monotone"
                    dataKey="load_naive"
                    name="Naive Seasonal Baseline (t-24)"
                    stroke={baselineColor}
                    strokeWidth={1.5}
                    dot={false}
                    strokeDasharray="3 3"
                  />
                </>
              )}

              <Brush 
                dataKey="timestamp" 
                height={28} 
                stroke="var(--accent)" 
                fill="var(--surface-raised)"
                tickFormatter={(val) => val.substring(5, 10)}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

    </div>
  );
}

