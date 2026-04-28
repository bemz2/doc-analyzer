# Document Analyzer

Веб-приложение для автоматического анализа больших документов Word с использованием LLM (Large Language Models). Поддерживает OpenAI, Anthropic и локальные модели.

## Возможности

- 📄 **Анализ документов Word** - загрузка и обработка .docx файлов
- 🤖 **Поддержка нескольких LLM провайдеров**:
  - OpenAI (GPT-4, GPT-4o-mini и др.)
  - Anthropic (Claude 3.5 Sonnet и др.)
  - Локальные модели (Ollama, LM Studio, vLLM и др.)
- 📊 **Детальный анализ**:
  - Разбиение документа на части для обработки больших файлов
  - Поиск проблем по категориям (стиль, грамматика, структура, логика, соответствие требованиям)
  - Оценка серьезности проблем (низкая, средняя, высокая)
  - Глобальный анализ всего документа
- 📈 **Оценка стоимости** - расчет токенов и стоимости анализа для разных моделей
- 📝 **Экспорт отчетов** - JSON, DOCX, HTML форматы
- 🎨 **Современный UI** - React интерфейс с темной темой
- 💾 **Управление настройками** - сохранение API ключей и настроек в базе данных
- 📜 **История анализов** - отслеживание предыдущих анализов
- 🔧 **Шаблоны инструкций** - сохранение и переиспользование инструкций для анализа

## Требования

### Для запуска с Docker (рекомендуется)

- Docker 20.10+
- Docker Compose 2.0+
- 4GB свободной оперативной памяти
- Доступ к интернету (для загрузки образов)

### Для локального запуска

- Python 3.11+
- Node.js 18+ и npm
- 4GB свободной оперативной памяти

### API ключи (один из вариантов)

- **OpenAI API ключ** - для использования GPT моделей
- **Anthropic API ключ** - для использования Claude моделей
- **Локальная модель** - Ollama, LM Studio или другой совместимый сервер

## Быстрый старт с Docker

1. **Клонируйте репозиторий**
```bash
git clone https://github.com/yourusername/doc-analyzer.git
cd doc-analyzer
```

2. **Создайте .env файл**
```bash
cp .env.example .env
```

3. **Запустите приложение**
```bash
docker-compose up -d
```

4. **Откройте браузер**
```
http://localhost
```

5. **Настройте API ключи**
   - Перейдите в раздел "Настройки" в веб-интерфейсе
   - Выберите провайдера (OpenAI, Anthropic или Custom)
   - Введите API ключ и модель
   - Сохраните настройки

## Локальный запуск (без Docker)

### Backend (FastAPI)

1. **Создайте виртуальное окружение**
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или
.venv\Scripts\activate  # Windows
```

2. **Установите зависимости**
```bash
pip install -r requirements.txt
```

3. **Создайте .env файл**
```bash
cp .env.example .env
```

4. **Запустите сервер**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend (React)

1. **Перейдите в директорию frontend**
```bash
cd frontend
```

2. **Установите зависимости**
```bash
npm install
```

3. **Запустите dev сервер**
```bash
npm start
```

4. **Откройте браузер**
```
http://localhost:3000
```

## Настройка провайдеров LLM

### OpenAI

1. Получите API ключ на https://platform.openai.com/api-keys
2. В веб-интерфейсе выберите провайдера "OpenAI"
3. Введите API ключ
4. Выберите модель (например, `gpt-4o-mini`)
5. Сохраните настройки

### Anthropic

1. Получите API ключ на https://console.anthropic.com/
2. В веб-интерфейсе выберите провайдера "Anthropic"
3. Введите API ключ
4. Выберите модель (например, `claude-3-5-sonnet-20241022`)
5. Сохраните настройки

### Локальные модели (Ollama, LM Studio и др.)

#### Ollama

1. **Установите Ollama**
```bash
# Mac/Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows - скачайте с https://ollama.com/download
```

2. **Запустите модель**
```bash
ollama run llama2
# или другую модель
```

3. **Настройте в веб-интерфейсе**
   - Провайдер: Custom
   - API Base URL: `http://host.docker.internal:11434/v1` (для Docker) или `http://localhost:11434/v1` (локально)
   - API Key: `ollama` (или оставьте пустым)
   - Model: `llama2` (или название вашей модели)

#### LM Studio

