import React, { useEffect, useRef, useState } from 'react';
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
import DashboardOverview from './components/layout/DashboardOverview';
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
  const gridDataRequested = useRef(false);
  const activeTabRef = useRef(activeTab);
  const gridSnapshotLoaded = useRef(false);
  const gridSnapshotLoading = useRef(false);

  const fetchGridSnapshot = async () => {
    if (gridSnapshotLoaded.current || gridSnapshotLoading.current) return;
    gridSnapshotLoading.current = true;
    try {
      const [summaryResponse, topologyResponse] = await Promise.all([
        fetch(`${API_BASE}/api/grid/summary`),
        fetch(`${API_BASE}/api/grid/topology`),
      ]);
      if (summaryResponse.ok) setSummary(await summaryResponse.json());
      if (topologyResponse.ok) setTopology(await topologyResponse.json());
      gridSnapshotLoaded.current = summaryResponse.ok && topologyResponse.ok;
    } catch (err) {
      console.error('Grid snapshot error:', err);
    } finally {
      gridSnapshotLoading.current = false;
    }
  };

  useEffect(() => {
    let interval;
    let isFetching = false;
    const fetchGridInfo = async () => {
      if (isFetching) return;
      isFetching = true;
      try {
        const healthResponse = await fetch(`${API_BASE}/api/health`);
        const online = healthResponse.ok;
        setApiOnline(online);
        if (online && (activeTabRef.current === 'grid' || activeTabRef.current === 'all')) {
          await fetchGridSnapshot();
        }
      } catch (err) {
        console.error('API Error:', err);
        setApiOnline(false);
      } finally {
        isFetching = false;
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

  const showGrid = activeTab === 'grid';

  useEffect(() => {
    activeTabRef.current = activeTab;
  }, [activeTab]);

  const handleSelectTab = (tab) => {
    setActiveTab(tab);
    if (tab === 'grid' || tab === 'all') {
      fetchGridSnapshot();
    }
    if (tab === 'grid' && !gridDataRequested.current) {
      gridDataRequested.current = true;
      fetchTimeSeries(startDate, endDate);
    }
  };

  return (
    <ThemeProvider>
      <AppShell
        activeTab={activeTab}
        onSelectTab={handleSelectTab}
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

        {activeTab === 'all' && (
          <DashboardOverview
            summary={summary}
            apiOnline={apiOnline}
            onNavigate={handleSelectTab}
          />
        )}
        {showGrid && <MetricCards summary={summary} />}
        {activeTab === 'showcase' && <ShowcasePanel />}
        {activeTab === 'surrogate' && <SurrogatePanel />}
        {activeTab === 'time_plan' && <TimePlanPanel />}
        {activeTab === 'engine' && <ViolationEnginePanel />}
        {activeTab === 'mpc' && <MpcControlPanel />}
        {showGrid && <NetworkTopologyCanvas topology={topology} />}
        {showGrid && <TimeSeriesChart data={solarLoadData} startDate={startDate} endDate={endDate} />}
        {activeTab === 'forecast' && <ForecastPanel />}
        {showGrid && <TelemetryTables topology={topology} />}
      </AppShell>

      {/* Floating Chatbot Assistant Widget */}
      <ChatWidget />
    </ThemeProvider>
  );
}