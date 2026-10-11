import React, { useId, useState } from 'react';
import { ChartNoAxesCombined, ChevronDown } from 'lucide-react';

export default function ChartDisclosure({ title, summary, children }) {
  const contentId = useId();
  const [open, setOpen] = useState(false);

  return (
    <section className="vp-chart-disclosure">
      <button
        type="button"
        className="vp-chart-disclosure-toggle"
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => setOpen(!open)}
      >
        <ChartNoAxesCombined size={18} aria-hidden="true" />
        <span className="vp-chart-disclosure-copy">
          <strong>{title}</strong>
          {summary && <small>{summary}</small>}
        </span>
        <span className="vp-chart-disclosure-action">{open ? 'Hide chart' : 'Show chart'}</span>
        <ChevronDown className={open ? 'is-open' : ''} size={17} aria-hidden="true" />
      </button>
      <div id={contentId} className="vp-chart-disclosure-content" hidden={!open}>
        {open && children}
      </div>
    </section>
  );
}
