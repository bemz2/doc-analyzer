import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const uploadDocument = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return response.data;
};

export const analyzeDocument = async (fileId, instructions) => {
  const formData = new FormData();
  formData.append('instructions', instructions);
  
  const response = await api.post(`/analyze/${fileId}`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return response.data;
};

export const getSettings = async () => {
  const response = await api.get('/settings');
  return response.data;
};

export const saveSettings = async (settings) => {
  const response = await api.post('/settings', {
    provider: settings.provider,
    api_key: settings.apiKey || '',
    model: settings.model,
    api_base: settings.apiBase || null,
  });
  return response.data;
};

export const getReport = async (reportId) => {
  const response = await api.get(`/report/${reportId}`);
  return response.data;
};

export const downloadReport = async (reportId, format) => {
  const response = await api.get(`/download/${reportId}/${format}`, {
    responseType: 'blob',
  });
  
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `report.${format}`);
  document.body.appendChild(link);
  link.click();
  link.remove();
};

export const getProgress = async (fileId) => {
  const response = await api.get(`/progress/${fileId}`);
  return response.data;
};

export default api;
