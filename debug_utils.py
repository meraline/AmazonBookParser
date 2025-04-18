import logging
import json
import time
import traceback
import os
import sys
from functools import wraps

# Создаем директорию для логов, если она не существует
if not os.path.exists('logs'):
    os.makedirs('logs')

# Настраиваем основной логгер
logging.basicConfig(
    level=logging.DEBUG,  # Максимально подробный уровень логирования
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Создаем отдельные логгеры для разных модулей
def get_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Файловый обработчик для подробных логов
    file_handler = logging.FileHandler(f'logs/{name}.log', mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    ))
    
    # Консольный обработчик для информационных сообщений
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    
    # Добавляем обработчики к логгеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Логгеры для разных компонентов системы
selenium_logger = get_logger('selenium_debug')
api_logger = get_logger('api_debug')
parsing_logger = get_logger('parsing_debug')
web_logger = get_logger('web_debug')

# Декоратор для логирования вызовов функций
def log_function_call(logger):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            logger.debug(f"НАЧАЛО {func.__name__} - Аргументы: {args}, Kwargs: {kwargs}")
            
            try:
                result = func(*args, **kwargs)
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Форматируем вывод результата в зависимости от типа
                if isinstance(result, (dict, list)):
                    try:
                        result_str = json.dumps(result, ensure_ascii=False, indent=2)
                        if len(result_str) > 500:
                            result_str = result_str[:500] + "... [Обрезано]"
                    except:
                        result_str = str(result)
                else:
                    result_str = str(result)
                
                logger.debug(f"КОНЕЦ {func.__name__} - Время выполнения: {execution_time:.2f}с - Результат: {result_str}")
                return result
                
            except Exception as e:
                end_time = time.time()
                execution_time = end_time - start_time
                logger.error(f"ОШИБКА {func.__name__} - Время выполнения: {execution_time:.2f}с - Исключение: {str(e)}")
                logger.error(f"Трассировка: {traceback.format_exc()}")
                raise
                
        return wrapper
    return decorator

# Функция для логирования HTML содержимого страницы
def log_page_content(driver, description, logger=selenium_logger):
    try:
        page_source = driver.page_source
        page_url = driver.current_url
        
        # Создаем директорию для HTML-логов, если её нет
        if not os.path.exists('logs/html'):
            os.makedirs('logs/html')
        
        # Генерируем имя файла на основе текущего времени
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"logs/html/{timestamp}_{description.replace(' ', '_')}.html"
        
        # Сохраняем HTML-содержимое
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"<!-- URL: {page_url} -->\n")
            f.write(page_source)
        
        logger.debug(f"HTML содержимое сохранено: {description} -> {filename}")
        return filename
    except Exception as e:
        logger.error(f"Не удалось сохранить HTML содержимое: {str(e)}")
        return None

# Функция для логирования скриншота
def log_screenshot(driver, description, logger=selenium_logger):
    try:
        # Создаем директорию для скриншотов, если её нет
        if not os.path.exists('logs/screenshots'):
            os.makedirs('logs/screenshots')
        
        # Генерируем имя файла на основе текущего времени
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"logs/screenshots/{timestamp}_{description.replace(' ', '_')}.png"
        
        # Сохраняем скриншот
        driver.save_screenshot(filename)
        
        logger.debug(f"Скриншот сохранен: {description} -> {filename}")
        return filename
    except Exception as e:
        logger.error(f"Не удалось сохранить скриншот: {str(e)}")
        return None

# Функция для логирования API-запросов
def log_api_request(url, method, headers, data=None, logger=api_logger):
    try:
        logger.debug(f"API-запрос: {method} {url}")
        logger.debug(f"Заголовки: {json.dumps(headers, indent=2)}")
        
        if data:
            try:
                if isinstance(data, str):
                    # Пробуем распарсить строку как JSON
                    parsed_data = json.loads(data)
                    logger.debug(f"Данные: {json.dumps(parsed_data, ensure_ascii=False, indent=2)}")
                elif isinstance(data, (dict, list)):
                    logger.debug(f"Данные: {json.dumps(data, ensure_ascii=False, indent=2)}")
                else:
                    logger.debug(f"Данные: {data}")
            except:
                logger.debug(f"Данные: {data}")
    except Exception as e:
        logger.error(f"Ошибка при логировании API-запроса: {str(e)}")

