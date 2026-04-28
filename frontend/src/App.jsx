import React, { useEffect, useState } from 'react';
import FileUpload from './components/FileUpload';
import ModelSettings from './components/ModelSettings';
import Results from './components/Results';
import { uploadDocument, analyzeDocument, getSettings, saveSettings } from './services/api';

const defaultLlmSettings = {
  openai: {
    apiKey: '',
    model: 'gpt-4.1-mini'
  },
  anthropic: {
    apiKey: '',
    model: 'claude-3-5-sonnet-20241022'
  },
  custom: {
    apiBase: 'http://host.docker.internal:11434/v1',
    apiKey: 'ollama',
    model: 'llama2'
  }
};

const getInitialModelSettings = () => {
  return {
    provider: 'openai',
    ...defaultLlmSettings.openai
  };
};

function App() {
  const [file, setFile] = useState(null);
  const [uploadedFileId, setUploadedFileId] = useState(null);
  const [uploadInfo, setUploadInfo] = useState(null);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [instructions, setInstructions] = useState('');
  const [modelSettings, setModelSettings] = useState(getInitialModelSettings);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [report, setReport] = useState(null);
  const [reportId, setReportId] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('upload');

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const saved = await getSettings();
        const loadedSettings = {
          provider: saved.provider,
          apiKey: saved.api_key || '',
          model: saved.model,
          apiBase: saved.api_base || ''
        };
        setModelSettings(loadedSettings);
      } catch (err) {
        console.error('Settings load error:', err);
      }
    };

    loadSettings();
  }, []);

  const handleFileSelect = async (selectedFile) => {
    setFile(selectedFile);
    setUploadedFileId(null);
    setUploadInfo(null);
    setError(null);

    if (!selectedFile) {
      return;
    }

    setUploadingFile(true);
    try {
      await saveSettings(modelSettings);
      const uploadResult = await uploadDocument(selectedFile);
      setUploadedFileId(uploadResult.file_id);
      setUploadInfo(uploadResult);
    } catch (err) {
      console.error('Upload error:', err);
      setError(err.response?.data?.detail || err.message || 'Произошла ошибка при загрузке');
      setFile(null);
    } finally {
      setUploadingFile(false);
    }
  };

  const handleAnalyze = async () => {
    if (!file) {
      alert('Пожалуйста, выберите файл');
      return;
    }

    if (!uploadedFileId) {
      alert('Дождитесь загрузки файла');
      return;
    }

    if (!instructions.trim()) {
      alert('Пожалуйста, введите инструкции для анализа');
      return;
    }

    setLoading(true);
    setError(null);
    setProgress(0);
    setProgressMessage('Загрузка файла...');

    try {
      setProgress(10);
      setProgressMessage('Сохранение настроек модели...');
      await saveSettings(modelSettings);

      setProgress(30);
      setProgressMessage('Анализ документа...');
      
      const analysisResult = await analyzeDocument(uploadedFileId, instructions);
      
      setProgress(100);
      setProgressMessage('Анализ завершён');
      
      setReport(analysisResult.report || analysisResult.summary);
      setReportId(analysisResult.report_id);
      setActiveTab('results');

    } catch (err) {
      console.error('Analysis error:', err);
      setError(err.response?.data?.detail || err.message || 'Произошла ошибка при анализе');
    } finally {
      setLoading(false);
    }
  };

  const resetAnalysis = () => {
    setFile(null);
    setUploadedFileId(null);
    setUploadInfo(null);
    setInstructions('');
    setReport(null);
    setReportId(null);
    setError(null);
    setProgress(0);
    setProgressMessage('');
    setActiveTab('upload');
  };

  return (
    <div>
      <div className="header">
        <div className="container">
          <h1>Document Analyzer</h1>
        </div>
      </div>

      <div className="container">
        <div className="tabs">
          <button 
            className={`tab ${activeTab === 'upload' ? 'active' : ''}`}
            onClick={() => setActiveTab('upload')}
          >
            Загрузка и анализ
          </button>
          <button 
            className={`tab ${activeTab === 'settings' ? 'active' : ''}`}
            onClick={() => setActiveTab('settings')}
          >
            Настройки модели
          </button>
          {report && (
            <button 
              className={`tab ${activeTab === 'results' ? 'active' : ''}`}
              onClick={() => setActiveTab('results')}
            >
              Результаты
            </button>
          )}
        </div>

        {error && (
          <div className="alert alert-error">
            <strong>Ошибка:</strong> {error}
          </div>
        )}

        {activeTab === 'upload' && (
          <>
            <FileUpload onFileSelect={handleFileSelect} />

            {uploadingFile && (
              <div className="card">
                <div className="loading">
                  <div className="spinner"></div>
                  <p>Загрузка документа и подсчёт токенов...</p>
                </div>
              </div>
            )}

            {uploadInfo?.token_estimation && (
              <div className="card">
                <h2>Оценка токенов и контекста</h2>
                <div className="token-grid">
                  <div className="token-metric">
                    <div className="token-value">{uploadInfo.token_estimation.document_tokens.toLocaleString()}</div>
                    <div className="token-label">Токенов в документе</div>
                  </div>
                  <div className="token-metric">
                    <div className="token-value">{uploadInfo.token_estimation.total_estimated_tokens.toLocaleString()}</div>
                    <div className="token-label">Примерно токенов на анализ</div>
                  </div>
                  <div className="token-metric">
                    <div className="token-value">{uploadInfo.token_estimation.total_chunks}</div>
                    <div className="token-label">Частей документа</div>
                  </div>
                  <div className="token-metric">
                    <div className="token-value">{uploadInfo.token_estimation.context.chunk_context_limit_tokens.toLocaleString()}</div>
                    <div className="token-label">Контекст на часть</div>
                  </div>
                  <div className="token-metric">
                    <div className="token-value">{uploadInfo.token_estimation.context.model_context_window_tokens.toLocaleString()}</div>
                    <div className="token-label">Контекст модели</div>
                  </div>
                  <div className="token-metric">
                    <div className="token-value">
                      {uploadInfo.token_estimation.selected_model_estimate
                        ? `$${uploadInfo.token_estimation.selected_model_estimate.total_cost}`
                        : 'Локально'}
                    </div>
                    <div className="token-label">Оценка стоимости</div>
                  </div>
                </div>
                <p className="token-note">
                  Провайдер: {uploadInfo.token_estimation.provider}, модель: {uploadInfo.token_estimation.model}.
                  Оценка включает текст документа, служебные инструкции и примерный ответ модели.
                </p>
              </div>
            )}

            <div className="card">
              <h2>Инструкции для анализа</h2>
              <div className="form-group">
                <label>Что нужно проверить в документе?</label>
                <textarea
                  placeholder="Например: Проверь документ на грамматические ошибки, логические несоответствия и соответствие научному стилю изложения."
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                />
              </div>

              <div style={{ marginTop: '20px' }}>
                <strong>Примеры инструкций:</strong>
                <ul style={{ marginTop: '10px', marginLeft: '20px', color: '#718096' }}>
                  <li>Проверь на грамматические ошибки и опечатки</li>
                  <li>Найди логические несоответствия и противоречия</li>
                  <li>Проверь соответствие научному стилю изложения</li>
                  <li>Оцени структуру документа и последовательность изложения</li>
                </ul>
              </div>
            </div>

            {loading && (
              <div className="card">
                <div className="loading">
                  <div className="spinner"></div>
                  <p>{progressMessage}</p>
                </div>
                <div className="progress-bar">
                  <div 
                    className="progress-bar-fill" 
                    style={{ width: `${progress}%` }}
                  ></div>
                </div>
                <div className="progress-text">{progress}%</div>
              </div>
            )}

            <div style={{ display: 'flex', gap: '10px', marginTop: '20px' }}>
              <button 
                className="btn btn-primary" 
                onClick={handleAnalyze}
                disabled={loading || uploadingFile || !file || !uploadedFileId || !instructions.trim()}
              >
                {loading ? 'Анализ...' : 'Анализировать документ'}
              </button>
              
              {report && (
                <button 
                  className="btn btn-secondary" 
                  onClick={resetAnalysis}
                >
                  Новый анализ
                </button>
              )}
            </div>
          </>
        )}

        {activeTab === 'settings' && (
          <ModelSettings onSettingsChange={setModelSettings} />
        )}

        {activeTab === 'results' && (
          <Results report={report} reportId={reportId} />
        )}
      </div>
    </div>
  );
}

export default App;
