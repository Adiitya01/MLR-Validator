import { useState, useRef, useEffect } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import '../styles/PDFHighlighter.css'
 
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min?url'
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker

export default function PDFHighlighter({ pdfFile, validationResults }) {
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(0)
  const [loading, setLoading] = useState(false)
  const [statementsOnPage, setStatementsOnPage] = useState([])
  const [selectedStatement, setSelectedStatement] = useState(null)
 
  const canvasRef = useRef(null)
  const containerRef = useRef(null)
  const overlayRef = useRef(null)
  const pdfDocRef = useRef(null)

  // Extract only the statement part (remove title)
  const getCleanStatement = (fullStatement) => {
    if (!fullStatement) return fullStatement
    
    const text = String(fullStatement).trim()
    
    // Split by period and take everything after first sentence (which is title)
    const parts = text.split('. ')
    if (parts.length > 1) {
      return parts.slice(1).join('. ').trim()
    }
    
    return text
  }
 
  useEffect(() => {
    if (!pdfFile) return
 
    const load = async () => {
      setLoading(true)
      const buffer = await pdfFile.arrayBuffer()
      const pdf = await pdfjsLib.getDocument({ data: buffer }).promise
      pdfDocRef.current = pdf
      setTotalPages(pdf.numPages)
      setCurrentPage(1)
      setLoading(false)
    }
 
    load()
  }, [pdfFile])
 
  useEffect(() => {
    if (!pdfDocRef.current) return
 
    const render = async () => {
      setLoading(true)

      const page = await pdfDocRef.current.getPage(currentPage)
      /* OLD CODE - Commented out
      const scale = 2.0
      */
      const scale = 0.9
      const viewport = page.getViewport({ scale })

      const canvas = canvasRef.current
      const ctx = canvas.getContext('2d')

      canvas.width = viewport.width
      canvas.height = viewport.height

      await page.render({ canvasContext: ctx, viewport }).promise

      const textContent = await page.getTextContent()

      // Show ALL statements on page (don't filter by page_no - it may not be set)
      // If page_no is not available, show all statements on every page
      const pageStatements = validationResults.filter(
        s => !s.page_no || s.page_no === currentPage || s.page_no === 1
      )
      setStatementsOnPage(pageStatements)

      drawCallouts({
        textContent,
        statements: pageStatements,
        viewport
      })
 
      setLoading(false)
    }
 
    render()
  }, [currentPage, validationResults])
 
  const drawCallouts = ({ textContent, statements, viewport }) => {
    console.log(`Processing ${statements.length} statements on page ${currentPage}`)
    
    if (overlayRef.current) overlayRef.current.remove()

    const overlay = document.createElement('div')
    overlay.className = 'page-highlight-overlay'
    overlay.style.cssText = `
      position: absolute;
      inset: 0;
      pointer-events: none;
      z-index: 20;
    `

    // Normalize text for matching
    const normalize = t =>
      t.toLowerCase().replace(/[^a-z0-9\s]/g, '').replace(/\s+/g, ' ').trim()

    // Find where statement appears in PDF
    function findStatementMatch(statement, items) {
      const stmtTokens = normalize(statement).split(' ').filter(Boolean)
      if (stmtTokens.length === 0) return null

      const flat = []
      items.forEach((item, idx) => {
        const tokens = normalize(item.str).split(' ').filter(Boolean)
        tokens.forEach(token => {
          flat.push({ token, idx, item })
        })
      })

      if (flat.length === 0) return null

      let bestMatch = { score: 0, indices: [], startIdx: -1 }

      for (let i = 0; i < flat.length; i++) {
        let matched = 0
        let indices = []

        for (let j = 0; j < stmtTokens.length && i + j < flat.length; j++) {
          if (flat[i + j].token === stmtTokens[j]) {
            matched++
            indices.push(flat[i + j].idx)
          }
        }

        const score = matched / stmtTokens.length

        if (score >= 0.5 && score > bestMatch.score) {
          bestMatch = { score, indices, startIdx: i }
        }
      }

      if (bestMatch.score >= 0.5) {
        const uniqueIndices = [...new Set(bestMatch.indices)]
        return uniqueIndices.map(i => items[i])
      }

      return null
    }

    const fragment = document.createDocumentFragment()

    statements.forEach((statement, idx) => {
      console.log(`Processing statement ${idx + 1}`)
      // CLEAN STATEMENT FIRST - remove title
      const cleanedStatement = getCleanStatement(statement.statement)
      
      // MATCH ONLY THE CLEANED STATEMENT (without title)
      let matches = findStatementMatch(cleanedStatement, textContent.items)
      
      if (!matches || !matches.length) {
        const circle = document.createElement('div')
        circle.className = 'statement-circle not-found'
        circle.textContent = idx + 1
        circle.style.cssText = `
          position: absolute;
          left: 0;
          top: 0;
          width: 17px;
          height: 17px;
          border-radius: 50%;
          background: #fff;
          border: 2px solid #ef4444;
          color: #ef4444;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: bold;
          font-size: 12px;
          z-index: 99;
          pointer-events: auto;
          cursor: pointer;
          transition: all 0.2s ease;
          box-shadow: 0 2px 6px rgba(0,0,0,0.15);
        `
        circle.title = cleanedStatement
        circle.addEventListener('click', () => setSelectedStatement(statement))
        circle.addEventListener('mouseenter', () => {
          circle.style.transform = 'scale(1.2)'
          circle.style.boxShadow = '0 4px 12px rgba(0,0,0,0.25)'
        })
        circle.addEventListener('mouseleave', () => {
          circle.style.transform = 'scale(1)'
          circle.style.boxShadow = '0 2px 6px rgba(0,0,0,0.15)'
        })
        fragment.appendChild(circle)
        return
      }

      // Found - place circle at matched location
      const first = matches[0]
      const [vx, vy] = viewport.convertToViewportPoint(
        first.transform[4],
        first.transform[5] - first.height * 0.8
      )

      const circle = document.createElement('div')
      circle.className = `statement-circle ${
        statement.validation_result === 'Supported' ? 'supported' : 'not-supported'
      }`
      circle.textContent = idx + 1
      circle.style.cssText = `
        position: absolute;
        left: ${(vx / viewport.width) * 100}%;
        top: ${(vy / viewport.height) * 100}%;
        width: 17px;
        height: 17px;
        border-radius: 50%;
        background: ${
          statement.validation_result === 'Supported' ||
          statement.validation_result === 'Strongly Supported'
            ? '#dcfce7'
            : '#fee2e2'
        };
        border: 2px solid ${
          statement.validation_result === 'Supported' ||
          statement.validation_result === 'Strongly Supported'
            ? '#22c55e'
            : '#ef4444'
        };
        color: ${
          statement.validation_result === 'Supported' ||
          statement.validation_result === 'Strongly Supported'
            ? '#22c55e'
            : '#ef4444'
        };
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 12px;
        z-index: 99;
        pointer-events: auto;
        cursor: pointer;
        transition: all 0.2s ease;
        box-shadow: 0 2px 6px rgba(0,0,0,0.15);
      `
      circle.title = cleanedStatement
      circle.addEventListener('click', () => setSelectedStatement(statement))
      circle.addEventListener('mouseenter', () => {
        circle.style.transform = 'scale(1.2)'
        circle.style.boxShadow = '0 4px 12px rgba(0,0,0,0.25)'
      })
      circle.addEventListener('mouseleave', () => {
        circle.style.transform = 'scale(1)'
        circle.style.boxShadow = '0 2px 6px rgba(0,0,0,0.15)'
      })
      fragment.appendChild(circle)
    })

    overlay.appendChild(fragment)
    containerRef.current.appendChild(overlay)
    overlayRef.current = overlay
    
    console.log(`Completed validation for ${statements.length} statements`)
  }
 
  return (
    <div className="pdf-highlighter">
      {!pdfFile ? (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: '300px',
          backgroundColor: '#f3f4f6',
          borderRadius: '8px',
          border: '2px dashed #d1d5db'
        }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '48px', marginBottom: '12px' }}>📄</div>
            <p style={{ margin: '0 0 8px 0', color: '#666', fontSize: '16px', fontWeight: '500' }}>
              PDF Not Available
            </p>
            <p style={{ margin: 0, color: '#999', fontSize: '14px' }}>
              Upload a new brochure to view highlighted PDF results
            </p>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', gap: '20px', width: '100%' }}>
          {/* PDF Viewer */}
          <div
            className="pdf-viewer"
            ref={containerRef}
            style={{
              position: 'relative',
              border: '1px solid #ccc',
              height: '70vh',
              width: 'auto',
              maxWidth: '70vw',
              overflow: 'hidden',
              margin: '0 auto',
              borderRadius: '8px'
            }}
          >
            {loading && <div style={{ padding: 20 }}>Loading…</div>}
            <canvas ref={canvasRef} style={{ width: '100%', height: '100%' }} />
          </div>

        {/* Statement Summary Panel */}
        {selectedStatement && (
          <div style={{
            width: '400px',
            height: '700px',
            border: '1px solid #ddd',
            borderRadius: '8px',
            backgroundColor: '#f9fafb',
            overflow: 'auto',
            padding: '20px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 600 }}>Statement Details</h3>
              <button
                onClick={() => setSelectedStatement(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '20px',
                  cursor: 'pointer',
                  color: '#666'
                }}
              >
                ×
              </button>
            </div>

            {/* Status Badge */}
            <div style={{ marginBottom: '16px' }}>
              <span style={{
                display: 'inline-block',
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 600,
                backgroundColor: getStatusBackgroundColor(selectedStatement.validation_result),
                color: getStatusTextColor(selectedStatement.validation_result)
              }}>
                {selectedStatement.validation_result}
              </span>
            </div>

            {/* Statement - SHOW CLEANED VERSION */}
            <div style={{ marginBottom: '16px' }}>
              <h4 style={{ margin: '0 0 8px 0', fontSize: '12px', fontWeight: 600, color: '#666', textTransform: 'uppercase' }}>Statement</h4>
              <p style={{ margin: 0, fontSize: '14px', lineHeight: '1.5', color: '#333' }}>
                {getCleanStatement(selectedStatement.statement)}
              </p>
            </div>

            {/* Confidence Score */}
            <div style={{ marginBottom: '16px' }}>
              <h4 style={{ margin: '0 0 8px 0', fontSize: '12px', fontWeight: 600, color: '#666', textTransform: 'uppercase' }}>Confidence</h4>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{
                  flex: 1,
                  height: '8px',
                  backgroundColor: '#e5e7eb',
                  borderRadius: '4px',
                  overflow: 'hidden'
                }}>
                  <div style={{
                    height: '100%',
                    width: `${(selectedStatement.confidence_score || 0) * 100}%`,
                    backgroundColor: (selectedStatement.confidence_score || 0) > 0.7 ? '#22c55e' : '#f59e0b',
                    transition: 'width 0.3s ease'
                  }} />
                </div>
                <span style={{ fontSize: '14px', fontWeight: 600, minWidth: '40px' }}>
                  {(selectedStatement.confidence_score || 0).toFixed(2)}
                </span>
              </div>
            </div>

            {/* Reference */}
            {selectedStatement.reference && (
              <div style={{ marginBottom: '16px' }}>
                <h4 style={{ margin: '0 0 8px 0', fontSize: '12px', fontWeight: 600, color: '#666', textTransform: 'uppercase' }}>Reference</h4>
                <p style={{ margin: 0, fontSize: '14px', lineHeight: '1.5', color: '#555' }}>
                  {selectedStatement.reference}
                </p>
              </div>
            )}

            {/* Matched Paper */}
            {selectedStatement.matched_paper && (
              <div style={{ marginBottom: '16px' }}>
                <h4 style={{ margin: '0 0 8px 0', fontSize: '12px', fontWeight: 600, color: '#666', textTransform: 'uppercase' }}>Matched Paper</h4>
                <p style={{ margin: 0, fontSize: '14px', lineHeight: '1.5', color: '#555' }}>
                  {selectedStatement.matched_paper}
                </p>
              </div>
            )}

            {/* Evidence */}
            {selectedStatement.matched_evidence && (
              <div style={{ marginBottom: '16px' }}>
                <h4 style={{ margin: '0 0 8px 0', fontSize: '12px', fontWeight: 600, color: '#666', textTransform: 'uppercase' }}>Evidence Found</h4>
                <div style={{
                  backgroundColor: '#fff',
                  border: '1px solid #e5e7eb',
                  borderRadius: '6px',
                  padding: '12px',
                  fontSize: '13px',
                  lineHeight: '1.6',
                  color: '#333',
                  maxHeight: '150px',
                  overflow: 'auto'
                }}>
                  {selectedStatement.matched_evidence}
                </div>
              </div>
            )}

            {/* Page Location */}
            {selectedStatement.page_location && (
              <div style={{ marginBottom: '16px' }}>
                <h4 style={{ margin: '0 0 8px 0', fontSize: '12px', fontWeight: 600, color: '#666', textTransform: 'uppercase' }}>Page Location</h4>
                <p style={{ margin: 0, fontSize: '14px', color: '#555' }}>
                  {selectedStatement.page_location}
                </p>
              </div>
            )}

            {/* Matching Method */}
            {selectedStatement.matching_method && (
              <div>
                <h4 style={{ margin: '0 0 8px 0', fontSize: '12px', fontWeight: 600, color: '#666', textTransform: 'uppercase' }}>Matching Method</h4>
                <p style={{ margin: 0, fontSize: '13px', lineHeight: '1.5', color: '#555' }}>
                  {selectedStatement.matching_method}
                </p>
              </div>
            )}
          </div>
        )}
        
        {/* Controls */}
        <div className="pdf-controls" style={{ marginTop: '20px', display: 'flex', gap: '10px', justifyContent: 'center' }}>
          <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))}>
            ← Prev
          </button>
          <span>
            Page {currentPage} / {totalPages}
          </span>
          <button
            onClick={() =>
              setCurrentPage(p => Math.min(totalPages, p + 1))
            }
          >
            Next →
          </button>
        </div>
      </div>
      )}
    </div>
  )
}

function getStatusBackgroundColor(status) {
  switch (status) {
    case 'Supported':
    case 'Strongly Supported':
      return '#dcfce7'
    case 'Partially Supported':
      return '#fef08a'
    case 'Contradicted':
      return '#fee2e2'
    case 'Not Found':
      return '#f3f4f6'
    default:
      return '#f3f4f6'
  }
}

function getStatusTextColor(status) {
  switch (status) {
    case 'Supported':
    case 'Strongly Supported':
      return '#166534'
    case 'Partially Supported':
      return '#854d0e'
    case 'Contradicted':
      return '#b91c1c'
    case 'Not Found':
      return '#6b7280'
    default:
      return '#6b7280'
  }
}