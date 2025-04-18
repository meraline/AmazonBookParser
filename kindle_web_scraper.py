import trafilatura
import requests
import json
import logging
import time
from urllib.parse import urlparse, parse_qs

logging.basicConfig(filename='kindle_web_scraper.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class KindleWebScraper:
    def __init__(self, book_url=None, output_file="kindle_book.txt", session_cookies=None):
        """
        Инициализация веб-скрапера для Kindle Cloud Reader
        
        :param book_url: URL книги в Kindle Cloud Reader
        :param output_file: Имя файла для сохранения текста
        :param session_cookies: Cookies для авторизации (опционально)
        """
        self.book_url = book_url
        self.output_file = output_file
        self.session_cookies = session_cookies or {}
        self.session = requests.Session()
        
        # Устанавливаем заголовки для имитации браузера
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
            'Referer': 'https://read.amazon.com/',
            'Origin': 'https://read.amazon.com',
        }
        
        # Добавляем cookies в сессию
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
    
    def run(self):
        """
        Запускает процесс извлечения
        
        :return: True если успешно, иначе False
        """
        logging.info(f"Starting extraction from URL: {self.book_url}")
        
        # Пробуем получить контент через trafilatura
        content_extracted = self.get_book_content()
        
        # Если не удалось, пробуем через API
        if not content_extracted:
            logging.info("Direct content extraction failed, trying API endpoints...")
            content_extracted = self.try_api_endpoints()
        
        # Сохраняем результат, если есть что сохранять
        if content_extracted:
            return self.save_text()
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