Product Requirements Document & Technical Specification
VoltPredict — v3 (Dual-Audience System + Agentic Digital Grid Assistant)
Problem Statement ENR-02 · HackMatrix 5.0, PCCOE Pune
## 1. Executive Summary & One-Line Pitch
- One-Line Pitch: A digital twin of a local power distribution grid that forecasts near-term solar generation and demand, detects when rising rooftop solar pushes voltage or equipment limits out of safe ranges, and automatically compares corrective actions — curtailing solar, dispatching battery storage, or reconfiguring feeders — to keep the grid safe while minimizing clean energy waste.
- Primary Artifact: A defensible, independently testable Python backend (src/) paired with an interactive, clickable Streamlit frontend (app/), designed for live hackathon judging and judge Q&A.
- Secondary Artifact (updated): An agentic conversational interface to VoltPredict — the Digital Grid Assistant — that lets both technical and non-technical users explore, understand, query, and interpret the system's data, simulations, forecasts, scenarios, decisions, assumptions, methodology, and limitations in natural language. It never invents system state; it explains and synthesizes only from verified sources.
## 2. Target Users & Design Implications (Updated — Dual Audience)
VoltPredict is designed to be accessible to both professional and ordinary users, at the same time, without compromising technical precision for either.
VoltPredict is accessible to both technical and non-technical users. Professionals can inspect precise grid metrics, bus/line states, forecasts, violations and corrective actions, while ordinary users can interact with the same system through clear natural-language explanations without needing prior power-systems knowledge.
This is achieved through a dual-layer communication approach, not through simplifying the system itself. The underlying data, simulations, and forecasts are identical for both audiences — only the presentation layer adapts.
### For ordinary users
- Clear, understandable natural-language explanations.
- Technical terms are explained when they first appear (e.g. what “pu” or “curtailment” means).
- No assumption of prior electrical/power-systems knowledge.
- Still shown supporting measurable evidence — simplified language does not mean hidden data.
### For professionals
- Exact technical details are always preserved: bus IDs, line IDs, voltage in pu, loading %, forecast values, scenario names, action results, residual violations.
- Technical information is never hidden or diluted on the assumption that a non-expert might also be using the system.
The governing principle for every component in this project, including the dashboard and the chatbot, is:
Simple to understand, technically precise underneath.
## 3. System Architecture: Two Complementary Systems (Preserved)
This distinction is unchanged and remains mandatory for how the project is described to judges: the system contains one deterministic decision engine and one agentic conversational layer. They must not be conflated.
- The Decision Engine (Sections 6–8): a deterministic, rule-based propose → verify → repair search over corrective actions, using pandapower power-flow re-simulation as ground truth. This is not an LLM and does not use one — its outputs are physics-grounded numbers.
- The Digital Grid Assistant (Section 10): an LLM-driven agent that autonomously selects and calls tools to explain, inspect, query, and interpret the system's already-computed state and its own documented methodology. This is the genuinely “agentic AI” component and should be described as such specifically — not as a label for the whole system, and never applied to the deterministic engine.
## 4. The Core Problem & Solution Loop (Unchanged)
In residential and commercial networks with high rooftop solar penetration, sunny afternoons cause widespread power export back into the grid while local demand is low. This triggers two major failures: voltage rising above safe distribution tolerances (0.95–1.05 pu), and equipment overloads as surging currents push cables and transformers above rated thermal capacities. Utilities traditionally use blunt caps on solar exports, wasting clean energy. This project provides a smarter middle ground via a continuous five-step operational loop: Forecast → Simulate → Detect → Propose & Compare → Report Honestly. This loop, and the deterministic engine that implements it, remains the project's core contribution — the Digital Grid Assistant in Section 10 sits on top of it as an interaction layer, not a replacement for it.
## 5. Pinned Tech Stack & Verified APIs (Unchanged — no new libraries required)
## 6. Repository Structure & Separation of Concerns (Updated)
The existing rule is preserved and extended: src/ contains zero Streamlit or LLM-prompting logic and is evaluated directly via pytest or CLI. The assistant's tools wrap src/ functions rather than duplicating them, and its own orchestration code is isolated in src/chatbot/ so it can be tested independently of both the UI and the live LLM call. A new knowledge/ subfolder holds the curated, approved documentation the project-knowledge tool is allowed to read from.
voltpredict/
├── README.md
├── NOTES.md # Engineering assumptions & judge Q&A prep
├── requirements.txt
├── CHECKPOINT_1_REPORT.md ... CHECKPOINT_5_REPORT.md
├── data/
│ ├── raw/ # Cached PVGIS pulls
│ └── processed/ # Aligned time-series and saved models (joblib)
├── src/ # Pure Python backend (UI-free, LLM-prompt-free)
│ ├── grid.py # CIGRE network loading & baseline power flow
│ ├── data_pipeline.py # PVGIS fetcher & synthetic load generator
│ ├── forecast.py # LightGBM training & chronological validation
│ ├── violations.py # Limit checks (voltage & line loading)
│ ├── actions.py # Curtailment, battery dispatch, feeder switching
│ ├── engine.py # Propose -> Verify -> Repair decision loop
│ ├── scenarios.py # Scenario runner suite
│ └── chatbot/ # Digital Grid Assistant, isolated package
│ ├── tools_state.py # Category A - system-state tool wrappers
│ ├── tools_knowledge.py # Category B - search_project_knowledge tool
│ ├── knowledge/ # Curated, approved doc excerpts (PRD, NOTES.md, scenario docs)
│ ├── agent.py # LangGraph tool-calling graph + Groq client call
│ └── prompts.py # System prompt: dual-audience style + grounding contract
├── app/
│ ├── streamlit_app.py # Frontend entrypoint
│ └── components/
│ ├── diagram.py, metrics.py, tables.py # existing renderers
│ └── chat_panel.py # Renders conversation + evidence panel, calls src/chatbot/agent.py
├── tests/
│ ├── test_grid.py, test_forecast.py, test_violations.py, test_scenarios.py
│ └── test_chatbot.py # Numeric, conceptual, combined, missing-info, hallucination tests (10.7)
├── outputs/
│ ├── plots/
│ └── scenario_results/ # JSON/CSV per scenario — also a Digital Grid Assistant data source
└── main.py # CLI runner for backend pipeline

