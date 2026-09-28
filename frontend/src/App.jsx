import React, { useEffect, useState } from 'react';
import Header from './components/Header';
import DateRangePicker from './components/DateRangePicker';
import MetricCards from './components/MetricCards';
import NetworkTopologyCanvas from './components/NetworkTopologyCanvas';
import TimeSeriesChart from './components/TimeSeriesChart';
import TelemetryTables from './components/TelemetryTables';
import ForecastPanel from './components/ForecastPanel';
import ViolationEnginePanel from './components/ViolationEnginePanel';
import ChatWidget from './components/ChatWidget';
import { API_BASE } from './config';

export default function App() {
  const [apiOnline, setApiOnline] = useState(false);
  const [summary, setSummary] = useState(null);
  const [topology, setTopology] = useState(null);
  const [solarLoadData, setSolarLoadData] = useState([]);
  const [activeTab, setActiveTab] = useState('engine');
  const [startDate, setStartDate] = useState('2023-01-01');
  const [endDate, setEndDate] = useState('2023-01-31');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let interval;
    const fetchGridInfo = async () => {
      try {
        const healthResponse = await fetch(`${API_BASE}/api/health`);
        const online = healthResponse.ok;
        setApiOnline(online);
        if (online) {
          const [summaryResponse, topologyResponse] = await Promise.all([
            fetch(`${API_BASE}/api/grid/summary`),
            fetch(`${API_BASE}/api/grid/topology`),
          ]);
          if (summaryResponse.ok) setSummary(await summaryResponse.json());
          if (topologyResponse.ok) setTopology(await topologyResponse.json());
        }
      } catch (err) {
        console.error('API Error:', err);
        setApiOnline(false);
      }
    };

    fetchGridInfo();
    interval = setInterval(fetchGridInfo, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchTimeSeries = async (selectedStartDate, selectedEndDate) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/data/solar-load?start_date=${selectedStartDate}&end_date=${selectedEndDate}`);
      if (!response.ok) throw new Error(`Server returned ${response.status}`);
      const data = await response.json();
      setSolarLoadData(data);
      setStartDate(selectedStartDate);
      setEndDate(selectedEndDate);
      setApiOnline(true);
      setError(null);
    } catch (err) {
      console.error('Fetch error:', err);
      setError('Failed to load solar/demand data for selected date range (Check if backend API is online).');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTimeSeries(startDate, endDate);
  }, []);

  const showGrid = activeTab === 'all' || activeTab === 'grid';
  const tabs = [
    ['engine', '🛡️ Action Engine (Checkpoint 3)', '#f87171'],
    ['forecast', '🧠 AI Forecaster (Checkpoint 2)', '#c084fc'],
    ['grid', '⚡ Grid Topology & Power Flow (Checkpoint 1)', '#38bdf8'],
    ['all', '🌐 Full Digital Twin View', '#34d399'],
  ];

  return (
    <>
      <div style={{ maxWidth: '1380px', margin: '0 auto', padding: '24px 20px' }}>
        <Header apiOnline={apiOnline} />
        <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', backgroundColor: 'rgba(15, 23, 42, 0.75)', padding: '6px', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.08)', width: 'fit-content', maxWidth: '100%', flexWrap: 'wrap' }}>
          {tabs.map(([id, label, color]) => (
            <button key={id} onClick={() => setActiveTab(id)} style={{ backgroundColor: activeTab === id ? `${color}22` : 'transparent', color: activeTab === id ? color : '#94a3b8', border: activeTab === id ? `1px solid ${color}66` : '1px solid transparent', padding: '8px 14px', borderRadius: '8px', fontWeight: 600, fontSize: '0.82rem', cursor: 'pointer' }}>
              {label}
            </button>
          ))}
        </div>

        {showGrid && <DateRangePicker startDate={startDate} endDate={endDate} onApply={fetchTimeSeries} loading={loading} />}
        {error && (
          <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#f87171', padding: '12px 16px', borderRadius: '8px', marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
            <span>⚠️ {error}</span>
            <button
              onClick={() => fetchTimeSeries(startDate, endDate)}
              disabled={loading}
              style={{
                backgroundColor: 'rgba(239, 68, 68, 0.25)',
                color: '#ffffff',
                border: '1px solid rgba(239, 68, 68, 0.5)',
                padding: '6px 14px',
                borderRadius: '6px',
                fontWeight: 600,
                fontSize: '0.8rem',
                cursor: 'pointer'
              }}
            >
              🔄 {loading ? 'Retrying...' : 'Retry Load Data'}
            </button>
          </div>
        )}

        {showGrid && <MetricCards summary={summary} />}
        {(activeTab === 'all' || activeTab === 'engine') && <ViolationEnginePanel />}
        {showGrid && <NetworkTopologyCanvas topology={topology} />}
        {showGrid && <TimeSeriesChart data={solarLoadData} startDate={startDate} endDate={endDate} />}
        {(activeTab === 'all' || activeTab === 'forecast') && <ForecastPanel />}
        {showGrid && <TelemetryTables topology={topology} />}

        <footer className="glass-panel" style={{ padding: '16px 20px', textAlign: 'center', fontSize: '0.85rem', color: '#94a3b8', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', marginTop: '16px' }}>
          <div>⚡ <strong>VoltPredict</strong> — React.js SPA & FastAPI Backend</div>
          <div style={{ fontSize: '0.78rem', color: '#64748b' }}>Checkpoints 1, 2 & 3: Physics Grid • Chronological ML Forecaster • Propose-Verify-Repair Action Engine.</div>
        </footer>
      </div>

      {/* Floating Chatbot Assistant Widget */}
      <ChatWidget />
    </>
  );
}