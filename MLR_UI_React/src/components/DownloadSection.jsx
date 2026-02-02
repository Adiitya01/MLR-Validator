export default function DownloadSection({ results }) {
  const downloadExcel = () => {
    // Convert results to CSV format
    const headers = ['Statement', 'Reference No', 'Reference', 'Matched Paper', 'Validation Result', 'Confidence Score', 'Matched Evidence', 'Page Location', 'Matching Method']

    const rows = results.map(r => [
      `"${(r.statement || '').replace(/"/g, '""')}"`,
      r.reference_no || '',
      `"${(r.reference || '').replace(/"/g, '""')}"`,
      r.matched_paper || '',
      r.validation_result || '',
      (r.confidence_score || 0).toFixed(3),
      `"${(r.matched_evidence || '').replace(/"/g, '""')}"`,
      `"${(r.page_location || '').replace(/"/g, '""')}"`,
      `"${(r.matching_method || '').replace(/"/g, '""')}"`
    ])

    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `validation_results_${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
  }

  const downloadJSON = () => {
    const json = JSON.stringify(results, null, 2)
    const blob = new Blob([json], { type: 'application/json;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `validation_results_${new Date().toISOString().slice(0, 10)}.json`
    link.click()
  }

  const downloadExcelReport = () => {
    // Create a more detailed Excel-like CSV with summary
    const summary = {
      total: results.length,
      supported: results.filter(r => r.validation_result === 'Supported').length,
      uncited: results.filter(r => r.validation_result === 'Uncited').length,
      notFound: results.filter(r => r.validation_result === 'Not Found').length,
      avgConfidence: (results.reduce((sum, r) => sum + (r.confidence_score || 0), 0) / (results.length || 1)).toFixed(3)
    }

    let csv = 'SUMMARY\n'
    csv += `Total Results,${summary.total}\n`
    csv += `Supported,${summary.supported}\n`
    csv += `Uncited,${summary.uncited}\n`
    csv += `Not Found,${summary.notFound}\n`
    csv += `Average Confidence,${summary.avgConfidence}\n\n\n`

    csv += 'DETAILED RESULTS\n'
    const headers = ['Statement', 'Reference No', 'Reference', 'Matched Paper', 'Validation Result', 'Confidence Score', 'Matched Evidence']
    csv += headers.join(',') + '\n'

    results.forEach(r => {
      const row = [
        `"${(r.statement || '').replace(/"/g, '""')}"`,
        r.reference_no || '',
        `"${(r.reference || '').replace(/"/g, '""')}"`,
        r.matched_paper || '',
        r.validation_result || '',
        (r.confidence_score || 0).toFixed(3),
        `"${(r.matched_evidence || '').substring(0, 500).replace(/"/g, '""')}"`
      ]
      csv += row.join(',') + '\n'
    })

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `validation_results_detailed_${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
  }

  return (
    <div className="download-section">
      <h2>Download Results</h2>
      <div className="download-buttons">
        <button className="download-btn excel-btn" onClick={downloadExcelReport}>
          <span>📊</span> Download Excel (Full Report)
        </button>
        <button className="download-btn json-btn" onClick={downloadJSON}>
          <span>📄</span> Download JSON
        </button>
        <button className="download-btn csv-btn" onClick={downloadExcel}>
          <span>📋</span> Download CSV
        </button>
      </div>
    </div>
  )
}
