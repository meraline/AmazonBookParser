import requests
import json
import time
import logging
from urllib.parse import urlparse

logging.basicConfig(filename='kindle_api_scraper.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class KindleAPIScraper:
    def __init__(self, session_cookies=None, book_id=None, output_file="kindle_book.txt"):
        """
        Инициализация API скрапера для Kindle Cloud Reader
        
        :param session_cookies: Cookies из открытой сессии Kindle (из инструментов разработчика)
        :param book_id: ID книги в Kindle (из URL или запросов)
        :param output_file: Имя файла для сохранения текста
        """
        self.session_cookies = session_cookies or {}
        self.book_id = book_id
        self.output_file = output_file
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://read.amazon.com/',
            'Origin': 'https://read.amazon.com',
        }
        for cookie_name, cookie_value in self.session_cookies.items():
            self.session.cookies.set(cookie_name, cookie_value)
        
        self.text_content = []
        logging.info("Initialized Kindle API Scraper")
    
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
    
    def run(self, har_file=None, response_file=None):
        """
        Запускает процесс извлечения
        
        :param har_file: Путь к HAR файлу (опционально)
        :param response_file: Путь к файлу с ответом API (опционально)
        :return: True если успешно, иначе False
        """
        if har_file:
            logging.info(f"Starting extraction from HAR file: {har_file}")
            api_urls = self.extract_api_urls(har_file)
            if not api_urls:
                logging.error("No API URLs found in HAR file")
                return False
            return self.fetch_book_content(api_urls) and self.save_text()
        elif response_file:
            logging.info(f"Starting extraction from response file: {response_file}")
            return self.extract_from_api_response(response_file) and self.save_text()
        else:
            logging.error("No HAR or response file provided")
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