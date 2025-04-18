# Руководство по отладке парсера Kindle Cloud Reader

## Распространенные ошибки и их решения

### 1. "binary is not a Firefox executable"

**Причина:** Firefox не найден в стандартных путях системы.

**Решение:**
1. Установите Firefox, если он не установлен
2. В коде `kindle_auto_api_scraper.py` найдите список `firefox_paths` и добавьте правильный путь к вашему исполняемому файлу Firefox
   ```python
   firefox_paths = [
       "/usr/bin/firefox",
       "/path/to/your/firefox"  # Добавьте ваш путь здесь
   ]
   ```

### 2. "perfLoggingPrefs specified, but performance logging was not enabled"

**Причина:** Проблема совместимости с вашей версией Chrome.

**Решение:**
Закомментированы опции перехвата в Chrome, которые вызывали ошибку:
```python
# options.add_argument("--auto-open-devtools-for-tabs")
# options.add_experimental_option("perfLoggingPrefs", {...})
```

### 3. "Read timed out" при установке драйвера

**Причина:** Таймаут при загрузке драйвера с сервера GitHub.

**Решения:**
1. Скачайте драйверы вручную:
   - geckodriver: https://github.com/mozilla/geckodriver/releases
   - chromedriver: https://chromedriver.chromium.org/downloads
2. Поместите драйверы в рабочую директорию (там, где запускаете скрипт)
3. Парсер автоматически использует локальные драйверы при их наличии

### 4. "GeckoDriverManager.__init__() got an unexpected keyword argument 'timeout'"

**Причина:** Устаревшая версия webdriver-manager.

**Решение:**
1. Обновите webdriver-manager: `pip install --upgrade webdriver-manager`
2. Или уберите аргумент timeout (уже исправлено в коде)

### 5. Ошибки при авторизации Amazon

**Причина:** Защита Amazon от автоматизированных входов.

**Решения:**
1. Используйте более медленный ввод (добавлены задержки между нажатиями)
2. Добавьте обработку двухфакторной аутентификации, если она включена
3. Временное решение: войдите вручную, затем передайте куки в скрипт

## Анализ логов и отладка

### Лог-файлы

Программа создает несколько лог-файлов:
- `selenium_debug.log` - логи взаимодействия с браузером
- `api_debug.log` - логи API-запросов
- `parsing_debug.log` - логи извлечения данных
- `kindle_auto_scraper.log` - общие логи
- `environment_report.json` - информация о системе при ошибках

### Отладка с помощью скриншотов

При ошибках скрипт автоматически сохраняет скриншоты в текущую директорию:
- `firefox_direct_started.png` - Firefox запущен успешно
- `chrome_direct_started.png` - Chrome запущен успешно
- `login_page_before.png` - страница перед авторизацией
- `login_failure.png` - ошибка авторизации
- `error_state.png` - состояние при возникновении ошибки

### Создание отчета о системе

Если у вас возникают неизвестные ошибки, запустите функцию для создания диагностического отчета:

```python
from kindle_auto_api_scraper import KindleAutoAPIScraper

scraper = KindleAutoAPIScraper()
env_report = scraper._generate_environment_report()
print(f"Отчет сохранен в {env_report}")
```

## Как модифицировать код для решения проблем

### Пример 1: Использование конкретного пути к браузеру

```python
options = FirefoxOptions()
options.binary_location = "/точный/путь/к/вашему/firefox"
self.driver = webdriver.Firefox(options=options)
```

### Пример 2: Отключение логирования перехвата трафика

```python
options = ChromeOptions()
# Отключаем опции перехвата, которые вызывают ошибку
# options.add_argument("--auto-open-devtools-for-tabs")
# options.add_experimental_option("perfLoggingPrefs", {...})
```

### Пример 3: Ручное указание пути к драйверу

```python
from selenium.webdriver.firefox.service import Service

service = Service(executable_path="/путь/к/вашему/geckodriver")
self.driver = webdriver.Firefox(service=service, options=options)
```