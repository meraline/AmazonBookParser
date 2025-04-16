import os
import time
import threading
import logging
from flask import Flask, render_template, request, jsonify, session, flash, redirect, url_for
from kindle_scraper import KindleScraper

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
        scraper_status["total_pages"] = pages_to_read
        scraper_status["current_page"] = 0
        scraper_status["log_messages"] = []
        
        log_handler("Запуск процесса извлечения текста из Kindle Cloud Reader")
        
        scraper = KindleScraper(
            email=email,
            password=password,
            book_url=book_url,
            output_file=output_file,
            pages_to_read=pages_to_read,
            page_load_time=page_load_time
        )
        
        # Настройка драйвера
        log_handler("Настройка веб-драйвера...")
        if not scraper.setup_driver():
            log_handler("Ошибка при настройке драйвера!")
            scraper_status["running"] = False
            return
        
        # Авторизация
        log_handler("Авторизация в Amazon...")
        if not scraper.login():
            log_handler("Ошибка авторизации в Amazon!")
            scraper_status["running"] = False
            scraper.driver.quit()
            return
        
        # Открытие книги
        log_handler("Открытие книги...")
        if not scraper.open_book():
            log_handler("Ошибка при открытии книги!")
            scraper_status["running"] = False
            scraper.driver.quit()
            return
        
        # Клик по центру, чтобы убрать интерфейс
        scraper.driver.find_element_by_tag_name("body").click()
        time.sleep(2)
        
        # Извлечение текста
        log_handler(f"Начало извлечения текста. Планируется прочитать {pages_to_read} страниц")
        
        # Создаем файл для сохранения текста
        with open(output_file, 'w', encoding='utf-8') as f:
            for page in range(pages_to_read):
                try:
                    scraper_status["current_page"] = page + 1
                    scraper_status["progress"] = int((page + 1) / pages_to_read * 100)
                    
                    log_handler(f"Обработка страницы {page + 1}")
                    
                    # Попытка найти элементы с текстом (разные варианты селекторов)
                    content_elements = []
                    selectors = [
                        "div.textLayer", 
                        "div.kcrPage", 
                        "div.bookReaderContainer", 
                        "div.kindleReaderPage"
                    ]
                    
                    for selector in selectors:
                        try:
                            elements = scraper.driver.find_elements_by_css_selector(selector)
                            if elements:
                                content_elements = elements
                                break
                        except:
                            continue
                    
                    # Если не нашли элементы ни по одному из селекторов, попробуем извлечь весь текст страницы
                    if not content_elements:
                        log_handler("Не найдены стандартные элементы с текстом, извлекаем весь текст страницы")
                        content_elements = [scraper.driver.find_element_by_tag_name("body")]
                    
                    # Извлекаем текст
                    page_text = ""
                    for elem in content_elements:
                        elem_text = elem.text.strip()
                        if elem_text:
                            page_text += elem_text + "\n"
                    
                    # Записываем в файл
                    f.write(f"\n\n=== Страница {page + 1} ===\n")
                    f.write(page_text.strip())
                    
                    # Нажимаем стрелку "вперёд"
                    body = scraper.driver.find_element_by_tag_name("body")
                    body.send_keys(scraper.Keys.ARROW_RIGHT)
                    
                    # Ждем загрузки новой страницы
                    time.sleep(page_load_time)
                    
                except Exception as e:
                    log_handler(f"Ошибка на странице {page+1}: {str(e)}")
                    # Продолжаем, несмотря на ошибку на одной странице
                    continue
        
        log_handler(f"Извлечение текста завершено. Сохранено {pages_to_read} страниц в файл: {output_file}")
        
    except Exception as e:
        log_handler(f"Ошибка в процессе скрапинга: {str(e)}")
    finally:
        if scraper and scraper.driver:
            scraper.driver.quit()
            log_handler("Веб-драйвер закрыт")
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
