import React, { useState, useEffect } from 'react';
import { getSettings, saveSettings } from '../services/api';

const defaultSettings = {
  openai: {
    apiKey: '',
    model: 'gpt-4o-mini'
  },
  anthropic: {
    apiKey: '',
    model: 'claude-3-5-sonnet-20241022'
  },
  custom: {
    apiBase: 'http://host.docker.internal:11434/v1',
    apiKey: '',
    model: 'llama2'
  }
};

const providerDefaults = {
  openai: defaultSettings.openai,
  anthropic: defaultSettings.anthropic,
  custom: defaultSettings.custom
};

const ModelSettings = ({ onSettingsChange }) => {
  const [provider, setProvider] = useState('openai');
  const [settings, setSettings] = useState(defaultSettings);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState('');

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const saved = await getSettings();
        const savedProvider = saved.provider || 'openai';
        const nextSettings = {
          ...defaultSettings,
          [savedProvider]: {
            ...providerDefaults[savedProvider],
            apiKey: saved.api_key || '',
            apiBase: saved.api_base || providerDefaults[savedProvider]?.apiBase || '',
            model: saved.model || providerDefaults[savedProvider]?.model || ''
          }
        };

        if (nextSettings.openai.model === 'gpt-4-turbo-preview' || nextSettings.openai.model === 'gpt-4.1-mini') {
          nextSettings.openai.model = 'gpt-4o-mini';
        }

        setProvider(savedProvider);
        setSettings(nextSettings);
        if (onSettingsChange) {
          onSettingsChange({
            provider: savedProvider,
            ...nextSettings[savedProvider]
          });
        }
      } catch (error) {
        console.error('Settings load error:', error);
        setStatus('Не удалось загрузить настройки из БД');
      }
    };

    loadSettings();
  }, [onSettingsChange]);

  const handleProviderChange = (newProvider) => {
    setProvider(newProvider);
    setStatus('');
    if (onSettingsChange) {
      onSettingsChange({
        provider: newProvider,
        ...settings[newProvider]
      });
    }
  };

  const handleSettingChange = (field, value) => {
    setStatus('');
    const newSettings = {
      ...settings,
      [provider]: {
        ...settings[provider],
        [field]: value
      }
    };
    setSettings(newSettings);
    
    if (onSettingsChange) {
      onSettingsChange({
        provider,
        ...newSettings[provider]
      });
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setStatus('');
    try {
      await saveSettings({
        provider,
        ...settings[provider]
      });
      setStatus('Настройки сохранены в БД');
    } catch (error) {
      console.error('Settings save error:', error);
      setStatus(error.response?.data?.detail || 'Не удалось сохранить настройки');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card">
      <h2>Настройки модели</h2>
      
      <div className="form-group">
        <label>Провайдер LLM</label>
        <select 
          value={provider} 
          onChange={(e) => handleProviderChange(e.target.value)}
        >
          <option value="openai">OpenAI</option>
          <option value="anthropic">Anthropic Claude</option>
          <option value="custom">Локальная модель</option>
        </select>
      </div>

      {provider === 'openai' && (
        <div className="settings-grid">
          <div className="form-group">
            <label>OpenAI API Key</label>
            <input
              type="password"
              placeholder="sk-..."
              value={settings.openai.apiKey}
              onChange={(e) => handleSettingChange('apiKey', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Название модели</label>
            <input
              type="text"
              placeholder="gpt-4o-mini, gpt-4o, gpt-4-turbo, gpt-4"
              value={settings.openai.model}
              onChange={(e) => handleSettingChange('model', e.target.value)}
            />
            <small style={{ color: '#718096', marginTop: '5px', display: 'block' }}>
              Популярные: gpt-4o-mini (рекомендуется), gpt-4o, gpt-4-turbo, gpt-4
            </small>
          </div>
        </div>
      )}

      {provider === 'anthropic' && (
        <div className="settings-grid">
          <div className="form-group">
            <label>Anthropic API Key</label>
            <input
              type="password"
              placeholder="sk-ant-..."
              value={settings.anthropic.apiKey}
              onChange={(e) => handleSettingChange('apiKey', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Название модели</label>
            <input
              type="text"
              placeholder="claude-3-5-sonnet-20241022, claude-3-opus-20240229"
              value={settings.anthropic.model}
              onChange={(e) => handleSettingChange('model', e.target.value)}
            />
            <small style={{ color: '#718096', marginTop: '5px', display: 'block' }}>
              Популярные: claude-3-5-sonnet-20241022 (рекомендуется), claude-3-opus-20240229, claude-3-sonnet-20240229
            </small>
          </div>
        </div>
      )}

      {provider === 'custom' && (
        <div className="settings-grid">
          <div className="form-group">
            <label>API Base URL</label>
            <input
              type="text"
              placeholder="http://host.docker.internal:11434/v1"
              value={settings.custom.apiBase}
              onChange={(e) => handleSettingChange('apiBase', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>API Key</label>
            <input
              type="text"
              placeholder="ollama"
              value={settings.custom.apiKey}
              onChange={(e) => handleSettingChange('apiKey', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Название модели</label>
            <input
              type="text"
              placeholder="llama2, mistral, qwen2.5"
              value={settings.custom.model}
              onChange={(e) => handleSettingChange('model', e.target.value)}
            />
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginTop: '20px' }}>
        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Сохранение...' : 'Сохранить настройки'}
        </button>
        {status && <span style={{ color: status.includes('сохранены') ? '#22543d' : '#c53030' }}>{status}</span>}
      </div>
    </div>
  );
};

export default ModelSettings;
