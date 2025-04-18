import requests
import json
import time
import logging
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup

logging.basicConfig(filename='kindle_api_scraper.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class KindleAPIScraper:
    def __init__(self, email=None, password=None, book_id=None, book_url=None, output_file="kindle_book.txt", session_cookies=None):
        """
        Инициализация API скрапера для Kindle Cloud Reader
        
        :param email: Email для входа в Amazon
        :param password: Пароль для входа в Amazon
        :param book_id: ID книги в Kindle (из URL или запросов)
        :param book_url: URL книги в Kindle Cloud Reader
        :param output_file: Имя файла для сохранения текста
        :param session_cookies: Cookies из открытой сессии Kindle (из инструментов разработчика, опционально)
        """
        self.email = email
        self.password = password
        self.book_id = book_id
        self.book_url = book_url
        self.output_file = output_file
        self.session_cookies = session_cookies or {}
        self.session = requests.Session()
        self.is_authenticated = False
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://read.amazon.com/',
            'Origin': 'https://read.amazon.com',
        }
        
        # Добавляем cookies в сессию, если они предоставлены
        for cookie_name, cookie_value in self.session_cookies.items():
            self.session.cookies.set(cookie_name, cookie_value)
        
        # Извлекаем ID книги из URL, если предоставлен
        if not self.book_id and self.book_url:
            self.book_id = self._extract_asin(self.book_url)
            
        self.text_content = []
        self.structured_content = {
            "type": "Success",
            "result": {
                "bookId": self.book_id,
                "title": "",
                "author": "",
                "content": []
            }
        }
        logging.info("Initialized Kindle API Scraper")
        
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
    
    def extract_api_urls(self, har_file):
        """
        Извлекает API URL из HAR файла (экспортированного из Network tab)
        
        :param har_file: Путь к HAR файлу
        :return: Список URL-ов для API запросов
        """
        try:
            with open(har_file, 'r', encoding='utf-8') as f:
                har_data = json.load(f)
            
            api_urls = []
            for entry in har_data['log']['entries']:
                url = entry['request']['url']
                # Фильтруем только нужные запросы (к API kindle)
                if 'read.amazon.com' in url and ('getFileToken' in url or 'content' in url):
                    api_urls.append(url)
                    logging.info(f"Found API URL: {url}")
            
            return api_urls
        except Exception as e:
            logging.error(f"Error extracting API URLs: {e}")
            return []
    
    def extract_text_from_json(self, json_data):
        """
        Извлекает текст из JSON структуры
        
        :param json_data: JSON данные из ответа API
        :return: Извлеченный текст или None
        """
        # Это упрощенная функция, которую нужно адаптировать под формат ответа Kindle API
        try:
            # Вариант 1: Прямой доступ к полю 'content'
            if isinstance(json_data, dict) and 'content' in json_data:
                return json_data['content']
            
            # Вариант 2: Доступ к полю 'text'
            if isinstance(json_data, dict) and 'text' in json_data:
                return json_data['text']
            
            # Вариант 3: Извлечение текста из вложенного JSON объекта
            # Kindle Cloud Reader может возвращать данные в разных форматах
            if isinstance(json_data, dict):
                # Проверяем наличие ключа 'data'
                if 'data' in json_data:
                    data = json_data['data']
                    if isinstance(data, dict):
                        # Проверяем наличие поля 'content' внутри 'data'
                        if 'content' in data:
                            return data['content']
                        # Проверяем наличие поля 'text' внутри 'data'
                        if 'text' in data:
                            return data['text']
                
                # Некоторые API могут возвращать текст в структуре HTML
                if 'html' in json_data:
                    html_content = json_data['html']
                    # Здесь можно использовать BeautifulSoup для извлечения текста из HTML
                    # Но это требует дополнительной библиотеки
                    return html_content
                
                # Проверка на структуру JSON-RPC ответа
                if 'result' in json_data:
                    result = json_data['result']
                    if isinstance(result, dict):
                        if 'content' in result:
                            return result['content']
                        if 'text' in result:
                            return result['text']
            
            # Вариант 4: Извлечение из массива
            if isinstance(json_data, list):
                extracted_text = []
                for item in json_data:
                    if isinstance(item, dict):
                        if 'content' in item:
                            extracted_text.append(item['content'])
                        elif 'text' in item:
                            extracted_text.append(item['text'])
                if extracted_text:
                    return '\n'.join(extracted_text)
            
            # Если ничего не найдено, логируем структуру для анализа
            logging.warning(f"Could not extract text from JSON structure. JSON keys: {json_data.keys() if isinstance(json_data, dict) else 'Not a dict'}")
            return None
        except Exception as e:
            logging.error(f"Error extracting text from JSON: {e}")
            return None
    
    def fetch_book_content(self, api_urls):
        """
        Извлекает содержимое книги через API запросы
        
        :param api_urls: Список URL для запросов
        :return: True если успешно, иначе False
        """
        try:
            for url in api_urls:
                logging.info(f"Fetching content from: {url}")
                response = self.session.get(url, headers=self.headers)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        extracted_text = self.extract_text_from_json(data)
                        if extracted_text:
                            self.text_content.append(extracted_text)
                            logging.info(f"Successfully extracted content from {url}")
                        else:
                            logging.warning(f"No text content found in response from {url}")
                    except json.JSONDecodeError:
                        # Возможно, ответ не в формате JSON
                        logging.warning(f"Response is not JSON: {response.text[:100]}...")
                else:
                    logging.error(f"Failed to fetch content, status code: {response.status_code}")
                
                # Небольшая задержка между запросами
                time.sleep(1)
                
            return len(self.text_content) > 0
        except Exception as e:
            logging.error(f"Error fetching book content: {e}")
            return False
    
    def extract_from_api_response(self, response_file):
        """
        Извлекает текст из сохраненного ответа API
        
        :param response_file: Путь к файлу с сохраненным ответом API
        :return: True если успешно, иначе False
        """
        try:
            with open(response_file, 'r', encoding='utf-8') as f:
                try:
                    response_data = json.load(f)
                    extracted_text = self.extract_text_from_json(response_data)
                    if extracted_text:
                        self.text_content.append(extracted_text)
                        logging.info(f"Extracted text from response file: {len(extracted_text)} characters")
                        return True
                    else:
                        # Если текст не найден в JSON структуре, пробуем прочитать файл как обычный текст
                        f.seek(0)  # Перемещаем указатель в начало файла
                        text_content = f.read()
                        if text_content.strip():
                            self.text_content.append(text_content)
                            logging.info(f"Extracted raw text from file: {len(text_content)} characters")
                            return True
                        else:
                            logging.warning("No text content found in response file")
                            return False
                except json.JSONDecodeError:
                    # Если файл не является JSON, считаем его текстовым файлом
                    f.seek(0)  # Перемещаем указатель в начало файла
                    text_content = f.read()
                    if text_content.strip():
                        self.text_content.append(text_content)
                        logging.info(f"File is not JSON, treating as raw text: {len(text_content)} characters")
                        return True
                    else:
                        logging.warning("File is not valid JSON and contains no text content")
                        return False
        except Exception as e:
            logging.error(f"Error extracting from API response: {e}")
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
                    f.write('\n\n')
            
            logging.info(f"Text saved to {self.output_file}")
            return True
        except Exception as e:
            logging.error(f"Error saving text: {e}")
            return False
    
    def discover_api_endpoints(self):
        """
        Автоматически определяет API эндпоинты для заданной книги
        
        :return: Список URL для API запросов
        """
        if not self.book_id:
            logging.error("Book ID (ASIN) is required to discover API endpoints")
            return []
            
        # Список потенциальных API эндпоинтов
        api_endpoints = [
            f"https://read.amazon.com/api/book/{self.book_id}/metadata",
            f"https://read.amazon.com/api/book/{self.book_id}/content",
            f"https://read.amazon.com/service/metadata/lookup?asin={self.book_id}",
            f"https://read.amazon.com/service/content/lookup?asin={self.book_id}",
            f"https://read.amazon.com/api/book/get-content?asin={self.book_id}",
            f"https://read.amazon.com/api/book/{self.book_id}/properties",
            f"https://read.amazon.com/service/content/json?asin={self.book_id}",
            # Добавляем для Quantum Poker
            f"https://read.amazon.com/api/book/B009SE1Z9E/content",
            f"https://read.amazon.com/api/book/B009SE1Z9E/pages",
            f"https://read.amazon.com/api/book/B009SE1Z9E/chapters"
        ]
        
        logging.info(f"Generated {len(api_endpoints)} potential API endpoints for book ID: {self.book_id}")
        return api_endpoints
    
    def parse_structured_content(self, response_data):
        """
        Парсит API-ответ и форматирует в структурированный JSON
        
        :param response_data: JSON данные из ответа API
        :return: True если успешно, иначе False
        """
        try:
            # Если уже имеем правильный формат
            if (isinstance(response_data, dict) and "type" in response_data and 
                response_data.get("type") == "Success" and "result" in response_data):
                self.structured_content = response_data
                
                # Обновляем ID книги, если он не был установлен
                if not self.book_id and "bookId" in response_data["result"]:
                    self.book_id = response_data["result"]["bookId"]
                    self.structured_content["result"]["bookId"] = self.book_id
                
                logging.info("Successfully parsed structured content in correct format")
                return True
            
            # Пытаемся извлечь метаданные и контент
            if isinstance(response_data, dict):
                # Извлекаем метаданные
                if "bookId" in response_data:
                    self.structured_content["result"]["bookId"] = response_data["bookId"]
                elif "asin" in response_data:
                    self.structured_content["result"]["bookId"] = response_data["asin"]
                else:
                    self.structured_content["result"]["bookId"] = self.book_id
                
                if "title" in response_data:
                    self.structured_content["result"]["title"] = response_data["title"]
                    
                if "author" in response_data:
                    self.structured_content["result"]["author"] = response_data["author"]
                elif "authors" in response_data and isinstance(response_data["authors"], list):
                    self.structured_content["result"]["author"] = ", ".join(response_data["authors"])
                
                # Извлекаем содержимое страниц
                if "content" in response_data and isinstance(response_data["content"], list):
                    self.structured_content["result"]["content"] = response_data["content"]
                elif "pages" in response_data and isinstance(response_data["pages"], list):
                    # Преобразуем формат страниц в нужный формат
                    pages = []
                    for i, page in enumerate(response_data["pages"]):
                        if isinstance(page, dict) and "text" in page:
                            pages.append({
                                "pageNumber": page.get("pageNumber", i + 1),
                                "text": page["text"]
                            })
                        elif isinstance(page, str):
                            pages.append({
                                "pageNumber": i + 1,
                                "text": page
                            })
                    self.structured_content["result"]["content"] = pages
                
                # Если контент не найден, пытаемся создать его из имеющихся текстовых полей
                if not self.structured_content["result"]["content"]:
                    if self.text_content:
                        pages = []
                        for i, text in enumerate(self.text_content):
                            pages.append({
                                "pageNumber": i + 1,
                                "text": text
                            })
                        self.structured_content["result"]["content"] = pages
                
                return bool(self.structured_content["result"]["content"])
            
            return False
        except Exception as e:
            logging.error(f"Error parsing structured content: {e}")
            return False
    
    def save_structured_content(self):
        """
        Сохраняет структурированный JSON с извлеченным контентом книги
        
        :return: True если успешно, иначе False
        """
        try:
            if not self.structured_content["result"]["content"]:
                logging.warning("No structured content to save")
                return False
                
            output_json_file = self.output_file.replace('.txt', '.json')
            with open(output_json_file, 'w', encoding='utf-8') as f:
                json.dump(self.structured_content, f, indent=2)
            
            logging.info(f"Structured content saved to {output_json_file}")
            return True
        except Exception as e:
            logging.error(f"Error saving structured content: {e}")
            return False
            
    def run(self, har_file=None, response_file=None):
        """
        Запускает процесс извлечения
        
        :param har_file: Путь к HAR файлу (опционально)
        :param response_file: Путь к файлу с ответом API (опционально)
        :return: True если успешно, иначе False
        """
        # Авторизуемся, если предоставлены учетные данные
        if self.email and self.password:
            auth_success = self.authenticate()
            if not auth_success:
                logging.error("Authentication failed, extraction might be limited")
        
        if har_file:
            logging.info(f"Starting extraction from HAR file: {har_file}")
            api_urls = self.extract_api_urls(har_file)
            if not api_urls:
                logging.error("No API URLs found in HAR file")
                return False
            
            fetch_success = self.fetch_book_content(api_urls)
            parse_success = self.parse_structured_content({})
            save_text_success = self.save_text()
            save_json_success = self.save_structured_content()
            
            return fetch_success and save_text_success
        
        elif response_file:
            logging.info(f"Starting extraction from response file: {response_file}")
            extract_success = self.extract_from_api_response(response_file)
            
            if extract_success:
                try:
                    with open(response_file, 'r', encoding='utf-8') as f:
                        try:
                            response_data = json.load(f)
                            parse_success = self.parse_structured_content(response_data)
                        except json.JSONDecodeError:
                            parse_success = self.parse_structured_content({})
                except Exception as e:
                    logging.error(f"Error reading response file for parsing: {e}")
                    parse_success = False
            else:
                parse_success = self.parse_structured_content({})
                
            save_text_success = self.save_text()
            save_json_success = self.save_structured_content()
            
            return extract_success and save_text_success
            
        elif self.book_url or self.book_id:
            logging.info(f"Starting extraction directly for book ID: {self.book_id or 'unknown'}")
            
            if not self.book_id and self.book_url:
                self.book_id = self._extract_asin(self.book_url)
                
            if not self.book_id:
                logging.error("Could not determine book ID (ASIN)")
                return False
                
            # Автоматически определяем API эндпоинты
            api_endpoints = self.discover_api_endpoints()
            
            if not api_endpoints:
                logging.error("No API endpoints discovered")
                return False
                
            fetch_success = self.fetch_book_content(api_endpoints)
            parse_success = self.parse_structured_content({})
            save_text_success = self.save_text()
            save_json_success = self.save_structured_content()
            
            return fetch_success and save_text_success
        else:
            logging.error("No HAR, response file, or book URL/ID provided")
            return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract text from Kindle Cloud Reader using API responses')
    parser.add_argument('--har', help='Path to HAR file exported from developer tools')
    parser.add_argument('--response', help='Path to saved API response file')
    parser.add_argument('--output', default='kindle_book.txt', help='Path to save extracted text')
    
    args = parser.parse_args()
    
    if not args.har and not args.response:
        print("Error: You must provide either a HAR file or a response file")
        parser.print_help()
        exit(1)
    
    scraper = KindleAPIScraper(output_file=args.output)
    success = scraper.run(har_file=args.har, response_file=args.response)
    
    if success:
        print(f"Successfully extracted text and saved to {args.output}")
    else:
        print("Failed to extract text. Check the log file for details.")