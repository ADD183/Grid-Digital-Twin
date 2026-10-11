import React, { useEffect, useState } from 'react';
import DateRangePicker from './components/DateRangePicker';
import MetricCards from './components/MetricCards';
import NetworkTopologyCanvas from './components/NetworkTopologyCanvas';
import TimeSeriesChart from './components/TimeSeriesChart';
import TelemetryTables from './components/TelemetryTables';
import ForecastPanel from './components/ForecastPanel';
import ViolationEnginePanel from './components/ViolationEnginePanel';
import MpcControlPanel from './components/MpcControlPanel';
import TimePlanPanel from './components/TimePlanPanel';
import SurrogatePanel from './components/SurrogatePanel';
import ShowcasePanel from './components/ShowcasePanel';
import ChatWidget from './components/ChatWidget';
import AppShell from './components/layout/AppShell';
import { ThemeProvider } from './theme/ThemeProvider';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { API_BASE } from './config';

export default function App() {
  const [apiOnline, setApiOnline] = useState(false);
  const [summary, setSummary] = useState(null);
  const [topology, setTopology] = useState(null);
  const [solarLoadData, setSolarLoadData] = useState([]);
  const [activeTab, setActiveTab] = useState('showcase');
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

  return (
    <ThemeProvider>
      <AppShell
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        apiOnline={apiOnline}
      >
        {showGrid && (
          <DateRangePicker
            startDate={startDate}
            endDate={endDate}
            onApply={fetchTimeSeries}
            loading={loading}
          />
        )}

        {error && (
          <div className="vp-alert" data-tone="danger" style={{ marginBottom: '20px', justifyContent: 'space-between', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle size={18} style={{ color: 'var(--danger)', flexShrink: 0 }} />
              <span>{error}</span>
            </div>
            <button
              type="button"
              className="vp-btn vp-btn-secondary"
              onClick={() => fetchTimeSeries(startDate, endDate)}
              disabled={loading}
              style={{ height: '32px', fontSize: '0.8rem' }}
            >
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
              <span>{loading ? 'Retrying...' : 'Retry Load Data'}</span>
            </button>
          </div>
        )}

        {showGrid && <MetricCards summary={summary} />}
        {(activeTab === 'all' || activeTab === 'showcase') && <ShowcasePanel />}
        {(activeTab === 'all' || activeTab === 'surrogate') && <SurrogatePanel />}
        {(activeTab === 'all' || activeTab === 'time_plan') && <TimePlanPanel />}
        {(activeTab === 'all' || activeTab === 'engine') && <ViolationEnginePanel />}
        {activeTab === 'mpc' && <MpcControlPanel />}
        {showGrid && <NetworkTopologyCanvas topology={topology} />}
        {showGrid && <TimeSeriesChart data={solarLoadData} startDate={startDate} endDate={endDate} />}
        {(activeTab === 'all' || activeTab === 'forecast') && <ForecastPanel />}
        {showGrid && <TelemetryTables topology={topology} />}
      </AppShell>

      {/* Floating Chatbot Assistant Widget */}
      <ChatWidget />
    </ThemeProvider>
  );
}