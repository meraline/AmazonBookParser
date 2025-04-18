import json
import logging
import os
import time
from urllib.parse import urlparse, parse_qs
import re
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.firefox import GeckoDriverManager

# Импортируем расширенное логирование
from debug_utils import (
    selenium_logger,
    api_logger, 
    parsing_logger,
    log_function_call,
    log_page_content,
    log_screenshot,
    log_parsed_content
)

# Настраиваем базовое логирование
logging.basicConfig(
    level=logging.DEBUG,  # Повышаем уровень детализации
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    filename='kindle_auto_scraper.log'
)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger('').addHandler(console_handler)

# Логируем запуск модуля
selenium_logger.info("Модуль kindle_auto_api_scraper инициализирован")

class KindleAutoAPIScraper:
    def __init__(self, email=None, password=None, book_url=None, output_file="kindle_auto_book.txt", page_load_time=5, max_wait_time=30):
        """
        Инициализация автоматического API скрапера для Kindle Cloud Reader
        
        :param email: Email для входа в Amazon
        :param password: Пароль для входа в Amazon
        :param book_url: URL книги в Kindle Cloud Reader
        :param output_file: Имя файла для сохранения текста
        :param page_load_time: Время ожидания загрузки страницы в секундах
        :param max_wait_time: Максимальное время ожидания для операций Selenium
        """
        self.email = email
        self.password = password
        self.book_url = book_url
        self.output_file = output_file
        self.page_load_time = page_load_time
        self.max_wait_time = max_wait_time
        self.driver = None
        self.extracted_text = ""
        self.current_page = 0
        self.total_pages = 0
        self.current_page_callback = None
        self.asin = self._extract_asin(book_url) if book_url else None
        self.structured_content = {
            "type": "Success",
            "result": {
                "bookId": self.asin,
                "title": "",
                "author": "",
                "content": []
            }
        }

    def _extract_asin(self, url):
        """
        Извлекает ASIN книги из URL
        
        :param url: URL книги
        :return: ASIN книги или None
        """
        if not url:
            return None
            
        # Пытаемся найти ASIN в разных форматах URL
        try:
            # Формат 1: https://read.amazon.com/?asin=B009SE1Z9E
            if 'asin=' in url:
                parsed_url = urlparse(url)
                query_params = parse_qs(parsed_url.query)
                if 'asin' in query_params:
                    return query_params['asin'][0]
                    
            # Формат 2: https://read.amazon.com/reader?asin=B009SE1Z9E
            if 'reader?asin=' in url:
                parsed_url = urlparse(url)
                query_params = parse_qs(parsed_url.query)
                if 'asin' in query_params:
                    return query_params['asin'][0]
            
            # Формат 3: Другие форматы URL, пытаемся найти ASIN с помощью регулярного выражения
            asin_match = re.search(r'[A-Z0-9]{10}', url)
            if asin_match:
                return asin_match.group(0)
                
        except Exception as e:
            logging.error(f"Ошибка при извлечении ASIN: {str(e)}")
            
        return None

    def setup_driver(self):
        """
        Настройка и запуск веб-драйвера Firefox с перехватом сетевых запросов
        """
        try:
            logging.info("Настройка веб-драйвера Firefox")
            
            options = Options()
            options.add_argument("-headless")  # Запуск в фоновом режиме
            
            # Добавляем логгирование непосредственно в опции
            options.set_preference("devtools.netmonitor.enabled", True)
            options.set_preference("devtools.netmonitor.har.enabled", True)
            options.set_preference("devtools.netmonitor.har.defaultLogDir", os.getcwd())
            options.set_preference("devtools.netmonitor.har.enableAutoExportToFile", True)
            
            # Добавляем настройки логгирования
            options.log.level = "trace"  # Максимальный уровень логгирования
            
            service = Service(GeckoDriverManager().install())
            self.driver = webdriver.Firefox(service=service, options=options)
            self.driver.set_window_size(1366, 768)
            
            logging.info("Веб-драйвер Firefox успешно настроен")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при настройке веб-драйвера: {str(e)}")
            return False

    @log_function_call(selenium_logger)
    def login(self):
        """
        Авторизация на сайте Amazon
        
        :return: True если авторизация прошла успешно, иначе False
        """
        if not self.email or not self.password:
            selenium_logger.warning("Email или пароль не указаны, авторизация невозможна")
            return False
            
        try:
            selenium_logger.info("Открываем страницу авторизации Amazon")
            self.driver.get("https://www.amazon.com/ap/signin")
            
            # Сохраняем страницу до авторизации для отладки
            log_page_content(self.driver, "login_page_before")
            log_screenshot(self.driver, "login_page_before")
            
            # Ждем загрузки страницы
            WebDriverWait(self.driver, self.max_wait_time).until(
                EC.presence_of_element_located((By.ID, "ap_email"))
            )
            
            # Вводим email
            selenium_logger.info(f"Вводим email: {self.email}")
            email_field = self.driver.find_element(By.ID, "ap_email")
            email_field.clear()
            email_field.send_keys(self.email)
            
            # Логируем состояние после ввода email
            log_screenshot(self.driver, "after_email_entry")
            
            # Нажимаем кнопку "Continue"
            continue_button = self.driver.find_element(By.ID, "continue")
            continue_button.click()
            
            # Ждем загрузки страницы для ввода пароля
            WebDriverWait(self.driver, self.max_wait_time).until(
                EC.presence_of_element_located((By.ID, "ap_password"))
            )
            
            # Логируем состояние страницы пароля
            log_screenshot(self.driver, "password_page")
            
            # Вводим пароль
            selenium_logger.info("Вводим пароль")
            password_field = self.driver.find_element(By.ID, "ap_password")
            password_field.clear()
            password_field.send_keys(self.password)
            
            # Нажимаем кнопку "Sign-In"
            signin_button = self.driver.find_element(By.ID, "signInSubmit")
            signin_button.click()
            
            # Проверяем, что авторизация прошла успешно
            try:
                WebDriverWait(self.driver, self.max_wait_time).until(
                    lambda driver: "amazon.com" in driver.current_url and "ap/signin" not in driver.current_url
                )
                
                # Логируем состояние после авторизации
                log_screenshot(self.driver, "after_login_success")
                log_page_content(self.driver, "after_login_page")
                
                selenium_logger.info("Авторизация прошла успешно")
                return True
                
            except TimeoutException:
                # Логируем неудачную авторизацию
                log_screenshot(self.driver, "login_failure")
                log_page_content(self.driver, "login_failure_page")
                
                selenium_logger.error("Ошибка авторизации. Проверьте учетные данные.")
                return False
                
        except Exception as e:
            # Логируем ошибку
            log_screenshot(self.driver, "login_exception")
            selenium_logger.error(f"Ошибка при авторизации: {str(e)}")
            selenium_logger.error(f"Трассировка: {traceback.format_exc()}")
            return False

    def open_kindle_cloud_reader(self):
        """
        Открываем Kindle Cloud Reader
        
        :return: True если удалось открыть, иначе False
        """
        try:
            logging.info("Открываем Kindle Cloud Reader")
            self.driver.get("https://read.amazon.com")
            
            # Ждем загрузки страницы
            WebDriverWait(self.driver, self.max_wait_time).until(
                lambda driver: "read.amazon.com" in driver.current_url
            )
            
            # Проверяем, не перенаправило ли нас на страницу авторизации
            if "ap/signin" in self.driver.current_url:
                logging.info("Требуется авторизация")
                return self.login()
                
            logging.info("Kindle Cloud Reader успешно открыт")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при открытии Kindle Cloud Reader: {str(e)}")
            return False

    def open_book(self):
        """
        Открываем книгу по URL или ASIN
        
        :return: True если удалось открыть, иначе False
        """
        if not self.book_url and not self.asin:
            logging.error("Не указан URL книги или ASIN")
            return False
            
        try:
            url_to_open = self.book_url
            
            # Если URL не указан, но есть ASIN, формируем URL
            if not url_to_open and self.asin:
                url_to_open = f"https://read.amazon.com/reader?asin={self.asin}"
                
            logging.info(f"Открываем книгу по URL: {url_to_open}")
            self.driver.get(url_to_open)
            
            # Ждем загрузки книги
            time.sleep(self.page_load_time)
            
            # Проверяем, что книга открылась
            try:
                # Проверяем наличие элементов интерфейса Kindle Reader
                WebDriverWait(self.driver, self.max_wait_time).until(
                    lambda driver: "read.amazon.com/reader" in driver.current_url or 
                                  "read.amazon.com/kp" in driver.current_url
                )
                
                logging.info("Книга успешно открыта")
                return True
                
            except TimeoutException:
                logging.error("Ошибка при открытии книги. Проверьте URL или ASIN.")
                return False
                
        except Exception as e:
            logging.error(f"Ошибка при открытии книги: {str(e)}")
            return False

    def capture_network_traffic(self):
        """
        Перехватываем сетевой трафик для получения API-ответов
        
        :return: Словарь с перехваченными API-ответами
        """
        captured_data = []
        
        try:
            logging.info("Начинаем перехват сетевого трафика")
            
            # Включаем режим разработчика в Selenium (открываем DevTools)
            self.driver.execute_script("window.open()")
            self.driver.switch_to.window(self.driver.window_handles[1])
            self.driver.get("about:blank")
            
            # Запускаем JavaScript для перехвата запросов
            capture_script = """
            let capturedData = [];
            
            // Создаем новый объект Performance Observer
            const observer = new PerformanceObserver((list) => {
                list.getEntries().forEach((entry) => {
                    // Фильтруем только запросы к API Kindle
                    if (entry.initiatorType === 'xmlhttprequest' && 
                        (entry.name.includes('read.amazon.com/api') || 
                         entry.name.includes('amazon.com/service'))) {
                        console.log('Captured API request:', entry.name);
                        
                        // Отправляем запрос к URL для получения содержимого
                        fetch(entry.name)
                            .then(response => response.json())
                            .then(data => {
                                capturedData.push({
                                    url: entry.name,
                                    data: data
                                });
                                console.log('API response captured:', entry.name);
                            })
                            .catch(error => {
                                console.error('Error fetching API data:', error);
                            });
                    }
                });
            });
            
            // Начинаем наблюдение за PerformanceEntry типа resource
            observer.observe({ entryTypes: ['resource'] });
            
            // Функция для получения собранных данных
            window.getCapturedData = function() {
                return capturedData;
            };
            """
            
            self.driver.execute_script(capture_script)
            
            # Возвращаемся к окну с книгой
            self.driver.switch_to.window(self.driver.window_handles[0])
            
            # Перелистываем несколько страниц для получения контента
            logging.info("Перелистываем страницы для получения контента")
            for i in range(5):  # Перелистываем 5 страниц
                # Нажимаем на правую часть экрана для перелистывания вперед
                try:
                    webdriver.ActionChains(self.driver).move_to_element_with_offset(
                        self.driver.find_element(By.TAG_NAME, 'body'),
                        self.driver.get_window_size()['width'] - 100,
                        self.driver.get_window_size()['height'] // 2
                    ).click().perform()
                    
                    # Пауза для загрузки страницы
                    time.sleep(self.page_load_time)
                    self.current_page = i + 1
                    
                    if self.current_page_callback:
                        self.current_page_callback(self.current_page, 5)
                        
                    logging.info(f"Перелистана страница {i+1}")
                    
                except Exception as e:
                    logging.error(f"Ошибка при перелистывании страницы: {str(e)}")
                    
            # Переходим обратно к окну с DevTools
            self.driver.switch_to.window(self.driver.window_handles[1])
            
            # Получаем собранные данные
            captured_data = self.driver.execute_script("return window.getCapturedData();")
            
            logging.info(f"Перехвачено {len(captured_data)} API-ответов")
            
            # Возвращаемся к окну с книгой
            self.driver.switch_to.window(self.driver.window_handles[0])
            
            return captured_data
            
        except Exception as e:
            logging.error(f"Ошибка при перехвате сетевого трафика: {str(e)}")
            return []

    def extract_content_from_api_responses(self, api_responses):
        """
        Извлекает структурированный контент из перехваченных API-ответов
        
        :param api_responses: Список с перехваченными API-ответами
        :return: True если удалось извлечь контент, иначе False
        """
        if not api_responses:
            logging.warning("Нет перехваченных API-ответов для обработки")
            return False
            
        try:
            logging.info(f"Начинаем обработку {len(api_responses)} API-ответов")
            
            # Создаем словарь для отслеживания номеров страниц
            page_content = {}
            book_metadata = {
                "title": "",
                "author": "",
                "bookId": self.asin or ""
            }
            
            # Обрабатываем каждый ответ
            for response in api_responses:
                url = response.get('url', '')
                data = response.get('data', {})
                
                # Пропускаем пустые ответы
                if not data:
                    continue
                    
                logging.info(f"Обрабатываем ответ API: {url}")
                
                # Обработка различных типов API-ответов
                
                # Тип 1: Ответ с метаданными книги
                if '/metadata' in url or '/lookup' in url:
                    if isinstance(data, dict):
                        if 'title' in data:
                            book_metadata['title'] = data['title']
                        if 'author' in data:
                            book_metadata['author'] = data['author']
                        if 'asin' in data:
                            book_metadata['bookId'] = data['asin']
                            
                # Тип 2: Ответ с содержимым страницы
                if '/content' in url or '/pages' in url:
                    self._process_content_response(data, page_content)
                    
                # Тип 3: Ответ со структурой глав
                if '/chapters' in url or '/toc' in url:
                    self._process_chapters_response(data)
                    
            # Формируем структурированный контент
            self._format_structured_content(book_metadata, page_content)
            
            return len(page_content) > 0
            
        except Exception as e:
            logging.error(f"Ошибка при извлечении контента из API-ответов: {str(e)}")
            return False

    def _process_content_response(self, data, page_content):
        """
        Обрабатывает ответ API с содержимым страницы
        
        :param data: Данные ответа API
        :param page_content: Словарь для сохранения содержимого страниц
        """
        try:
            # Ищем текстовое содержимое в разных форматах API-ответов
            
            # Формат 1: Прямой ответ с содержимым
            if 'content' in data:
                content = data['content']
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and 'pageNumber' in item and 'text' in item:
                            page_number = item['pageNumber']
                            text = item['text']
                            page_content[page_number] = text
                            
                elif isinstance(content, dict):
                    for page_number, text in content.items():
                        if isinstance(text, str):
                            page_content[page_number] = text
                            
            # Формат 2: Вложенная структура с содержимым
            elif 'result' in data and 'content' in data['result']:
                content = data['result']['content']
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and 'pageNumber' in item and 'text' in item:
                            page_number = item['pageNumber']
                            text = item['text']
                            page_content[page_number] = text
                            
            # Формат 3: Содержимое в виде HTML
            elif 'html' in data or 'body' in data:
                html_content = data.get('html', data.get('body', ''))
                if html_content:
                    # Примитивное извлечение текста из HTML
                    text = re.sub(r'<[^>]+>', ' ', html_content)
                    text = re.sub(r'\s+', ' ', text).strip()
                    
                    # Используем текущее количество страниц + 1
                    page_number = len(page_content) + 1
                    page_content[page_number] = text
                    
        except Exception as e:
            logging.error(f"Ошибка при обработке содержимого страницы: {str(e)}")

    def _process_chapters_response(self, data):
        """
        Обрабатывает ответ API со структурой глав
        
        :param data: Данные ответа API
        """
        # Реализация будет добавлена при необходимости
        pass

    def _format_structured_content(self, metadata, page_content):
        """
        Форматирует извлеченный контент в структурированный формат
        
        :param metadata: Метаданные книги
        :param page_content: Словарь с содержимым страниц
        """
        try:
            # Обновляем метаданные книги
            self.structured_content['result']['bookId'] = metadata['bookId']
            self.structured_content['result']['title'] = metadata['title']
            self.structured_content['result']['author'] = metadata['author']
            
            # Очищаем существующий контент
            self.structured_content['result']['content'] = []
            
            # Добавляем содержимое страниц в отсортированном порядке
            for page_number in sorted(page_content.keys(), key=lambda x: int(x) if isinstance(x, str) and x.isdigit() else x):
                text = page_content[page_number]
                self.structured_content['result']['content'].append({
                    'pageNumber': page_number,
                    'text': text
                })
                
            # Обновляем общее количество страниц
            self.total_pages = len(self.structured_content['result']['content'])
            
            # Формируем извлеченный текст
            self.extracted_text = ""
            for item in self.structured_content['result']['content']:
                self.extracted_text += f"--- Страница {item['pageNumber']} ---\n"
                self.extracted_text += item['text']
                self.extracted_text += "\n\n"
                
            logging.info(f"Структурированный контент сформирован. Извлечено {self.total_pages} страниц.")
            
        except Exception as e:
            logging.error(f"Ошибка при форматировании структурированного контента: {str(e)}")

    def save_text(self):
        """
        Сохраняет извлеченный текст в файл
        
        :return: True если успешно, иначе False
        """
        try:
            if not self.extracted_text:
                logging.warning("Нет текстового содержимого для сохранения")
                return False
                
            # Сохраняем текст в файл
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(self.extracted_text)
                
            logging.info(f"Текст успешно сохранен в файл: {self.output_file}")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при сохранении текста: {str(e)}")
            return False

    def save_structured_content(self):
        """
        Сохраняет структурированный JSON с извлеченным контентом книги
        
        :return: True если успешно, иначе False
        """
        try:
            if not self.structured_content['result']['content']:
                logging.warning("Нет структурированного содержимого для сохранения")
                return False
                
            # Формируем имя файла JSON
            json_file = self.output_file.replace('.txt', '.json')
            
            # Сохраняем JSON в файл
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(self.structured_content, f, ensure_ascii=False, indent=2)
                
            logging.info(f"Структурированный контент успешно сохранен в файл: {json_file}")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при сохранении структурированного контента: {str(e)}")
            return False

    def cleanup(self):
        """
        Очистка ресурсов и закрытие драйвера
        """
        try:
            if self.driver:
                logging.info("Закрываем браузер")
                self.driver.quit()
                
        except Exception as e:
            logging.error(f"Ошибка при закрытии браузера: {str(e)}")

    def run(self):
        """
        Запускает весь процесс извлечения
        
        :return: True если успешно, иначе False
        """
        try:
            # Настраиваем веб-драйвер
            if not self.setup_driver():
                return False
                
            # Открываем Kindle Cloud Reader
            if not self.open_kindle_cloud_reader():
                self.cleanup()
                return False
                
            # Открываем книгу
            if not self.open_book():
                self.cleanup()
                return False
                
            # Перехватываем сетевой трафик
            api_responses = self.capture_network_traffic()
            
            # Извлекаем контент из API-ответов
            if not self.extract_content_from_api_responses(api_responses):
                logging.warning("Не удалось извлечь контент из API-ответов")
                
                # Если не удалось извлечь контент, пробуем получить текст напрямую со страницы
                logging.info("Пытаемся извлечь текст напрямую со страницы")
                
                # Переключаемся на окно с книгой
                self.driver.switch_to.window(self.driver.window_handles[0])
                
                # Извлекаем текст
                text_elements = self.driver.find_elements(By.CSS_SELECTOR, ".kindleReader-content")
                if text_elements:
                    self.extracted_text = "\n\n".join([el.text for el in text_elements if el.text])
                    
                    # Формируем примитивный структурированный контент
                    self.structured_content['result']['content'] = [{
                        'pageNumber': 1,
                        'text': self.extracted_text
                    }]
                    
                    self.total_pages = 1
                    
                    logging.info("Текст успешно извлечен напрямую со страницы")
                else:
                    logging.error("Не удалось извлечь текст со страницы")
                    self.cleanup()
                    return False
                    
            # Сохраняем извлеченный текст
            self.save_text()
            
            # Сохраняем структурированный контент
            self.save_structured_content()
            
            # Очищаем ресурсы
            self.cleanup()
            
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при запуске процесса извлечения: {str(e)}")
            self.cleanup()
            return False


# Пример использования
if __name__ == "__main__":
    scraper = KindleAutoAPIScraper(
        email="your.email@example.com",
        password="your_password",
        book_url="https://read.amazon.com/reader?asin=B009SE1Z9E",
        output_file="kindle_auto_book.txt"
    )
    
    scraper.run()