## 7. Data Sources & Engineering Justifications (Unchanged)
## 8. Machine Learning Forecasting Approach (Unchanged)
- Model Selection: Gradient-boosted trees (lightgbm or GradientBoostingRegressor) using lagged features (t-1, t-2, t-3, t-24) combined with calendar metadata (hour of day, day of year). Deep learning is explicitly excluded to maintain speed, simplicity, and explainability.
- Validation Strategy: A strict chronological holdout split over the final 2–4 weeks (preventing future-data leakage from random shuffling), benchmarked against a naive persistence baseline using MAE and RMSE.
## 9. Corrective Action Engine (Unchanged, terminology preserved)
This is the deterministic component referenced in Section 3. When a violation is detected via power-flow execution (pandapower.runpp), the engine evaluates three corrective strategies across multiple magnitudes, re-simulates each, and ranks them on constraint resolution, clean-energy retention %, and an operational cost proxy:
- Curtailment — reduces solar export (sgen) at offending buses. Easiest to implement, but directly wastes clean energy.
- Battery Dispatch — charges batteries to absorb excess solar (fixing overvoltage) or discharges them to support demand (fixing overloads). Preserves energy, but constrained by capacity limits.
- Feeder Reconfiguration — toggles network switches (net.switch) to reroute sections and rebalance load without touching generation.
The structured ranking this engine produces — per-action scores, not just a single winner — is exactly what the Digital Grid Assistant reads from in Section 10; no new computation is added for the chatbot to work.
## 10. The Digital Grid Assistant (Expanded — was “Conversational Query Assistant”)
Positioning: an agentic conversational interface to VoltPredict that allows both technical and non-technical users to explore, understand, query, and interpret the system through natural language. It is still a secondary, stretch feature — the core contribution remains the Forecast → Simulate → Detect → Propose & Compare → Report Honestly loop (Section 4). The assistant is an intelligent interaction layer on top of that system, not a replacement for it.
The assistant is no longer scoped to numeric lookups only. It is designed to answer any reasonable question about VoltPredict, spanning five broad categories:
- Quantitative — “What is the voltage at Bus 7?”, “Is Line 4 overloaded?”, “How much renewable energy was retained after battery dispatch?”
- Explanatory — “Why is the voltage too high?”, “What does 1.05 pu mean?”, “Why can rooftop solar cause overvoltage?”
- System / methodology — “How does VoltPredict work?”, “Where does the solar data come from?”, “Why is the load data synthetic?”
- Scenario — “What happened in the high-solar scenario?”, “Was the evening peak scenario resolved?”
- Decision / limitation — “Why did the engine select battery dispatch?”, “Is this a real Indian grid?”, “How accurate is the forecasting model?”
### 10.1 Dual-Audience Response Principle (New)
Every response is natural language first, evidence second. The assistant never behaves like a terminal that only dumps a raw value.
Instead of:
Bus 7: 1.082 pu
the assistant responds:
Answer: Bus 7 is currently experiencing an overvoltage condition. Its simulated voltage is 1.082 pu, which is above the project's 1.05 pu upper operating limit.
Supporting evidence: Bus 7 voltage: 1.082 pu · Safe upper limit: 1.05 pu · Violation margin: +0.032 pu · Scenario: High Solar / Low Load
Exact UI formatting (a collapsible “evidence” panel, inline badges, etc.) is left to implementation, but the two-part structure — natural-language explanation, then measurable/system-grounded evidence — is mandatory for every response where evidence exists. For purely conceptual questions with no scenario-specific metric to attach (e.g. “what is curtailment?”), the evidence section instead cites the documented definition/source the answer came from, rather than fabricating a number to fill the slot.
### 10.2 Grounding Contract (Strengthened)
The LLM may explain, summarize, and reason over information available in approved system sources, but it must never invent system state, simulation values, forecast values, scenario outcomes, metrics, or other factual claims about VoltPredict.
- For numerical / system-state questions: no tool call or verified source → no system-specific numeric claim.
- For conceptual / documentation questions: the assistant may answer from the approved project knowledge base, provided the information exists there.
If the requested information is not available in (1) live system/tool output, (2) saved scenario data, or (3) approved project documentation, the assistant must clearly say the information is not available. It must not estimate, fabricate, or produce a plausible-looking value or explanation to fill the gap.
### 10.3 Tool Set — Two Categories, Kept Separate
Category A reads actual computed values. Category B answers conceptual and methodology questions from approved documentation only — it does not draw on unrestricted external web knowledge for project-specific facts.
search_project_knowledge deliberately does not reach the open web: project-specific facts (why a library was chosen, what a limitation is, how validation works) must trace to this project's own approved documents, not to the LLM's general training knowledge, which could drift from what was actually built.
### 10.4 Multi-Tool Orchestration (New)
The agent can call more than one tool per turn when a question spans both categories. For example, for “Why is Bus 7 violating the voltage limit, and what can we do about it?” the agent reads Bus 7's actual state (Category A), reads the active-violation and action-comparison data (Category A), and pulls the conceptual explanation of overvoltage (Category B), then synthesizes one natural-language answer supported by the real values it retrieved. Conceptually:
User question → agent interprets intent → selects one or more tools → obtains verified information → synthesizes one answer → attaches supporting evidence.
This multi-tool synthesis, not any single lookup, is where the “agentic” behavior actually lives — consistent with the Section 3 distinction that only this component earns the term.
### 10.5 Example Exchange (illustrates evidence requirement, Change 4)
User: “Why was battery dispatch preferred?” — the assistant must not answer “because batteries are better.” It must retrieve the actual comparison and answer, for example: “Battery dispatch was preferred because it resolved the overvoltage while preserving more renewable generation than curtailment. In this scenario, battery dispatch retained 94% of renewable output, while curtailment retained 78%.” Both percentages must come from the actual compare_actions() tool result, never invented to sound plausible.
### 10.6 UI Principle (Updated)
The chat panel should feel like an intelligent engineering assistant that communicates naturally but can expose technical evidence when needed — not a raw developer terminal. Two worked examples:
- “Is the grid safe right now?” → “No. The current simulated state contains an overvoltage violation at Bus 7. The voltage is 1.082 pu, above the 1.05 pu upper limit. Two other buses remain within the allowed range.” Evidence: Bus 7: 1.082 pu · Upper limit: 1.05 pu · Scenario: High Solar / Low Load.
- “What is curtailment?” → “Curtailment means intentionally reducing renewable generation to relieve grid stress. In this system, it is one of the corrective actions considered when solar output contributes to a violation.” Evidence: Action type: Curtailment · Applied to: solar sgen · Purpose: reduce renewable export.
### 10.7 Testing (Expanded)
tests/test_chatbot.py covers five categories, independent of any live LLM call where possible so correctness stays verifiable in CI without spending API credits:
- Grounded numeric — e.g. “What is Bus 7 voltage?”: assert the correct tool is called, the returned value is used verbatim, and no value is fabricated.
- Conceptual — e.g. “What is feeder reconfiguration?”: assert search_project_knowledge is used and the answer traces to approved documentation.
- Combined — e.g. “Why is Bus 7 overloaded and what action was selected?”: assert multiple tools are called and the synthesized answer includes supporting evidence from each.
- Missing information — e.g. asking about a scenario that has not been run: assert the assistant explicitly states the information is unavailable rather than guessing.
- Hallucination protection — assert the assistant never produces a system-specific number that did not originate from a tool result or an approved document.
## 11. Demo Scenarios (Unchanged, chatbot usage updated)
- High Solar / Low Load (Midday, Sunny): classic overvoltage/export case; demonstrates curtailment vs. battery trade-offs.
- Evening Peak Load, Low Solar: classic overload/undervoltage case when solar is inactive.
- Cloudy Day / Rapid Solar Drop: tests rapid-response actions (batteries) against sudden generation drops.
- Deliberately Infeasible Scenario: a widespread violation too severe for any single action or realistic combination to fix. The system transparently reports “Unresolved, best partial mitigation was X, residual violation Y” rather than failing silently.
Suggested live-demo moment: after triggering the infeasible scenario, ask the assistant “was this scenario resolved?” and “why not?” — and show it reports the honest partial-mitigation result, with the underlying residual-violation numbers as evidence, rather than a false success. This ties Sections 4, 9 and 10 together in one demo beat, for either a technical or non-technical judge.
## 12. Staged Implementation Checkpoints (Updated)
Checkpoints 1–3 remain the required, non-negotiable core — they are what satisfies the problem statement's core outcomes. Checkpoint 4 is the full scenario suite. Checkpoint 5 is now the Agentic Digital Grid Assistant (renamed and expanded), and remains stretch work, attempted only once Checkpoints 1–3 are solid and demoable.
- Checkpoint 1 (Core): Grid foundation (pandapower CIGRE MV setup), PVGIS data pipeline integration, and a Streamlit UI rendering a color-coded network diagram.
- Checkpoint 2 (Core): Feature engineering, LightGBM model training, chronological holdout validation, and the UI forecast comparison chart.
- Checkpoint 3 (Core): Violation detection module, all three corrective actions, the propose-verify-repair loop, and interactive UI trigger — scoped to one primary scenario for the MVP.
- Checkpoint 4 (Stretch): Full 4-scenario suite including the deliberately infeasible case, JSON/CSV artifact saving, and UI polish.
### Checkpoint 5 (Stretch, updated) — Agentic Digital Grid Assistant
- Project knowledge tool (search_project_knowledge) over curated, approved documentation.
- Runtime state tools (Category A, Section 10.3).
- LangGraph / tool-calling orchestration supporting multi-tool questions (Section 10.4).
- Groq-hosted LLM integration for grounded natural-language response generation.
- Evidence/support section in every response (Section 10.1).
- Chat panel UI (Section 10.6).
- Tool-level and response-level testing (Section 10.7).
This checkpoint only begins once Checkpoint 3 is approved and stable. If time runs short, Checkpoint 5 remains the first checkpoint to cut — not Checkpoints 1–3.
## 13. Engineering Assumptions & Known Limitations (Updated)
- Voltage limits are strictly set to ±5% (0.95–1.05 pu), the standard distribution tolerance.
- Line loadings above 100% flag thermal overload and asset degradation risk.
- Batteries are modeled as simplified storage approximations, not a full electrochemical model.
- Streamlit is used instead of a custom React/FastAPI build to maximize live interactivity within a tight timeline.
- Updated: the Digital Grid Assistant answers only from tool-returned data or approved project documentation; it has no independent access to network state and cannot answer questions about scenarios that have not been run and saved, or about facts not present in its curated knowledge base.
- Updated: the assistant is designed for both professional and non-technical users simultaneously (Section 2) — it adapts its explanation style, not the precision or availability of the underlying data.
## 14. Explicit Guardrails / “Do Not” List (Updated)
- Do not bypass the UI after Checkpoint 1; backend slices and frontend renderers ship together.
- Do not couple Streamlit logic inside src/ files.
- Do not pull in unnecessary external packages like simbench.
- Do not use deep learning or LSTM architectures for forecasting.
- Do not hide or crash on the infeasible scenario — it must be explicitly surfaced as an honest system limitation.
- Do not let the assistant answer a numeric or system-state question without a corresponding tool call in the same turn — no exceptions, even for values that seem obvious from conversation context.
- Do not describe the deterministic decision engine (Section 9) as “agentic AI” in documentation or to judges — reserve that term for the Digital Grid Assistant, per Section 3.
- Do not begin Checkpoint 5 (Digital Grid Assistant) before Checkpoint 3's core engine is approved and stable.
- New: do not restrict the assistant to professional users, and do not simplify or omit technical data on the assumption that a user might be non-technical — both audiences see the same underlying evidence, only the explanation layer adapts (Section 2).
- New: do not let search_project_knowledge draw on unrestricted external web knowledge for project-specific facts — it is scoped to the project's own approved documentation only.
- New: do not respond to any question with a bare value or bare terminal-style dump when a natural-language explanation is expected — evidence supports the explanation, it does not replace it (Section 10.1).
## 15. Anticipated Judge Q&A — Digital Grid Assistant (New)
### “Why have a chatbot if you already have a dashboard?”
The dashboard provides visual operational detail, while the conversational assistant lets both technical and non-technical users query and understand the same system through natural language, without manually navigating multiple panels.
### “Can the chatbot invent a grid value?”
No. System-specific values must come from a tool or an approved system source. The LLM only interprets and communicates those results — it never generates a number on its own.
### “Can a non-technical user understand the system?”
Yes. The assistant explains concepts in plain language, while still exposing the measurable evidence behind its conclusions, so nothing is hidden from a more technical user reading the same answer.
### “Can the chatbot answer questions beyond voltage and loading?”
Yes. It can answer questions about grid state, forecasts, scenarios, corrective actions, architecture, assumptions, methodology, limitations, and other information contained in the project's approved knowledge base.
### “Is the chatbot the core AI of the project?”
No. The predictive model provides forecasting, the deterministic engine evaluates corrective actions against power-system physics, and the chatbot provides an agentic natural-language interface over those verified outputs. The chatbot is a stretch feature; the forecast-simulate-detect-compare-verify loop is the core contribution.

