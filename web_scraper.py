import requests
import trafilatura
import time
import logging
import re
import json
from bs4 import BeautifulSoup

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("kindle_scraper.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class KindleWebScraper:
    def __init__(self, email=None, password=None, book_url=None, output_file="kindle_book.txt", pages_to_read=50):
        """
        Инициализация скрапера для Kindle без использования Selenium
        
        :param email: Email для входа в Amazon
        :param password: Пароль для входа в Amazon
        :param book_url: URL книги в Kindle Cloud Reader
        :param output_file: Имя файла для сохранения текста
        :param pages_to_read: Количество страниц для чтения
        """
        self.email = email
        self.password = password
        self.book_url = book_url
        self.output_file = output_file
        self.pages_to_read = pages_to_read
        self.session = requests.Session()
        self.cookies = {}
        
        # Заголовки для запросов
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
    def extract_book_info(self):
        """Извлечение информации о книге из URL"""
        asin_match = re.search(r'asin=([A-Z0-9]+)', self.book_url)
        if asin_match:
            return asin_match.group(1)
        return None
        
    def extract_text_from_url(self, url):
        """Извлечение текста с веб-страницы с помощью trafilatura"""
        try:
            logging.info(f"Извлечение содержимого с URL: {url}")
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(downloaded)
                return text
            else:
                logging.warning(f"Не удалось загрузить контент с URL: {url}")
                return None
        except Exception as e:
            logging.error(f"Ошибка при извлечении текста: {e}")
            return None
            
    def get_book_text(self):
        """Получение текста книги"""
        try:
            # Извлекаем ASIN книги из URL
            asin = self.extract_book_info()
            if not asin:
                logging.error("Не удалось извлечь ASIN книги из URL")
                return False
                
            logging.info(f"Получаем информацию о книге с ASIN: {asin}")
                
            # Строим URL для получения общедоступной информации о книге на Amazon
            amazon_book_url = f"https://www.amazon.com/dp/{asin}"
            
            # Используем trafilatura для извлечения информации о книге
            book_info = self.extract_text_from_url(amazon_book_url)
            
            if book_info:
                logging.info("Успешно получена информация о книге")
                
                # Записываем результат в файл
                with open(self.output_file, 'w', encoding='utf-8') as f:
                    f.write("=== Информация о книге ===\n\n")
                    f.write(book_info)
                    
                logging.info(f"Информация сохранена в файл: {self.output_file}")
                return True
            else:
                logging.error("Не удалось получить информацию о книге")
                return False
                
        except Exception as e:
            logging.error(f"Ошибка при получении текста книги: {e}")
            return False
            
    def search_book_preview(self):
        """Поиск предпросмотра книги на Amazon"""
        try:
            asin = self.extract_book_info()
            if not asin:
                return False
                
            # Формируем URL для поиска предпросмотра книги
            preview_url = f"https://www.amazon.com/gp/product/{asin}/look-inside/"
            
            logging.info(f"Поиск предпросмотра книги по URL: {preview_url}")
            
            response = self.session.get(preview_url, headers=self.headers)
            
            if response.status_code == 200:
                logging.info("Найдена страница предпросмотра книги")
                
                # Проверяем, есть ли предпросмотр контента
                if "Look Inside" in response.text or "Search Inside This Book" in response.text:
                    logging.info("Книга имеет функцию предпросмотра")
                    
                    # Извлекаем доступный предпросмотр с помощью trafilatura
                    text = trafilatura.extract(response.text)
                    
                    if text:
                        # Записываем результат в файл
                        with open(self.output_file, 'a', encoding='utf-8') as f:
                            f.write("\n\n=== Предпросмотр книги ===\n\n")
                            f.write(text)
                            
                        logging.info(f"Предпросмотр сохранен в файл: {self.output_file}")
                        return True
                else:
                    logging.warning("Книга не имеет функции предпросмотра")
            else:
                logging.warning(f"Не удалось получить страницу предпросмотра. Код ответа: {response.status_code}")
                
            return False
        except Exception as e:
            logging.error(f"Ошибка при поиске предпросмотра книги: {e}")
            return False
            
    def run(self):
        """Запуск процесса извлечения информации о книге"""
        success = False
        try:
            logging.info("Начало процесса получения информации о книге")
            
            # Получаем основную информацию о книге
            book_info_success = self.get_book_text()
            
            # Пытаемся найти предпросмотр книги
            preview_success = self.search_book_preview()
            
            success = book_info_success or preview_success
            
            if success:
                logging.info("Процесс извлечения информации о книге завершен успешно")
            else:
                logging.warning("Процесс извлечения завершен, но не удалось получить полную информацию о книге")
                
            # Добавляем уведомление о том, что для полного извлечения текста книги требуется авторизация
            with open(self.output_file, 'a', encoding='utf-8') as f:
                f.write("\n\n=== Примечание ===\n\n")
                f.write("Для получения полного текста книги требуется авторизация в Kindle Cloud Reader и ")
                f.write("использование специальных инструментов, которые не могут быть запущены в данной среде.\n")
                f.write("Данный скрипт извлекает только общедоступную информацию о книге и, если доступно, предпросмотр.\n")
                
            return success
        except Exception as e:
            logging.error(f"Ошибка в процессе извлечения информации о книге: {e}")
            return False
            
def get_website_text_content(url: str) -> str:
    """
    Получение текстового содержимого сайта с использованием trafilatura
    """
    downloaded = trafilatura.fetch_url(url)
    if downloaded:
        text = trafilatura.extract(downloaded)
        return text
    return "Не удалось извлечь содержимое с данного URL."

if __name__ == "__main__":
    # Пример использования
    scraper = KindleWebScraper(
        email="meraline7@gmail.com",
        password="uYX-8q3-J6u-j8v",
        book_url="https://read.amazon.com/?x-client-id=ads-store&_encoding=UTF8&asin=B009SE1Z9E&consumptionLimitReached=false&hasMultimedia=false&requiredCapabilities=EBOK_PURCHASE_ALLOWED&ref_=ast_author_rff",
        output_file="kindle_book_info.txt",
        pages_to_read=10
    )
    success = scraper.run()
    
    if success:
        print(f"Информация о книге успешно извлечена и сохранена в файл {scraper.output_file}")
    else:
        print("Произошла ошибка при извлечении информации о книге. Проверьте лог-файл для деталей.")