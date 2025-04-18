import os
import json
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='amazon_auth.log'
)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logging.getLogger('').addHandler(console_handler)

class AmazonAuth:
    """
    Класс для автоматической авторизации в Amazon и получения cookies для доступа к Kindle Cloud Reader
    """
    
    def __init__(self, email=None, password=None, headless=True, cookies_file="amazon_cookies.json"):
        """
        Инициализация класса авторизации Amazon
        
        :param email: Email для входа в Amazon
        :param password: Пароль для входа в Amazon
        :param headless: Запускать браузер в фоновом режиме (без GUI)
        :param cookies_file: Имя файла для сохранения cookies
        """
        self.email = email
        self.password = password
        self.headless = headless
        self.cookies_file = cookies_file
        self.driver = None
        self.cookies = None

    def setup_driver(self):
        """
        Настройка и запуск веб-драйвера Firefox
        
        :return: True если драйвер успешно запущен, иначе False
        """
        try:
            logging.info("Настройка веб-драйвера Firefox")
            
            options = Options()
            if self.headless:
                options.add_argument("-headless")
                
            # Дополнительные настройки для лучшей совместимости
            options.set_preference("dom.webdriver.enabled", False)
            options.set_preference("useAutomationExtension", False)
            options.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            service = Service(GeckoDriverManager().install())
            self.driver = webdriver.Firefox(service=service, options=options)
            self.driver.set_window_size(1366, 768)
            
            logging.info("Веб-драйвер Firefox успешно настроен")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при настройке веб-драйвера: {str(e)}")
            return False

    def login(self, max_wait_time=30):
        """
        Авторизация на сайте Amazon
        
        :param max_wait_time: Максимальное время ожидания для операций Selenium
        :return: True если авторизация прошла успешно, иначе False
        """
        if not self.email or not self.password:
            logging.warning("Email или пароль не указаны, авторизация невозможна")
            return False
            
        try:
            logging.info("Открываем страницу авторизации Amazon")
            self.driver.get("https://www.amazon.com/ap/signin")
            
            # Ждем загрузки страницы
            WebDriverWait(self.driver, max_wait_time).until(
                EC.presence_of_element_located((By.ID, "ap_email"))
            )
            
            # Вводим email
            logging.info(f"Вводим email: {self.email}")
            email_field = self.driver.find_element(By.ID, "ap_email")
            email_field.clear()
            email_field.send_keys(self.email)
            
            # Нажимаем кнопку "Continue"
            continue_button = self.driver.find_element(By.ID, "continue")
            continue_button.click()
            
            # Ждем загрузки страницы для ввода пароля
            WebDriverWait(self.driver, max_wait_time).until(
                EC.presence_of_element_located((By.ID, "ap_password"))
            )
            
            # Вводим пароль
            logging.info("Вводим пароль")
            password_field = self.driver.find_element(By.ID, "ap_password")
            password_field.clear()
            password_field.send_keys(self.password)
            
            # Находим флажок "Remember me" и устанавливаем его
            try:
                remember_me = self.driver.find_element(By.NAME, "rememberMe")
                if not remember_me.is_selected():
                    remember_me.click()
                    logging.info("Установлен флажок 'Remember me'")
            except NoSuchElementException:
                logging.info("Флажок 'Remember me' не найден")
            
            # Нажимаем кнопку "Sign-In"
            signin_button = self.driver.find_element(By.ID, "signInSubmit")
            signin_button.click()
            
            # Проверяем, что авторизация прошла успешно
            try:
                WebDriverWait(self.driver, max_wait_time).until(
                    lambda driver: "amazon.com" in driver.current_url and "ap/signin" not in driver.current_url
                )
                logging.info("Авторизация прошла успешно")
                return True
                
            except TimeoutException:
                logging.error("Ошибка авторизации. Проверьте учетные данные.")
                
                # Проверяем наличие капчи или двухфакторной аутентификации
                if "ap/mfa" in self.driver.current_url:
                    logging.warning("Требуется двухфакторная аутентификация. Автоматическая авторизация невозможна.")
                elif self.driver.find_elements(By.ID, "auth-captcha-image"):
                    logging.warning("Требуется ввод капчи. Автоматическая авторизация невозможна.")
                
                return False
                
        except Exception as e:
            logging.error(f"Ошибка при авторизации: {str(e)}")
            return False

    def open_kindle_cloud_reader(self, max_wait_time=30):
        """
        Открываем Kindle Cloud Reader
        
        :param max_wait_time: Максимальное время ожидания для операций Selenium
        :return: True если удалось открыть, иначе False
        """
        try:
            logging.info("Открываем Kindle Cloud Reader")
            self.driver.get("https://read.amazon.com")
            
            # Ждем загрузки страницы
            WebDriverWait(self.driver, max_wait_time).until(
                lambda driver: "read.amazon.com" in driver.current_url
            )
            
            # Проверяем, не перенаправило ли нас на страницу авторизации
            if "ap/signin" in self.driver.current_url:
                logging.info("Требуется авторизация")
                return self.login(max_wait_time)
                
            logging.info("Kindle Cloud Reader успешно открыт")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при открытии Kindle Cloud Reader: {str(e)}")
            return False

    def extract_cookies(self):
        """
        Извлечение cookies после успешной авторизации
        
        :return: True если cookies успешно извлечены, иначе False
        """
        try:
            logging.info("Извлечение cookies")
            
            # Получаем все cookies
            all_cookies = self.driver.get_cookies()
            
            # Фильтруем cookies для amazon.com и read.amazon.com
            filtered_cookies = [
                cookie for cookie in all_cookies 
                if ".amazon.com" in cookie.get("domain", "")
            ]
            
            self.cookies = filtered_cookies
            
            logging.info(f"Извлечено {len(filtered_cookies)} cookies")
            return len(filtered_cookies) > 0
            
        except Exception as e:
            logging.error(f"Ошибка при извлечении cookies: {str(e)}")
            return False

    def save_cookies(self):
        """
        Сохранение cookies в файл
        
        :return: True если cookies успешно сохранены, иначе False
        """
        if not self.cookies:
            logging.warning("Нет cookies для сохранения")
            return False
            
        try:
            logging.info(f"Сохранение cookies в файл: {self.cookies_file}")
            
            with open(self.cookies_file, 'w', encoding='utf-8') as f:
                json.dump(self.cookies, f, ensure_ascii=False, indent=2)
                
            logging.info(f"Cookies успешно сохранены в файл: {self.cookies_file}")
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при сохранении cookies: {str(e)}")
            return False

    def load_cookies(self):
        """
        Загрузка cookies из файла
        
        :return: True если cookies успешно загружены, иначе False
        """
        if not os.path.exists(self.cookies_file):
            logging.warning(f"Файл cookies не найден: {self.cookies_file}")
            return False
            
        try:
            logging.info(f"Загрузка cookies из файла: {self.cookies_file}")
            
            with open(self.cookies_file, 'r', encoding='utf-8') as f:
                self.cookies = json.load(f)
                
            logging.info(f"Загружено {len(self.cookies)} cookies из файла")
            return len(self.cookies) > 0
            
        except Exception as e:
            logging.error(f"Ошибка при загрузке cookies: {str(e)}")
            return False

    def add_cookies_to_driver(self):
        """
        Добавление cookies в драйвер
        
        :return: True если cookies успешно добавлены, иначе False
        """
        if not self.cookies:
            logging.warning("Нет cookies для добавления в драйвер")
            return False
            
        try:
            logging.info("Добавление cookies в драйвер")
            
            # Открываем amazon.com перед добавлением cookies
            self.driver.get("https://www.amazon.com")
            
            # Добавляем каждый cookie в драйвер
            added_count = 0
            for cookie in self.cookies:
                try:
                    # Удаляем лишние поля, которые могут вызвать ошибку
                    if 'expiry' in cookie:
                        cookie['expiry'] = int(cookie['expiry'])
                    
                    # Некоторые поля не поддерживаются Selenium
                    cookie_dict = {
                        'name': cookie.get('name'),
                        'value': cookie.get('value'),
                        'domain': cookie.get('domain'),
                        'path': cookie.get('path'),
                        'secure': cookie.get('secure', False),
                        'httpOnly': cookie.get('httpOnly', False)
                    }
                    
                    # Добавляем expiry, если он есть
                    if 'expiry' in cookie:
                        cookie_dict['expiry'] = cookie['expiry']
                        
                    self.driver.add_cookie(cookie_dict)
                    added_count += 1
                except Exception as e:
                    logging.warning(f"Не удалось добавить cookie {cookie.get('name')}: {str(e)}")
                    
            logging.info(f"Добавлено {added_count} cookies в драйвер")
            return added_count > 0
            
        except Exception as e:
            logging.error(f"Ошибка при добавлении cookies в драйвер: {str(e)}")
            return False

    def verify_authentication(self):
        """
        Проверка авторизации
        
        :return: True если авторизация подтверждена, иначе False
        """
        try:
            logging.info("Проверка авторизации")
            
            # Открываем страницу Kindle Cloud Reader
            self.driver.get("https://read.amazon.com")
            
            # Проверяем, не перенаправило ли нас на страницу авторизации
            if "ap/signin" in self.driver.current_url:
                logging.warning("Авторизация не подтверждена, требуется повторный вход")
                return False
                
            # Пытаемся найти элементы, которые доступны только авторизованным пользователям
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda driver: driver.find_elements(By.ID, "library") or 
                                  driver.find_elements(By.CLASS_NAME, "library") or
                                  "read.amazon.com/your_content" in driver.current_url
                )
                logging.info("Авторизация подтверждена")
                return True
            except TimeoutException:
                logging.warning("Авторизация не подтверждена, элементы библиотеки не найдены")
                return False
                
        except Exception as e:
            logging.error(f"Ошибка при проверке авторизации: {str(e)}")
            return False

    def run(self, force_login=False):
        """
        Запуск процесса авторизации и получения cookies
        
        :param force_login: Принудительная авторизация, даже если cookies уже есть
        :return: True если процесс успешен, иначе False
        """
        try:
            # Настраиваем драйвер
            if not self.setup_driver():
                return False
                
            # Пытаемся загрузить cookies из файла
            cookies_loaded = False
            if not force_login:
                cookies_loaded = self.load_cookies()
                
            if cookies_loaded:
                logging.info("Cookies загружены из файла, пытаемся использовать их для авторизации")
                self.add_cookies_to_driver()
                
                # Проверяем авторизацию с загруженными cookies
                if self.verify_authentication():
                    logging.info("Успешная авторизация с использованием сохраненных cookies")
                    return True
                else:
                    logging.info("Авторизация с сохраненными cookies не удалась, выполняем полную авторизацию")
            
            # Выполняем полную авторизацию
            if not self.login():
                return False
                
            # Проверяем, что мы успешно авторизовались
            if not self.verify_authentication():
                return False
                
            # Извлекаем cookies
            if not self.extract_cookies():
                return False
                
            # Сохраняем cookies
            self.save_cookies()
            
            return True
            
        except Exception as e:
            logging.error(f"Ошибка при запуске процесса авторизации: {str(e)}")
            return False
        finally:
            # Закрываем драйвер
            if self.driver:
                self.driver.quit()
                logging.info("Драйвер закрыт")

    def get_session_data(self):
        """
        Получение данных сессии для использования в requests
        
        :return: Словарь с cookies и user-agent или None при ошибке
        """
        if not self.cookies:
            logging.warning("Нет cookies для получения данных сессии")
            return None
            
        try:
            # Формируем словарь cookies для requests
            cookies_dict = {}
            for cookie in self.cookies:
                cookies_dict[cookie['name']] = cookie['value']
                
            # Определяем user-agent
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            
            return {
                'cookies': cookies_dict,
                'user_agent': user_agent
            }
            
        except Exception as e:
            logging.error(f"Ошибка при получении данных сессии: {str(e)}")
            return None


if __name__ == "__main__":
    # Пример использования
    auth = AmazonAuth(
        email="your.email@example.com",
        password="your_password",
        headless=True
    )
    
    success = auth.run()
    if success:
        print("Авторизация успешна, cookies сохранены")
        session_data = auth.get_session_data()
        print(f"Доступно {len(session_data['cookies'])} cookies для использования в requests")
    else:
        print("Ошибка авторизации")