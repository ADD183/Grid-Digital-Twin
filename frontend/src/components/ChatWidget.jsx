import React, { useState, useRef, useEffect } from 'react';
import { MessageCircle, X, Send, Bot, Sparkles, ChevronDown, ChevronRight, CheckCircle2, AlertTriangle } from 'lucide-react';
import './ChatWidget.css';
import { API_BASE } from '../config';

const MIN_VISIBLE = 60;

const EVIDENCE_LABELS = {
  bus_count: 'Grid buses',
  der_count: 'Distributed energy resources',
  sgen_count: 'Generators',
  storage_count: 'Storage units',
  vm_pu_min: 'Minimum voltage',
  vm_pu_max: 'Maximum voltage',
  max_vm_pu: 'Maximum voltage',
  max_line_loading_percent: 'Maximum line loading',
  converged: 'Power-flow calculation completed',
  has_violations: 'Active grid violations',
  total_violations: 'Total active violations',
  voltage_violations: 'Voltage violations',
  loading_violations: 'Line loading violations',
  trafo_violations: 'Transformer violations',
  all_violations: 'All active violations',
  voltage_violation_count: 'Voltage violation count',
  loading_violation_count: 'Line loading violation count',
  trafo_violation_count: 'Transformer violation count',
  min_vm_pu: 'Minimum voltage',
  max_vm_pu: 'Maximum voltage',
  max_voltage_deviation: 'Maximum voltage deviation',
  max_loading_margin: 'Maximum loading margin',
  worst_voltage_bus: 'Bus with worst voltage',
  worst_loading_line: 'Line with highest loading',
  fully_resolved: 'Fully resolved',
  status: 'Scenario status',
  scenario_id: 'Scenario',
  explanation: 'Result details',
  error: 'Data availability',
};

const evidenceLabel = (key) => EVIDENCE_LABELS[key] || key
  .replace(/_/g, ' ')
  .replace(/\b\w/g, (letter) => letter.toUpperCase());

