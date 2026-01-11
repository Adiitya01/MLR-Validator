// import '../styles/ValidationResults.css'

// export default function ValidationResults({ results, expandedResult, setExpandedResult, totalResults }) {
//   // Safety check
//   if (!results || !Array.isArray(results)) {
//     console.error('[ValidationResults] Invalid results prop:', results)
//     return <div className="validation-results"><p>Error: Invalid results data</p></div>
//   }

//   console.log('[ValidationResults] Rendering with:', {
//     resultsCount: results.length,
//     expandedResult,
//     totalResults,
//     firstResult: results[0] || null
//   })

//   const getStatusColor = (status) => {
//     switch (status) {
//       case 'Supported':
//       case 'Strongly Supported':
//         return '#d4edda'
//       case 'Partially Supported':
//         return '#fff3cd'
//       case 'Contradicted':
//         return '#f8d7da'
//       case 'Not Found':
//         return '#f8f9fa'
//       default:
//         return '#e2e3e5'
//     }
//   }

//   const getStatusEmoji = (status) => {
//     switch (status) {
//       case 'Supported':
//       case 'Strongly Supported':
//         return '✓'
//       case 'Partially Supported':
//         return '◐'
//       case 'Contradicted':
//         return '✗'
//       case 'Not Found':
//         return '○'
//       default:
//         return '?'
//     }
//   }

//   // Log evidence data for debugging
//   React.useEffect(() => {
//     if (results && results.length > 0 && expandedResult !== null) {
//       const expandedResult_data = results[expandedResult]
//       console.log(`[DEBUG] Expanded result #${expandedResult}:`, {
//         statement: expandedResult_data.statement,
//         validation_result: expandedResult_data.validation_result,
//         matched_evidence: expandedResult_data.matched_evidence,
//         matched_evidence_length: expandedResult_data.matched_evidence?.length || 0,
//         matched_paper: expandedResult_data.matched_paper
//       })
//     }
//   }, [expandedResult, results])

//   return (
//     <div className="validation-results">
//       <div className="results-header">
//         <h2>Detailed Results</h2>
//         <p className="results-info">Showing {results.length} of {totalResults} results</p>
//       </div>

//       <div className="results-list">
//         {results.map((result, index) => {
//           try {
//             return (
//               <div key={index} className="result-item">
//                 <div
//                   className="result-header"
//                   onClick={() => setExpandedResult(expandedResult === index ? null : index)}
//                   style={{ backgroundColor: getStatusColor(result.validation_result) }}
//                 >
//                   <div className="result-title">
//                     <span className="status-emoji">{getStatusEmoji(result.validation_result || 'Error')}</span>
//                     <span className="result-number">{index + 1}.</span>
//                     <span className="result-text">{(result.statement && typeof result.statement === 'string') ? result.statement.substring(0, 100) : 'Unknown'}...</span>
//                   </div>
//                   <div className="result-meta">
//                     <span className="confidence">Confidence: {((result.confidence_score !== undefined && result.confidence_score !== null) ? result.confidence_score : 0).toFixed(2)}</span>
//                     <span className="status-badge">{result.validation_result || 'Unknown'}</span>
//                   </div>
//                 </div>

//                 {expandedResult === index && (
//                   <div className="result-details">
//                     <div className="detail-section">
//                       <h4>Statement</h4>
//                       <p>{(result.statement && typeof result.statement === 'string') ? result.statement : 'N/A'}</p>
//                     </div>

//                     <div className="detail-section">
//                       <h4>Confidence</h4>
//                       <p><strong>{((result.confidence_score !== undefined && result.confidence_score !== null) ? result.confidence_score : 0).toFixed(2)}</strong> ({((result.confidence_score !== undefined && result.confidence_score !== null) ? result.confidence_score : 0).toLocaleString('en-US', {style: 'percent'})})</p>
//                     </div>

//                     <div className="detail-section">
//                       <h4>Matched Paper</h4>
//                       <p>{(result.matched_paper && typeof result.matched_paper === 'string') ? result.matched_paper : 'N/A'}</p>
//                     </div>

//                     <div className="detail-section evidence">
//                       <h4>Supported Evidence</h4>
//                       <div className="evidence-box">
//                         {(() => {
//                           try {
//                             const evidence = result.matched_evidence
//                             if (evidence && typeof evidence === 'string' && evidence.trim().length > 0) {
//                               return evidence.split('\n').filter(line => line.trim()).map((line, idx) => (
//                                 <div key={idx} style={{marginBottom: '8px', padding: '10px', backgroundColor: '#f9f9f9', borderLeft: '3px solid #27ae60', marginLeft: '0', paddingLeft: '15px'}}>
//                                   {line}
//                                 </div>
//                               ))
//                             } else {
//                               return <p style={{color: '#999'}}>No evidence found</p>
//                             }
//                           } catch (e) {
//                             console.error('[ValidationResults] Error rendering evidence:', e, { evidence: result.matched_evidence })
//                             return <p style={{color: '#c00'}}>Error displaying evidence</p>
//                           }
//                         })()}
//                       </div>
//                     </div>

