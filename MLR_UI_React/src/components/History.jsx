import { useState, useEffect, useRef } from 'react'
import { apiClient } from '../api'
import '../styles/History.css'

export default function History({ onSelectBrochure }) {
  const [brochures, setBrochures] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedBrochure, setSelectedBrochure] = useState(null)
  const [expandedDetails, setExpandedDetails] = useState(null)
  const componentRef = useRef(null)

  // Fetch brochure history on mount
  useEffect(() => {
    fetchBrochureHistory()
    // Expose refresh function to parent
    if (componentRef.current) {
      componentRef.current.refreshHistory = fetchBrochureHistory
    }
  }, [])

  const fetchBrochureHistory = async () => {
    try {
      setLoading(true)
      setError(null)
      // Fetch all validation history with results from single endpoint
      const apiBaseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiBaseURL}/validation-history`)
      if (!response.ok) {
        throw new Error('Failed to fetch history')
      }
      const data = await response.json()
      // History already sorted by created_at DESC from backend
      setBrochures(data.history || [])
    } catch (err) {
      setError('Failed to load history')
      console.error('Error fetching history:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectBrochure = async (brochure) => {
    try {
      setSelectedBrochure(brochure)
      // Results already loaded from history endpoint, pass them directly
      onSelectBrochure(brochure, brochure.results || [])
    } catch (err) {
      setError('Failed to load results')
      console.error('Error loading results:', err)
    }
  }

  const formatDate = (dateString) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getStatusBadge = (status) => {
    const statusMap = {
      completed: { bg: '#22c55e', tooltip: 'Completed' },
      processing: { bg: '#eab308', tooltip: 'Processing' },
      failed: { bg: '#ef4444', tooltip: 'Failed' }
    }
    const s = statusMap[status] || statusMap.completed
    return (
      <div
        className="status-indicator"
        title={s.tooltip}
        style={{
          background: s.bg,
          width: '12px',
          height: '12px',
          borderRadius: '50%',
          cursor: 'default'
        }}
      />
    )
  }

  const getConfidenceStats = (results) => {
    if (!results || results.length === 0) return null

    const high = results.filter(r => r.confidence_score >= 0.8).length
    const medium = results.filter(r => r.confidence_score >= 0.6 && r.confidence_score < 0.8).length
    const low = results.filter(r => r.confidence_score < 0.6).length

    return { high, medium, low }
  }

  if (loading) {
    return (
      <div className="history-container">
        <div className="history-loading">
          <div className="spinner"></div>
          <p>Loading history...</p>
        </div>
      </div>
    )
  }

  if (error && brochures.length === 0) {
    return (
      <div className="history-container">
        <div className="history-error">
          <p>⚠️ {error}</p>
          <button onClick={fetchBrochureHistory} className="retry-btn">
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (brochures.length === 0) {
    return (
      <div className="history-container">
        <div className="history-empty">
          <p>📋 No validation history yet</p>
          <p style={{ fontSize: '13px', color: '#666', marginTop: '8px' }}>
            Run your first validation to see results here
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="history-container" ref={componentRef} data-history-refresh>
      <div className="history-header">
        <h3>📋 Validation History</h3>
        <button onClick={fetchBrochureHistory} className="refresh-btn" title="Refresh">
          🔄
        </button>
      </div>

      <div className="history-list">
        {brochures.map((brochure, index) => {
          const isCompleted = brochure.status === 'completed'
          const isFailed = brochure.status === 'failed'

          return (
            <div
              key={brochure.id}
              className={`history-result-row ${isCompleted ? 'completed' : isFailed ? 'failed' : 'processing'}`}
              onClick={() => {
                handleSelectBrochure(brochure)
              }}
            >
              <div className="result-left">
                <span className="result-icon">
                  {isCompleted ? '✓' : isFailed ? '○' : '⏳'}
                </span>
                <div className="result-info">
                  <span className="result-index">{index + 1}.</span>
                  <span className="result-text">
                    {brochure.filename || brochure.name || 'Unknown File'}
                  </span>
                </div>
              </div>
              <div className="result-right">
                <span className="result-confidence">
                  Confidence: {brochure.avg_confidence ? (brochure.avg_confidence * 100).toFixed(2) : 'N/A'}
                </span>
                <span className={`result-status ${isFailed ? 'not-found' : isCompleted ? 'supported' : 'processing'}`}>
                  {isCompleted ? 'Completed' : isFailed ? 'Failed' : 'Processing'}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