# Функция для логирования API-ответов
def log_api_response(url, status_code, headers, data, logger=api_logger):
    try:
        logger.debug(f"API-ответ: {status_code} от {url}")
        logger.debug(f"Заголовки ответа: {json.dumps(dict(headers), indent=2)}")
        
        try:
            if isinstance(data, str):
                # Пробуем распарсить строку как JSON
                parsed_data = json.loads(data)
                # Обрезаем вывод, если он слишком большой
                data_str = json.dumps(parsed_data, ensure_ascii=False, indent=2)
                if len(data_str) > 2000:
                    logger.debug(f"Данные ответа: {data_str[:2000]}... [Обрезано, полный размер: {len(data_str)} символов]")
                else:
                    logger.debug(f"Данные ответа: {data_str}")
            elif isinstance(data, (dict, list)):
                data_str = json.dumps(data, ensure_ascii=False, indent=2)
                if len(data_str) > 2000:
                    logger.debug(f"Данные ответа: {data_str[:2000]}... [Обрезано, полный размер: {len(data_str)} символов]")
                else:
                    logger.debug(f"Данные ответа: {data_str}")
            else:
                if len(str(data)) > 2000:
                    logger.debug(f"Данные ответа: {str(data)[:2000]}... [Обрезано, полный размер: {len(str(data))} символов]")
                else:
                    logger.debug(f"Данные ответа: {data}")
        except:
            if len(str(data)) > 2000:
                logger.debug(f"Данные ответа: {str(data)[:2000]}... [Обрезано]")
            else:
                logger.debug(f"Данные ответа: {data}")
            
    except Exception as e:
        logger.error(f"Ошибка при логировании API-ответа: {str(e)}")

# Функция для логирования объектов парсинга
def log_parsed_content(content, description, logger=parsing_logger):
    try:
        # Создаем директорию для данных парсинга, если её нет
        if not os.path.exists('logs/parsed'):
            os.makedirs('logs/parsed')
        
        # Генерируем имя файла на основе текущего времени
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"logs/parsed/{timestamp}_{description.replace(' ', '_')}.json"
        
        # Сохраняем объект в JSON-файл
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
        
        # Выводим первые 50 строк или элементов для анализа
        if isinstance(content, list):
            sample = content[:min(50, len(content))]
            logger.debug(f"Список распарсенных элементов ({len(content)} шт.), пример первых {len(sample)}: {json.dumps(sample, ensure_ascii=False, indent=2)}")
        elif isinstance(content, dict):
            logger.debug(f"Распарсенный объект: {json.dumps(content, ensure_ascii=False, indent=2)}")
        else:
            content_str = str(content)
            if len(content_str) > 1000:
                logger.debug(f"Распарсенное содержимое (обрезано): {content_str[:1000]}...")
            else:
                logger.debug(f"Распарсенное содержимое: {content_str}")
        
        logger.debug(f"Содержимое парсинга сохранено: {description} -> {filename}")
        return filename
    except Exception as e:
        logger.error(f"Не удалось сохранить содержимое парсинга: {str(e)}")
        return None

# Функция для логирования веб-запросов Flask
def log_web_request(request, logger=web_logger):
    try:
        logger.debug(f"Веб-запрос: {request.method} {request.path}")
        logger.debug(f"IP: {request.remote_addr}, User-Agent: {request.headers.get('User-Agent')}")
        
        # Логируем параметры запроса
        if request.args:
            logger.debug(f"Query параметры: {dict(request.args)}")
        
        # Логируем данные формы
        if request.form:
            logger.debug(f"Form данные: {dict(request.form)}")
        
        # Логируем JSON, если есть
        if request.is_json:
            logger.debug(f"JSON данные: {request.get_json()}")
            
        # Логируем файлы, если есть
        if request.files:
            files_info = {}
            for key, file in request.files.items():
                files_info[key] = {
                    'filename': file.filename,
                    'content_type': file.content_type,
                    'size': len(file.read()) if file else 0
                }
                # Сбрасываем курсор файла на начало
                if file:
                    file.seek(0)
            logger.debug(f"Files: {files_info}")
            
    except Exception as e:
        logger.error(f"Ошибка при логировании веб-запроса: {str(e)}")

