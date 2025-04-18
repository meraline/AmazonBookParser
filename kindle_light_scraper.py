#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import logging
import traceback
import base64
import requests
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
import traceback

from debug_utils import (
    selenium_logger, api_logger, parsing_logger, 
    log_function_call, log_api_request, log_api_response, log_parsed_content
)

class KindleLightScraper:
    """
    Облегченный скрапер для Kindle Cloud Reader, использующий минимум ресурсов.
    Предназначен для работы в ограниченных средах, таких как Replit.
    """
    
    @log_function_call(selenium_logger)
    def __init__(self, email=None, password=None, book_url=None, output_file="kindle_light_book.txt", book_id=None, max_pages=50, session_cookies=None):
        """
        Инициализация облегченного скрапера для Kindle Cloud Reader
        
        :param email: Email для входа в Amazon
        :param password: Пароль для входа в Amazon
        :param book_url: URL книги в Kindle Cloud Reader
        :param output_file: Имя файла для сохранения текста
        :param book_id: ID книги (ASIN) - если не указан, будет извлечен из URL
        :param max_pages: Максимальное количество страниц для обработки
        :param session_cookies: Cookies сессии (опционально)
        """
        self.email = email
        self.password = password
        self.book_url = book_url
        self.output_file = output_file
        self.book_id = book_id
        self.max_pages = max_pages
        self.session_cookies = session_cookies
        
        # Извлекаем ASIN из URL, если он не указан
        if not self.book_id and self.book_url:
            self.book_id = self._extract_asin(self.book_url)
            
        # Инициализируем сессию requests с сохранением cookies
        self.session = requests.Session()
        
        # Устанавливаем user-agent браузера для запросов
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        self.session.headers.update({
            'User-Agent': self.user_agent
        })
        
        # Если переданы cookies, устанавливаем их
        if self.session_cookies:
            for cookie in self.session_cookies:
                self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', ''))
        
        # Создаем структуру данных для хранения результатов
        self.structured_content = {
            "success": True,
            "result": {
                "bookId": self.book_id or "",
                "title": "",
                "author": "",
                "content": []
            }
        }
        
        # Для удобства также сохраняем в виде плоского текста
        self.extracted_text = ""
        
        # Состояние и прогресс
        self.is_authenticated = False
        self.current_page = 0
        self.current_page_callback = None  # Функция для обновления прогресса
        
        selenium_logger.info(f"Инициализирован облегченный скрапер для книги {self.book_id or self.book_url}")

    @log_function_call(selenium_logger)
    def _extract_asin(self, url):
        """
        Извлекает ASIN книги из URL
        
        :param url: URL книги
        :return: ASIN книги или None
        """
        try:
            parsed_url = urlparse(url)
            
            # Извлекаем из параметра asin
            query_params = parse_qs(parsed_url.query)
            if 'asin' in query_params:
                return query_params['asin'][0]
                
            # Извлекаем из пути URL
            path_parts = parsed_url.path.split('/')
            for part in path_parts:
                # ASIN обычно имеет формат из 10 символов, например B009SE1Z9E
                if part and len(part) == 10 and part[0] == 'B' and part[1:].isalnum():
                    return part
                    
            selenium_logger.warning(f"Не удалось извлечь ASIN из URL: {url}")
            return None
            
        except Exception as e:
            selenium_logger.error(f"Ошибка при извлечении ASIN из URL: {str(e)}")
            return None

    @log_function_call(api_logger)
    def authenticate(self):
        """
        Аутентификация на сайте Amazon
        
        :return: True если авторизация прошла успешно, иначе False
        """
        try:
            if not self.email or not self.password:
                api_logger.error("Не указаны email или пароль для авторизации")
                return False
                
            api_logger.info(f"Аутентификация пользователя {self.email}")
            
            # Загружаем главную страницу Amazon для получения начальных cookies и токенов
            main_page_url = "https://www.amazon.com"
            log_api_request(main_page_url, "GET", self.session.headers)
            
            response = self.session.get(main_page_url)
            log_api_response(main_page_url, response.status_code, response.headers, "Главная страница Amazon")
            
            # Загружаем страницу логина
            login_page_url = "https://www.amazon.com/ap/signin"
            
            login_params = {
                "openid.pape.max_auth_age": "0",
                "openid.return_to": "https://www.amazon.com/ref=nav_ya_signin",
                "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
                "openid.assoc_handle": "usflex",
                "openid.mode": "checkid_setup",
                "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
                "openid.ns": "http://specs.openid.net/auth/2.0"
            }
            
            log_api_request(login_page_url, "GET", self.session.headers, params=login_params)
            response = self.session.get(login_page_url, params=login_params)
            log_api_response(login_page_url, response.status_code, response.headers, "Страница логина")
            
            # Парсим форму и извлекаем скрытые поля
            soup = BeautifulSoup(response.text, 'html.parser')
            form = soup.find('form', {'name': 'signIn'})
            
            if not form:
                api_logger.error("Не найдена форма входа на странице авторизации")
                return False
                
            # Извлекаем все скрытые поля формы
            form_data = {}
            for input_field in form.find_all('input'):
                if input_field.get('name'):
                    form_data[input_field.get('name')] = input_field.get('value', '')
            
            # Добавляем учетные данные
            form_data['email'] = self.email
            form_data['password'] = self.password
            
            # Отправляем форму авторизации
            post_url = "https://www.amazon.com/ap/signin"
            log_api_request(post_url, "POST", self.session.headers, data=form_data)
            
            response = self.session.post(post_url, data=form_data)
            log_api_response(post_url, response.status_code, response.headers, "Отправка формы авторизации")
            
            # Проверяем успешность авторизации
            if "auth-error-message" in response.text or "There was a problem" in response.text:
                api_logger.error("Ошибка авторизации: неверные учетные данные")
                return False
                
            # Проверяем, есть ли редирект на страницу с проверкой безопасности
            if "approve" in response.url or "mfa" in response.url:
                api_logger.error("Требуется дополнительная проверка безопасности (MFA, капча и т.д.)")
                return False
                
            # Теперь проверим, имеем ли мы доступ к Kindle
            kindle_url = "https://read.amazon.com"
            log_api_request(kindle_url, "GET", self.session.headers)
            
            response = self.session.get(kindle_url)
            log_api_response(kindle_url, response.status_code, response.headers, "Проверка доступа к Kindle")
            
            # Если нас перенаправило на страницу логина, значит авторизация не прошла
            if "ap/signin" in response.url or response.status_code >= 400:
                api_logger.error("Не удалось получить доступ к Kindle Cloud Reader после авторизации")
                return False
                
            api_logger.info(f"Успешная авторизация пользователя {self.email}")
            self.is_authenticated = True
            return True
            
        except Exception as e:
            api_logger.error(f"Ошибка при авторизации: {str(e)}")
            api_logger.error(f"Трассировка: {traceback.format_exc()}")
            return False

    @log_function_call(api_logger)
    def fetch_book_metadata(self):
        """
        Получает метаданные книги
        
        :return: True если успешно, иначе False
        """
        try:
            if not self.book_id:
                api_logger.error("Не указан ID книги (ASIN)")
                return False
                
            api_logger.info(f"Получение метаданных для книги с ASIN: {self.book_id}")
            
            # Формируем URL для получения метаданных книги
            metadata_url = f"https://read.amazon.com/service/metadata?asin={self.book_id}"
            
            log_api_request(metadata_url, "GET", self.session.headers)
            response = self.session.get(metadata_url)
            log_api_response(metadata_url, response.status_code, response.headers, "Запрос метаданных книги")
            
            if response.status_code != 200:
                api_logger.error(f"Не удалось получить метаданные книги. Код ответа: {response.status_code}")
                return False
                
            try:
                # Пытаемся распарсить JSON ответа
                metadata = response.json()
                log_parsed_content(metadata, "book_metadata")
                
                # Извлекаем название и автора
                if 'title' in metadata:
                    self.structured_content['result']['title'] = metadata['title']
                    api_logger.info(f"Название книги: {metadata['title']}")
                    
                if 'authors' in metadata and metadata['authors']:
                    if isinstance(metadata['authors'], list):
                        self.structured_content['result']['author'] = ', '.join(metadata['authors'])
                    else:
                        self.structured_content['result']['author'] = str(metadata['authors'])
                    api_logger.info(f"Автор книги: {self.structured_content['result']['author']}")
                    
                return True
                
            except json.JSONDecodeError as json_err:
                api_logger.error(f"Не удалось распарсить ответ как JSON: {str(json_err)}")
                
                # Если ответ не в формате JSON, попробуем извлечь информацию из HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Попытка найти название и автора
                title_elem = soup.find('title')
                if title_elem and title_elem.text:
                    title_text = title_elem.text.strip()
                    if " - " in title_text:
                        parts = title_text.split(" - ")
                        self.structured_content['result']['title'] = parts[0].strip()
                        if len(parts) > 1 and "Amazon" not in parts[1]:
                            self.structured_content['result']['author'] = parts[1].strip()
                        api_logger.info(f"Извлечено из HTML: {title_text}")
                        return True
                
                return False
                
        except Exception as e:
            api_logger.error(f"Ошибка при получении метаданных книги: {str(e)}")
            api_logger.error(f"Трассировка: {traceback.format_exc()}")
            return False

    @log_function_call(api_logger)
    def fetch_book_content(self):
        """
        Получает содержимое книги
        
        :return: True если успешно, иначе False
        """
        try:
            if not self.book_id:
                api_logger.error("Не указан ID книги (ASIN)")
                return False
                
            api_logger.info(f"Получение содержимого для книги с ASIN: {self.book_id}")
            
            # Пробуем получить информацию о структуре книги (главы, разделы)
            self._fetch_book_structure()
            
            # Главный цикл получения страниц
            for page_num in range(1, self.max_pages + 1):
                self.current_page = page_num
                
                # Вызываем колбэк для обновления прогресса
                if self.current_page_callback:
                    self.current_page_callback(self.current_page, self.max_pages)
                
                # Получаем содержимое текущей страницы
                if not self._fetch_page_content(page_num):
                    api_logger.info(f"Достигнут конец книги или максимальный лимит страниц: {page_num-1}")
                    break
                    
                # Делаем небольшую задержку между запросами
                time.sleep(1)
            
            return True
            
        except Exception as e:
            api_logger.error(f"Ошибка при получении содержимого книги: {str(e)}")
            api_logger.error(f"Трассировка: {traceback.format_exc()}")
            return False

    @log_function_call(api_logger)
    def _fetch_book_structure(self):
        """
        Получает структуру книги (оглавление, главы)
        
        :return: True если успешно, иначе False
        """
        try:
            # Формируем URL для получения структуры книги
            structure_url = f"https://read.amazon.com/service/toc?asin={self.book_id}"
            
            log_api_request(structure_url, "GET", self.session.headers)
            response = self.session.get(structure_url)
            log_api_response(structure_url, response.status_code, response.headers, "Запрос структуры книги")
            
            if response.status_code != 200:
                api_logger.warning(f"Не удалось получить структуру книги. Код ответа: {response.status_code}")
                return False
                
            try:
                # Пытаемся распарсить JSON ответа
                structure_data = response.json()
                log_parsed_content(structure_data, "book_structure")
                
                # Здесь может быть обработка структуры книги
                if 'toc' in structure_data and isinstance(structure_data['toc'], list):
                    api_logger.info(f"Получена структура книги: {len(structure_data['toc'])} разделов")
                    # Можно добавить структуру в результаты
                    self.structured_content['result']['structure'] = structure_data['toc']
                    
                return True
                
            except json.JSONDecodeError as json_err:
                api_logger.warning(f"Не удалось распарсить ответ структуры как JSON: {str(json_err)}")
                return False
                
        except Exception as e:
            api_logger.error(f"Ошибка при получении структуры книги: {str(e)}")
            return False
            
    @log_function_call(api_logger)
    def _fetch_page_content(self, page_num):
        """
        Получает содержимое определенной страницы
        
        :param page_num: Номер страницы
        :return: True если успешно и страница существует, иначе False
        """
        try:
            # Формируем URL для получения содержимого страницы
            # Пробуем несколько вариантов, так как точный API endpoint может отличаться
            
            endpoints = [
                f"https://read.amazon.com/service/reader/content?asin={self.book_id}&page={page_num}",
                f"https://read.amazon.com/api/book/content?asin={self.book_id}&page={page_num}",
                f"https://read.amazon.com/kp/notebook/content?asin={self.book_id}&page={page_num}"
            ]
            
            for endpoint_url in endpoints:
                log_api_request(endpoint_url, "GET", self.session.headers)
                response = self.session.get(endpoint_url)
                log_api_response(endpoint_url, response.status_code, response.headers, f"Запрос содержимого страницы {page_num}")
                
                # Проверяем успешность запроса
                if response.status_code == 200:
                    # Пытаемся обработать ответ как JSON
                    try:
                        content_data = response.json()
                        log_parsed_content(content_data, f"page_content_{page_num}")
                        
                        # Извлекаем текст из JSON-структуры
                        page_text = self._extract_text_from_json(content_data)
                        
                        if page_text:
                            self._add_page_to_results(page_num, page_text)
                            return True
                            
                    except json.JSONDecodeError:
                        # Если ответ не в формате JSON, пробуем извлечь из HTML
                        try:
                            soup = BeautifulSoup(response.text, 'html.parser')
                            content_elements = soup.select('.bookReaderPage, .kindleReaderPage, .kcrPage, .textLayer')
                            
                            if content_elements:
                                page_text = "\n".join([elem.get_text(strip=True) for elem in content_elements if elem.get_text(strip=True)])
                                if page_text:
                                    self._add_page_to_results(page_num, page_text)
                                    return True
                        except Exception as html_err:
                            api_logger.warning(f"Ошибка при извлечении текста из HTML: {str(html_err)}")
                
                # Если получили 404 или другой явный признак конца книги
                if response.status_code == 404 or "end of book" in response.text.lower():
                    api_logger.info(f"Достигнут конец книги на странице {page_num}")
                    return False
            
            # Если ни один из эндпоинтов не вернул полезные данные для этой страницы
            api_logger.warning(f"Не удалось получить содержимое страницы {page_num}")
            return False
            
        except Exception as e:
            api_logger.error(f"Ошибка при получении содержимого страницы {page_num}: {str(e)}")
            api_logger.error(f"Трассировка: {traceback.format_exc()}")
            return False

    @log_function_call(parsing_logger)
    def _extract_text_from_json(self, json_data):
        """
        Извлекает текст из JSON-структуры
        
        :param json_data: JSON-данные
        :return: Извлеченный текст или пустая строка
        """
        try:
            extracted_text = ""
            
            # Проверяем разные форматы JSON ответа
            if 'content' in json_data:
                # Формат 1: content как строка
                if isinstance(json_data['content'], str):
                    extracted_text = json_data['content']
                    
                # Формат 2: content как список объектов
                elif isinstance(json_data['content'], list):
                    for item in json_data['content']:
                        if isinstance(item, dict) and 'text' in item:
                            extracted_text += item['text'] + "\n"
                        elif isinstance(item, str):
                            extracted_text += item + "\n"
                            
            # Формат 3: text на верхнем уровне
            elif 'text' in json_data:
                extracted_text = json_data['text']
                
            # Формат 4: данные внутри вложенных объектов
            elif 'data' in json_data:
                if isinstance(json_data['data'], dict):
                    if 'content' in json_data['data']:
                        if isinstance(json_data['data']['content'], str):
                            extracted_text = json_data['data']['content']
                        elif isinstance(json_data['data']['content'], list):
                            for item in json_data['data']['content']:
                                if isinstance(item, dict) and 'text' in item:
                                    extracted_text += item['text'] + "\n"
                                elif isinstance(item, str):
                                    extracted_text += item + "\n"
                    elif 'text' in json_data['data']:
                        extracted_text = json_data['data']['text']
            
            # Рекурсивно ищем текст в других полях
            elif isinstance(json_data, dict):
                for key, value in json_data.items():
                    if isinstance(value, str) and len(value) > 50:  # Предполагаем, что длинные строки - текст
                        extracted_text += value + "\n"
                    elif isinstance(value, dict) or isinstance(value, list):
                        # Рекурсивный поиск текста во вложенных структурах
                        nested_text = self._extract_text_from_json(value)
                        if nested_text:
                            extracted_text += nested_text + "\n"
            
            # Очищаем текст от лишних символов
            extracted_text = extracted_text.strip()
            if extracted_text:
                parsing_logger.info(f"Извлечено {len(extracted_text)} символов текста")
                log_parsed_content(extracted_text[:100] + "..." if len(extracted_text) > 100 else extracted_text, "extracted_text_sample")
                
            return extracted_text
            
        except Exception as e:
            parsing_logger.error(f"Ошибка при извлечении текста из JSON: {str(e)}")
            parsing_logger.error(f"Трассировка: {traceback.format_exc()}")
            return ""

    def _add_page_to_results(self, page_num, page_text):
        """
        Добавляет страницу в результаты
        
        :param page_num: Номер страницы
        :param page_text: Текст страницы
        """
        try:
            # Добавляем в структурированный контент
            self.structured_content["result"]["content"].append({
                "pageNumber": page_num,
                "text": page_text
            })
            
            # Также сохраняем в плоский текст
            self.extracted_text += f"\n--- Страница {page_num} ---\n{page_text}\n"
            
            parsing_logger.info(f"Добавлена страница {page_num}: {len(page_text)} символов")
            
        except Exception as e:
            parsing_logger.error(f"Ошибка при добавлении страницы {page_num} в результаты: {str(e)}")

    @log_function_call(selenium_logger)
    def save_text(self):
        """
        Сохраняет извлеченный текст в файл
        
        :return: True если успешно, иначе False
        """
        try:
            if not self.extracted_text:
                selenium_logger.warning("Нет извлеченного текста для сохранения")
                return False
                
            selenium_logger.info(f"Сохранение текста в файл: {self.output_file}")
            
            # Формируем полный текст книги с метаданными
            full_text = f"Название: {self.structured_content['result']['title']}\n"
            full_text += f"Автор: {self.structured_content['result']['author']}\n"
            full_text += f"ID книги: {self.structured_content['result']['bookId']}\n\n"
            full_text += self.extracted_text
            
            # Сохраняем в файл
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(full_text)
                
            selenium_logger.info(f"Текст успешно сохранен в файл: {self.output_file}")
            return True
            
        except Exception as e:
            selenium_logger.error(f"Ошибка при сохранении текста в файл: {str(e)}")
            selenium_logger.error(f"Трассировка: {traceback.format_exc()}")
            return False

    @log_function_call(selenium_logger)
    def save_structured_content(self):
        """
        Сохраняет структурированный JSON с извлеченным контентом книги
        
        :return: True если успешно, иначе False
        """
        try:
            json_file = self.output_file.replace('.txt', '.json')
            
            selenium_logger.info(f"Сохранение структурированного контента в файл: {json_file}")
            
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(self.structured_content, f, ensure_ascii=False, indent=2)
                
            selenium_logger.info(f"Структурированный контент успешно сохранен в файл: {json_file}")
            return True
            
        except Exception as e:
            selenium_logger.error(f"Ошибка при сохранении структурированного контента: {str(e)}")
            selenium_logger.error(f"Трассировка: {traceback.format_exc()}")
            return False

    @log_function_call(selenium_logger)
    def run(self):
        """
        Запускает весь процесс извлечения
        
        :return: True если успешно, иначе False
        """
        try:
            selenium_logger.info("Запуск процесса извлечения")
            
            # Шаг 1: Аутентификация (если нет cookies)
            if not self.session_cookies and not self.is_authenticated:
                if not self.authenticate():
                    selenium_logger.error("Не удалось выполнить авторизацию")
                    return False
            
            # Шаг 2: Получаем метаданные книги
            if not self.fetch_book_metadata():
                selenium_logger.warning("Не удалось получить метаданные книги, но продолжаем процесс")
            
            # Шаг 3: Получаем содержимое книги
            if not self.fetch_book_content():
                selenium_logger.error("Ошибка при получении содержимого книги")
                return False
            
            # Шаг 4: Сохраняем результаты
            self.save_text()
            self.save_structured_content()
            
            selenium_logger.info("Процесс извлечения успешно завершен")
            return True
            
        except Exception as e:
            selenium_logger.error(f"Ошибка при запуске процесса извлечения: {str(e)}")
            selenium_logger.error(f"Трассировка: {traceback.format_exc()}")
            return False