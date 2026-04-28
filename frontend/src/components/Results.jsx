import React from 'react';
import { downloadReport } from '../services/api';

const Results = ({ report, reportId }) => {
  if (!report) return null;

  const handleDownload = async (format) => {
    try {
      await downloadReport(reportId, format);
    } catch (error) {
      console.error('Download error:', error);
      alert('Ошибка при скачивании отчёта');
    }
  };

  const highCount = report.chunk_analyses?.reduce((acc, chunk) => 
    acc + chunk.findings.filter(f => f.severity === 'high').length, 0) || 0;
  
  const mediumCount = report.chunk_analyses?.reduce((acc, chunk) => 
    acc + chunk.findings.filter(f => f.severity === 'medium').length, 0) || 0;
  
  const lowCount = report.chunk_analyses?.reduce((acc, chunk) => 
    acc + chunk.findings.filter(f => f.severity === 'low').length, 0) || 0;

  const allFindings = report.chunk_analyses?.flatMap((chunk, idx) => 
    chunk.findings.map(finding => ({ ...finding, chunkId: chunk.chunk_id }))
  ) || [];

  return (
    <div>
      <div className="card">
        <h2>Результаты анализа</h2>
        
        <div className="stats">
          <div className="stat-card">
            <div className="stat-value">{report.total_chunks}</div>
            <div className="stat-label">Частей документа</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{report.total_findings}</div>
            <div className="stat-label">Всего проблем</div>
          </div>
          <div className="stat-card">
            <div className="stat-value stat-high">{highCount}</div>
            <div className="stat-label">Высокая серьёзность</div>
          </div>
          <div className="stat-card">
            <div className="stat-value stat-medium">{mediumCount}</div>
            <div className="stat-label">Средняя серьёзность</div>
          </div>
          <div className="stat-card">
            <div className="stat-value stat-low">{lowCount}</div>
            <div className="stat-label">Низкая серьёзность</div>
          </div>
        </div>

        <div className="download-buttons">
          <button className="btn btn-primary" onClick={() => handleDownload('json')}>
            Скачать JSON
          </button>
          <button className="btn btn-primary" onClick={() => handleDownload('docx')}>
            Скачать DOCX
          </button>
          <button className="btn btn-primary" onClick={() => handleDownload('html')}>
            Скачать HTML
          </button>
        </div>
      </div>

      {report.global_analysis && (
        <div className="card">
          <h2>Глобальный анализ</h2>
          
          <div style={{ marginBottom: '20px' }}>
            <h3 style={{ marginBottom: '10px' }}>Общее резюме</h3>
            <p>{report.global_analysis.overall_summary}</p>
          </div>

          {report.global_analysis.document_structure_issues?.length > 0 && (
            <div style={{ marginBottom: '20px' }}>
              <h3 style={{ marginBottom: '10px' }}>Проблемы структуры</h3>
              <ul style={{ marginLeft: '20px' }}>
                {report.global_analysis.document_structure_issues.map((issue, idx) => (
                  <li key={idx} style={{ marginBottom: '5px' }}>{issue}</li>
                ))}
              </ul>
            </div>
          )}

          {report.global_analysis.consistency_issues?.length > 0 && (
            <div style={{ marginBottom: '20px' }}>
              <h3 style={{ marginBottom: '10px' }}>Проблемы согласованности</h3>
              <ul style={{ marginLeft: '20px' }}>
                {report.global_analysis.consistency_issues.map((issue, idx) => (
                  <li key={idx} style={{ marginBottom: '5px' }}>{issue}</li>
                ))}
              </ul>
            </div>
          )}

          {report.global_analysis.recommendations?.length > 0 && (
            <div>
              <h3 style={{ marginBottom: '10px' }}>Рекомендации</h3>
              <ul style={{ marginLeft: '20px' }}>
                {report.global_analysis.recommendations.map((rec, idx) => (
                  <li key={idx} style={{ marginBottom: '5px' }}>{rec}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="card">
        <h2>Найденные проблемы</h2>
        
        {allFindings.length === 0 ? (
          <div className="alert alert-success">
            Проблем не найдено. Документ выглядит хорошо.
          </div>
        ) : (
          <div className="findings">
            {allFindings.map((finding, idx) => (
              <div key={idx} className={`finding-item ${finding.severity}`}>
                <div className="finding-header">
                  <div>
                    <span className="finding-type">{finding.issue_type}</span>
                    <span style={{ color: '#718096', marginLeft: '10px' }}>
                      Часть {finding.chunkId}
                    </span>
                  </div>
                  <span className={`severity-badge ${finding.severity}`}>
                    {finding.severity}
                  </span>
                </div>
                
                <div className="finding-quote">
                  "{finding.quote}"
                </div>
                
                <div className="finding-problem">
                  <strong>Проблема:</strong> {finding.problem}
                </div>
                
                <div className="finding-recommendation">
                  <strong>Рекомендация:</strong> {finding.recommendation}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Results;
