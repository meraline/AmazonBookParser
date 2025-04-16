# Парсер Kindle Cloud Reader

Это приложение позволяет автоматически извлекать текст книги из Kindle Cloud Reader с помощью Selenium.

## Функциональность

- Авторизация в Amazon с использованием учетных данных
- Открытие книги в Kindle Cloud Reader
- Автоматическое перелистывание страниц
- Извлечение текста с каждой страницы
- Сохранение всего текста в файл

## Требования

- Python 3.6+
- Selenium
- webdriver-manager
- Flask (для веб-интерфейса)
- Chrome или Firefox

## Установка

1. Убедитесь, что у вас установлен Python 3.6 или выше
2. Установите необходимые зависимости:

```bash
pip install selenium webdriver-manager flask