function getEvidenceRows(evidence, parentLabel = '') {
  if (Array.isArray(evidence)) {
    if (evidence.length === 0) return [{ label: parentLabel, value: 'None' }];
    return evidence.flatMap((item, index) => getEvidenceRows(item, `${parentLabel} - Item ${index + 1}`));
  }

  if (evidence && typeof evidence === 'object') {
    return Object.entries(evidence).flatMap(([key, value]) => {
      const label = [parentLabel, evidenceLabel(key)].filter(Boolean).join(' · ');
      return getEvidenceRows(value, label);
    });
  }

  let value = evidence;
  if (value === null || value === undefined || value === 'N/A') value = 'Not available';
  else if (typeof value === 'boolean') value = value ? 'Yes' : 'No';
  else if (/(minimum|maximum) voltage$/i.test(parentLabel) && typeof value === 'number') value = `${value} p.u.`;
  else if (/maximum line loading$/i.test(parentLabel) && typeof value === 'number') value = `${value}%`;

  return [{ label: parentLabel, value: String(value) }];
}

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 480);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: 'assistant',
      text: 'Hello! I am your Digital Grid Assistant. Ask me about grid safety, active violations, line loading, scenario results, or forecasts.',
      evidence: null,
      showEvidence: false,
    },
  ]);

  const messagesEndRef = useRef(null);
  const panelRef = useRef(null);
  const dragOffsetRef = useRef(null);

  const clampPosition = (x, y, panelWidth) => ({
    x: Math.max(0, Math.min(x, window.innerWidth - MIN_VISIBLE)),
    y: Math.max(0, Math.min(y, window.innerHeight - MIN_VISIBLE)),
  });

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 480);
      if (position && panelRef.current && window.innerWidth >= 480) {
        const { width } = panelRef.current.getBoundingClientRect();
        setPosition((current) => current && clampPosition(current.x, current.y, width));
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [position]);

  const startDragging = (event) => {
    if (isMobile || event.button !== 0 || event.target.closest('button')) return;

    const bounds = panelRef.current.getBoundingClientRect();
    const nextPosition = clampPosition(bounds.left, bounds.top, bounds.width);
    dragOffsetRef.current = {
      x: event.clientX - bounds.left,
      y: event.clientY - bounds.top,
    };
    setPosition(nextPosition);
    setIsDragging(true);
    event.currentTarget.setPointerCapture(event.pointerId);
    event.preventDefault();
  };

  const dragPanel = (event) => {
    if (!isDragging || !dragOffsetRef.current || !panelRef.current) return;
    const { width } = panelRef.current.getBoundingClientRect();
    setPosition(clampPosition(
      event.clientX - dragOffsetRef.current.x,
      event.clientY - dragOffsetRef.current.y,
      width
    ));
  };

  const stopDragging = () => {
    dragOffsetRef.current = null;
    setIsDragging(false);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen, loading]);

  const sendMessage = async (textToSend) => {
    const query = textToSend || input;
    if (!query.trim() || loading) return;

    const userMsg = {
      id: Date.now(),
      sender: 'user',
      text: query,
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInput('');
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: query }),
      });

      if (!response.ok) {
        throw new Error(`Server returned status ${response.status}`);
      }

      const data = await response.json();
      const assistantMsg = {
        id: Date.now() + 1,
        sender: 'assistant',
        text: data.reply || 'No response generated.',
        evidence: data.evidence && Object.keys(data.evidence).length > 0 ? data.evidence : null,
        showEvidence: false,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      console.error('Chat API Error:', err);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: 'assistant',
          text: `⚠️ Error connecting to chatbot backend: ${err.message}`,
          evidence: null,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const toggleEvidence = (id) => {
    setMessages((prev) =>
      prev.map((msg) => (msg.id === id ? { ...msg, showEvidence: !msg.showEvidence } : msg))
    );
  };

  const suggestions = [
    'Is the grid safe right now?',
    "What's the current max line loading?",
    'What scenarios can I run?',
    'What happened in the infeasible scenario?',
  ];

  return (
    <>
      {/* Floating Action Button */}
      <button
        className="chat-fab-button"
        onClick={() => {
          setIsOpen((open) => !open);
          setPosition(null);
        }}
        title={isOpen ? 'Close Assistant' : 'Open Digital Grid Assistant'}
        aria-label="Toggle Digital Grid Assistant"
      >
        {isOpen ? <X size={26} /> : <MessageCircle size={26} />}
      </button>

      {/* Floating Chat Panel */}
      {isOpen && (
        <div
          ref={panelRef}
          className="chat-widget-panel glass-panel"
          style={!isMobile && position ? {
            left: `${position.x}px`,
            top: `${position.y}px`,
            right: 'auto',
            bottom: 'auto',
          } : undefined}
        >
          {/* Header */}
          <div
            className={`chat-header${isDragging ? ' is-dragging' : ''}`}
            onPointerDown={startDragging}
            onPointerMove={dragPanel}
            onPointerUp={stopDragging}
            onPointerCancel={stopDragging}
          >
            <div className="chat-header-title">
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '6px',
                  background: 'linear-gradient(135deg, #06b6d4, #3b82f6)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Bot size={16} color="#ffffff" />
              </div>
              <div>
                <div style={{ fontSize: '0.9rem', fontWeight: 600 }}>Digital Grid Assistant</div>
                <div style={{ fontSize: '0.7rem', color: '#34d399', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#10b981' }} />
                  Grounded Tool-Calling Active
                </div>
              </div>
            </div>
            <button className="chat-close-btn" onClick={() => {
              setIsOpen(false);
              setPosition(null);
            }} title="Close">
              <X size={18} />
            </button>
          </div>

          {/* Messages Area */}
          <div className="chat-messages-container">
            {messages.map((msg) => (
              <div key={msg.id} className={`chat-message ${msg.sender}`}>
                <div>{msg.text}</div>
                {msg.evidence && (
                  <div>
                    <button
                      className="chat-evidence-toggle"
                      onClick={() => toggleEvidence(msg.id)}
                    >
                      {msg.showEvidence ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                      <span>{msg.showEvidence ? 'Hide Details' : 'View Grounded Details'}</span>
                    </button>
                    {msg.showEvidence && (
                      <div className="chat-evidence-content">
                        <table className="chat-evidence-table">
                          <tbody>
                            {getEvidenceRows(msg.evidence).map((row, index) => (
                              <tr key={`${row.label}-${index}`}>
                                <th scope="row">{row.label}</th>
                                <td>{row.value}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="chat-message assistant">
                <div className="typing-dots">
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Hints & Suggestion Chips */}
          <div className="chat-suggestions">
            <span style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 500, marginRight: '4px' }}>Ask:</span>
            {suggestions.map((chip, idx) => (
              <button
                key={idx}
                className="chat-suggestion-chip"
                onClick={() => sendMessage(chip)}
                disabled={loading}
              >
                {chip}
              </button>
            ))}
          </div>

          {/* Text Input Area */}
          <form
            className="chat-input-area"
            onSubmit={(e) => {
              e.preventDefault();
              sendMessage();
            }}
          >
            <input
              type="text"
              className="chat-input"
              placeholder="Ask a question about the grid state..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={loading}
            />
            <button type="submit" className="chat-send-btn" disabled={!input.trim() || loading} title="Send Message">
              <Send size={16} />
            </button>
          </form>
        </div>
      )}
    </>
  );
}
