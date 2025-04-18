import json
import logging
import os
import sys
import time
import traceback
from urllib.parse import urlparse, parse_qs
import re
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.chrome import ChromeDriverManager

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

    @log_function_call(selenium_logger)
    def setup_driver(self):
        """
        Настройка и запуск веб-драйвера с поддержкой различных браузеров
        """
        try:
            # Пробуем сначала использовать Firefox напрямую
            return self._setup_direct_browser()
        except Exception as direct_error:
            selenium_logger.warning(f"Не удалось настроить браузер напрямую: {str(direct_error)}")
            selenium_logger.info("Пробуем установить браузерный драйвер...")
            
            # Если прямой запуск не удался, пробуем установку драйвера
            try:
                return self._setup_managed_browser()
            except Exception as managed_error:
                selenium_logger.error(f"Не удалось установить и настроить драйвер: {str(managed_error)}")
                selenium_logger.error(f"Трассировка: {traceback.format_exc()}")
                return False
    
    def _setup_direct_browser(self):
        """
        Настройка и запуск браузера с использованием локальных драйверов
        """
        selenium_logger.info("Пробуем настроить локально установленный браузер")
        
        # Сначала пробуем Firefox с явным указанием пути
        try:
            selenium_logger.info("Пробуем локальный Firefox с поиском пути")
            
            # Ищем исполняемый файл Firefox в системе
            firefox_paths = [
                "/usr/bin/firefox",
                "/usr/local/bin/firefox",
                "/snap/bin/firefox",
                "/Applications/Firefox.app/Contents/MacOS/firefox-bin",  # macOS
                "C:\\Program Files\\Mozilla Firefox\\firefox.exe",       # Windows
                "C:\\Program Files (x86)\\Mozilla Firefox\\firefox.exe"  # Windows 32-bit
            ]
            
            firefox_binary = None
            for path in firefox_paths:
                if os.path.exists(path):
                    firefox_binary = path
                    selenium_logger.info(f"Найден Firefox по пути: {path}")
                    break
            
            options = FirefoxOptions()
            if firefox_binary:
                options.binary_location = firefox_binary
            
            # Минимальные настройки для стабильного запуска
            options.set_preference("browser.cache.disk.enable", False)
            options.set_preference("browser.cache.memory.enable", False)
            
            # Создаём драйвер, возможно с указанием пути к драйверу
            geckodriver_path = os.path.join(os.getcwd(), "geckodriver")
            if os.path.exists(geckodriver_path):
                selenium_logger.info(f"Используем локальный geckodriver: {geckodriver_path}")
                service = FirefoxService(executable_path=geckodriver_path)
                self.driver = webdriver.Firefox(service=service, options=options)
            else:
                self.driver = webdriver.Firefox(options=options)
                
            self.driver.set_window_size(1366, 768)
            selenium_logger.info("Firefox запущен успешно с локальным драйвером")
            
            return True
        except Exception as firefox_error:
            selenium_logger.warning(f"Не удалось запустить локальный Firefox: {str(firefox_error)}")
            
            # Если Firefox не удалось запустить, пробуем Chrome
            try:
                selenium_logger.info("Пробуем локальный Chrome со стандартными опциями")
                
                # Поиск пути к Chrome
                chrome_paths = [
                    "/usr/bin/google-chrome",
                    "/usr/bin/chromium-browser",
                    "/usr/bin/chromium",
                    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
                    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",    # Windows
                    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"  # Windows 32-bit
                ]
                
                chrome_binary = None
                for path in chrome_paths:
                    if os.path.exists(path):
                        chrome_binary = path
                        selenium_logger.info(f"Найден Chrome по пути: {path}")
                        break
                
                options = ChromeOptions()
                if chrome_binary:
                    options.binary_location = chrome_binary
                
                # Минимальные опции для стабильного запуска
                options.add_argument("--window-size=1366,768")
                options.add_argument("--disable-notifications")
                
                # Отключаем опции перехвата, которые вызывают ошибку
                # options.add_argument("--auto-open-devtools-for-tabs")
                # options.add_experimental_option("perfLoggingPrefs", {...})
                
                # Проверяем, есть ли локальный chromedriver
                chromedriver_path = os.path.join(os.getcwd(), "chromedriver")
                if os.path.exists(chromedriver_path):
                    selenium_logger.info(f"Используем локальный chromedriver: {chromedriver_path}")
                    service = ChromeService(executable_path=chromedriver_path)
                    self.driver = webdriver.Chrome(service=service, options=options)
                else:
                    self.driver = webdriver.Chrome(options=options)
                
                selenium_logger.info("Chrome запущен успешно с локальным драйвером")
                
                return True
            except Exception as chrome_error:
                selenium_logger.warning(f"Не удалось запустить локальный Chrome: {str(chrome_error)}")
                raise Exception(f"Firefox error: {str(firefox_error)}, Chrome error: {str(chrome_error)}")
    
    def _setup_managed_browser(self):
        """
        Настройка и запуск браузера с автоматической установкой драйверов
        """
        selenium_logger.info("Пробуем установить драйвер и запустить браузер")
        
        try:
            # Сначала Firefox с webdriver-manager
            selenium_logger.info("Устанавливаем geckodriver")
            options = FirefoxOptions()
            
            # Минимальные настройки для стабильного запуска
            options.set_preference("browser.cache.disk.enable", False)
            options.set_preference("browser.cache.memory.enable", False)
            
            # Устанавливаем без параметра timeout (который вызывает ошибку в вашей версии)
            service = FirefoxService(GeckoDriverManager().install())
            self.driver = webdriver.Firefox(service=service, options=options)
            self.driver.set_window_size(1366, 768)
            
            selenium_logger.info("Firefox успешно запущен с установленным драйвером")
            return True
        except Exception as firefox_error:
            selenium_logger.warning(f"Не удалось установить и запустить Firefox: {str(firefox_error)}")
            
            # Если Firefox не удалось, пробуем Chrome
            try:
                selenium_logger.info("Устанавливаем chromedriver")
                options = ChromeOptions()
                options.add_argument("--window-size=1366,768")
                options.add_argument("--disable-notifications")
                
                # Отключаем опции, которые вызывают ошибку
                # options.add_argument("--auto-open-devtools-for-tabs")
                # options.add_experimental_option("perfLoggingPrefs", {...})
                
                # Устанавливаем без параметра timeout (который вызывает ошибку в вашей версии)
                service = ChromeService(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
                
                selenium_logger.info("Chrome успешно запущен с установленным драйвером")
                return True
            except Exception as chrome_error:
                selenium_logger.error(f"Не удалось установить и запустить Chrome: {str(chrome_error)}")
                raise Exception(f"Firefox install error: {str(firefox_error)}, Chrome install error: {str(chrome_error)}")

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

    @log_function_call(parsing_logger)
    def navigate_with_screenshots(self):
        """
        Перелистывает страницы книги и делает скриншот каждой страницы
        
        :return: True если успешно, иначе False
        """
        try:
            selenium_logger.info("Начинаем навигацию по страницам книги со скриншотами")
            
            # Создаем директорию для скриншотов, если она не существует
            screenshots_dir = os.path.join(os.getcwd(), "kindle_screenshots")
            if not os.path.exists(screenshots_dir):
                os.makedirs(screenshots_dir)
                selenium_logger.info(f"Создана директория для скриншотов: {screenshots_dir}")
            
            # Ждем некоторое время, чтобы интерфейс Kindle полностью загрузился
            time.sleep(self.page_load_time)
            
            # Начинаем с первой страницы
            current_page = 1
            max_pages = self.max_wait_time  # Используем max_wait_time в качестве ограничения
            
            # Делаем скриншот первой страницы
            screenshot_path = os.path.join(screenshots_dir, f"page_{current_page:04d}.png")
            selenium_logger.info(f"Делаем скриншот страницы {current_page}")
            self.driver.save_screenshot(screenshot_path)
            selenium_logger.info(f"Скриншот сохранен: {screenshot_path}")
            
            # Обрабатываем остальные страницы
            while current_page < max_pages:
                # Перелистываем на следующую страницу
                try:
                    # Находим body и отправляем ARROW_RIGHT для перелистывания
                    from selenium.webdriver.common.keys import Keys
                    body = self.driver.find_element(By.TAG_NAME, "body")
                    body.send_keys(Keys.ARROW_RIGHT)
                    
                    # Ждем загрузки новой страницы
                    time.sleep(2)  # Увеличенная задержка для надежности
                    
                    # Увеличиваем счетчик текущей страницы
                    current_page += 1
                    
                    # Обновляем callback при наличии
                    if self.current_page_callback:
                        self.current_page_callback(current_page, max_pages)
                    
                    # Делаем скриншот
                    screenshot_path = os.path.join(screenshots_dir, f"page_{current_page:04d}.png")
                    selenium_logger.info(f"Делаем скриншот страницы {current_page}")
                    self.driver.save_screenshot(screenshot_path)
                    selenium_logger.info(f"Скриншот сохранен: {screenshot_path}")
                    
                except Exception as e:
                    selenium_logger.error(f"Ошибка при перелистывании на страницу {current_page + 1}: {str(e)}")
                    break
            
            selenium_logger.info(f"Навигация завершена. Создано {current_page} скриншотов.")
            selenium_logger.info(f"Скриншоты сохранены в директории: {screenshots_dir}")
            return True
            
        except Exception as e:
            selenium_logger.error(f"Ошибка при навигации и создании скриншотов: {str(e)}")
            selenium_logger.error(f"Трассировка: {traceback.format_exc()}")
            return False
    
    def extract_content_from_api_responses(self, api_responses):
        """
        Извлекает структурированный контент из перехваченных API-ответов
        
        :param api_responses: Список с перехваченными API-ответами
        :return: True если удалось извлечь контент, иначе False
        """
        if not api_responses:
            parsing_logger.warning("Нет перехваченных API-ответов для обработки")
            return False
            
        try:
            # Сохраняем все API-ответы для детального анализа
            log_parsed_content(api_responses, "raw_api_responses")
            
            parsing_logger.info(f"Начинаем обработку {len(api_responses)} API-ответов")
            
            # Создаем словарь для отслеживания номеров страниц
            page_content = {}
            book_metadata = {
                "title": "",
                "author": "",
                "bookId": self.asin or ""
            }
            
            # Обрабатываем каждый ответ
            for index, response in enumerate(api_responses):
                url = response.get('url', '')
                data = response.get('data', {})
                
                # Сохраняем ответ для детального анализа
                log_parsed_content(response, f"api_response_{index}")
                
                # Пропускаем пустые ответы
                if not data:
                    parsing_logger.warning(f"Пропускаем пустой ответ API #{index} от URL: {url}")
                    continue
                    
                parsing_logger.info(f"Обрабатываем ответ API #{index}: {url}")
                
                # Обработка различных типов API-ответов
                
                # Тип 1: Ответ с метаданными книги
                if '/metadata' in url or '/lookup' in url:
                    parsing_logger.debug(f"Определен тип ответа: МЕТАДАННЫЕ (URL: {url})")
                    if isinstance(data, dict):
                        if 'title' in data:
                            book_metadata['title'] = data['title']
                            parsing_logger.info(f"Извлечено название книги: {data['title']}")
                        if 'author' in data:
                            book_metadata['author'] = data['author']
                            parsing_logger.info(f"Извлечен автор книги: {data['author']}")
                        if 'asin' in data:
                            book_metadata['bookId'] = data['asin']
                            parsing_logger.info(f"Извлечен ID книги: {data['asin']}")
                            
                # Тип 2: Ответ с содержимым страницы
                if '/content' in url or '/pages' in url:
                    parsing_logger.debug(f"Определен тип ответа: СОДЕРЖИМОЕ СТРАНИЦЫ (URL: {url})")
                    # Сохраняем данные для анализа структуры страницы
                    log_parsed_content(data, f"content_response_{index}")
                    
                    # Проверяем структуру данных перед обработкой
                    if isinstance(data, dict):
                        parsing_logger.debug(f"Структура ответа: {list(data.keys())}")
                    elif isinstance(data, list):
                        parsing_logger.debug(f"Ответ представляет собой список из {len(data)} элементов")
                    
                    self._process_content_response(data, page_content)
                    
                # Тип 3: Ответ со структурой глав
                if '/chapters' in url or '/toc' in url:
                    parsing_logger.debug(f"Определен тип ответа: СТРУКТУРА ГЛАВ (URL: {url})")
                    # Сохраняем данные для анализа структуры глав
                    log_parsed_content(data, f"chapters_response_{index}")
                    self._process_chapters_response(data)
            
            # Сохраняем извлеченные метаданные для анализа
            log_parsed_content(book_metadata, "extracted_metadata")
            
            # Сохраняем извлеченное содержимое страниц
            log_parsed_content(page_content, "extracted_page_content")
                    
            # Формируем структурированный контент
            self._format_structured_content(book_metadata, page_content)
            
            # Сохраняем итоговую структуру контента
            log_parsed_content(self.structured_content, "final_structured_content")
            
            # Проверяем, удалось ли извлечь контент
            result = len(page_content) > 0
            if result:
                parsing_logger.info(f"Успешно извлечено содержимое {len(page_content)} страниц")
            else:
                parsing_logger.error("Не удалось извлечь контент из API-ответов")
                
            return result
            
        except Exception as e:
            parsing_logger.error(f"Ошибка при извлечении контента из API-ответов: {str(e)}")
            parsing_logger.error(f"Трассировка: {traceback.format_exc()}")
            return False

    @log_function_call(parsing_logger)
    def _process_content_response(self, data, page_content):
        """
        Обрабатывает ответ API с содержимым страницы
        
        :param data: Данные ответа API
        :param page_content: Словарь для сохранения содержимого страниц
        """
        try:
            # Ищем текстовое содержимое в разных форматах API-ответов
            parsing_logger.debug(f"Начинаем обработку содержимого страницы, тип данных: {type(data).__name__}")
            
            # Формат 1: Прямой ответ с содержимым
            if 'content' in data:
                parsing_logger.debug("Обнаружен ключ 'content' в ответе")
                content = data['content']
                
                if isinstance(content, list):
                    parsing_logger.debug(f"Содержимое представляет собой список из {len(content)} элементов")
                    for index, item in enumerate(content):
                        if isinstance(item, dict) and 'pageNumber' in item and 'text' in item:
                            page_number = item['pageNumber']
                            text = item['text']
                            page_content[page_number] = text
                            parsing_logger.debug(f"Извлечен текст для страницы {page_number} ({len(text)} символов)")
                        else:
                            parsing_logger.warning(f"Элемент #{index} не содержит необходимых полей: {item.keys() if isinstance(item, dict) else type(item).__name__}")
                            
                elif isinstance(content, dict):
                    parsing_logger.debug(f"Содержимое представляет собой словарь с ключами: {list(content.keys())}")
                    for page_number, text in content.items():
                        if isinstance(text, str):
                            page_content[page_number] = text
                            parsing_logger.debug(f"Извлечен текст для страницы {page_number} ({len(text)} символов)")
                        else:
                            parsing_logger.warning(f"Значение для страницы {page_number} не является строкой: {type(text).__name__}")
                else:
                    parsing_logger.warning(f"Содержимое имеет неожиданный тип: {type(content).__name__}")
                            
            # Формат 2: Вложенная структура с содержимым
            elif 'result' in data and 'content' in data['result']:
                parsing_logger.debug("Обнаружена вложенная структура 'result.content'")
                content = data['result']['content']
                
                if isinstance(content, list):
                    parsing_logger.debug(f"Содержимое представляет собой список из {len(content)} элементов")
                    for index, item in enumerate(content):
                        if isinstance(item, dict) and 'pageNumber' in item and 'text' in item:
                            page_number = item['pageNumber']
                            text = item['text']
                            page_content[page_number] = text
                            parsing_logger.debug(f"Извлечен текст для страницы {page_number} ({len(text)} символов)")
                        else:
                            parsing_logger.warning(f"Элемент #{index} не содержит необходимых полей: {item.keys() if isinstance(item, dict) else type(item).__name__}")
                else:
                    parsing_logger.warning(f"Содержимое в 'result.content' имеет неожиданный тип: {type(content).__name__}")
                            
            # Формат 3: Содержимое в виде HTML
            elif 'html' in data or 'body' in data:
                parsing_logger.debug("Обнаружен HTML-контент")
                html_content = data.get('html', data.get('body', ''))
                
                if html_content:
                    # Логируем фрагмент HTML для анализа
                    sample = html_content[:200] + "..." if len(html_content) > 200 else html_content
                    parsing_logger.debug(f"Образец HTML: {sample}")
                    
                    # Примитивное извлечение текста из HTML
                    text = re.sub(r'<[^>]+>', ' ', html_content)
                    text = re.sub(r'\s+', ' ', text).strip()
                    
                    # Используем текущее количество страниц + 1
                    page_number = len(page_content) + 1
                    page_content[page_number] = text
                    parsing_logger.debug(f"Извлечен текст из HTML для страницы {page_number} ({len(text)} символов)")
            else:
                # Не найдены известные структуры данных
                parsing_logger.warning(f"Не обнаружена известная структура данных. Доступные ключи: {list(data.keys()) if isinstance(data, dict) else 'Не словарь'}")
                
            # Логируем результат обработки
            parsing_logger.info(f"Извлечено {len(page_content)} страниц контента")
                    
        except Exception as e:
            parsing_logger.error(f"Ошибка при обработке содержимого страницы: {str(e)}")
            parsing_logger.error(f"Трассировка: {traceback.format_exc()}")

    def _process_chapters_response(self, data):
        """
        Обрабатывает ответ API со структурой глав
        
        :param data: Данные ответа API
        """
        # Реализация будет добавлена при необходимости
        pass

    @log_function_call(parsing_logger)
    def _format_structured_content(self, metadata, page_content):
        """
        Форматирует извлеченный контент в структурированный формат
        
        :param metadata: Метаданные книги
        :param page_content: Словарь с содержимым страниц
        """
        try:
            parsing_logger.debug(f"Начинаем форматирование структурированного контента. Метаданные: {metadata}")
            parsing_logger.debug(f"Количество страниц с контентом: {len(page_content)}")
            
            # Обновляем метаданные книги
            self.structured_content['result']['bookId'] = metadata['bookId']
            self.structured_content['result']['title'] = metadata['title']
            self.structured_content['result']['author'] = metadata['author']
            
            # Логируем обновленные метаданные
            parsing_logger.info(f"Обновлены метаданные книги: ID={metadata['bookId']}, Название='{metadata['title']}', Автор='{metadata['author']}'")
            
            # Очищаем существующий контент
            self.structured_content['result']['content'] = []
            
            # Добавляем содержимое страниц в отсортированном порядке
            page_keys = list(page_content.keys())
            parsing_logger.debug(f"Номера страниц перед сортировкой: {page_keys}")
            
            # Сортируем номера страниц
            sorted_keys = sorted(page_content.keys(), key=lambda x: int(x) if isinstance(x, str) and x.isdigit() else x)
            parsing_logger.debug(f"Номера страниц после сортировки: {sorted_keys}")
            
            for page_number in sorted_keys:
                text = page_content[page_number]
                self.structured_content['result']['content'].append({
                    'pageNumber': page_number,
                    'text': text
                })
                parsing_logger.debug(f"Добавлена страница {page_number} с текстом ({len(text)} символов)")
                
            # Обновляем общее количество страниц
            self.total_pages = len(self.structured_content['result']['content'])
            
            # Формируем извлеченный текст
            self.extracted_text = ""
            for item in self.structured_content['result']['content']:
                self.extracted_text += f"--- Страница {item['pageNumber']} ---\n"
                self.extracted_text += item['text']
                self.extracted_text += "\n\n"
                
            # Сохраняем образец извлеченного текста для анализа
            text_sample = self.extracted_text[:500] + "..." if len(self.extracted_text) > 500 else self.extracted_text
            parsing_logger.debug(f"Образец извлеченного текста: {text_sample}")
            
            parsing_logger.info(f"Структурированный контент сформирован. Извлечено {self.total_pages} страниц.")
            parsing_logger.info(f"Общий размер извлеченного текста: {len(self.extracted_text)} символов")
            
        except Exception as e:
            parsing_logger.error(f"Ошибка при форматировании структурированного контента: {str(e)}")
            parsing_logger.error(f"Трассировка: {traceback.format_exc()}")

    @log_function_call(parsing_logger)
    def save_text(self):
        """
        Сохраняет извлеченный текст в файл
        
        :return: True если успешно, иначе False
        """
        try:
            if not self.extracted_text:
                parsing_logger.warning("Нет текстового содержимого для сохранения")
                return False
            
            parsing_logger.info(f"Сохраняем извлеченный текст в файл: {self.output_file}")
            parsing_logger.debug(f"Размер текста: {len(self.extracted_text)} символов")
                
            # Сохраняем текст в файл
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(self.extracted_text)
                
            parsing_logger.info(f"Текст успешно сохранен в файл: {self.output_file}")
            return True
            
        except Exception as e:
            parsing_logger.error(f"Ошибка при сохранении текста: {str(e)}")
            parsing_logger.error(f"Трассировка: {traceback.format_exc()}")
            return False

    @log_function_call(parsing_logger)
    def save_structured_content(self):
        """
        Сохраняет структурированный JSON с извлеченным контентом книги
        
        :return: True если успешно, иначе False
        """
        try:
            if not self.structured_content['result']['content']:
                parsing_logger.warning("Нет структурированного содержимого для сохранения")
                return False
            
            # Формируем имя файла JSON
            json_file = self.output_file.replace('.txt', '.json')
            parsing_logger.info(f"Сохраняем структурированный контент в файл: {json_file}")
            
            # Логируем статистику контента
            content_stats = {
                "total_pages": len(self.structured_content['result']['content']),
                "title_length": len(self.structured_content['result']['title']),
                "author_length": len(self.structured_content['result']['author']),
                "bookId": self.structured_content['result']['bookId']
            }
            parsing_logger.debug(f"Статистика контента: {content_stats}")
            
            # Сохраняем JSON в файл
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(self.structured_content, f, ensure_ascii=False, indent=2)
                
            parsing_logger.info(f"Структурированный контент успешно сохранен в файл: {json_file}")
            return True
            
        except Exception as e:
            parsing_logger.error(f"Ошибка при сохранении структурированного контента: {str(e)}")
            parsing_logger.error(f"Трассировка: {traceback.format_exc()}")
            return False

    @log_function_call(selenium_logger)
    def cleanup(self):
        """
        Очистка ресурсов и закрытие драйвера
        """
        try:
            if self.driver:
                selenium_logger.info("Закрываем браузер")
                
                # Сохраняем финальный скриншот для отладки
                try:
                    log_screenshot(self.driver, "final_state_before_quit")
                except Exception as screenshot_err:
                    selenium_logger.warning(f"Не удалось сохранить финальный скриншот: {str(screenshot_err)}")
                
                self.driver.quit()
                selenium_logger.info("Браузер успешно закрыт")
                
        except Exception as e:
            selenium_logger.error(f"Ошибка при закрытии браузера: {str(e)}")
            selenium_logger.error(f"Трассировка: {traceback.format_exc()}")

    def _generate_environment_report(self):
        """
        Генерирует отчет о системном окружении для отладки
        """
        try:
            env_report = {
                "os_info": os.name,
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "cwd": os.getcwd(),
                "packages": {
                    "selenium": getattr(selenium, "__version__", "unknown"),
                    "requests": getattr(requests, "__version__", "unknown")
                }
            }
            
            # Проверяем доступность браузеров
            try:
                import shutil
                env_report["browsers"] = {
                    "firefox_path": shutil.which("firefox"),
                    "chrome_path": shutil.which("chrome") or shutil.which("chromium") or shutil.which("google-chrome"),
                    "geckodriver_path": shutil.which("geckodriver"),
                    "chromedriver_path": shutil.which("chromedriver")
                }
            except Exception as browser_error:
                env_report["browsers_error"] = str(browser_error)
            
            # Проверяем сетевую доступность ключевых сервисов
            try:
                network_checks = {}
                for url in ["https://www.amazon.com", "https://read.amazon.com"]:
                    try:
                        response = requests.head(url, timeout=5)
                        network_checks[url] = {
                            "status_code": response.status_code,
                            "reachable": True
                        }
                    except Exception as req_err:
                        network_checks[url] = {
                            "error": str(req_err),
                            "reachable": False
                        }
                env_report["network_checks"] = network_checks
            except Exception as net_error:
                env_report["network_error"] = str(net_error)
                
            # Записываем отчет в файл
            report_file = "environment_report.json"
            with open(report_file, "w") as f:
                json.dump(env_report, f, indent=2)
                
            selenium_logger.info(f"Отчет о системном окружении сохранен в {report_file}")
            return env_report
        except Exception as e:
            selenium_logger.error(f"Ошибка при создании отчета окружения: {str(e)}")
            return {"error": str(e)}

    @log_function_call(selenium_logger)
    def run(self):
        """
        Запускает весь процесс извлечения
        
        :return: True если успешно, иначе False
        """
        try:
            selenium_logger.info("Запускаем процесс извлечения книги")
            selenium_logger.info(f"URL книги: {self.book_url}")
            selenium_logger.info(f"ASIN книги: {self.asin}")
            
            # Настраиваем веб-драйвер
            selenium_logger.info("Настраиваем веб-драйвер")
            if not self.setup_driver():
                selenium_logger.error("Не удалось настроить веб-драйвер")
                # Генерируем отчет о среде при неудаче
                self._generate_environment_report()
                return False
                
            # Открываем Kindle Cloud Reader
            selenium_logger.info("Открываем Kindle Cloud Reader")
            if not self.open_kindle_cloud_reader():
                selenium_logger.error("Не удалось открыть Kindle Cloud Reader")
                self.cleanup()
                return False
                
            # Открываем книгу
            selenium_logger.info(f"Открываем книгу, ASIN: {self.asin}")
            if not self.open_book():
                selenium_logger.error(f"Не удалось открыть книгу, ASIN: {self.asin}")
                self.cleanup()
                return False
                
            # Перехватываем сетевой трафик
            selenium_logger.info("Перехватываем сетевой трафик")
            api_responses = self.capture_network_traffic()
            selenium_logger.info(f"Перехвачено {len(api_responses) if api_responses else 0} API-ответов")
            
            # Извлекаем контент из API-ответов
            parsing_logger.info("Извлекаем контент из API-ответов")
            if not self.extract_content_from_api_responses(api_responses):
                parsing_logger.warning("Не удалось извлечь контент из API-ответов")
                
                # Если не удалось извлечь контент, пробуем получить текст напрямую со страницы
                selenium_logger.info("Пытаемся извлечь текст напрямую со страницы")
                
                # Переключаемся на окно с книгой
                try:
                    selenium_logger.debug(f"Доступные окна: {len(self.driver.window_handles)}")
                    self.driver.switch_to.window(self.driver.window_handles[0])
                    
                    # Логируем состояние страницы для отладки
                    log_screenshot(self.driver, "before_direct_extraction")
                    log_page_content(self.driver, "before_direct_extraction")
                    
                    # Извлекаем текст
                    selenium_logger.debug("Ищем элементы контента на странице")
                    text_elements = self.driver.find_elements(By.CSS_SELECTOR, ".kindleReader-content")
                    selenium_logger.debug(f"Найдено {len(text_elements)} элементов контента")
                    
                    if text_elements:
                        extracted_texts = [el.text for el in text_elements if el.text]
                        self.extracted_text = "\n\n".join(extracted_texts)
                        selenium_logger.info(f"Извлечен текст ({len(self.extracted_text)} символов)")
                        
                        # Формируем примитивный структурированный контент
                        self.structured_content['result']['content'] = [{
                            'pageNumber': 1,
                            'text': self.extracted_text
                        }]
                        
                        self.total_pages = 1
                        
                        parsing_logger.info(f"Текст успешно извлечен напрямую со страницы: {len(self.extracted_text)} символов")
                    else:
                        selenium_logger.error("Не удалось найти элементы контента на странице")
                        
                        # Пробуем альтернативные селекторы
                        alternative_selectors = [
                            ".kindle-book-content", 
                            "#kindleReader-content", 
                            ".bookContent",
                            "#book-content",
                            ".book-container",
                            ".bookTextView",
                            "#bookTextView"
                        ]
                        
                        for selector in alternative_selectors:
                            selenium_logger.debug(f"Пробуем альтернативный селектор: {selector}")
                            alt_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if alt_elements:
                                selenium_logger.info(f"Найдены элементы с селектором {selector}: {len(alt_elements)}")
                                self.extracted_text = "\n\n".join([el.text for el in alt_elements if el.text])
                                if self.extracted_text:
                                    selenium_logger.info(f"Извлечен текст с помощью селектора {selector}: {len(self.extracted_text)} символов")
                                    
                                    # Формируем примитивный структурированный контент
                                    self.structured_content['result']['content'] = [{
                                        'pageNumber': 1,
                                        'text': self.extracted_text
                                    }]
                                    
                                    self.total_pages = 1
                                    break
                        
                        if not self.extracted_text:
                            # Если все попытки не удались, попробуем извлечь весь текст страницы
                            selenium_logger.debug("Пробуем извлечь весь текст страницы")
                            body_text = self.driver.find_element(By.TAG_NAME, "body").text
                            if body_text:
                                self.extracted_text = body_text
                                selenium_logger.info(f"Извлечен текст страницы: {len(self.extracted_text)} символов")
                                
                                # Формируем примитивный структурированный контент
                                self.structured_content['result']['content'] = [{
                                    'pageNumber': 1,
                                    'text': self.extracted_text
                                }]
                                
                                self.total_pages = 1
                            else:
                                selenium_logger.error("Не удалось извлечь текст со страницы")
                                # Сохраняем скриншот для отладки
                                log_screenshot(self.driver, "extraction_failure")
                                self.cleanup()
                                return False
                                
                except Exception as extraction_err:
                    selenium_logger.error(f"Ошибка при прямом извлечении текста: {str(extraction_err)}")
                    selenium_logger.error(f"Трассировка: {traceback.format_exc()}")
                    self.cleanup()
                    return False
                    
            # Сохраняем извлеченный текст
            parsing_logger.info("Сохраняем извлеченный текст")
            self.save_text()
            
            # Сохраняем структурированный контент
            parsing_logger.info("Сохраняем структурированный контент")
            self.save_structured_content()
            
            # Очищаем ресурсы
            selenium_logger.info("Очищаем ресурсы")
            self.cleanup()
            
            selenium_logger.info("Процесс извлечения успешно завершен")
            return True
            
        except Exception as e:
            selenium_logger.error(f"Ошибка при запуске процесса извлечения: {str(e)}")
            selenium_logger.error(f"Трассировка: {traceback.format_exc()}")
            
            # Генерируем отчет о системном окружении при ошибке
            self._generate_environment_report()
            
            # Сохраняем скриншот для отладки, если драйвер существует
            if self.driver:
                try:
                    log_screenshot(self.driver, "error_state")
                except Exception:
                    pass
                    
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