export default function ResultsSummary({ results }) {
  const total = results.length
  const supported = results.filter(r => r.validation_result === 'Supported').length
  const notFound = results.filter(r => r.validation_result === 'Not Found').length

  return (
    <div className="results-summary">
      <h2>Results Summary</h2>
      
      <div className="metrics-grid">
        {/* OLD CODE - Commented out
        <div className="metric-card">
          <div className="metric-label">Supported</div>
          <div className="metric-value">{supported}</div>
          <div className="metric-percentage">{(supported/total*100).toFixed(1)}%</div>
        </div>
        */}
        <div className="metric-card highlight">
          <div className="metric-label">Supported</div>
          <div className="metric-value">{supported}</div>
          <div className="metric-percentage">{total > 0 ? (supported/total*100).toFixed(1) : 0}%</div>
        </div>

        <div className={`metric-card ${notFound > 0 ? 'not-found-highlight' : ''}`}>
          <div className="metric-label">Not Found</div>
          <div className="metric-value">{notFound}</div>
          <div className="metric-percentage">{total > 0 ? (notFound/total*100).toFixed(1) : 0}%</div>
        </div>

        <div className="metric-card">
          <div className="metric-label">Total Results</div>
          <div className="metric-value">{total}</div>
          <div className="metric-percentage">100%</div>
        </div>
      </div>
    </div>
  )
}
