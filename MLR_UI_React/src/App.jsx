import { useState, useRef, useEffect } from 'react'
import './App.css'
import ValidationResults from './components/ValidationResults'
import SpecialUseCasesSidebar from './components/SpecialUseCasesSidebar'
import ResultsSummary from './components/ResultsSummary'
import DownloadSection from './components/DownloadSection'
import PDFHighlighter from './components/PDFHighlighter'
import History from './components/History'
import ErrorBoundary from './components/ErrorBoundary'
import { apiClient } from './api'

function App() {
  const [specialSidebarCollapsed, setSpecialSidebarCollapsed] = useState(true)
  const [brochureFile, setBrochureFile] = useState(null)
  const [backendStatus, setBackendStatus] = useState('checking') // 'checking', 'connected', 'error'
  const [referenceFiles, setReferenceFiles] = useState([])
  const [extractedStatements, setExtractedStatements] = useState([])
  const [validationResults, setValidationResults] = useState([])
  const [isValidating, isValidatingSet] = useState(false)
  const [resultFilter, setResultFilter] = useState([])
  const [minConfidence, setMinConfidence] = useState(0)
  const [expandedResult, setExpandedResult] = useState(null)
  const [extractionStatus, setExtractionStatus] = useState('ready') // 'ready', 'extracting', 'success', 'error'
  const [liveLog, setLiveLog] = useState('')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [showHistoryModal, setShowHistoryModal] = useState(false)
  const [userData, setUserData] = useState(null)
  const [isLoadingAuth, setIsLoadingAuth] = useState(true)
  const [drugPipelineNotification, setDrugPipelineNotification] = useState(false)
  const [validationType, setValidationType] = useState('research') // 'research' or 'drug'
  const brochureInputRef = useRef(null)
  const referenceInputRef = useRef(null)

  // Load user data from localStorage and check authentication
  useEffect(() => {
    const loadUserData = () => {
      try {
        const token = localStorage.getItem('access_token');
        const userDataStr = localStorage.getItem('user_data');

        if (token && userDataStr) {
          const user = JSON.parse(userDataStr);
          setUserData(user);
        } else {
          // Redirect to login if not authenticated
          window.location.href = '/login';
        }
      } catch (err) {
        console.error('Error loading user data:', err);
        window.location.href = '/login';
      } finally {
        setIsLoadingAuth(false);
      }
    };

    loadUserData();
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_data');
    window.location.href = '/login';
  };

  // Test backend connection on app load
  useEffect(() => {
    const checkBackend = async () => {
      const connected = await apiClient.testConnection();
      setBackendStatus(connected ? 'connected' : 'error');
    };
    checkBackend();
  }, []);

  // Poll logs for validation progress while validating
  useEffect(() => {
    if (!isValidating) return

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${apiClient.baseUrl}/logs/latest`)
        const data = await res.json()

        const validatingLogs = data.logs
          .map(l => l.message)
          .filter(msg => msg.includes('VALIDATING_STATEMENT'))

        if (validatingLogs.length > 0) {
          const last = validatingLogs[validatingLogs.length - 1]
          const match = last.match(/VALIDATING_STATEMENT (.+)/)
          if (match) {
            setLiveLog(`Validating statement ${match[1]}`)
          }
        }
      } catch (e) {
        // silent fail — logger should never break UI
      }
    }, 300)

    return () => clearInterval(interval)
  }, [isValidating])

  const handleSelectFromHistory = (brochure, results) => {
    // Load previous validation results from MongoDB
    // results is already the array of validation results from brochure.results
    console.log('Loading from history:', { brochure, results })

    setValidationResults(results || [])
    setExtractedStatements(results || [])
    setResultFilter(['Supported', 'Not Found', 'Partially Supported', 'Inconclusive']) // Show all results
    setMinConfidence(0)
    setExtractionStatus('success')
    setShowHistoryModal(false) // Close modal after selection

    // Scroll to results
    setTimeout(() => {
      const resultsSection = document.querySelector('.results-section')
      if (resultsSection) {
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }, 100)
  }

  const resetAll = () => {
    setBrochureFile(null)
    setReferenceFiles([])
    setExtractedStatements([])
    setValidationResults([])
    setResultFilter([])
    setMinConfidence(0)
    setExtractionStatus('ready')
  }

  const handleBrochureUpload = (e) => {
    const file = e.target.files?.[0]
    if (file) setBrochureFile(file)
  }

  const handleReferenceUpload = (e) => {
    const files = e.target.files
    if (files) {
      const newFiles = Array.from(files).map(file => ({
        id: Date.now() + Math.random(),
        file: file,
        name: file.name,
        size: (file.size / 1024).toFixed(2),
        status: 'loaded'
      }))
      setReferenceFiles([...referenceFiles, ...newFiles])
    }
  }

  const handleExtractCitations = async () => {
    if (!brochureFile || referenceFiles.length === 0) {
      alert('Please upload both brochure PDF and at least one reference PDF')
      return
    }

    isValidatingSet(true)
    setValidationResults([])
    setExtractionStatus('extracting')
    setLiveLog('')

    try {
      const results = await apiClient.runPipeline(brochureFile, referenceFiles.map(f => f.file), validationType)

      console.log('[DEBUG] API Response Results:', results)
      if (results && results.length > 0) {
        console.log('[DEBUG] First result sample:', {
          statement: results[0].statement,
          matched_evidence: results[0].matched_evidence,
          validation_result: results[0].validation_result,
          matched_paper: results[0].matched_paper
        })
      }

      if (!results || results.length === 0) {
        alert('Pipeline completed but no validation results were generated')
        setExtractionStatus('error')
        return
      }

      setExtractedStatements(results)
      setValidationResults(results)
      setExtractionStatus('success')

      // Refresh History component after validation
      const historyElement = document.querySelector('[data-history-refresh]')
      if (historyElement && historyElement.refreshHistory) {
        historyElement.refreshHistory()
      }

    } catch (error) {
      console.error('Pipeline error:', error)
      alert(`Error running pipeline: ${error.message}`)
      setExtractionStatus('error')
    } finally {
      setLiveLog('Validation completed')
      isValidatingSet(false)
    }
  }

  const removeBrochure = () => setBrochureFile(null)

  const removeReference = (id) => {
    setReferenceFiles(referenceFiles.filter(f => f.id !== id))
  }

  const filteredResults = validationResults.filter(r => {
    const matchesFilter = resultFilter.length === 0 || resultFilter.includes(r.validation_result)
    const meetsConfidence = r.confidence_score >= minConfidence
    return matchesFilter && meetsConfidence
  })

  // Debug logging for filtered results
  useEffect(() => {
    if (resultFilter.length > 0) {
      console.log('[DEBUG] Filter applied:', {
        filter: resultFilter,
        totalResults: validationResults.length,
        filteredCount: filteredResults.length,
        firstResult: filteredResults[0] || 'NO RESULTS',
        allResults: filteredResults
      })
    }
  }, [resultFilter, filteredResults])

  return (
    <ErrorBoundary>
      <div className={`app-container ${sidebarCollapsed ? 'sidebar-collapsed' : ''} ${specialSidebarCollapsed ? '' : 'special-sidebar-open'}`}>
        {/* Persistent Left Sidebar */}
        <aside className={`app-sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
          <div className="sidebar-header">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, fontSize: '20px', color: '#1f2937', fontWeight: '700' }}>
                {!sidebarCollapsed && 'Menu'}
              </h3>
              <button
                onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
                className="sidebar-toggle-btn"
                title={sidebarCollapsed ? 'Expand' : 'Collapse'}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '18px',
                  cursor: 'pointer',
                  color: '#2563eb',
                  padding: '4px 8px',
                  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                  transform: sidebarCollapsed ? 'rotate(180deg)' : 'rotate(0deg)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}
                onMouseEnter={(e) => {
                  e.target.style.backgroundColor = '#eff6ff'
                  e.target.style.borderRadius = '6px'
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = 'transparent'
                }}
              >
                ◀
              </button>
            </div>
          </div>

          {/* Profile Section */}
          {!sidebarCollapsed && userData && (
            <div className="sidebar-section">
              <p className="sidebar-label">Account</p>
              <div className="profile-card">
                <div className="profile-avatar">{userData.full_name?.charAt(0).toUpperCase() || userData.email?.charAt(0).toUpperCase() || 'U'}</div>
                <div>
                  <p className="profile-name">{userData.full_name || userData.email?.split('@')[0]}</p>
                  <p className="profile-email">{userData.email}</p>
                </div>
              </div>
            </div>
          )}

          {/* Menu Items Section */}
          {!sidebarCollapsed && (
            <div className="sidebar-section">
              <p className="sidebar-label">Tools</p>
              <button
                onClick={() => setShowHistoryModal(true)}
                className="menu-item"
              >
                <span className="menu-icon">📋</span>
                <span>View History</span>
              </button>
              <button className="menu-item">
                <span className="menu-icon">⚙️</span>
                <span>Settings</span>
              </button>
              <button
                onClick={handleLogout}
                className="menu-item"
                style={{ color: '#ef4444' }}
              >
                <span className="menu-icon">🚪</span>
                <span>Sign Out</span>
              </button>
            </div>
          )}

          {/* Sidebar Footer */}
          {!sidebarCollapsed && (
            <div className="sidebar-footer">
              MLR Tool v1.0
            </div>
          )}
        </aside>

        {/* Persistent Right Sidebar for Special Use Cases - INDEPENDENT OF LEFT SIDEBAR */}
        <SpecialUseCasesSidebar
          collapsed={specialSidebarCollapsed}
          onClose={() => setSpecialSidebarCollapsed(!specialSidebarCollapsed)}
          onDrugsClick={() => {
            // Toggle drug pipeline mode
            const newType = validationType === 'drug' ? 'research' : 'drug'
            setValidationType(newType)
            // Show notification
            setDrugPipelineNotification(true)
            // Auto-hide after 3 seconds
            setTimeout(() => setDrugPipelineNotification(false), 3000)
          }}
        />

        {/* Drug Pipeline Notification */}
        {drugPipelineNotification && (
          <div style={{
            position: 'fixed',
            top: '20px',
            left: '50%',
            transform: 'translateX(-50%)',
            backgroundColor: '#0891b2',
            color: 'white',
            padding: '16px 24px',
            borderRadius: '8px',
            boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
            zIndex: 9999,
            fontWeight: '600',
            animation: 'slideDown 0.3s ease-out',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}>
            <span>{validationType === 'drug' ? 'Using' : 'Switched to'} <strong>{validationType === 'drug' ? 'ANTIBIOTICS' : validationType.toUpperCase()} PIPELINE</strong></span>
            <button
              onClick={() => setDrugPipelineNotification(false)}
              style={{
                background: 'none',
                border: 'none',
                color: 'white',
                cursor: 'pointer',
                fontSize: '18px',
                marginLeft: '12px'
              }}
            >
              ✕
            </button>
          </div>
        )}

        <header className="header" style={{ position: 'relative' }}>
          <div className="header-content">

            <div className="header-title-section">
              <h1>MLR Validation Tool</h1>
              <p className="header-subtitle">Professional Citation and Claims Validator</p>
            </div>
            <div className="header-logo-section-right">
              <img src={new URL('./assets/ethosh-logo.svg', import.meta.url).href} alt="ethosh logo" className="header-logo-full" />
            </div>
          </div>
        </header>

        <main className="main-content">
          {/* Loading State */}
          {isLoadingAuth && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: '100vh',
              background: '#f3f4f6',
              fontSize: '18px',
              color: '#6b7280'
            }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{
                  width: '40px',
                  height: '40px',
                  border: '3px solid #e5e7eb',
                  borderTopColor: '#667eea',
                  borderRadius: '50%',
                  margin: '0 auto 20px',
                  animation: 'spin 0.8s linear infinite'
                }}></div>
                Loading...
              </div>
            </div>
          )}

          {!isLoadingAuth && (
            <>
              <div className="content-container">
                <div className="upload-section">
                  <div className="upload-column">
                    <div className="column-header">
                      <span>Upload Collateral</span>
                    </div>

                    <div className="upload-area" onClick={() => brochureInputRef.current?.click()}>
                      <label className="file-input-label">
                        <input
                          ref={brochureInputRef}
                          type="file"
                          accept=".pdf"
                          onChange={handleBrochureUpload}
                          className="file-input"
                        />
                        {brochureFile ? (
                          <div className="upload-content">
                            <p className="upload-instruction">{brochureFile.name}</p>
                          </div>
                        ) : (
                          <div className="upload-content">
                            <p className="upload-instruction">Select your PDF file</p>
                            <span className="upload-hint">or drag and drop</span>
                            <span className="file-size-hint">Up to 25 MB</span>
                          </div>
                        )}
                      </label>
                      <button className="browse-btn" disabled={!!brochureFile} onClick={(e) => { e.stopPropagation(); brochureInputRef.current?.click() }}>Browse Files</button>
                    </div>
                  </div>

                  <div className="upload-column">
                    <div className="column-header">
                      <span>Upload Supporting References</span>
                    </div>

                    <div className="upload-area" onClick={() => referenceInputRef.current?.click()}>
                      <label className="file-input-label">
                        <input
                          ref={referenceInputRef}
                          type="file"
                          accept=".pdf"
                          multiple
                          onChange={handleReferenceUpload}
                          className="file-input"
                        />
                        {referenceFiles.length > 0 ? (
                          <div className="upload-content">
                            <p className="upload-instruction">{referenceFiles.length} file{referenceFiles.length !== 1 ? 's' : ''} selected</p>
                          </div>
                        ) : (
                          <div className="upload-content">
                            <p className="upload-instruction">Select reference PDFs</p>
                            <span className="upload-hint">or drag and drop</span>
                            <span className="file-size-hint">Up to 25 MB per file</span>
                          </div>
                        )}
                      </label>
                      <button className="browse-btn" disabled={referenceFiles.length > 0} onClick={(e) => { e.stopPropagation(); referenceInputRef.current?.click() }}>Browse Files</button>
                    </div>

                    {referenceFiles.length > 0 && (
                      <div className="reference-files-container">
                        <div className="files-summary">
                          <h4>Reference PDFs ({referenceFiles.length} {referenceFiles.length === 1 ? 'file' : 'files'})</h4>
                        </div>
                        <div className="file-list scrollable">
                          {referenceFiles.map((file) => (
                            <div key={file.id} className="file-item success">
                              <span className="file-name">{file.name}</span>
                              <button onClick={() => removeReference(file.id)} className="remove-btn">✕</button>
                            </div>
                          ))}
                          <div className="file-item-status">
                            <span className="status-icon">✓</span>
                            <span className="status-text">All files loaded</span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Start Validation Button - Inside Upload Files Box */}
                  {brochureFile && referenceFiles.length > 0 && (
                    <div className="validation-button-container-inside">
                      <button
                        className="start-validation-btn"
                        onClick={handleExtractCitations}
                        disabled={isValidating}
                      >
                        {isValidating ? (
                          <>
                            <span className="spinner"></span>
                            Validating...
                          </>
                        ) : (
                          'Start Validation'
                        )}
                      </button>
                      {isValidating && liveLog && (
                        <div style={{
                          marginTop: '12px',
                          fontSize: '14px',
                          color: '#555',
                          textAlign: 'center'
                        }}>
                          {liveLog}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* History Modal Window */}
                {showHistoryModal && (
                  <>
                    {/* Modal Overlay */}
                    <div
                      onClick={() => setShowHistoryModal(false)}
                      style={{
                        position: 'fixed',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        backgroundColor: 'rgba(0, 0, 0, 0.4)',
                        zIndex: 998,
                        animation: 'fadeIn 0.2s ease-out',
                        backdropFilter: 'blur(2px)'
                      }}
                    />

                    {/* Modal Window */}
                    <div style={{
                      position: 'fixed',
                      top: '50%',
                      left: '50%',
                      transform: 'translate(-50%, -50%)',
                      backgroundColor: 'white',
                      borderRadius: '12px',
                      width: '90%',
                      maxWidth: '750px',
                      maxHeight: '85vh',
                      overflow: 'auto',
                      zIndex: 999,
                      boxShadow: '0 20px 60px rgba(0, 0, 0, 0.25)',
                      animation: 'slideUp 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)'
                    }}>
                      {/* Modal Header */}
                      <div style={{
                        padding: '24px',
                        borderBottom: '1px solid #e5e7eb',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        backgroundColor: '#f9fafb',
                        position: 'sticky',
                        top: 0,
                        zIndex: 10
                      }}>
                        <h2 style={{ margin: 0, fontSize: '24px', color: '#1f2937', fontWeight: '700' }}>
                          📋 Validation History
                        </h2>
                        <button
                          onClick={() => setShowHistoryModal(false)}
                          style={{
                            background: 'none',
                            border: 'none',
                            fontSize: '28px',
                            cursor: 'pointer',
                            color: '#6b7280',
                            padding: '4px 8px',
                            transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                            borderRadius: '6px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                          }}
                          onMouseEnter={(e) => {
                            e.target.style.color = '#ef4444'
                            e.target.style.backgroundColor = '#fee2e2'
                          }}
                          onMouseLeave={(e) => {
                            e.target.style.color = '#6b7280'
                            e.target.style.backgroundColor = 'transparent'
                          }}
                        >
                          ✕
                        </button>
                      </div>

                      {/* Modal Content */}
                      <div style={{ padding: '24px' }}>
                        <History onSelectBrochure={handleSelectFromHistory} />
                      </div>
                    </div>
                  </>
                )}

                {/* Extracted Statements Preview */}
                {extractedStatements.length > 0 && (
                  <div className="statements-section">
                    <div className="statements-header">
                      <h2>Extracted Statements ({extractedStatements.length})</h2>
                    </div>

                    <div className="statements-table">
                      <table>
                        <thead>
                          <tr>
                            <th>Sr.No</th>
                            <th>Statement</th>
                            <th>Reference No</th>
                          </tr>
                        </thead>
                        <tbody>
                          {extractedStatements.map((stmt, idx) => (
                            <tr key={idx}>
                              <td>{idx + 1}</td>
                              <td className="statement-cell" title={stmt.statement}>
                                <span className="statement-text">{stmt.statement?.substring(0, 80)}...</span>
                              </td>
                              <td>{stmt.reference_no || stmt.id}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Results Summary */}
                {validationResults.length > 0 && !isValidating && (
                  <div className="results-section">
                    <ResultsSummary results={validationResults} />

                    {/* PDF Highlighter Section */}
                    <div className="pdf-highlighter-section">
                      <h3>Highlighted PDF Results</h3>
                      <p className="section-description">Green highlights = Supported | Red highlights = Not Found</p>
                      <PDFHighlighter pdfFile={brochureFile} validationResults={validationResults} />
                    </div>

                    {/* Filter Controls */}
                    <div className="filter-section">
                      <div className="filter-group">
                        <label>Filter by Result:</label>
                        <div className="filter-checkboxes">
                          {['Supported', 'Not Found'].map(status => (
                            <label key={status} className="checkbox-label">
                              <input
                                type="checkbox"
                                checked={resultFilter.includes(status)}
                                onChange={(e) => {
                                  if (e.target.checked) {
                                    setResultFilter([...resultFilter, status])
                                  } else {
                                    setResultFilter(resultFilter.filter(s => s !== status))
                                  }
                                }}
                              />
                              {status}
                            </label>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Detailed Results - Only show when filter is selected */}
                    {resultFilter.length > 0 && filteredResults.length > 0 && (
                      <>
                        <ValidationResults
                          results={filteredResults}
                          expandedResult={expandedResult}
                          setExpandedResult={setExpandedResult}
                          totalResults={validationResults.length}
                        />
                      </>
                    )}

                    {resultFilter.length > 0 && filteredResults.length === 0 && (
                      <div style={{ padding: '20px', backgroundColor: '#f9f9f9', borderRadius: '8px', marginTop: '20px' }}>
                        <p style={{ color: '#666', textAlign: 'center' }}>No results match the selected filter</p>
                      </div>
                    )}

                    {/* Download Section */}
                    <DownloadSection results={validationResults} />
                  </div>
                )}
              </div>

              <footer className="footer">
                <div className="footer-content">
                  <div className="footer-buttons">
                    {(brochureFile || referenceFiles.length > 0 || extractedStatements.length > 0 || validationResults.length > 0) && (
                      <button className="reset-btn" onClick={resetAll} disabled={isValidating}>
                        Reset All
                      </button>
                    )}
                  </div>
                </div>
              </footer>
            </>
          )}
        </main>
      </div>
    </ErrorBoundary>
  )
}

export default App