| Component | Technology | Verified API / Notes |
| --- | --- | --- |
| Grid & Simulation | pandapower | create_cigre_network_mv(with_der="all"), runpp(net), res_bus.vm_pu, res_line.loading_percent |
| Solar Data | pvlib (PVGIS) | pvlib.iotools.get_pvgis_hourly(latitude, longitude, start, end) |
| Forecasting | lightgbm (fallback: scikit-learn GradientBoostingRegressor) | Standard .fit() / .predict(), lagged + calendar features |
| Data Handling | pandas, numpy | Time-series cleaning and alignment |
| Frontend UI | streamlit, plotly | streamlit.plotly_chart — diagrams, forecast charts, scenario picker, chat panel |
| Testing | pytest | Independent unit tests for src/ logic, isolated from UI and from the LLM |
| Assistant LLM | Groq-hosted LLM (e.g. Llama 3.x via Groq API) | Function-calling / tool-use completion API — low-latency, suited to a live demo |
| Assistant Orchestration | LangGraph (or a minimal manual tool-call loop if time-constrained) | user question → tool selection → tool execution → grounded synthesis |
| Project Knowledge Lookup | Plain Python dict/JSON lookup over curated doc excerpts (no new dependency) | Deliberately kept simple: the knowledge base is a handful of curated documents (PRD, NOTES.md, scenario docs), not a large corpus, so a keyword/section-keyed lookup is sufficient and avoids adding an embeddings/vector-DB dependency under time pressure. See Section 10.4. |


