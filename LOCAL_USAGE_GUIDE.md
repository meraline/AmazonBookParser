# Руководство по запуску парсера на локальном компьютере

## Улучшенный способ запуска для локальных компьютеров

Мы обновили парсер, чтобы он лучше работал на локальных компьютерах, где уже установлены браузеры Firefox и Chrome.

### Подготовка к работе

1. Убедитесь, что у вас установлен Firefox или Chrome (или оба)
2. Перед запуском установите необходимые библиотеки:

```bash
pip install -r requirements.txt
```

### Новые возможности

Новая версия парсера теперь автоматически:

1. Пытается использовать локально установленные браузеры (Firefox или Chrome)
2. При неудаче пытается установить драйверы автоматически через webdriver-manager
3. Создает подробный отчет о системе при ошибках для диагностики

### Запуск парсера через интерфейс

1. Запустите Flask-приложение:

```bash
python main.py
```

2. Откройте в браузере: http://localhost:5000/
3. Заполните поля для входа и выберите книгу для загрузки

### Запуск через код

Вы можете запустить парсер напрямую из своего кода:

```python
from kindle_auto_api_scraper import KindleAutoAPIScraper

scraper = KindleAutoAPIScraper(
    email="ваш_email",
    password="ваш_пароль",
    book_url="https://read.amazon.com/reader?asin=B009SE1Z9E",
    output_file="результат.txt"
)
success = scraper.run()

if success:
    print("Книга успешно извлечена!")
else:
    print("Произошла ошибка при извлечении книги.")
```

### Решение проблем

Если возникает ошибка "Read timed out" во время установки драйвера:

1. Проверьте подключение к интернету
2. Увеличьте таймаут (изменив код в setup_driver)
3. Попробуйте скачать драйвер вручную:
   - [geckodriver](https://github.com/mozilla/geckodriver/releases) для Firefox
   - [chromedriver](https://chromedriver.chromium.org/downloads) для Chrome

После ручной установки укажите путь к драйверу:

```python
from selenium import webdriver
from selenium.webdriver.firefox.service import Service

# Используйте явный путь к драйверу
service = Service('/путь/к/вашему/geckodriver')
driver = webdriver.Firefox(service=service)
```

### Диагностика

При возникновении проблем, проверьте следующие файлы:

- `selenium_debug.log` - логи взаимодействия с браузером
- `api_debug.log` - логи API-запросов
- `parsing_debug.log` - логи извлечения данных
- `environment_report.json` - отчет о системном окружении (создается при ошибках)

### Поддержка

Если у вас возникли проблемы, которые не удается решить самостоятельно:

1. Соберите файлы логов и отчета о системе
2. Опишите подробно шаги, которые привели к ошибке
3. Приложите скриншоты, если они есть