# Функция для логирования веб-ответов Flask
def log_web_response(response, logger=web_logger):
    try:
        logger.debug(f"Веб-ответ: Статус {response.status_code}")
        logger.debug(f"Заголовки: {dict(response.headers)}")
        
        # Пытаемся логировать тело ответа, если это возможно
        if hasattr(response, 'get_data'):
            data = response.get_data(as_text=True)
            if len(data) > 1000:
                logger.debug(f"Тело ответа (обрезано): {data[:1000]}...")
            else:
                logger.debug(f"Тело ответа: {data}")
            
    except Exception as e:
        logger.error(f"Ошибка при логировании веб-ответа: {str(e)}")

# Декоратор для логирования Flask маршрутов
def log_route(logger=web_logger):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request
            
            # Логируем входящий запрос
            log_web_request(request, logger)
            
            # Замеряем время выполнения
            start_time = time.time()
            
            try:
                # Вызываем оригинальную функцию
                response = func(*args, **kwargs)
                end_time = time.time()
                execution_time = end_time - start_time
                
                # Логируем ответ
                logger.debug(f"Маршрут {func.__name__} выполнен за {execution_time:.2f}с")
                log_web_response(response, logger)
                
                return response
                
            except Exception as e:
                end_time = time.time()
                execution_time = end_time - start_time
                logger.error(f"Ошибка в маршруте {func.__name__} после {execution_time:.2f}с: {str(e)}")
                logger.error(f"Трассировка: {traceback.format_exc()}")
                raise
                
        return wrapper
    return decorator

# Патчим модули requests для автоматического логирования
def patch_requests():
    import requests
    old_request = requests.Session.request
    
    @wraps(old_request)
    def new_request(self, method, url, **kwargs):
        headers = kwargs.get('headers', {})
        data = kwargs.get('data')
        json_data = kwargs.get('json')
        
        # Логируем запрос
        if json_data is not None:
            log_api_request(url, method, headers, json_data)
        else:
            log_api_request(url, method, headers, data)
        
        # Выполняем запрос
        response = old_request(self, method, url, **kwargs)
        
        # Логируем ответ
        log_api_response(url, response.status_code, response.headers, response.text)
        
        return response
    
    requests.Session.request = new_request
    api_logger.debug("Модуль requests успешно пропатчен для логирования")

# Инициализируем патчи при импорте модуля
patch_requests()

# Примеры использования:

# 1. Для Selenium-операций:
"""
from debug_utils import selenium_logger, log_function_call, log_page_content, log_screenshot

@log_function_call(selenium_logger)
def login_to_amazon(driver, email, password):
    # ...код логина...
    log_page_content(driver, "after_login_page")
    log_screenshot(driver, "login_success")
    return True
"""

# 2. Для API-запросов (будут логироваться автоматически)
"""
import requests
response = requests.get("https://example.com/api/data")
"""

# 3. Для парсинга данных:
"""
from debug_utils import parsing_logger, log_parsed_content, log_function_call

@log_function_call(parsing_logger)
def extract_book_content(json_data):
    # ...код извлечения...
    log_parsed_content(extracted_content, "book_chapter_1")
    return extracted_content
"""

# 4. Для Flask-маршрутов:
"""
from flask import Flask, request
from debug_utils import web_logger, log_route

app = Flask(__name__)

@app.route('/api/data', methods=['POST'])
@log_route(web_logger)
def api_data():
    # ...код обработки...
    return jsonify({"status": "success"})
"""