| Data Layer | Source | Justification |
| --- | --- | --- |
| Grid Topology | pandapower built-in CIGRE MV network with DER | Public utility feeder data at this granularity does not exist due to proprietary regulation. CIGRE MV is the internationally recognized benchmark for DER-integration research. |
| Solar Generation | PVGIS via pvlib (Pune coordinates: lat 18.52, lon 73.85) | Free, globally covers India, requires no API key, and is backed by the EU Joint Research Centre (JRC). |
| Household Demand | Hand-built synthetic load curve (morning ramp, evening peak, overnight trough) | Real per-household smart-meter data is restricted; a documented synthetic profile represents standard residential/commercial patterns transparently. |


| Category | Tool | Wraps / Source | Answers questions like |
| --- | --- | --- | --- |
| A — System State | get_bus_status(bus_id) | grid.py / violations.py | “What's the voltage at Bus 7 right now?” |
| A — System State | get_line_status(line_id) | grid.py / violations.py | “Is Line 4 overloaded in this scenario?” |
| A — System State | list_active_violations() | violations.py | “Is the grid safe right now?” |
| A — System State | get_forecast(series, horizon) | forecast.py | “What's the predicted solar output for the next 3 hours?” |
| A — System State | get_scenario_result(name) | scenarios.py / outputs/ | “What happened in the cloudy-day scenario?” |
| A — System State | compare_actions(scenario_name) | engine.py ranking output | “Which action preserved the most renewable energy?” |
| B — Project Knowledge | search_project_knowledge(topic_or_question) | PRD, NOTES.md, scenario docs (curated, approved excerpts only) | “What is curtailment?”, “Why CIGRE MV?”, “What are this model's limitations?” |
