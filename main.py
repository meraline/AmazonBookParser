from flask import Flask, render_template, request, jsonify, session, flash, redirect, url_for
import os
import threading
import time
import logging
import traceback
from web_scraper import KindleWebScraper, get_website_text_content

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "kindle_scraper_secret_key")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("kindle_scraper_web.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Глобальные переменные для отслеживания прогресса
scraper_status = {
    "running": False,
    "progress": 0,
    "total_pages": 0,
    "current_page": 0,
    "log_messages": []
}

def log_handler(message):
    """Обработчик логов для вывода в веб-интерфейс"""
    scraper_status["log_messages"].append(message)
    if len(scraper_status["log_messages"]) > 100:
        # Ограничиваем количество сообщений в логе
        scraper_status["log_messages"] = scraper_status["log_messages"][-100:]

def run_scraper(email, password, book_url, output_file, pages_to_read, page_load_time):
    """Функция для запуска скрапера в отдельном потоке"""
    try:
        scraper_status["running"] = True
        scraper_status["progress"] = 0
        scraper_status["total_pages"] = 100  # Условное количество шагов процесса
        scraper_status["current_page"] = 0
        scraper_status["log_messages"] = []
        
        log_handler("Запуск процесса извлечения информации о книге из Kindle Cloud Reader")
        
        # Используем новый скрапер на основе trafilatura
        scraper = KindleWebScraper(
            email=email,
            password=password,
            book_url=book_url,
            output_file=output_file,
            pages_to_read=pages_to_read
        )
        
        # Извлечение информации о книге
        log_handler("Анализ URL книги и получение ASIN...")
        scraper_status["current_page"] = 10
        scraper_status["progress"] = 10
        
        # Получаем общедоступную информацию о книге
        log_handler("Получение общедоступной информации о книге...")
        scraper_status["current_page"] = 30
        scraper_status["progress"] = 30
        
        # Попытка найти предпросмотр книги
        log_handler("Поиск предпросмотра книги на Amazon...")
        scraper_status["current_page"] = 50
        scraper_status["progress"] = 50
        
        # Запускаем процесс извлечения информации
        success = scraper.run()
        
        scraper_status["current_page"] = 100
        scraper_status["progress"] = 100
        
        if success:
            log_handler(f"Процесс извлечения информации о книге успешно завершен. Результаты сохранены в файл: {output_file}")
            
            # Добавляем уведомление о том, что для полного извлечения текста книги требуется использовать другой подход
            log_handler("ПРИМЕЧАНИЕ: Для извлечения полного текста книги из Kindle Cloud Reader требуется использовать Selenium WebDriver с реальным браузером Chrome, что невозможно в текущей среде Replit.")
            log_handler("Полученная информация содержит общедоступные данные о книге и, если доступно, предпросмотр контента.")
        else:
            log_handler("Возникли проблемы при извлечении информации о книге. Пожалуйста, проверьте URL книги.")
        
        # Дополнительно используем функцию для прямого извлечения
        try:
            log_handler("Попытка прямого извлечения текста с URL книги...")
            
            # Извлекаем общую информацию из URL книги
            text_content = get_website_text_content(book_url)
            
            if text_content and len(text_content) > 50:
                with open(output_file, 'a', encoding='utf-8') as f:
                    f.write("\n\n=== Дополнительная информация с URL книги ===\n\n")
                    f.write(text_content)
                log_handler("Добавлена дополнительная информация с URL книги")
            else:
                log_handler("Не удалось получить дополнительную информацию с URL книги")
        except Exception as e:
            log_handler(f"Ошибка при попытке прямого извлечения: {str(e)}")
        
    except Exception as e:
        error_details = traceback.format_exc()
        log_handler(f"Ошибка в процессе извлечения информации: {str(e)}")
        log_handler(f"Детали ошибки: {error_details}")
    finally:
        scraper_status["running"] = False


@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    """Запуск процесса скрапинга"""
    if scraper_status["running"]:
        return jsonify({"status": "error", "message": "Процесс уже запущен"})
    
    # Получаем параметры из формы
    email = request.form.get('email', '')
    password = request.form.get('password', '')
    book_url = request.form.get('book_url', '')
    output_file = request.form.get('output_file', 'kindle_book.txt')
    
    try:
        pages_to_read = int(request.form.get('pages_to_read', 50))
        page_load_time = float(request.form.get('page_load_time', 3))
    except ValueError:
        return jsonify({"status": "error", "message": "Неверный формат числа страниц или времени загрузки"})
    
    # Проверяем наличие всех необходимых параметров
    if not email or not password or not book_url:
        return jsonify({"status": "error", "message": "Не указаны все необходимые параметры"})
    
    # Запускаем скрапер в отдельном потоке
    threading.Thread(
        target=run_scraper, 
        args=(email, password, book_url, output_file, pages_to_read, page_load_time)
    ).start()
    
    return jsonify({"status": "success", "message": "Процесс запущен"})

@app.route('/get_status')
def get_status():
    """Получение текущего статуса скрапера"""
    return jsonify(scraper_status)

@app.route('/stop_scraping')
def stop_scraping():
    """Остановка процесса скрапинга"""
    if not scraper_status["running"]:
        return jsonify({"status": "error", "message": "Процесс не запущен"})
    
    # Устанавливаем флаг остановки
    scraper_status["running"] = False
    return jsonify({"status": "success", "message": "Процесс остановлен"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)