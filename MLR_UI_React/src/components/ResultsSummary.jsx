export default function ResultsSummary({ results }) {
  const total = results.length

  const categories = [
    { label: 'Supported', key: 'Supported', color: '#dcfce7', textColor: '#166534', borderColor: '#22c55e' },
    { label: 'Not Found', key: 'Not Found', color: '#f3f4f6', textColor: '#374151', borderColor: '#9ca3af' },
    { label: 'Uncited', key: 'Uncited', color: '#e0e7ff', textColor: '#3730a3', borderColor: '#818cf8' }
  ]

  const getMetricCount = (key) => {
    return results.filter(r => r.validation_result === key).length
  }

  // Filter out categories with 0 results to keep it clean, but always show Supported and Not Found
  const activeCategories = categories.filter(cat =>
    getMetricCount(cat.key) > 0 || ['Supported', 'Not Found'].includes(cat.label)
  )

  return (
    <div className="results-summary" style={{ marginBottom: '24px' }}>
      <h2 style={{ fontSize: '20px', marginBottom: '16px', color: '#111827' }}>Results Summary</h2>

      <div className="metrics-grid" style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
        gap: '16px'
      }}>
        {activeCategories.map(cat => {
          const count = getMetricCount(cat.key)
          const percentage = total > 0 ? (count / total * 100).toFixed(1) : 0

          return (
            <div key={cat.key} className="metric-card" style={{
              backgroundColor: cat.color,
              padding: '16px',
              borderRadius: '12px',
              border: `1px solid ${cat.borderColor}`,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'transform 0.2s',
              cursor: 'default'
            }}>
              <div className="metric-label" style={{
                fontSize: '14px',
                fontWeight: '600',
                color: cat.textColor,
                marginBottom: '4px',
                textAlign: 'center'
              }}>
                {cat.label}
              </div>
              <div className="metric-value" style={{
                fontSize: '24px',
                fontWeight: '800',
                color: cat.textColor,
                lineHeight: '1'
              }}>
                {count}
              </div>
              <div className="metric-percentage" style={{
                fontSize: '12px',
                color: cat.textColor,
                opacity: 0.8,
                marginTop: '4px'
              }}>
                {percentage}%
              </div>
            </div>
          )
        })}

        <div className="metric-card" style={{
          backgroundColor: '#ffffff',
          padding: '16px',
          borderRadius: '12px',
          border: '1px solid #e5e7eb',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
        }}>
          <div className="metric-label" style={{
            fontSize: '14px',
            fontWeight: '600',
            color: '#374151',
            marginBottom: '4px'
          }}>
            Total Results
          </div>
          <div className="metric-value" style={{
            fontSize: '24px',
            fontWeight: '800',
            color: '#111827',
            lineHeight: '1'
          }}>
            {total}
          </div>
          <div className="metric-percentage" style={{
            fontSize: '12px',
            color: '#6b7280',
            marginTop: '4px'
          }}>
            100%
          </div>
        </div>
      </div>
    </div>
  )
}
