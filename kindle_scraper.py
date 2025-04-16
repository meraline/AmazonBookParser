import time
import os
import logging
import tempfile
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("kindle_scraper.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class KindleScraper:
    def __init__(self, email=None, password=None, book_url=None, output_file="kindle_book.txt", pages_to_read=50, page_load_time=5):
        """
        Инициализация скрапера для Kindle Cloud Reader
        
        :param email: Email для входа в Amazon
        :param password: Пароль для входа в Amazon
        :param book_url: URL книги в Kindle Cloud Reader
        :param output_file: Имя файла для сохранения текста
        :param pages_to_read: Количество страниц для чтения
        :param page_load_time: Время ожидания загрузки страницы в секундах
        """
        self.email = email or os.environ.get("AMAZON_EMAIL")
        self.password = password or os.environ.get("AMAZON_PASSWORD")
        self.book_url = book_url
        self.output_file = output_file
        self.pages_to_read = pages_to_read
        self.page_load_time = page_load_time
        self.driver = None
        
    def setup_driver(self):
        """Настройка и запуск веб-драйвера Firefox"""
        try:
            logging.info("Настройка веб-драйвера Firefox...")
            
            # Настраиваем опции Firefox
            options = FirefoxOptions()
            options.set_preference("browser.download.folderList", 2)
            options.set_preference("browser.download.manager.showWhenStarting", False)
            options.set_preference("browser.download.dir", os.getcwd())
            options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/pdf")
            
            # Отключаем headless режим, чтобы видеть процесс
            # options.add_argument("--headless")
            
            # Используем geckodriver через webdriver_manager
            service = FirefoxService(GeckoDriverManager().install())
            
            # Запускаем Firefox с нашими опциями
            self.driver = webdriver.Firefox(service=service, options=options)
            
            # Настраиваем размер окна и таймауты
            self.driver.maximize_window()
            self.driver.set_page_load_timeout(60)
            self.driver.implicitly_wait(20)
            
            logging.info("Веб-драйвер Firefox успешно настроен")
            return True
        except Exception as e:
            logging.error(f"Ошибка при настройке драйвера: {e}")
            return False
            
    def login(self):
        """Ожидание ручного входа пользователя"""
        try:
            logging.info("Открытие страницы Kindle Cloud Reader...")
            self.driver.get("https://read.amazon.com/")
            
            # Даем пользователю время для входа в систему вручную
            logging.info("Ожидание ручного входа пользователя...")
            print("\n============================================")
            print("Пожалуйста, войдите в свой аккаунт Amazon вручную.")
            print("После входа перейдите в библиотеку.")
            print("У вас есть 60 секунд для выполнения входа.")
            print("============================================\n")
            
            # Ждем некоторое время для ручного входа
            time.sleep(60)  # Даем пользователю 60 секунд на ручной вход
            
            logging.info("Проверка состояния входа...")
            
            # Проверяем, что мы находимся на странице Kindle Cloud Reader
            if "read.amazon.com" in self.driver.current_url:
                logging.info("Пользователь успешно вошел и открыл Kindle Cloud Reader")
                return True
            else:
                logging.error("Не похоже, что мы находимся на странице Kindle Cloud Reader")
                return False
        except Exception as e:
            logging.error(f"Ошибка при авторизации: {e}")
            return False
            
    def open_book(self):
        """Ожидание, пока пользователь откроет книгу вручную"""
        try:
            logging.info("Ожидание, пока пользователь откроет книгу вручную...")
            print("\n============================================")
            print("Пожалуйста, выберите книгу 'Quantum Poker' и откройте её.")
            print("После открытия книги в режиме чтения, у вас есть")
            print("30 секунд для подготовки книги к скрапингу.")
            print("Рекомендуется кликнуть по центру страницы, чтобы")
            print("скрыть элементы интерфейса.")
            print("============================================\n")
            
            # Ждем, пока пользователь откроет книгу
            time.sleep(30)
            
            # Проверяем, что мы находимся на странице чтения книги
            if "read.amazon.com" in self.driver.current_url and ("/reader/" in self.driver.current_url or "/kindle-library" in self.driver.current_url):
                logging.info("Книга успешно открыта")
                return True
            else:
                logging.error("Не похоже, что мы находимся на странице чтения книги")
                return False
        except Exception as e:
            logging.error(f"Ошибка при открытии книги: {e}")
            return False
            
    def extract_text(self):
        """Извлечение текста из книги"""
        try:
            logging.info(f"Начало извлечения текста. Планируется прочитать {self.pages_to_read} страниц")
            
            # Клик по центру, чтобы убрать интерфейс
            self.driver.find_element(By.TAG_NAME, "body").click()
            time.sleep(2)
            
            # Создаем файл для сохранения текста
            with open(self.output_file, 'w', encoding='utf-8') as f:
                for page in range(self.pages_to_read):
                    try:
                        logging.info(f"Обработка страницы {page + 1}")
                        
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
                                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                if elements:
                                    content_elements = elements
                                    logging.info(f"Найдены элементы с текстом по селектору: {selector}")
                                    break
                            except:
                                continue
                        
                        # Если не нашли элементы ни по одному из селекторов, попробуем извлечь весь текст страницы
                        if not content_elements:
                            logging.warning("Не найдены стандартные элементы с текстом, извлекаем весь текст страницы")
                            content_elements = [self.driver.find_element(By.TAG_NAME, "body")]
                        
                        # Извлекаем текст
                        page_text = ""
                        for elem in content_elements:
                            elem_text = elem.text.strip()
                            if elem_text:
                                page_text += elem_text + "\n"
                        
                        # Записываем в файл
                        f.write(f"\n\n=== Страница {page + 1} ===\n")
                        f.write(page_text.strip())
                        
                        # Делаем скриншот для проверки (опционально)
                        # self.driver.save_screenshot(f"page_{page+1}.png")
                        
                        # Нажимаем стрелку "вперёд"
                        body = self.driver.find_element(By.TAG_NAME, "body")
                        body.send_keys(Keys.ARROW_RIGHT)
                        
                        # Ждем загрузки новой страницы
                        time.sleep(self.page_load_time)
                        
                    except Exception as e:
                        logging.error(f"Ошибка на странице {page+1}: {e}")
                        # Продолжаем, несмотря на ошибку на одной странице
                        continue
                
            logging.info(f"Извлечение текста завершено. Сохранено {self.pages_to_read} страниц в файл: {self.output_file}")
            return True
        except Exception as e:
            logging.error(f"Ошибка при извлечении текста: {e}")
            return False
            
    def run(self):
        """Запуск всего процесса скрапинга"""
        try:
            success = self.setup_driver()
            if not success:
                return False
                
            success = self.login()
            if not success:
                return False
                
            success = self.open_book()
            if not success:
                return False
                
            success = self.extract_text()
            if not success:
                return False
                
            logging.info("Процесс скрапинга успешно завершен")
            return True
        except Exception as e:
            logging.error(f"Ошибка в процессе скрапинга: {e}")
            return False
        finally:
            if self.driver:
                self.driver.quit()
                logging.info("Веб-драйвер закрыт")


if __name__ == "__main__":
    # Пример использования скрипта напрямую
    scraper = KindleScraper(
        email="meraline7@gmail.com",
        password="uYX-8q3-J6u-j8v",
        book_url="https://read.amazon.com/?x-client-id=ads-store&_encoding=UTF8&asin=B009SE1Z9E&consumptionLimitReached=false&hasMultimedia=false&requiredCapabilities=EBOK_PURCHASE_ALLOWED&ref_=ast_author_rff",
        output_file="my_kindle_book.txt",
        pages_to_read=100,
        page_load_time=3
    )
    
    success = scraper.run()
    if success:
        print(f"Книга успешно извлечена и сохранена в файл {scraper.output_file}")
    else:
        print("Произошла ошибка при извлечении книги. Проверьте лог-файл для деталей.")
