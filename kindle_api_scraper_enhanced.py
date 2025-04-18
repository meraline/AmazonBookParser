import requests
import json
import time
import logging
import os
import re
import base64
import traceback
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='kindle_api_scraper_enhanced.log'
)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger('').addHandler(console_handler)

class KindleAPIScraperEnhanced:
    def __init__(self, email=None, password=None, book_url=None, output_file="kindle_enhanced_book.txt", images_dir="kindle_images", page_load_time=5, max_pages=50):
        """
        Инициализация улучшенного API скрапера для Kindle Cloud Reader с поддержкой изображений
        
        :param email: Email для входа в Amazon
        :param password: Пароль для входа в Amazon
        :param book_url: URL книги в Kindle Cloud Reader
        :param output_file: Имя файла для сохранения текста
        :param images_dir: Директория для сохранения изображений
        :param page_load_time: Время ожидания загрузки страницы в секундах
        :param max_pages: Максимальное количество страниц для обработки
        """
        self.email = email
        self.password = password
        self.book_url = book_url
        self.output_file = output_file
        self.images_dir = images_dir
        self.page_load_time = page_load_time
        self.max_pages = max_pages
        
        # Создаем директорию для изображений, если она не существует
        if not os.path.exists(self.images_dir):
            os.makedirs(self.images_dir)
            
        self.driver = None
        self.extracted_text = ""
        self.current_page = 0
        self.total_pages = 0
        self.current_page_callback = None
        self.asin = self._extract_asin(book_url) if book_url else None
        self.images = []
        self.structured_content = {
            "type": "Success",
            "result": {
                "bookId": self.asin,
                "title": "",
                "author": "",
                "content": []
            }
        }
        
        # Сетевые запросы и ответы для перехвата
        self.captured_requests = []
        self.captured_images = []

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
        Настройка Firefox для работы с Kindle Cloud Reader
        """
        try:
            selenium_logger.info("Настраиваем Firefox для работы с Kindle Cloud Reader")
            
            # Настраиваем опции Firefox
            options = Options()
            options.add_argument("--width=1366")
            options.add_argument("--height=768")
            
            # Настраиваем Firefox для логирования
            options.set_preference("devtools.console.stdout.content", True)
            options.set_preference("browser.cache.disk.enable", False)
            options.set_preference("browser.cache.memory.enable", False)
            options.set_preference("browser.cache.offline.enable", False)
            options.set_preference("network.http.use-cache", False)
            
            # Инициализируем драйвер
            service = Service(GeckoDriverManager().install())
            self.driver = webdriver.Firefox(service=service, options=options)
            
            # Сохраняем скриншот для подтверждения запуска
            try:
                log_screenshot(self.driver, "firefox_started")
            except Exception as screenshot_err:
                selenium_logger.warning(f"Не удалось сохранить скриншот запуска: {str(screenshot_err)}")
            
            # Устанавливаем скрипт для перехвата запросов
            self.setup_request_interceptor()
            
            selenium_logger.info("Firefox успешно настроен")
            return True
            
        except Exception as e:
            selenium_logger.error(f"Ошибка при настройке Firefox: {str(e)}")
            selenium_logger.error(f"Трассировка: {traceback.format_exc()}")
            return False

    @log_function_call(selenium_logger)
    def setup_request_interceptor(self):
        """
        Устанавливает JavaScript для перехвата и сохранения запросов
        """
        if not self.driver:
            selenium_logger.error("Нельзя установить перехватчик запросов: драйвер не инициализирован")
            return
            
        interceptor_script = """
        // Создаем массив для хранения перехваченных запросов
        window.capturedRequests = [];
        window.capturedImages = [];
        
        // Перехватываем fetch запросы
        const originalFetch = window.fetch;
        window.fetch = async function(url, options) {
            // Вызываем оригинальный fetch
            const response = await originalFetch(url, options);
            
            try {
                // Проверяем, относится ли URL к API Kindle или blob
                if (url.includes('amazon.com') && 
                   (url.includes('/api/') || url.includes('/service/') || 
                    url.includes('blob:') || url.startsWith('blob:'))) {
                    
                    console.log('Captured API request to: ' + url);
                    
                    // Клонируем ответ (т.к. response.json() можно вызвать только один раз)
                    const clone = response.clone();
                    
                    // Пытаемся получить тело ответа в зависимости от Content-Type
                    const contentType = response.headers.get('Content-Type') || '';
                    console.log('Content-Type: ' + contentType);
                    
                    if (contentType.includes('application/json')) {
                        // Для JSON данных
                        clone.json().then(data => {
                            console.log('Parsed JSON data from: ' + url);
                            window.capturedRequests.push({
                                url: url,
                                type: 'json',
                                data: data
                            });
                        }).catch(e => console.log('Error parsing JSON: ' + e));
                    } 
                    else if (contentType.includes('image/') || url.includes('blob:')) {
                        // Для изображений или blob-данных
                        clone.blob().then(blob => {
                            console.log('Processing blob/image from: ' + url);
                            const reader = new FileReader();
                            reader.onload = function() {
                                console.log('Image/blob data converted to base64');
                                window.capturedImages.push({
                                    url: url,
                                    type: contentType || 'blob',
                                    data: reader.result
                                });
                            };
                            reader.readAsDataURL(blob);
                        }).catch(e => console.log('Error processing blob: ' + e));
                    }
                }
            } catch (e) {
                console.log('Error in fetch interceptor: ' + e);
                console.log('Error stack: ' + e.stack);
            }
            
            // Возвращаем оригинальный ответ
            return response;
        };
        
        // Функция для получения перехваченных запросов
        window.getCapturedRequests = function() {
            console.log('getCapturedRequests called, count: ' + window.capturedRequests.length);
            return window.capturedRequests;
        };
        
        // Функция для получения перехваченных изображений
        window.getCapturedImages = function() {
            console.log('getCapturedImages called, count: ' + window.capturedImages.length);
            return window.capturedImages;
        };
        
        console.log('Interceptor installed successfully');
        """
        
        try:
            # Выполняем скрипт
            self.driver.execute_script(interceptor_script)
            selenium_logger.info("Установлен перехватчик запросов")
            
            # Проверяем, успешно ли установлен скрипт
            check_script = """
            return typeof window.getCapturedRequests === 'function' && 
                  typeof window.getCapturedImages === 'function';
            """
            is_installed = self.driver.execute_script(check_script)
            
            if is_installed:
                selenium_logger.info("Перехватчик успешно проверен")
            else:
                selenium_logger.warning("Перехватчик установлен, но функции не обнаружены")
                
        except Exception as e:
            selenium_logger.error(f"Ошибка при установке перехватчика запросов: {str(e)}")
            selenium_logger.error(f"Трассировка: {traceback.format_exc()}")

    @log_function_call(selenium_logger)
    def login_to_amazon(self):
        """
        Входит в аккаунт Amazon
        
        :return: True если авторизация прошла успешно, иначе False
        """
        if not self.driver or not self.email or not self.password:
            selenium_logger.error("Драйвер не инициализирован или не указаны учетные данные")
            return False
            
        try:
            selenium_logger.info("Открываем страницу авторизации Amazon")
            self.driver.get("https://www.amazon.com/ap/signin")
            
            # Сохраняем скриншот до авторизации
            log_screenshot(self.driver, "before_login")
            
            # Ждем загрузки страницы
            selenium_logger.info("Ожидаем загрузку страницы авторизации")
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "ap_email"))
            )
            
            # Вводим email
            selenium_logger.info(f"Вводим email: {self.email}")
            email_field = self.driver.find_element(By.ID, "ap_email")
            email_field.clear()
            email_field.send_keys(self.email)
            
            # Нажимаем кнопку "Continue"
            selenium_logger.info("Нажимаем кнопку Continue")
            continue_button = self.driver.find_element(By.ID, "continue")
            continue_button.click()
            
            # Сохраняем скриншот перед вводом пароля
            log_screenshot(self.driver, "before_password")
            
            # Ждем загрузки страницы для ввода пароля
            selenium_logger.info("Ожидаем страницу для ввода пароля")
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "ap_password"))
            )
            
            # Вводим пароль
            selenium_logger.info("Вводим пароль")
            password_field = self.driver.find_element(By.ID, "ap_password")
            password_field.clear()
            password_field.send_keys(self.password)
            
            # Нажимаем кнопку "Sign-In"
            selenium_logger.info("Нажимаем кнопку Sign-In")
            signin_button = self.driver.find_element(By.ID, "signInSubmit")
            signin_button.click()
            
            # Сохраняем скриншот после авторизации
            log_screenshot(self.driver, "after_login")
            
            # Проверяем, что авторизация прошла успешно
            try:
                selenium_logger.info("Проверяем успешность авторизации")
                WebDriverWait(self.driver, 20).until(
                    lambda driver: "amazon.com" in driver.current_url and "ap/signin" not in driver.current_url
                )
                selenium_logger.info("Авторизация прошла успешно")
                return True
                
            except TimeoutException:
                selenium_logger.error("Ошибка авторизации. Проверьте учетные данные.")
                log_screenshot(self.driver, "login_error")
                return False
                
        except Exception as e:
            selenium_logger.error(f"Ошибка при авторизации: {str(e)}")
            selenium_logger.error(f"Трассировка: {traceback.format_exc()}")
            log_screenshot(self.driver, "login_exception")
            return False

    def open_kindle_cloud_reader(self):
        """
        Открывает Kindle Cloud Reader
        
        :return: True если открытие прошло успешно, иначе False
        """
        if not self.driver:
            logging.error("Драйвер не инициализирован")
            return False
            
        try:
            logging.info("Открываем Kindle Cloud Reader")
            self.driver.get("https://read.amazon.com")
            
            # Ждем загрузки страницы
            WebDriverWait(self.driver, 20).until(
                lambda driver: "read.amazon.com" in driver.current_url
            )
            
            # Проверяем, не перенаправило ли нас на страницу авторизации
            if "ap/signin" in self.driver.current_url:
                logging.info("Требуется авторизация")
                return self.login_to_amazon()
                
            logging.info("Kindle Cloud Reader успешно открыт")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при открытии Kindle Cloud Reader: {str(e)}")
            return False

    def open_book(self):
        """
        Открывает книгу по указанному URL или ASIN
        
        :return: True если книга успешно открыта, иначе False
        """
        if not self.driver:
            logging.error("Драйвер не инициализирован")
            return False
            
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
            
            # Ждем загрузки книги (проверяем, что URL содержит reader или kp)
            WebDriverWait(self.driver, 20).until(
                lambda driver: "read.amazon.com/reader" in driver.current_url or 
                              "read.amazon.com/kp" in driver.current_url
            )
            
            # Время на полную загрузку интерфейса
            time.sleep(self.page_load_time)
            
            # Извлекаем метаданные книги
            self.extract_book_metadata()
            
            logging.info("Книга успешно открыта")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при открытии книги: {str(e)}")
            return False

    def extract_book_metadata(self):
        """
        Извлекает метаданные книги (название, автор)
        """
        if not self.driver:
            return
            
        try:
            # Пытаемся найти название книги
            try:
                title_element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".bookTitle, .book-title"))
                )
                self.structured_content["result"]["title"] = title_element.text.strip()
            except Exception:
                logging.info("Не удалось найти название книги")
                
            # Пытаемся найти автора книги
            try:
                author_element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".bookAuthor, .book-author"))
                )
                self.structured_content["result"]["author"] = author_element.text.strip()
            except Exception:
                logging.info("Не удалось найти автора книги")
                
            logging.info(f"Извлечены метаданные книги: {self.structured_content['result']['title']} - {self.structured_content['result']['author']}")
            
        except Exception as e:
            logging.error(f"Ошибка при извлечении метаданных книги: {str(e)}")

    def navigate_pages(self):
        """
        Перелистывает страницы и собирает контент
        
        :return: True если успешно, иначе False
        """
        if not self.driver:
            logging.error("Драйвер не инициализирован")
            return False
            
        try:
            logging.info(f"Начинаем навигацию по страницам. Максимум страниц: {self.max_pages}")
            
            # Устанавливаем счетчики
            self.current_page = 1
            
            # Ожидаем загрузку первой страницы
            time.sleep(self.page_load_time)
            
            # Извлекаем контент с первой страницы
            self.extract_current_page_content()
            
            # Перелистываем страницы до достижения максимума
            for page_num in range(2, self.max_pages + 1):
                logging.info(f"Перелистываем на страницу {page_num}")
                
                # Нажимаем на область справа для перехода на следующую страницу
                try:
                    # Нажимаем на правую часть экрана для перелистывания вперед
                    webdriver.ActionChains(self.driver).move_to_element_with_offset(
                        self.driver.find_element(By.TAG_NAME, 'body'),
                        self.driver.get_window_size()['width'] - 100,
                        self.driver.get_window_size()['height'] // 2
                    ).click().perform()
                    
                    # Обновляем текущую страницу
                    self.current_page = page_num
                    
                    # Вызываем колбэк для обновления статуса
                    if self.current_page_callback:
                        self.current_page_callback(self.current_page, self.max_pages)
                    
                    # Ждем загрузки страницы
                    time.sleep(self.page_load_time)
                    
                    # Извлекаем контент с текущей страницы
                    self.extract_current_page_content()
                    
                except Exception as e:
                    logging.error(f"Ошибка при перелистывании на страницу {page_num}: {str(e)}")
                    break
            
            # Собираем все перехваченные запросы
            self.collect_captured_data()
            
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при навигации по страницам: {str(e)}")
            return False

    def extract_current_page_content(self):
        """
        Извлекает текст и изображения с текущей страницы
        """
        if not self.driver:
            return
            
        try:
            logging.info(f"Извлекаем контент со страницы {self.current_page}")
            
            # Извлекаем текст
            try:
                # Пытаемся найти элементы с текстом (разные варианты селекторов)
                content_elements = []
                selectors = [
                    "div.textLayer", 
                    "div.kcrPage", 
                    "div.bookReaderContainer", 
                    "div.kindleReaderPage",
                    "div.kb-viewarea"
                ]
                
                for selector in selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            content_elements = elements
                            break
                    except:
                        continue
                
                # Если не нашли элементы ни по одному из селекторов, попробуем извлечь весь текст страницы
                if not content_elements:
                    logging.info("Не найдены стандартные элементы с текстом, извлекаем весь текст страницы")
                    content_elements = [self.driver.find_element(By.TAG_NAME, "body")]
                
                # Извлекаем текст
                page_text = ""
                for elem in content_elements:
                    elem_text = elem.text.strip()
                    if elem_text:
                        page_text += elem_text + "\n"
                
                # Добавляем текст в структурированный контент
                if page_text:
                    self.structured_content["result"]["content"].append({
                        "pageNumber": self.current_page,
                        "text": page_text
                    })
                    
                    logging.info(f"Извлечен текст со страницы {self.current_page}: {len(page_text)} символов")
                else:
                    logging.warning(f"Не удалось извлечь текст со страницы {self.current_page}")
                
            except Exception as e:
                logging.error(f"Ошибка при извлечении текста со страницы {self.current_page}: {str(e)}")
            
            # Извлекаем изображения
            try:
                # Пытаемся найти изображения на странице
                image_selectors = [
                    "img.kfx-image",
                    "img.kc-kindle-image",
                    "img.kb-image",
                    "img:not(.ui-icon)"
                ]
                
                images = []
                for selector in image_selectors:
                    try:
                        found_images = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if found_images:
                            images.extend(found_images)
                    except:
                        continue
                
                # Обрабатываем найденные изображения
                for idx, img in enumerate(images):
                    try:
                        src = img.get_attribute("src")
                        if src and (src.startswith("data:image") or src.startswith("blob:")):
                            # Сохраняем информацию об изображении
                            self.images.append({
                                "pageNumber": self.current_page,
                                "index": idx + 1,
                                "src": src,
                                "alt": img.get_attribute("alt") or f"Image_{self.current_page}_{idx+1}"
                            })
                            
                            logging.info(f"Найдено изображение на странице {self.current_page}: {idx+1}")
                    except Exception as img_err:
                        logging.error(f"Ошибка при обработке изображения {idx+1} на странице {self.current_page}: {str(img_err)}")
                
            except Exception as e:
                logging.error(f"Ошибка при извлечении изображений со страницы {self.current_page}: {str(e)}")
            
        except Exception as e:
            logging.error(f"Ошибка при извлечении контента со страницы {self.current_page}: {str(e)}")

    def collect_captured_data(self):
        """
        Собирает перехваченные данные (запросы и изображения)
        """
        if not self.driver:
            return
            
        try:
            logging.info("Собираем перехваченные данные")
            
            # Получаем перехваченные запросы
            self.captured_requests = self.driver.execute_script("return window.getCapturedRequests ? window.getCapturedRequests() : [];")
            logging.info(f"Получено перехваченных запросов: {len(self.captured_requests)}")
            
            # Получаем перехваченные изображения
            self.captured_images = self.driver.execute_script("return window.getCapturedImages ? window.getCapturedImages() : [];")
            logging.info(f"Получено перехваченных изображений: {len(self.captured_images)}")
            
            # Обрабатываем и сохраняем изображения
            self.process_captured_images()
            
            # Обрабатываем JSON контент из запросов
            self.process_captured_json()
            
        except Exception as e:
            logging.error(f"Ошибка при сборе перехваченных данных: {str(e)}")

    def process_captured_images(self):
        """
        Обрабатывает и сохраняет перехваченные изображения
        """
        if not self.captured_images:
            logging.info("Нет перехваченных изображений для обработки")
            return
            
        try:
            logging.info(f"Обработка {len(self.captured_images)} перехваченных изображений")
            
            for idx, img_data in enumerate(self.captured_images):
                try:
                    # Получаем данные изображения
                    image_url = img_data.get('url', '')
                    image_type = img_data.get('type', 'image/jpeg')
                    image_base64 = img_data.get('data', '')
                    
                    # Пропускаем, если нет данных
                    if not image_base64 or not image_base64.startswith('data:'):
                        continue
                    
                    # Получаем расширение файла
                    if 'image/png' in image_type:
                        ext = 'png'
                    elif 'image/gif' in image_type:
                        ext = 'gif'
                    elif 'image/svg' in image_type:
                        ext = 'svg'
                    else:
                        ext = 'jpg'
                    
                    # Создаем имя файла
                    filename = f"image_{self.current_page}_{idx+1}.{ext}"
                    filepath = os.path.join(self.images_dir, filename)
                    
                    # Декодируем и сохраняем изображение
                    try:
                        # Извлекаем часть Base64 после запятой
                        base64_data = image_base64.split(',')[1]
                        
                        # Декодируем Base64 в бинарные данные
                        image_data = base64.b64decode(base64_data)
                        
                        # Сохраняем в файл
                        with open(filepath, 'wb') as f:
                            f.write(image_data)
                            
                        logging.info(f"Сохранено изображение: {filename}")
                        
                        # Добавляем информацию в структурированный контент
                        image_info = {
                            "pageNumber": self.current_page,
                            "fileName": filename,
                            "path": filepath
                        }
                        
                        # Добавляем в список изображений, если его еще нет
                        if not any(img['fileName'] == filename for img in self.images):
                            self.images.append(image_info)
                        
                    except Exception as save_err:
                        logging.error(f"Ошибка при сохранении изображения {filename}: {str(save_err)}")
                    
                except Exception as img_err:
                    logging.error(f"Ошибка при обработке изображения {idx+1}: {str(img_err)}")
            
            logging.info(f"Всего сохранено изображений: {len(self.images)}")
            
        except Exception as e:
            logging.error(f"Ошибка при обработке перехваченных изображений: {str(e)}")

    def process_captured_json(self):
        """
        Обрабатывает JSON-контент из перехваченных запросов
        """
        if not self.captured_requests:
            logging.info("Нет перехваченных запросов для обработки")
            return
            
        try:
            logging.info(f"Обработка {len(self.captured_requests)} перехваченных запросов")
            
            for idx, req_data in enumerate(self.captured_requests):
                try:
                    # Получаем данные запроса
                    req_url = req_data.get('url', '')
                    req_type = req_data.get('type', '')
                    req_json = req_data.get('data', {})
                    
                    logging.info(f"Обработка запроса {idx+1}: {req_url[:50]}...")
                    
                    # Пропускаем, если нет данных или не JSON
                    if not req_json or req_type != 'json':
                        continue
                    
                    # Проверяем, содержит ли запрос контент книги
                    self.extract_content_from_json(req_json, req_url)
                    
                except Exception as req_err:
                    logging.error(f"Ошибка при обработке запроса {idx+1}: {str(req_err)}")
            
        except Exception as e:
            logging.error(f"Ошибка при обработке перехваченных JSON запросов: {str(e)}")

    def extract_content_from_json(self, json_data, url):
        """
        Извлекает контент книги из JSON данных
        
        :param json_data: JSON данные из запроса
        :param url: URL запроса
        """
        try:
            # Если это запрос с метаданными книги
            if ('metadata' in url or 'lookup' in url) and isinstance(json_data, dict):
                # Извлекаем заголовок
                if 'title' in json_data and not self.structured_content['result']['title']:
                    self.structured_content['result']['title'] = json_data['title']
                
                # Извлекаем автора
                if 'author' in json_data and not self.structured_content['result']['author']:
                    self.structured_content['result']['author'] = json_data['author']
                
                # Извлекаем ASIN
                if 'asin' in json_data and not self.structured_content['result']['bookId']:
                    self.structured_content['result']['bookId'] = json_data['asin']
                
                logging.info(f"Извлечены метаданные из JSON: {self.structured_content['result']['title']} - {self.structured_content['result']['author']}")
            
            # Если это запрос с контентом книги
            if 'content' in url or 'pages' in url or 'reader' in url:
                # Ищем контент в разных форматах JSON
                if isinstance(json_data, dict):
                    # Формат 1: Прямой ответ с контентом
                    if 'content' in json_data and isinstance(json_data['content'], list):
                        for item in json_data['content']:
                            if isinstance(item, dict) and 'pageNumber' in item and 'text' in item:
                                # Если такой страницы еще нет в нашем контенте, добавляем
                                if not any(p['pageNumber'] == item['pageNumber'] for p in self.structured_content['result']['content']):
                                    self.structured_content['result']['content'].append(item)
                                    logging.info(f"Добавлен контент для страницы {item['pageNumber']} из JSON")
                    
                    # Формат 2: Вложенная структура с контентом
                    elif 'result' in json_data and 'content' in json_data['result'] and isinstance(json_data['result']['content'], list):
                        for item in json_data['result']['content']:
                            if isinstance(item, dict) and 'pageNumber' in item and 'text' in item:
                                # Если такой страницы еще нет в нашем контенте, добавляем
                                if not any(p['pageNumber'] == item['pageNumber'] for p in self.structured_content['result']['content']):
                                    self.structured_content['result']['content'].append(item)
                                    logging.info(f"Добавлен контент для страницы {item['pageNumber']} из JSON")
                    
                    # Обновляем общее количество страниц
                    self.total_pages = len(self.structured_content['result']['content'])
        
        except Exception as e:
            logging.error(f"Ошибка при извлечении контента из JSON: {str(e)}")

    def save_text(self):
        """
        Сохраняет извлеченный текст в файл
        
        :return: True если успешно, иначе False
        """
        try:
            # Сортируем контент по номеру страницы
            sorted_content = sorted(
                self.structured_content['result']['content'],
                key=lambda x: x['pageNumber']
            )
            
            # Формируем текст для сохранения
            text_to_save = ""
            
            # Добавляем заголовок
            if self.structured_content['result']['title']:
                text_to_save += f"Название: {self.structured_content['result']['title']}\n"
            
            # Добавляем автора
            if self.structured_content['result']['author']:
                text_to_save += f"Автор: {self.structured_content['result']['author']}\n"
            
            # Добавляем ASIN
            if self.structured_content['result']['bookId']:
                text_to_save += f"ASIN: {self.structured_content['result']['bookId']}\n"
            
            text_to_save += "\n\n"
            
            # Добавляем контент страниц
            for item in sorted_content:
                text_to_save += f"=== Страница {item['pageNumber']} ===\n\n"
                text_to_save += item['text'] + "\n\n"
            
            # Сохраняем в файл
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(text_to_save)
                
            logging.info(f"Текст успешно сохранен в файл: {self.output_file}")
            
            # Формируем список изображений
            if self.images:
                images_section = "\n=== Список изображений ===\n\n"
                for idx, img in enumerate(sorted(self.images, key=lambda x: (x['pageNumber'], x.get('index', 0)))):
                    images_section += f"{idx+1}. Страница {img['pageNumber']}: {img.get('fileName', '')}\n"
                
                # Добавляем список изображений в файл
                with open(self.output_file, 'a', encoding='utf-8') as f:
                    f.write(images_section)
                
                logging.info(f"Список из {len(self.images)} изображений добавлен в файл")
            
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
            # Формируем имя файла JSON
            json_file = self.output_file.replace('.txt', '.json')
            
            # Добавляем информацию об изображениях
            if self.images:
                self.structured_content['result']['images'] = self.images
            
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
        Закрывает браузер и освобождает ресурсы
        """
        try:
            if self.driver:
                logging.info("Закрываем браузер")
                self.driver.quit()
                self.driver = None
                
        except Exception as e:
            logging.error(f"Ошибка при закрытии браузера: {str(e)}")

    def run(self):
        """
        Запускает весь процесс извлечения
        
        :return: True если успешно, иначе False
        """
        try:
            # Настраиваем браузер
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
                
            # Перелистываем страницы и собираем контент
            if not self.navigate_pages():
                logging.warning("Произошла ошибка при навигации по страницам")
                
            # Сохраняем извлеченный текст
            self.save_text()
            
            # Сохраняем структурированный контент
            self.save_structured_content()
            
            # Выводим итоговую информацию
            logging.info(f"Извлечено страниц текста: {len(self.structured_content['result']['content'])}")
            logging.info(f"Извлечено изображений: {len(self.images)}")
            
            # Очищаем ресурсы
            self.cleanup()
            
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при запуске процесса извлечения: {str(e)}")
            self.cleanup()
            return False


# Пример использования
if __name__ == "__main__":
    scraper = KindleAPIScraperEnhanced(
        email="your.email@example.com",
        password="your_password",
        book_url="https://read.amazon.com/?asin=B009SE1Z9E",
        output_file="kindle_enhanced_book.txt",
        images_dir="kindle_images",
        page_load_time=5,
        max_pages=20
    )
    
    scraper.run()