import trafilatura
import requests
import json
import logging
import time
import os
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

logging.basicConfig(filename='kindle_web_scraper.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class KindleWebScraper:
    def __init__(self, book_url=None, output_file="kindle_book.txt", email=None, password=None, session_cookies=None, page_count=50, auto_paginate=True):
        """
        Инициализация веб-скрапера для Kindle Cloud Reader
        
        :param book_url: URL книги в Kindle Cloud Reader
        :param output_file: Имя файла для сохранения текста
        :param email: Email для входа в Amazon
        :param password: Пароль для входа в Amazon
        :param session_cookies: Cookies для авторизации (опционально)
        :param page_count: Количество страниц для чтения (при автоматической пагинации)
        :param auto_paginate: Включение автоматической пагинации
        """
        self.book_url = book_url
        self.output_file = output_file
        self.email = email
        self.password = password
        self.session_cookies = session_cookies or {}
        self.session = requests.Session()
        self.page_count = page_count
        self.auto_paginate = auto_paginate
        self.current_page = 0
        self.current_page_callback = None
        self.stop_requested = False
        self.is_authenticated = False
        
        # Устанавливаем заголовки для имитации браузера
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
            'Referer': 'https://read.amazon.com/',
            'Origin': 'https://read.amazon.com',
        }
        
        # Добавляем cookies в сессию, если они предоставлены
        for cookie_name, cookie_value in self.session_cookies.items():
            self.session.cookies.set(cookie_name, cookie_value)
        
        self.text_content = []
        self.asin = self._extract_asin(book_url) if book_url else None
        logging.info(f"Initialized Kindle Web Scraper for ASIN: {self.asin}")
    
    def _extract_asin(self, url):
        """
        Извлекает ASIN книги из URL
        
        :param url: URL книги
        :return: ASIN книги или None
        """
        try:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)
            
            if 'asin' in query_params:
                return query_params['asin'][0]
            
            # Если ASIN не найден в параметрах, ищем в пути URL
            path_parts = parsed_url.path.split('/')
            for part in path_parts:
                if part.startswith('B0') and len(part) == 10:
                    return part
            
            return None
        except Exception as e:
            logging.error(f"Error extracting ASIN: {e}")
            return None
    
    def get_book_content(self):
        """
        Пытается получить содержимое книги через trafilatura
        
        :return: True если успешно, иначе False
        """
        try:
            if not self.book_url:
                logging.error("Book URL is not provided")
                return False
            
            logging.info(f"Attempting to fetch content from URL: {self.book_url}")
            
            # Используем trafilatura для извлечения содержимого
            downloaded = trafilatura.fetch_url(self.book_url)
            if not downloaded:
                logging.error("Failed to download content")
                return False
            
            text = trafilatura.extract(downloaded)
            if text:
                self.text_content.append(text)
                logging.info(f"Successfully extracted content from URL: {len(text)} characters")
                return True
            else:
                logging.warning("No text content extracted from the URL")
                return False
        except Exception as e:
            logging.error(f"Error getting book content: {e}")
            return False
    
    def try_api_endpoints(self):
        """
        Пытается получить данные через известные API-эндпоинты Kindle
        
        :return: True если успешно, иначе False
        """
        try:
            if not self.asin:
                logging.error("ASIN is not available")
                return False
            
            # Пробуем разные API endpoints
            api_endpoints = [
                f"https://read.amazon.com/api/book/{self.asin}/metadata",
                f"https://read.amazon.com/api/book/{self.asin}/content",
                f"https://read.amazon.com/service/metadata/lookup?asin={self.asin}",
                f"https://read.amazon.com/service/content/lookup?asin={self.asin}"
            ]
            
            for endpoint in api_endpoints:
                logging.info(f"Trying API endpoint: {endpoint}")
                response = self.session.get(endpoint, headers=self.headers)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data:
                            self.text_content.append(json.dumps(data, indent=2))
                            logging.info(f"Successfully got data from endpoint: {endpoint}")
                            return True
                    except:
                        # Возможно, ответ не в формате JSON, сохраняем как текст
                        text = response.text
                        if text:
                            self.text_content.append(text)
                            logging.info(f"Got text response from endpoint: {endpoint}")
                            return True
                
                # Задержка между запросами
                time.sleep(1)
            
            logging.warning("No successful responses from API endpoints")
            return False
        except Exception as e:
            logging.error(f"Error trying API endpoints: {e}")
            return False
    
    def save_text(self):
        """
        Сохраняет извлеченный текст в файл
        
        :return: True если успешно, иначе False
        """
        try:
            if not self.text_content:
                logging.warning("No text content to save")
                return False
                
            with open(self.output_file, 'w', encoding='utf-8') as f:
                for content in self.text_content:
                    f.write(content)
                    f.write('\n\n--- Page Break ---\n\n')
            
            logging.info(f"Text saved to {self.output_file}")
            return True
        except Exception as e:
            logging.error(f"Error saving text: {e}")
            return False
    
    def get_content_with_pagination(self):
        """
        Автоматическая пагинация и извлечение контента со страниц
        
        :return: True если успешно, иначе False
        """
        try:
            if not self.auto_paginate:
                logging.info("Automatic pagination is disabled")
                return False
                
            if not self.book_url or not self.asin:
                logging.error("Cannot paginate without book URL and ASIN")
                return False
                
            # URL-шаблон для страниц книги
            page_url_template = f"https://read.amazon.com/read?asin={self.asin}&page={{0}}"
            
            logging.info(f"Starting automatic pagination for {self.page_count} pages")
            
            # Перебираем страницы
            for page_num in range(1, self.page_count + 1):
                # Проверяем флаг остановки
                if self.stop_requested:
                    logging.info("Stop requested, interrupting pagination")
                    break
                    
                if page_num > 1:
                    # Сохраняем прогресс после каждой страницы
                    self.save_text()
                
                self.current_page = page_num
                
                # Обновляем статус через callback, если он установлен
                if self.current_page_callback:
                    self.current_page_callback(self.current_page, self.page_count)
                
                page_url = page_url_template.format(page_num)
                
                logging.info(f"Fetching page {page_num} of {self.page_count}: {page_url}")
                
                # Получаем контент страницы
                response = self.session.get(page_url, headers=self.headers)
                
                if response.status_code == 200:
                    # Извлекаем текст из HTML с помощью BeautifulSoup
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Ищем контент - в разных книгах он может быть в разных элементах
                    content_elements = soup.select('.page-content, .bookReaderReadingPanel, .kindleReaderPage')
                    
                    if content_elements:
                        for element in content_elements:
                            text = element.get_text(strip=True)
                            if text:
                                self.text_content.append(f"Page {page_num}:\n{text}")
                                logging.info(f"Extracted {len(text)} characters from page {page_num}")
                    else:
                        # Если не нашли специальные элементы, попробуем извлечь весь текст страницы
                        try:
                            text = trafilatura.extract(response.text)
                            if text:
                                self.text_content.append(f"Page {page_num}:\n{text}")
                                logging.info(f"Extracted {len(text)} characters from page {page_num} using trafilatura")
                            else:
                                # Если trafilatura не смогла извлечь текст, извлекаем весь текст страницы через BeautifulSoup
                                text = soup.get_text(strip=True)
                                if text:
                                    self.text_content.append(f"Page {page_num} (raw):\n{text}")
                                    logging.info(f"Extracted {len(text)} characters as raw text from page {page_num}")
                                else:
                                    logging.warning(f"No text found on page {page_num}")
                        except Exception as tex:
                            # Если с trafilatura проблемы, используем BeautifulSoup
                            logging.warning(f"Error using trafilatura: {tex}, falling back to BeautifulSoup")
                            text = soup.get_text(strip=True)
                            if text:
                                self.text_content.append(f"Page {page_num} (raw):\n{text}")
                                logging.info(f"Extracted {len(text)} characters as raw text from page {page_num}")
                else:
                    logging.error(f"Failed to fetch page {page_num}, status code: {response.status_code}")
                
                # Пауза между запросами, чтобы не перегружать сервер
                time.sleep(2)
            
            logging.info(f"Pagination completed, processed {self.current_page} of {self.page_count} pages")
            
            # Финальное сохранение всего контента
            self.save_text()
            return True
            
        except Exception as e:
            logging.error(f"Error during pagination: {e}")
            return False
    
    def authenticate(self):
        """
        Авторизация на сайте Amazon
        
        :return: True если авторизация прошла успешно, иначе False
        """
        if self.is_authenticated:
            return True
            
        if not self.email or not self.password:
            logging.warning("No credentials provided for authentication")
            return False
            
        try:
            logging.info("Attempting to authenticate with Amazon")
            
            # Открываем страницу входа
            login_url = "https://www.amazon.com/ap/signin"
            response = self.session.get(login_url, headers=self.headers)
            
            if response.status_code != 200:
                logging.error(f"Failed to load login page, status code: {response.status_code}")
                return False
                
            # Извлекаем формы и скрытые поля
            soup = BeautifulSoup(response.text, 'html.parser')
            form = soup.find('form', {'name': 'signIn'})
            
            if not form:
                logging.error("Login form not found")
                return False
                
            # Получаем URL для отправки формы
            post_url = form.get('action')
            if not post_url:
                post_url = "https://www.amazon.com/ap/signin"
            elif not post_url.startswith('http'):
                post_url = f"https://www.amazon.com{post_url}"
                
            # Собираем все скрытые поля
            form_data = {}
            for input_field in form.find_all('input'):
                name = input_field.get('name')
                value = input_field.get('value')
                if name and name not in ['email', 'password']:
                    form_data[name] = value
                    
            # Добавляем учетные данные
            form_data['email'] = self.email
            form_data['password'] = self.password
            
            # Отправляем форму входа
            logging.info("Submitting login form")
            login_response = self.session.post(
                post_url,
                data=form_data,
                headers={
                    **self.headers,
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Referer': login_url
                }
            )
            
            # Проверяем успешность входа
            if 'auth-error-message' in login_response.text:
                logging.error("Authentication failed: invalid credentials")
                return False
                
            if "Your Account" in login_response.text or "Hello," in login_response.text:
                logging.info("Successfully authenticated with Amazon")
                self.is_authenticated = True
                return True
                
            # Проверяем перенаправление на страницу Kindle
            if "read.amazon.com" in login_response.url:
                logging.info("Redirected to Kindle Cloud Reader, authentication successful")
                self.is_authenticated = True
                return True
                
            logging.warning("Authentication status uncertain, proceeding anyway")
            self.is_authenticated = True
            return True
            
        except Exception as e:
            logging.error(f"Error during authentication: {e}")
            return False

    def run(self):
        """
        Запускает процесс извлечения
        
        :return: True если успешно, иначе False
        """
        logging.info(f"Starting extraction from URL: {self.book_url}")
        success = False
        
        # Авторизуемся, если предоставлены учетные данные
        if self.email and self.password:
            auth_success = self.authenticate()
            if not auth_success:
                logging.error("Authentication failed, extraction might be limited")
        
        # Пробуем получить контент через trafilatura
        content_extracted = self.get_book_content()
        
        # Если не удалось, пробуем через API
        if not content_extracted:
            logging.info("Direct content extraction failed, trying API endpoints...")
            content_extracted = self.try_api_endpoints()
        
        # Если API не помог, пробуем автоматическую пагинацию
        if not content_extracted and self.auto_paginate:
            logging.info("API extraction failed, trying automatic pagination...")
            content_extracted = self.get_content_with_pagination()
        
        # Сохраняем результат, если есть что сохранять
        if content_extracted or self.text_content:
            success = self.save_text()
            
        if success:
            logging.info("Text extraction completed successfully")
            return True
        else:
            logging.error("Failed to extract content from any source")
            return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract text from Kindle Cloud Reader using web scraping')
    parser.add_argument('--url', required=True, help='URL of the Kindle book')
    parser.add_argument('--output', default='kindle_book.txt', help='Path to save extracted text')
    
    args = parser.parse_args()
    
    scraper = KindleWebScraper(book_url=args.url, output_file=args.output)
    success = scraper.run()
    
    if success:
        print(f"Successfully extracted text and saved to {args.output}")
    else:
        print("Failed to extract text. Check the log file for details.")