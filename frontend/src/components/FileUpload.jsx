import React, { useState } from 'react';

const FileUpload = ({ onFileSelect }) => {
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = (selectedFile) => {
    if (!selectedFile.name.endsWith('.docx')) {
      alert('Пожалуйста, выберите файл .docx');
      return;
    }
    
    setFile(selectedFile);
    if (onFileSelect) {
      onFileSelect(selectedFile);
    }
  };

  const removeFile = () => {
    setFile(null);
    if (onFileSelect) {
      onFileSelect(null);
    }
  };

  return (
    <div className="card">
      <h2>Загрузка документа</h2>
      
      <div
        className={`file-upload ${dragActive ? 'active' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => document.getElementById('file-input').click()}
      >
        <input
          id="file-input"
          type="file"
          accept=".docx"
          onChange={handleChange}
        />
        <div>
          <svg
            width="64"
            height="64"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            style={{ margin: '0 auto 15px', display: 'block', color: '#667eea' }}
          >
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          <p style={{ fontSize: '1.1rem', marginBottom: '10px' }}>
            <strong>Перетащите файл сюда</strong> или кликните для выбора
          </p>
          <p style={{ color: '#718096', fontSize: '0.9rem' }}>
            Поддерживаются файлы .docx до 50MB
          </p>
        </div>
      </div>

      {file && (
        <div className="file-info">
          <div>
            <strong>{file.name}</strong>
            <p style={{ color: '#718096', fontSize: '0.9rem', marginTop: '5px' }}>
              {(file.size / 1024 / 1024).toFixed(2)} MB
            </p>
          </div>
          <button className="btn btn-secondary" onClick={removeFile}>
            Удалить
          </button>
        </div>
      )}
    </div>
  );
};

export default FileUpload;
