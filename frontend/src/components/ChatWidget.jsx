import React, { useState, useRef, useEffect } from 'react';
import { MessageCircle, X, Send, Bot, Sparkles, ChevronDown, ChevronRight, CheckCircle2, AlertTriangle } from 'lucide-react';
import './ChatWidget.css';

const API_BASE = 'http://127.0.0.1:8000';

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
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
        onClick={() => setIsOpen(!isOpen)}
        title={isOpen ? 'Close Assistant' : 'Open Digital Grid Assistant'}
        aria-label="Toggle Digital Grid Assistant"
      >
        {isOpen ? <X size={26} /> : <MessageCircle size={26} />}
      </button>

      {/* Floating Chat Panel */}
      {isOpen && (
        <div className="chat-widget-panel glass-panel">
          {/* Header */}
          <div className="chat-header">
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
            <button className="chat-close-btn" onClick={() => setIsOpen(false)} title="Close">
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
                      <span>{msg.showEvidence ? 'Hide System Evidence' : 'View Grounded Evidence'}</span>
                    </button>
                    {msg.showEvidence && (
                      <div className="chat-evidence-content">
                        {JSON.stringify(msg.evidence, null, 2)}
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
