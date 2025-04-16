import time
import os
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

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
        """Настройка и запуск веб-драйвера Chrome"""
        try:
            logging.info("Настройка веб-драйвера Chrome...")
            options = webdriver.ChromeOptions()
            # options.add_argument("--headless") # Убираем headless режим
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            
            # Создаем временную директорию для профиля
            import tempfile
            import os
            user_data_dir = os.path.join(tempfile.gettempdir(), f"chrome_profile_{os.getpid()}")
            os.makedirs(user_data_dir, exist_ok=True)
            logging.info(f"Используем временную директорию для профиля: {user_data_dir}")
            options.add_argument(f"--user-data-dir={user_data_dir}")
            
            # Маскируем автоматизацию
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            
            # Устанавливаем более длинные таймауты
            self.driver.set_page_load_timeout(60)
            self.driver.implicitly_wait(20)
            
            # Маскируем automation
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logging.info("Веб-драйвер Chrome успешно настроен")
            return True
        except Exception as e:
            logging.error(f"Ошибка при настройке драйвера: {e}")
            return False
            
    def login(self):
        """Авторизация в Amazon"""
        try:
            logging.info("Авторизация в Amazon...")
            self.driver.get("https://www.amazon.com/ap/signin")
            
            # Ожидание загрузки страницы авторизации
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "ap_email"))
            )
            
            # Ввод email и продолжение
            email_field = self.driver.find_element(By.ID, "ap_email")
            email_field.clear()
            email_field.send_keys(self.email)
            
            # Нажимаем "Continue"
            continue_button = self.driver.find_element(By.ID, "continue")
            continue_button.click()
            
            # Ожидаем появления поля пароля
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "ap_password"))
            )
            
            # Ввод пароля
            password_field = self.driver.find_element(By.ID, "ap_password")
            password_field.clear()
            password_field.send_keys(self.password)
            
            # Нажимаем "Sign-In"
            signin_button = self.driver.find_element(By.ID, "signInSubmit")
            signin_button.click()
            
            # Ожидаем загрузки страницы после входа
            time.sleep(5)
            
            # Проверяем, успешно ли вошли, проверяя наличие элементов ошибки
            if "auth-error-message-box" in self.driver.page_source:
                error_message = self.driver.find_element(By.ID, "auth-error-message-box").text
                logging.error(f"Ошибка авторизации: {error_message}")
                return False
                
            logging.info("Авторизация успешна")
            return True
        except Exception as e:
            logging.error(f"Ошибка при авторизации: {e}")
            return False
            
    def open_book(self):
        """Открытие книги по URL"""
        try:
            logging.info(f"Открытие книги по URL: {self.book_url}")
            self.driver.get(self.book_url)
            
            # Ожидаем загрузки книги
            time.sleep(10)
            
            # Проверяем, открылась ли книга, ищем элементы, характерные для Kindle Reader
            if "read.amazon.com" not in self.driver.current_url:
                logging.error("Не удалось открыть страницу книги")
                return False
                
            logging.info("Книга успешно открыта")
            return True
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
