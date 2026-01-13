"use client";

import { useState } from 'react';

export default function Home() {
  const [url, setUrl] = useState('');
  const [points, setPoints] = useState('');
  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState({}); // Tracking individual evaluations
  const [evaluatingGoogle, setEvaluatingGoogle] = useState({}); // Tracking Google search evaluations
  const [evaluatingAll, setEvaluatingAll] = useState(false);
  const [result, setResult] = useState(null);
  const [evalResults, setEvalResults] = useState({}); // Individual prompt results
  const [googleEvalResults, setGoogleEvalResults] = useState({}); // Google Grounded results
  const [report, setReport] = useState(null); // Full report results
  const [hoveredDetail, setHoveredDetail] = useState(null); // For the hover report
  const [selectedDetail, setSelectedDetail] = useState(null); // For the persistent modal
  const [toasts, setToasts] = useState([]); // For notifications
  const [error, setError] = useState(null);

  const addToast = (message, type = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 3000);
  };

  const handleAnalyze = async () => {
    if (!url && !points) {
      setError("Please provide at least a URL or manual points.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setEvalResults({});
    setGoogleEvalResults({});
    setReport(null);
    addToast("Initializing Global Analysis...", "info");

    try {
      const response = await fetch('http://localhost:8000/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url, points }),
      });

      if (!response.ok) {
        let errorMessage = 'Analysis failed';
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch {
          errorMessage = `Analysis failed: ${response.status} ${response.statusText}`;
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();
      setResult(data);
      addToast("✅ Analysis complete! Generated " + data.prompts.length + " test prompts.", "success");
    } catch (err) {
      setError(err.message);
      addToast("❌ Analysis failed: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  };

  const handleEvaluatePrompt = async (prompt, index, useGoogleSearch = false) => {
    if (useGoogleSearch) {
      setEvaluatingGoogle(prev => ({ ...prev, [index]: true }));
      addToast("Launching Google AI Search Check...", "success");
    } else {
      setEvaluating(prev => ({ ...prev, [index]: true }));
      addToast("Sending prompt to Gemini...", "info");
    }

    try {
      const response = await fetch('http://localhost:8000/evaluate-prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_profile: result.company_profile,
          prompt: prompt,
          use_google_search: useGoogleSearch
        }),
      });

      if (!response.ok) {
        let errorMessage = 'Evaluation failed';
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch {
          errorMessage = `Evaluation failed: ${response.status} ${response.statusText}`;
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();

      if (useGoogleSearch) {
        setGoogleEvalResults(prev => ({ ...prev, [index]: data }));
      } else {
        setEvalResults(prev => ({ ...prev, [index]: data }));
      }
    } catch (err) {
      console.error('Evaluation error:', err);
      addToast(`${useGoogleSearch ? 'Google Search' : 'Gemini'} check failed: ${err.message}`, 'error');
    } finally {
      if (useGoogleSearch) {
        setEvaluatingGoogle(prev => ({ ...prev, [index]: false }));
      } else {
        setEvaluating(prev => ({ ...prev, [index]: false }));
      }
    }
  };

  const handleEvaluateAll = async () => {
    setEvaluatingAll(true);
    addToast("Starting Full Visibility Audit...", "info");
    try {
      const response = await fetch('http://localhost:8000/evaluate-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_profile: result.company_profile,
          prompts: result.prompts
        }),
      });

      if (!response.ok) {
        let errorMessage = 'Full report failed';
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch {
          errorMessage = `Full report failed: ${response.status} ${response.statusText}`;
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();
      setReport(data);
      addToast("✅ Full audit complete! Score: " + data.overall_score + "/100", "success");
    } catch (err) {
      console.error('Full audit error:', err);
      addToast("❌ Full audit failed: " + err.message, "error");
    } finally {
      setEvaluatingAll(false);
    }
  };

  return (
    <main>
      <img src="/ethosh-logo.png" alt="Ethosh Logo" className="top-right-logo" />
      <header>
        <h1>GEO Analytics</h1>
        <p className="subtitle">
          Optimize your company&apos;s visibility in AI search results using generative engine optimization.
        </p>
      </header>

      <div className="input-group">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#a1a1aa' }}>Company Website</label>
          <input
            type="text"
            placeholder="https://example.com"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#a1a1aa' }}>Manual Points (Optional)</label>
          <textarea
            placeholder="Key offerings, unique selling points, or target audience..."
            rows={4}
            value={points}
            onChange={(e) => setPoints(e.target.value)}
          />
        </div>

        <button onClick={handleAnalyze} disabled={loading}>
          {loading ? 'Analyzing...' : 'Start Analysis'}
        </button>

        {error && (
          <div style={{ color: '#ef4444', fontSize: '0.875rem', textAlign: 'center', marginTop: '8px' }}>
            {error}
          </div>
        )}
      </div>

      {result && (
        <section className="results-container">
          <div className="company-info" style={{ border: 'none', padding: 0 }}>
            <div>
              <div className="company-name">{result.company_name}</div>
              <div className="industry-badge" style={{ marginTop: '8px' }}>{result.industry}</div>
            </div>
            <button
              className="secondary-btn"
              onClick={handleEvaluateAll}
              disabled={evaluatingAll}
            >
              {evaluatingAll ? 'Evaluating All...' : 'Run Full Visibility Audit'}
            </button>
          </div>

          {report && (
            <div className="report-card">
              <h2 style={{ fontSize: '1.5rem', color: 'var(--accent)', marginBottom: '24px' }}>
                Overall Visibility Score: {report.overall_score}/100
              </h2>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
                <div>
                  <h4 style={{ color: '#a1a1aa', marginBottom: '12px' }}>Key Findings</h4>
                  <ul style={{ paddingLeft: '20px' }}>
                    {(report.key_findings || []).map((f, i) => <li key={i} style={{ marginBottom: '8px' }}>{f}</li>)}
                  </ul>
                </div>
                <div>
                  <h4 style={{ color: '#a1a1aa', marginBottom: '12px' }}>Optimizer Tips</h4>
                  <ul style={{ paddingLeft: '20px' }}>
                    {(report.optimizer_tips || []).map((t, i) => <li key={i} style={{ marginBottom: '8px', color: 'var(--accent)' }}>{t}</li>)}
                  </ul>
                </div>
              </div>
            </div>
          )}

          <div style={{ marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.25rem', marginBottom: '8px' }}>Suggested AI Test Prompts</h3>
            <p style={{ color: '#a1a1aa' }}>Use these prompts to see how AI models perceive your brand.</p>
          </div>

          <div className="prompt-grid">
            {result.prompts.map((p, index) => (
              <div
                key={index}
                className="prompt-card"
                onMouseEnter={() => setHoveredDetail({ ...p, index })}
                onMouseLeave={() => setHoveredDetail(null)}
                onClick={() => setSelectedDetail({ ...p, index })}
              >
                <div className="view-hint">Hover to preview | Click for persistent view</div>
                <span className="category-label">{p.intent_category}</span>
                <p className="prompt-text">"{p.prompt_text}"</p>

                <div
                  style={{ marginTop: 'auto', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.05)' }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
                    <button
                      onClick={() => handleEvaluatePrompt(p, index, false)}
                      disabled={evaluating[index]}
                      style={{ flex: 1, padding: '8px', fontSize: '0.75rem', background: evalResults[index] ? 'rgba(44, 51, 149, 0.4)' : 'var(--primary)' }}
                    >
                      {evaluating[index] ? '...' : (evalResults[index] ? 'Gemini ✓' : 'Gemini Check')}
                    </button>
                    <button
                      onClick={() => handleEvaluatePrompt(p, index, true)}
                      disabled={evaluatingGoogle[index]}
                      style={{ flex: 1, padding: '8px', fontSize: '0.75rem', background: googleEvalResults[index] ? 'rgba(34, 197, 94, 0.4)' : 'var(--accent)', color: 'white' }}
                    >
                      {evaluatingGoogle[index] ? '...' : (googleEvalResults[index] ? 'Google ✓' : 'Google Search')}
                    </button>
                  </div>

                  {(evalResults[index] || googleEvalResults[index]) && (
                    <div className="eval-result-box" style={{ animation: 'fadeIn 0.3s ease', padding: '8px', fontSize: '0.7rem' }}>
                      <div style={{ color: 'var(--primary-light)' }}>
                        Rank: {evalResults[index]?.evaluation?.recommendation_rank || 'N/A'} | GS: {googleEvalResults[index]?.evaluation?.recommendation_rank || 'N/A'}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {hoveredDetail && !selectedDetail && (
        <div className="hover-detail-panel" style={{ animation: 'slideRight 0.4s cubic-bezier(0.4, 0, 0.2, 1)' }}>
          <div className="modal-section">
            <span className="modal-label">Quick Preview: {hoveredDetail.intent_category}</span>
            <p className="modal-text" style={{ fontStyle: 'italic', fontSize: '0.9rem', color: '#a1a1aa' }}>"{hoveredDetail.prompt_text}"</p>
          </div>

          <div className="modal-section" style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '20px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div>
                <span className="modal-label" style={{ color: 'var(--primary-light)' }}>Gemini AI (Standard)</span>
                {evalResults[hoveredDetail.index] ? (
                  <div className="response-full" style={{ padding: '12px', fontSize: '0.8rem', maxHeight: '200px', overflowY: 'auto' }}>
                    {evalResults[hoveredDetail.index].response_text}
                  </div>
                ) : <p style={{ fontSize: '0.75rem', color: '#666' }}>Not analyzed</p>}
              </div>
              <div>
                <span className="modal-label" style={{ color: 'var(--accent)' }}>Google AI Search (Grounded)</span>
                {googleEvalResults[hoveredDetail.index] ? (
                  <div className="response-full" style={{ padding: '12px', fontSize: '0.8rem', borderLeft: '2px solid var(--accent)', maxHeight: '200px', overflowY: 'auto' }}>
                    {googleEvalResults[hoveredDetail.index].response_text}
                  </div>
                ) : <p style={{ fontSize: '0.75rem', color: '#666' }}>Not analyzed</p>}
              </div>
            </div>
          </div>
        </div>
      )}

      {selectedDetail && (
        <div className="modal-backdrop" onClick={() => setSelectedDetail(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="close-btn" onClick={() => setSelectedDetail(null)}>&times;</button>

            <div className="modal-section">
              <span className="modal-label">Detailed Analysis: {selectedDetail.intent_category}</span>
              <p className="modal-text" style={{ fontStyle: 'italic', fontSize: '1.2rem' }}>"{selectedDetail.prompt_text}"</p>
            </div>

            <div className="modal-section" style={{ borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '24px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
                {/* Gemini Column */}
                <div>
                  <span className="modal-label">Gemini standard</span>
                  {evalResults[selectedDetail.index] ? (
                    <div className="response-full">
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px', paddingBottom: '12px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <span style={{ color: evalResults[selectedDetail.index]?.evaluation?.brand_present ? 'var(--accent)' : '#ef4444', fontWeight: 700, fontSize: '0.8rem' }}>
                          {evalResults[selectedDetail.index]?.evaluation?.brand_present ? '✓ Mentioned' : '✗ Missing'}
                        </span>
                        <span style={{ color: 'var(--primary-light)', fontWeight: 700, fontSize: '0.8rem' }}>Rank: {evalResults[selectedDetail.index]?.evaluation?.recommendation_rank || 'N/A'}</span>
                      </div>
                      <div style={{ fontSize: '0.9rem', lineHeight: 1.6 }}>{evalResults[selectedDetail.index].response_text}</div>
                    </div>
                  ) : (
                    <button onClick={() => handleEvaluatePrompt(selectedDetail, selectedDetail.index, false)} style={{ width: '100%', padding: '20px' }}>Run Gemini</button>
                  )}
                </div>

                {/* Google Search Column */}
                <div>
                  <span className="modal-label" style={{ color: 'var(--accent)' }}>Google AI Search</span>
                  {googleEvalResults[selectedDetail.index] ? (
                    <div className="response-full" style={{ borderLeft: '2px solid var(--accent)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px', paddingBottom: '12px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <span style={{ color: googleEvalResults[selectedDetail.index]?.evaluation?.brand_present ? 'var(--accent)' : '#ef4444', fontWeight: 700, fontSize: '0.8rem' }}>
                          {googleEvalResults[selectedDetail.index]?.evaluation?.brand_present ? '✓ Mentioned' : '✗ Missing'}
                        </span>
                        <span style={{ color: 'var(--primary-light)', fontWeight: 700, fontSize: '0.8rem' }}>Rank: {googleEvalResults[selectedDetail.index]?.evaluation?.recommendation_rank || 'N/A'}</span>
                      </div>
                      <div style={{ fontSize: '0.9rem', lineHeight: 1.6 }}>{googleEvalResults[selectedDetail.index].response_text}</div>
                    </div>
                  ) : (
                    <button onClick={() => handleEvaluatePrompt(selectedDetail, selectedDetail.index, true)} style={{ width: '100%', padding: '20px', background: 'var(--accent)' }}>Run Google Search</button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Toast Notifications */}
      <div className="toast-container">
        {toasts.map(toast => (
          <div key={toast.id} className={`toast ${toast.type}`}>
            <div className="toast-icon" />
            {toast.message}
          </div>
        ))}
      </div>
    </main>
  );
}
