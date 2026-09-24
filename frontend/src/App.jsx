import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import DateRangePicker from './components/DateRangePicker';
import MetricCards from './components/MetricCards';
import NetworkTopologyCanvas from './components/NetworkTopologyCanvas';
import TimeSeriesChart from './components/TimeSeriesChart';
import TelemetryTables from './components/TelemetryTables';
import ForecastPanel from './components/ForecastPanel';

const API_BASE = 'http://127.0.0.1:8000';

export default function App() {
  const [apiOnline, setApiOnline] = useState(false);
  const [summary, setSummary] = useState(null);
  const [topology, setTopology] = useState(null);
  const [solarLoadData, setSolarLoadData] = useState([]);
  const [activeTab, setActiveTab] = useState('all'); // 'all' | 'grid' | 'forecast'
  
  const [startDate, setStartDate] = useState('2023-01-01');
  const [endDate, setEndDate] = useState('2023-01-31');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch initial grid summary and network topology
  useEffect(() => {
    const fetchGridInfo = async () => {
      try {
        const resHealth = await fetch(`${API_BASE}/api/health`);
        if (resHealth.ok) {
          setApiOnline(true);
        }

        const resSum = await fetch(`${API_BASE}/api/grid/summary`);
        if (resSum.ok) {
          const sumData = await resSum.json();
          setSummary(sumData);
        }

        const resTop = await fetch(`${API_BASE}/api/grid/topology`);
        if (resTop.ok) {
          const topData = await resTop.json();
          setTopology(topData);
        }
      } catch (err) {
        console.error('API Error:', err);
        setApiOnline(false);
      }
    };

    fetchGridInfo();
  }, []);

  // Fetch time series solar + load dataset for given date range
  const fetchTimeSeries = async (sDate, eDate) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/data/solar-load?start_date=${sDate}&end_date=${eDate}`);
      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }
      const data = await res.json();
      setSolarLoadData(data);
      setStartDate(sDate);
      setEndDate(eDate);
      setApiOnline(true);
    } catch (err) {
      console.error('Fetch error:', err);
      setError('Failed to load solar/demand data for selected date range.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTimeSeries(startDate, endDate);
  }, []);

  return (
    <div style={{ maxWidth: '1380px', margin: '0 auto', padding: '24px 20px' }}>
      
      {/* Header Bar */}
      <Header apiOnline={apiOnline} />

      {/* Main Navigation Tabs */}
      <div 
        style={{ 
          display: 'flex', 
          gap: '10px', 
          marginBottom: '20px', 
          backgroundColor: 'rgba(15, 23, 42, 0.65)', 
          padding: '6px', 
          borderRadius: '12px', 
          border: '1px solid rgba(255, 255, 255, 0.08)',
          width: 'fit-content'
        }}
      >
        <button
          onClick={() => setActiveTab('all')}
          style={{
            backgroundColor: activeTab === 'all' ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
            color: activeTab === 'all' ? '#38bdf8' : '#94a3b8',
            border: activeTab === 'all' ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid transparent',
            padding: '8px 18px',
            borderRadius: '8px',
            fontWeight: 600,
            fontSize: '0.85rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            transition: 'all 0.2s'
          }}
        >
          🌐 Full Digital Twin View
        </button>
        <button
          onClick={() => setActiveTab('grid')}
          style={{
            backgroundColor: activeTab === 'grid' ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
            color: activeTab === 'grid' ? '#38bdf8' : '#94a3b8',
            border: activeTab === 'grid' ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid transparent',
            padding: '8px 18px',
            borderRadius: '8px',
            fontWeight: 600,
            fontSize: '0.85rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            transition: 'all 0.2s'
          }}
        >
          ⚡ Grid Topology & Power Flow
        </button>
        <button
          onClick={() => setActiveTab('forecast')}
          style={{
            backgroundColor: activeTab === 'forecast' ? 'rgba(168, 85, 247, 0.2)' : 'transparent',
            color: activeTab === 'forecast' ? '#c084fc' : '#94a3b8',
            border: activeTab === 'forecast' ? '1px solid rgba(168, 85, 247, 0.4)' : '1px solid transparent',
            padding: '8px 18px',
            borderRadius: '8px',
            fontWeight: 600,
            fontSize: '0.85rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            transition: 'all 0.2s'
          }}
        >
          🧠 AI Forecaster (Checkpoint 2)
        </button>
      </div>

      {/* Date Range Selection Bar (Grid & Time-Series Views) */}
      {activeTab !== 'forecast' && (
        <DateRangePicker
          startDate={startDate}
          endDate={endDate}
          onApply={(s, e) => fetchTimeSeries(s, e)}
          loading={loading}
        />
      )}

      {error && (
        <div 
          style={{ 
            backgroundColor: 'rgba(239, 68, 68, 0.15)', 
            border: '1px solid rgba(239, 68, 68, 0.3)', 
            color: '#f87171', 
            padding: '12px 16px', 
            borderRadius: '8px', 
            marginBottom: '20px',
            fontSize: '0.88rem'
          }}
        >
          ⚠️ {error}
        </div>
      )}

      {/* Metric Cards Summary */}
      {activeTab !== 'forecast' && <MetricCards summary={summary} />}

      {/* Interactive Topology Diagram */}
      {(activeTab === 'all' || activeTab === 'grid') && (
        <NetworkTopologyCanvas topology={topology} />
      )}

      {/* Solar Generation vs Demand Chart */}
      {(activeTab === 'all' || activeTab === 'grid') && (
        <TimeSeriesChart
          data={solarLoadData}
          startDate={startDate}
          endDate={endDate}
        />
      )}

      {/* Checkpoint 2: AI Forecasting Panel */}
      {(activeTab === 'all' || activeTab === 'forecast') && (
        <ForecastPanel />
      )}

      {/* Grid Elements Breakdown Tables */}
      {(activeTab === 'all' || activeTab === 'grid') && (
        <TelemetryTables topology={topology} />
      )}

      {/* Footer Banner */}
      <footer 
        className="glass-panel" 
        style={{ 
          padding: '16px 20px', 
          textAlign: 'center', 
          fontSize: '0.85rem', 
          color: '#94a3b8',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          marginTop: '16px'
        }}
      >
        <div>
          ⚡ <strong>Renewable Grid Digital Twin</strong> — React.js SPA & FastAPI Backend
        </div>
        <div style={{ fontSize: '0.78rem', color: '#64748b' }}>
          Checkpoint 2: LightGBM Solar & Load Forecasting + Chronological Holdout Benchmark Verified.
        </div>
      </footer>

    </div>
  );
}