1. Скачайте и установите LM Studio с https://lmstudio.ai/
2. Загрузите модель в LM Studio
3. Запустите локальный сервер в LM Studio (вкладка "Local Server")
4. Настройте в веб-интерфейсе:
   - Провайдер: Custom
   - API Base URL: `http://host.docker.internal:1234/v1` (для Docker) или `http://localhost:1234/v1` (локально)
   - API Key: оставьте пустым или введите любое значение
   - Model: название модели из LM Studio

## Структура проекта

```
doc-analyzer/
├── app/                      # Backend (FastAPI)
│   ├── main.py              # Главный файл приложения
│   ├── config.py            # Конфигурация
│   ├── analyzer.py          # Логика анализа документов
│   ├── llm_client.py        # Клиент для работы с LLM
│   ├── document_loader.py   # Загрузка документов
│   ├── chunker.py           # Разбиение на части
│   ├── report_generator.py  # Генерация отчетов
│   ├── database.py          # Работа с БД
│   └── schemas.py           # Pydantic модели
├── frontend/                # Frontend (React)
│   ├── src/
│   │   ├── components/      # React компоненты
│   │   ├── App.js          # Главный компонент
│   │   └── index.js        # Точка входа
│   └── package.json
├── uploads/                 # Загруженные файлы (не в git)
├── reports/                 # Сгенерированные отчеты (не в git)
├── data/                    # База данных SQLite (не в git)
├── docker-compose.yml       # Docker Compose конфигурация
├── Dockerfile              # Backend Dockerfile
├── requirements.txt        # Python зависимости
├── .env.example           # Пример .env файла
└── README.md              # Этот файл
```

## Конфигурация

Основные параметры в `.env`:

```bash
# Провайдер по умолчанию (можно изменить в UI)
LLM_PROVIDER=openai

# Модели по умолчанию
OPENAI_MODEL=gpt-4o-mini
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Обработка документов
MAX_FILE_SIZE_MB=50          # Максимальный размер файла
CHUNK_SIZE=3000              # Размер части документа в токенах
CHUNK_OVERLAP=200            # Перекрытие между частями

# Настройки LLM
TEMPERATURE=0.1              # Температура генерации (0-1)
MAX_RETRIES=3                # Количество повторных попыток
RETRY_DELAY=5                # Задержка между попытками (секунды)

# Логирование
LOG_LEVEL=INFO               # DEBUG, INFO, WARNING, ERROR
```

## API Endpoints

### Документы
- `POST /upload` - Загрузка документа
- `POST /analyze/{file_id}` - Анализ документа
- `GET /report/{report_id}` - Получение отчета
- `GET /download/{report_id}/{format}` - Скачивание отчета (json/docx/html)
- `DELETE /cleanup/{file_id}` - Удаление файлов

### Настройки
- `GET /settings` - Получение настроек
- `POST /settings` - Сохранение настроек

### История
- `GET /history` - История анализов

### Шаблоны инструкций
- `GET /instructions` - Список шаблонов
- `POST /instructions` - Создание шаблона
- `PUT /instructions/{id}` - Обновление шаблона
- `DELETE /instructions/{id}` - Удаление шаблона
- `POST /instructions/{id}/use` - Увеличение счетчика использования

## Устранение неполадок

### Docker

**Проблема**: Контейнер не может подключиться к локальной модели

**Решение**: Используйте `host.docker.internal` вместо `localhost` в API Base URL

**Проблема**: Ошибка "Connection error" при анализе

**Решение**: 
1. Проверьте, что локальный сервер модели запущен
2. Убедитесь, что API ключ правильный
3. Проверьте логи: `docker-compose logs fastapi`

### Локальный запуск

**Проблема**: ModuleNotFoundError

**Решение**: Убедитесь, что виртуальное окружение активировано и зависимости установлены

**Проблема**: Ошибка при установке зависимостей на Python 3.14

**Решение**: Используйте Python 3.11 или 3.12

## Разработка

### Запуск в режиме разработки

```bash
# Backend с hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend с hot reload
cd frontend && npm start
```

### Тестирование

```bash
# Backend тесты
pytest

# Frontend тесты
cd frontend && npm test
```

## Лицензия

MIT License - см. файл LICENSE

## Поддержка

Если у вас возникли проблемы или вопросы:
1. Проверьте раздел "Устранение неполадок"
2. Посмотрите логи: `docker-compose logs`
3. Создайте issue на GitHub

## Благодарности

- OpenAI за GPT модели
- Anthropic за Claude модели
- Ollama за простой способ запуска локальных моделей
- Сообщество open-source за инструменты и библиотеки
