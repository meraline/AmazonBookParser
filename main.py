from flask import Flask, render_template, request, jsonify, session, flash, redirect, url_for
import os
import threading
import time
import logging
import json
from kindle_scraper import KindleScraper
from kindle_api_scraper import KindleAPIScraper
from kindle_web_scraper import KindleWebScraper
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

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
        scraper.driver.find_element(By.TAG_NAME, "body").click()
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
                            elements = scraper.driver.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                content_elements = elements
                                break
                        except:
                            continue
                    
                    # Если не нашли элементы ни по одному из селекторов, попробуем извлечь весь текст страницы
                    if not content_elements:
                        log_handler("Не найдены стандартные элементы с текстом, извлекаем весь текст страницы")
                        content_elements = [scraper.driver.find_element(By.TAG_NAME, "body")]
                    
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
                    body = scraper.driver.find_element(By.TAG_NAME, "body")
                    body.send_keys(Keys.ARROW_RIGHT)
                    
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
        if scraper and hasattr(scraper, 'driver') and scraper.driver:
            scraper.driver.quit()
            log_handler("Веб-драйвер закрыт")
        scraper_status["running"] = False


def run_api_scraper(response_file, output_file):
    """Функция для запуска API скрапера в отдельном потоке"""
    try:
        scraper_status["running"] = True
        scraper_status["progress"] = 0
        scraper_status["total_pages"] = 1  # Одна операция извлечения
        scraper_status["current_page"] = 0
        scraper_status["log_messages"] = []
        
        log_handler("Запуск процесса извлечения текста через API")
        
        # Создаем экземпляр API скрапера
        scraper = KindleAPIScraper(output_file=output_file)
        
        # Запускаем извлечение
        log_handler(f"Начало обработки файла: {response_file}")
        
        success = scraper.run(response_file=response_file)
        
        if success:
            scraper_status["progress"] = 100
            log_handler(f"Текст успешно извлечен и сохранен в файл: {output_file}")
        else:
            log_handler("Ошибка при извлечении текста из API ответа")
        
    except Exception as e:
        log_handler(f"Ошибка в процессе обработки API: {str(e)}")
    finally:
        scraper_status["running"] = False

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/test_api_scraper')
def test_api_scraper():
    """Тестовая страница для API скрапера"""
    return render_template('api_scraper.html')

@app.route('/test_web_scraper')
def test_web_scraper():
    """Тестовая страница для веб-скрапера"""
    return render_template('web_scraper.html')

def run_web_scraper(book_url, output_file):
    """Функция для запуска веб-скрапера в отдельном потоке"""
    try:
        scraper_status["running"] = True
        scraper_status["progress"] = 0
        scraper_status["total_pages"] = 1  # Одна операция извлечения
        scraper_status["current_page"] = 0
        scraper_status["log_messages"] = []
        
        log_handler("Запуск процесса извлечения текста через веб-скрапер")
        
        # Создаем экземпляр веб-скрапера
        scraper = KindleWebScraper(book_url=book_url, output_file=output_file)
        
        # Запускаем извлечение
        log_handler(f"Попытка извлечения текста из URL: {book_url}")
        scraper_status["progress"] = 10
        
        # Пробуем получить ASIN книги
        if scraper.asin:
            log_handler(f"Обнаружен ASIN книги: {scraper.asin}")
        else:
            log_handler("ASIN книги не найден, используем полный URL")
        
        scraper_status["progress"] = 30
        log_handler("Попытка прямого извлечения контента...")
        
        success = scraper.run()
        
        scraper_status["progress"] = 100
        if success:
            log_handler(f"Текст успешно извлечен и сохранен в файл: {output_file}")
        else:
            log_handler("Ошибка при извлечении текста из веб-страницы")
        
    except Exception as e:
        log_handler(f"Ошибка в процессе веб-скрапинга: {str(e)}")
    finally:
        scraper_status["running"] = False

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    """Запуск процесса скрапинга"""
    if scraper_status["running"]:
        return jsonify({"status": "error", "message": "Процесс уже запущен"})
    
    # Получаем параметры из формы
    method = request.form.get('method', 'selenium')
    
    if method == 'selenium':
        # Получаем параметры для Selenium скрапера
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
    
    elif method == 'api':
        # Получаем параметры для API скрапера
        # В нашем тестовом случае используем предопределенный файл
        response_file = request.form.get('response_file', 'sample_kindle_response.json')
        output_file = request.form.get('output_file', 'kindle_api_book.txt')
        
        # Запускаем API скрапер в отдельном потоке
        threading.Thread(
            target=run_api_scraper,
            args=(response_file, output_file)
        ).start()
    
    elif method == 'web':
        # Получаем параметры для веб-скрапера
        book_url = request.form.get('book_url', '')
        output_file = request.form.get('output_file', 'kindle_web_book.txt')
        
        # Проверяем наличие URL
        if not book_url:
            return jsonify({"status": "error", "message": "URL книги не указан"})
        
        # Запускаем веб-скрапер в отдельном потоке
        threading.Thread(
            target=run_web_scraper,
            args=(book_url, output_file)
        ).start()
    
    else:
        return jsonify({"status": "error", "message": "Неверный метод скрапинга"})
    
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