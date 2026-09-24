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

const API_BASE = 'http://127.0.0.1:8000';

export default function ForecastPanel() {
  const [metrics, setMetrics] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [activeSeries, setActiveSeries] = useState('solar'); // 'solar' | 'load'
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

  return (
    <div className="glass-panel" style={{ padding: '24px', marginBottom: '24px', position: 'relative' }}>
      
      {/* Header Section */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', marginBottom: '20px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h2 style={{ margin: 0, fontSize: '1.35rem', fontWeight: 600, color: '#f8fafc' }}>
              🧠 AI Generation & Load Forecasting (Checkpoint 2)
            </h2>
            <span 
              style={{ 
                backgroundColor: 'rgba(16, 185, 129, 0.15)', 
                color: '#34d399', 
                border: '1px solid rgba(52, 211, 153, 0.3)',
                padding: '3px 10px', 
                borderRadius: '12px', 
                fontSize: '0.75rem', 
                fontWeight: 600 
              }}
            >
              {metrics?.engine_used || 'LightGBM GBDT'}
            </span>
          </div>
          <p style={{ margin: '6px 0 0 0', fontSize: '0.85rem', color: '#94a3b8' }}>
            Lagged features (t-1, t-2, t-3, t-24) + cyclical calendar features evaluated on chronological holdout test set vs. naive persistence benchmark.
          </p>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          
          {/* Target Toggle */}
          <div style={{ display: 'flex', backgroundColor: 'rgba(15, 23, 42, 0.8)', padding: '3px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
            <button
              onClick={() => setActiveSeries('solar')}
              style={{
                backgroundColor: activeSeries === 'solar' ? '#38bdf8' : 'transparent',
                color: activeSeries === 'solar' ? '#0f172a' : '#94a3b8',
                fontWeight: activeSeries === 'solar' ? 600 : 400,
                border: 'none',
                padding: '6px 14px',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '0.82rem',
                transition: 'all 0.2s ease'
              }}
            >
              ☀️ Solar PV (p.u.)
            </button>
            <button
              onClick={() => setActiveSeries('load')}
              style={{
                backgroundColor: activeSeries === 'load' ? '#a855f7' : 'transparent',
                color: activeSeries === 'load' ? '#ffffff' : '#94a3b8',
                fontWeight: activeSeries === 'load' ? 600 : 400,
                border: 'none',
                padding: '6px 14px',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '0.82rem',
                transition: 'all 0.2s ease'
              }}
            >
              ⚡ Grid Load (p.u.)
            </button>
          </div>

          {/* Window Length */}
          <select
            value={windowHours}
            onChange={(e) => setWindowHours(Number(e.target.value))}
            style={{
              backgroundColor: 'rgba(30, 41, 59, 0.8)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              color: '#f8fafc',
              padding: '6px 12px',
              borderRadius: '6px',
              fontSize: '0.82rem',
              cursor: 'pointer',
              outline: 'none'
            }}
          >
            <option value={48}>Last 48 Hours</option>
            <option value={168}>Last 7 Days (168h)</option>
            <option value={336}>Last 14 Days (336h)</option>
          </select>

          {/* Retrain Button */}
          <button
            onClick={handleRetrain}
            disabled={retraining}
            style={{
              backgroundColor: retraining ? 'rgba(56, 189, 248, 0.2)' : 'rgba(56, 189, 248, 0.15)',
              color: '#38bdf8',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              padding: '6px 16px',
              borderRadius: '6px',
              fontSize: '0.82rem',
              fontWeight: 600,
              cursor: retraining ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.2s'
            }}
          >
            {retraining ? '⏳ Retraining...' : '🔄 Retrain Models'}
          </button>
        </div>
      </div>

      {statusMsg && (
        <div 
          style={{
            backgroundColor: 'rgba(56, 189, 248, 0.12)',
            border: '1px solid rgba(56, 189, 248, 0.25)',
            color: '#38bdf8',
            padding: '8px 14px',
            borderRadius: '6px',
            marginBottom: '16px',
            fontSize: '0.82rem'
          }}
        >
          ℹ️ {statusMsg}
        </div>
      )}

      {error && (
        <div style={{
          backgroundColor: 'rgba(239, 68, 68, 0.15)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          color: '#f87171',
          padding: '8px 14px',
          borderRadius: '6px',
          marginBottom: '16px',
          fontSize: '0.82rem'
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* Benchmark Metric Cards */}
      {currentMetrics && (
        <div 
          style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', 
            gap: '14px', 
            marginBottom: '20px' 
          }}
        >
          {/* MAE Comparison */}
          <div 
            style={{ 
              backgroundColor: 'rgba(15, 23, 42, 0.65)', 
              border: '1px solid rgba(255, 255, 255, 0.08)', 
              borderRadius: '10px', 
              padding: '14px 18px' 
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.78rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Mean Absolute Error (MAE)
              </span>
              <span 
                style={{ 
                  backgroundColor: 'rgba(16, 185, 129, 0.2)', 
                  color: '#34d399', 
                  fontSize: '0.75rem', 
                  fontWeight: 600, 
                  padding: '2px 8px', 
                  borderRadius: '10px' 
                }}
              >
                -{currentMetrics.mae_improvement_pct}% vs Naive
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', marginTop: '8px' }}>
              <span style={{ fontSize: '1.45rem', fontWeight: 700, color: '#f8fafc' }}>
                {currentMetrics.model_metrics.mae} <span style={{ fontSize: '0.85rem', color: '#64748b' }}>p.u.</span>
              </span>
              <span style={{ fontSize: '0.85rem', color: '#64748b' }}>
                Naive: <strong style={{ color: '#f59e0b' }}>{currentMetrics.naive_metrics.mae}</strong>
              </span>
            </div>
          </div>

          {/* RMSE Comparison */}
          <div 
            style={{ 
              backgroundColor: 'rgba(15, 23, 42, 0.65)', 
              border: '1px solid rgba(255, 255, 255, 0.08)', 
              borderRadius: '10px', 
              padding: '14px 18px' 
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.78rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Root Mean Squared Error (RMSE)
              </span>
              <span 
                style={{ 
                  backgroundColor: 'rgba(16, 185, 129, 0.2)', 
                  color: '#34d399', 
                  fontSize: '0.75rem', 
                  fontWeight: 600, 
                  padding: '2px 8px', 
                  borderRadius: '10px' 
                }}
              >
                -{currentMetrics.rmse_improvement_pct}% vs Naive
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', marginTop: '8px' }}>
              <span style={{ fontSize: '1.45rem', fontWeight: 700, color: '#f8fafc' }}>
                {currentMetrics.model_metrics.rmse} <span style={{ fontSize: '0.85rem', color: '#64748b' }}>p.u.</span>
              </span>
              <span style={{ fontSize: '0.85rem', color: '#64748b' }}>
                Naive: <strong style={{ color: '#f59e0b' }}>{currentMetrics.naive_metrics.rmse}</strong>
              </span>
            </div>
          </div>

          {/* R-Squared Metric */}
          <div 
            style={{ 
              backgroundColor: 'rgba(15, 23, 42, 0.65)', 
              border: '1px solid rgba(255, 255, 255, 0.08)', 
              borderRadius: '10px', 
              padding: '14px 18px' 
            }}
          >
            <span style={{ fontSize: '0.78rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Fit Quality (R² Score)
            </span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', marginTop: '8px' }}>
              <span style={{ fontSize: '1.45rem', fontWeight: 700, color: '#38bdf8' }}>
                {(currentMetrics.model_metrics.r2 * 100).toFixed(1)}%
              </span>
              <span style={{ fontSize: '0.82rem', color: '#64748b' }}>
                (Naive: {(currentMetrics.naive_metrics.r2 * 100).toFixed(1)}%)
              </span>
            </div>
          </div>

          {/* Dataset Info */}
          <div 
            style={{ 
              backgroundColor: 'rgba(15, 23, 42, 0.65)', 
              border: '1px solid rgba(255, 255, 255, 0.08)', 
              borderRadius: '10px', 
              padding: '14px 18px' 
            }}
          >
            <span style={{ fontSize: '0.78rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Chronological Holdout Split
            </span>
            <div style={{ marginTop: '8px', fontSize: '0.85rem', color: '#f8fafc' }}>
              Train: <strong>{currentMetrics.train_samples}h</strong> | Test: <strong>{currentMetrics.test_samples}h</strong>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '4px' }}>
              Holdout window: {currentMetrics.test_start?.substring(0, 10)} to {currentMetrics.test_end?.substring(0, 10)}
            </div>
          </div>
        </div>
      )}

      {/* Chart Visualization */}
      <div style={{ height: '360px', width: '100%', marginTop: '10px' }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8' }}>
            Loading forecasting comparison data...
          </div>
        ) : chartData.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8' }}>
            No forecast evaluation data is available.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.07)" />
              <XAxis 
                dataKey="timestamp" 
                stroke="#64748b" 
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                tickFormatter={(val) => val.substring(5, 16)}
              />
              <YAxis 
                stroke="#64748b" 
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                domain={[0, 'auto']}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(15, 23, 42, 0.95)',
                  borderColor: 'rgba(255, 255, 255, 0.15)',
                  borderRadius: '8px',
                  color: '#f8fafc',
                  fontSize: '0.85rem',
                  boxShadow: '0 8px 32px rgba(0,0,0,0.5)'
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
                    stroke="#38bdf8"
                    strokeWidth={2.5}
                    dot={false}
                    activeDot={{ r: 6 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="solar_pred"
                    name="LightGBM ML Forecast"
                    stroke="#34d399"
                    strokeWidth={2}
                    dot={false}
                    strokeDasharray="4 2"
                  />
                  <Line
                    type="monotone"
                    dataKey="solar_naive"
                    name="Naive Seasonal Baseline (t-24)"
                    stroke="#f59e0b"
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
                    stroke="#c084fc"
                    strokeWidth={2.5}
                    dot={false}
                    activeDot={{ r: 6 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="load_pred"
                    name="LightGBM ML Forecast"
                    stroke="#34d399"
                    strokeWidth={2}
                    dot={false}
                    strokeDasharray="4 2"
                  />
                  <Line
                    type="monotone"
                    dataKey="load_naive"
                    name="Naive Seasonal Baseline (t-24)"
                    stroke="#f59e0b"
                    strokeWidth={1.5}
                    dot={false}
                    strokeDasharray="3 3"
                  />
                </>
              )}

              <Brush 
                dataKey="timestamp" 
                height={28} 
                stroke="#38bdf8" 
                fill="rgba(15, 23, 42, 0.8)"
                tickFormatter={(val) => val.substring(5, 10)}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

    </div>
  );
}
