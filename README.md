# Парсер Kindle Cloud Reader

Это приложение позволяет автоматически извлекать текст книги из Kindle Cloud Reader с помощью Selenium и веб-интерфейса на Flask.

## Функциональность

- Авторизация в Amazon с использованием учетных данных
- Открытие книги в Kindle Cloud Reader
- Автоматическое перелистывание страниц
- Извлечение текста с каждой страницы
- Сохранение всего текста в файл
- Мониторинг прогресса через веб-интерфейс

## Пошаговое руководство по использованию

### 1. Подготовка

Перед использованием парсера убедитесь, что:
- У вас есть активная учетная запись на Amazon
- Вы знаете свой логин (email) и пароль от аккаунта Amazon
- У вас есть доступ к книге, которую хотите извлечь
- Двухфакторная аутентификация на аккаунте Amazon отключена

### 2. Запуск приложения

1. Запустите приложение с помощью команды:
```bash
python main.py
```
или используйте готовую конфигурацию в Replit, нажав кнопку "Run".

2. После запуска откройте веб-браузер и перейдите по адресу:
```
http://localhost:5000
```
или используйте ссылку, предоставленную Replit.

### 3. Настройка параметров скрапинга

В веб-интерфейсе заполните следующие поля:

- **Email Amazon**: ваш email от аккаунта Amazon
- **Пароль Amazon**: ваш пароль от аккаунта Amazon
- **URL книги**: ссылка на книгу в Kindle Cloud Reader (в формате https://read.amazon.com/...)
- **Имя файла для сохранения**: название файла, куда будет сохранён результат (по умолчанию `kindle_book.txt`)
- **Количество страниц**: сколько страниц книги вы хотите извлечь
- **Задержка между страницами**: время ожидания между перелистываниями в секундах (рекомендуется 3-5 секунд)

### 4. Запуск процесса скрапинга

1. Нажмите кнопку "Запустить парсер"
2. Дождитесь завершения процесса - это может занять длительное время в зависимости от количества страниц и заданной задержки
3. Следите за статусом и прогрессом в разделе "Статус" и "Лог"
4. Если необходимо, вы можете остановить процесс кнопкой "Остановить"

### 5. Получение результатов

По завершении процесса скрапинга:
1. В разделе "Статус" появится сообщение "Процесс завершен"
2. Текст книги будет сохранен в указанный файл в корневой директории проекта
3. Вы можете скачать полученный файл и использовать его по своему усмотрению

### 6. Возможные проблемы и их решение

- **Если процесс авторизации не удается**: проверьте правильность логина и пароля, убедитесь, что двухфакторная аутентификация отключена
- **Если текст не извлекается**: увеличьте задержку между страницами, Amazon может блокировать слишком быстрые запросы
- **Если драйвер завершается с ошибкой**: убедитесь, что у вас установлен Chrome или Firefox, попробуйте перезапустить приложение

## Требования

- Python 3.6+
- Selenium
- webdriver-manager
- Flask (для веб-интерфейса)
- Chrome или Firefox

## Примечания

- Использование данного скрапера должно соответствовать условиям использования Amazon Kindle
- Извлекайте только те книги, на которые у вас есть права
- Не используйте полученный текст в коммерческих целях без соответствующих разрешений

## Установка зависимостей

```bash
pip install selenium webdriver-manager flask gunicorn flask-sqlalchemy
