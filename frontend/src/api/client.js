import { API_BASE } from '../config';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `Request failed with status ${response.status}`);
  }
  return payload;
}

export const update1Api = {
  getTelemetry: () => request('/api/update1/telemetry'),
  getForecast: () => request('/api/update1/forecast/horizon?steps=8'),
  getSurrogateStatus: () => request('/api/update1/surrogate/status'),
  trainSurrogate: (sampleCount = 32) => request('/api/update1/surrogate/train', {
    method: 'POST',
    body: JSON.stringify({ sample_count: sampleCount }),
  }),
  runMpc: (payload) => request('/api/update1/mpc/plan', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
  exportArtifacts: (sampleCount = 32) => request('/api/export-artifacts', {
    method: 'POST',
    body: JSON.stringify({ sample_count: sampleCount }),
  }),
};

export const controlApi = {
  getLimits: () => request('/api/control/limits'),
  getShowcaseEpisode: () => request('/api/control/episode/showcase'),
  runEpisode: (payload = {}) => request('/api/control/episode/run', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
  getAbBenchmark: () => request('/api/control/ab-test'),
  runScreenedEpisode: (payload = {}) => request('/api/control/episode/run-screened', {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
};

export const surrogateApi = {
  getStatus: () => request('/api/surrogate/status'),
  getEvaluationReport: () => request('/api/surrogate/evaluation'),
  trainEnsemble: () => request('/api/surrogate/train', { method: 'POST' }),
};