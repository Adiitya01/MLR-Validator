import React from 'react'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true }
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ERROR BOUNDARY] Caught error:', {
      error: error.toString(),
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      errorInfo
    })
    this.setState({
      error: error,
      errorInfo: errorInfo
    })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '20px',
          backgroundColor: '#f8d7da',
          border: '1px solid #f5c6cb',
          borderRadius: '8px',
          margin: '20px',
          color: '#721c24'
        }}>
          <h2>Something went wrong</h2>
          <p>The application encountered an error. Please refresh the page or contact support.</p>
          {process.env.NODE_ENV === 'development' && (
            <details style={{marginTop: '10px', whiteSpace: 'pre-wrap', fontSize: '12px'}}>
              <summary>Error details (dev only)</summary>
              <p>{this.state.error && this.state.error.toString()}</p>
              <p>{this.state.errorInfo && this.state.errorInfo.componentStack}</p>
            </details>
          )}
          <button 
            onClick={() => window.location.reload()}
            style={{
              marginTop: '10px',
              padding: '10px 20px',
              backgroundColor: '#721c24',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Refresh Page
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