//                     {result.matching_method && (
//                       <div className="detail-section">
//                         <h4>Matching Method</h4>
//                         <p className="method-text">{result.matching_method}</p>
//                       </div>
//                     )}

//                     {result.page_location && (
//                       <div className="detail-section">
//                         <h4>Page Location</h4>
//                         <p>{result.page_location}</p>
//                       </div>
//                     )}

//                     {result.reference && (
//                       <div className="detail-section">
//                         <h4>Reference</h4>
//                         <p>{result.reference}</p>
//                       </div>
//                     )}

//                     <div className="detail-meta">
//                       <span>Reference No: {result.reference_no || 'N/A'}</span>
//                       <span>Confidence: {((result.confidence_score !== undefined && result.confidence_score !== null) ? result.confidence_score : 0).toFixed(2)}</span>
//                     </div>

//                     <div className="confidence-bar">
//                       <div
//                         className="confidence-fill"
//                         style={{
//                           width: `${((result.confidence_score !== undefined && result.confidence_score !== null) ? result.confidence_score : 0) * 100}%`,
//                           backgroundColor: ((result.confidence_score !== undefined && result.confidence_score !== null) ? result.confidence_score : 0) > 0.7 ? '#27ae60' : ((result.confidence_score !== undefined && result.confidence_score !== null) ? result.confidence_score : 0) > 0.4 ? '#f39c12' : '#e74c3c'
//                         }}
//                       ></div>
//                     </div>
//                   </div>
//                 )}
//               </div>
//             )
//           } catch (error) {
//             console.error(`[ValidationResults] Error rendering result #${index}:`, error, result)
//             return (
//               <div key={index} className="result-item">
//                 <div className="result-header" style={{ backgroundColor: '#f8d7da' }}>
//                   <div className="result-title">
//                     <span className="status-emoji">!</span>
//                     <span className="result-number">{index + 1}.</span>
//                     <span className="result-text">Error rendering result</span>
//                   </div>
//                 </div>
//               </div>
//             )
//           }
//         })}
//       </div>
//     </div>
//   )
// }


export default function ValidationResults({ results, expandedResult, setExpandedResult, totalResults }) {
  const getStatusColor = (status) => {
    switch (status) {
      case 'Supported':
      case 'Strongly Supported':
        return '#d4edda'
      case 'Partially Supported':
        return '#fff3cd'
      case 'Contradicted':
        return '#f8d7da'
      case 'Not Found':
        return '#f8f9fa'
      default:
        return '#e2e3e5'
    }
  }

  const getStatusEmoji = (status) => {
    switch (status) {
      case 'Supported':
      case 'Strongly Supported':
        return '✓'
      case 'Partially Supported':
        return '◐'
      case 'Contradicted':
        return '✗'
      case 'Not Found':
        return '○'
      default:
        return '?'
    }
  }

  return (
    <div className="validation-results">
      <div className="results-header">
        <h2>Detailed Results</h2>
        <p className="results-info">Showing {results.length} of {totalResults} results</p>
      </div>

      <div className="results-list">
        {results.map((result, index) => (
          <div key={index} className="result-item">
            <div
              className="result-header"
              onClick={() => setExpandedResult(expandedResult === index ? null : index)}
              style={{ backgroundColor: getStatusColor(result.validation_result) }}
            >
              <div className="result-title">
                <span className="status-emoji">{getStatusEmoji(result.validation_result)}</span>
                <span className="result-number">{index + 1}.</span>
                <span className="result-text">{result.statement?.substring(0, 100)}...</span>
              </div>
              <div className="result-meta">
                <span className="confidence">Confidence: {(result.confidence_score || 0).toFixed(2)}</span>
                <span className="status-badge">{result.validation_result}</span>
              </div>
            </div>

            {expandedResult === index && (
              <div className="result-details">
                <div className="detail-section">
                  <h4>Statement</h4>
                  <p>{result.statement}</p>
                </div>

                <div className="detail-section">
                  <h4>Reference</h4>
                  <p>{result.reference}</p>
                </div>

                <div className="detail-section">
                  <h4>Matched Paper</h4>
                  <p>{result.matched_paper}</p>
                </div>

                {result.matching_method && (
                  <div className="detail-section">
                    <h4>Matching Method</h4>
                    <p className="method-text">{result.matching_method}</p>
                  </div>
                )}

                {result.matched_evidence && (
                  <div className="detail-section evidence">
                    <h4>Evidence Found</h4>
                    <div className="evidence-box">
                      {result.matched_evidence}
                    </div>
                  </div>
                )}

                {result.page_location && (
                  <div className="detail-section">
                    <h4>Page Location</h4>
                    <p>{result.page_location}</p>
                  </div>
                )}

                <div className="detail-meta">
                  <span>Reference No: {result.reference_no}</span>
                  <span>Confidence: {(result.confidence_score || 0).toFixed(2)}</span>
                </div>

                <div className="confidence-bar">
                  <div
                    className="confidence-fill"
                    style={{
                      width: `${(result.confidence_score || 0) * 100}%`,
                      backgroundColor: (result.confidence_score || 0) > 0.7 ? '#27ae60' : (result.confidence_score || 0) > 0.4 ? '#f39c12' : '#e74c3c'
                    }}
                  ></div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
