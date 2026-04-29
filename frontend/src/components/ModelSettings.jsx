import React, { useState, useEffect } from 'react';
import { getSettings, saveSettings } from '../services/api';

const providerPresets = {
  openai: {
    label: 'OpenAI',
    apiKey: '',
    apiBase: '',
    model: 'gpt-4o-mini',
    apiKeyPlaceholder: 'sk-...',
    modelPlaceholder: 'gpt-4o-mini, gpt-4o, gpt-4.1-mini',
    hint: 'Популярные: gpt-4o-mini, gpt-4o, gpt-4.1-mini'
  },
  anthropic: {
    label: 'Anthropic Claude',
    apiKey: '',
    apiBase: '',
    model: 'claude-3-5-sonnet-20241022',
    apiKeyPlaceholder: 'sk-ant-...',
    modelPlaceholder: 'claude-3-5-sonnet-20241022',
    hint: 'Популярные: claude-3-5-sonnet-20241022, claude-3-opus-20240229'
  },
  openrouter: {
    label: 'OpenRouter',
    apiKey: '',
    apiBase: 'https://openrouter.ai/api/v1',
    model: 'openai/gpt-4o-mini',
    apiKeyPlaceholder: 'sk-or-...',
    modelPlaceholder: 'openai/gpt-4o-mini, anthropic/claude-sonnet-4.5',
    hint: 'OpenAI-compatible API. Можно указать любую модель из OpenRouter.'
  },
  custom: {
    label: 'Custom OpenAI-compatible',
    apiKey: '',
    apiBase: 'http://host.docker.internal:11434/v1',
    model: 'llama2',
    apiKeyPlaceholder: 'ollama или ключ провайдера',
    modelPlaceholder: 'llama2, mistral, qwen2.5',
    hint: 'Подходит для Ollama, LM Studio, vLLM и других /v1 совместимых API.'
  }
};

const knownProviderIds = Object.keys(providerPresets);

const buildProviderConfig = (provider, saved = {}) => {
  const preset = providerPresets[provider] || providerPresets.custom;
  return {
    ...preset,
    apiKey: saved.api_key ?? saved.apiKey ?? preset.apiKey,
    apiBase: saved.api_base ?? saved.apiBase ?? preset.apiBase,
    model: saved.model || preset.model
  };
};

const ModelSettings = ({ onSettingsChange }) => {
  const [provider, setProvider] = useState('openai');
  const [providerId, setProviderId] = useState('custom');
  const [settings, setSettings] = useState(() => ({
    openai: buildProviderConfig('openai'),
    anthropic: buildProviderConfig('anthropic'),
    openrouter: buildProviderConfig('openrouter'),
    custom: buildProviderConfig('custom')
  }));
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState('');

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const saved = await getSettings();
        const savedProvider = (saved.provider || 'openai').toLowerCase();
        const nextSettings = {
          openai: buildProviderConfig('openai'),
          anthropic: buildProviderConfig('anthropic'),
          openrouter: buildProviderConfig('openrouter'),
          custom: buildProviderConfig('custom')
        };

        const activeProvider = knownProviderIds.includes(savedProvider) ? savedProvider : 'custom';
        nextSettings[activeProvider] = buildProviderConfig(activeProvider, saved);

        setProvider(activeProvider);
        setProviderId(savedProvider);
        setSettings(nextSettings);
        emitSettings(activeProvider, nextSettings[activeProvider], savedProvider);
      } catch (error) {
        console.error('Settings load error:', error);
        setStatus('Не удалось загрузить настройки из БД');
      }
    };

    loadSettings();
  }, []);

  const emitSettings = (activeProvider, activeSettings, idOverride = providerId) => {
    if (onSettingsChange) {
      onSettingsChange({
        provider: activeProvider === 'custom' ? idOverride.trim().toLowerCase() : activeProvider,
        apiKey: activeSettings.apiKey || '',
        apiBase: activeSettings.apiBase || '',
        model: activeSettings.model || ''
      });
    }
  };

  const handleProviderChange = (newProvider) => {
    setProvider(newProvider);
    setStatus('');
    const nextProviderId = newProvider === 'custom'
      ? (knownProviderIds.includes(providerId) ? 'custom' : providerId)
      : newProvider;
    setProviderId(nextProviderId);
    emitSettings(newProvider, settings[newProvider], nextProviderId);
  };

  const handleProviderIdChange = (value) => {
    const normalized = value.toLowerCase().replace(/\s+/g, '-');
    setProviderId(normalized);
    setStatus('');
    emitSettings(provider, settings[provider], normalized);
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
    emitSettings(provider, newSettings[provider]);
  };

  const handleSave = async () => {
    setSaving(true);
    setStatus('');
    try {
      const activeSettings = settings[provider];
      const effectiveProvider = provider === 'custom' ? providerId.trim().toLowerCase() : provider;
      await saveSettings({
        provider: effectiveProvider,
        apiKey: activeSettings.apiKey || '',
        apiBase: activeSettings.apiBase || '',
        model: activeSettings.model || ''
      });
      setStatus('Настройки сохранены в БД');
    } catch (error) {
      console.error('Settings save error:', error);
      setStatus(error.response?.data?.detail || 'Не удалось сохранить настройки');
    } finally {
      setSaving(false);
    }
  };

  const activeSettings = settings[provider];
  const requiresApiBase = provider !== 'openai' && provider !== 'anthropic';

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
          <option value="openrouter">OpenRouter</option>
          <option value="custom">Свой OpenAI-compatible</option>
        </select>
      </div>

      {provider === 'custom' && (
        <div className="form-group">
          <label>Provider ID</label>
          <input
            type="text"
            placeholder="openrouter, deepseek, groq, local"
            value={providerId}
            onChange={(e) => handleProviderIdChange(e.target.value)}
          />
          <small className="form-hint">
            Короткое имя провайдера для сохранения настроек. Для OpenAI-compatible API ниже укажите Base URL.
          </small>
        </div>
      )}

      <div className="settings-grid">
        {requiresApiBase && (
          <div className="form-group">
            <label>API Base URL</label>
            <input
              type="text"
              placeholder={providerPresets[provider]?.apiBase || 'https://provider.example/v1'}
              value={activeSettings.apiBase}
              onChange={(e) => handleSettingChange('apiBase', e.target.value)}
            />
          </div>
        )}

        <div className="form-group">
          <label>API Key</label>
          <input
            type={provider === 'custom' ? 'text' : 'password'}
            placeholder={activeSettings.apiKeyPlaceholder}
            value={activeSettings.apiKey}
            onChange={(e) => handleSettingChange('apiKey', e.target.value)}
          />
        </div>

        <div className="form-group">
          <label>Название модели</label>
          <input
            type="text"
            placeholder={activeSettings.modelPlaceholder}
            value={activeSettings.model}
            onChange={(e) => handleSettingChange('model', e.target.value)}
          />
          <small className="form-hint">{activeSettings.hint}</small>
        </div>
      </div>

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
