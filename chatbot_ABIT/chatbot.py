import requests
from bs4 import BeautifulSoup
import json
import logging
import os  # Для работы с переменными окружения
from typing import Dict, Any, List
from openai import OpenAI  # Изменено для нового клиента OpenAI

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # Установите на DEBUG, если нужно еще больше деталей
)
logger = logging.getLogger(__name__)

# URL-ы программ магистратуры
AI_URL = "https://abit.itmo.ru/program/master/ai"
AI_PRODUCT_URL = "https://abit.itmo.ru/program/master/ai_product"


class ITMOAdmissionChatbot:
    def __init__(self):
        # Инициализация нового клиента OpenAI, настроенного на OpenRouter
        self.client = OpenAI(
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=os.environ.get("OPENROUTER_API_KEY")
        )
        if not self.client.api_key:
            logger.error("API ключ для OpenRouter не найден в переменной окружения OPENROUTER_API_KEY.")
            raise ValueError("API ключ не настроен. Пожалуйста, установите переменную окружения OPENROUTER_API_KEY.")

        self.programs_data = {}
        self.load_program_data()  # Загружаем данные о программах при инициализации

        self.conversation_history = []
        self.user_profile = {}

    def load_program_data(self):
        """Загружает данные о программах при инициализации бота."""
        logger.info("Загрузка данных для программы 'Искусственный интеллект'...")
        self.programs_data["ai"] = self.fetch_program_data(AI_URL)
        if self.programs_data["ai"].get('error'):
            logger.warning("Не удалось загрузить данные для программы 'Искусственный интеллект'.")

        logger.info("Загрузка данных для программы 'Управление ИИ-продуктами/AI Product'...")
        self.programs_data["ai_product"] = self.fetch_program_data(AI_PRODUCT_URL)
        if self.programs_data["ai_product"].get('error'):
            logger.warning("Не удалось загрузить данные для программы 'Управление ИИ-продуктами/AI Product'.")

    def fetch_program_data(self, url: str) -> Dict[str, Any]:
        """
        Извлекает информацию о программе с указанного URL.
        Приоритет отдается данным из __NEXT_DATA__ JSON, затем HTML-парсинг.
        Добавлено детальное логирование.
        """
        program_info = {
            "name": "Название программы не найдено.",
            "details": {},
            "institute": "Институт не найден.",
            "description": "Информация о программе не найдена.",
            "career": "Информация о карьере не найдена.",
            "study_plan_pdf_link": "Ссылка на учебный план не найдена.",
            "url": url,
            "error": False
        }

        logger.info(f"Начинаю парсинг данных для программы: {url}")

        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            logger.info(f"HTTP запрос успешен для {url}. Статус: {response.status_code}")

            # --- Попытка парсинга из __NEXT_DATA__ JSON ---
            next_data_script = soup.find('script', id='__NEXT_DATA__', type='application/json')
            if next_data_script:
                logger.info(f"Скрипт __NEXT_DATA__ найден для {url}.")
                try:
                    next_data = json.loads(next_data_script.string)
                    props = next_data.get('props', {}).get('pageProps', {}).get('program', {})
                    logger.info(f"JSON из __NEXT_DATA__ успешно загружен и распарсен для {url}.")
                    logger.debug(f"Содержимое 'program' (props) из JSON: {props}")  # Добавлено для отладки

                    # Hardcoding PDF links as ID extraction from __NEXT_DATA__ is reported as failing
                    if url == AI_URL:
                        program_info[
                            'study_plan_pdf_link'] = "https://api.itmo.su/constructor-ep/api/v1/static/programs/10033/plan/abit/pdf"
                        logger.info(f"  PDF ссылка для AI программы (hardcoded): {program_info['study_plan_pdf_link']}")
                    elif url == AI_PRODUCT_URL:
                        program_info[
                            'study_plan_pdf_link'] = "https://api.itmo.su/constructor-ep/api/v1/static/programs/10130/plan/abit/pdf"
                        logger.info(
                            f"  PDF ссылка для AI Product программы (hardcoded): {program_info['study_plan_pdf_link']}")
                    else:
                        # Fallback to dynamic ID extraction for other/new programs
                        program_id = props.get('id')
                        if program_id:
                            program_info[
                                'study_plan_pdf_link'] = f"https://api.itmo.su/constructor-ep/api/v1/static/programs/{program_id}/plan/abit/pdf"
                            logger.info(
                                f"  PDF ссылка сформирована через ID ({program_id}) из JSON: {program_info['study_plan_pdf_link']}")
                        else:
                            logger.warning(
                                f"  ID программы не найден в __NEXT_DATA__ для {url}. PDF ссылка не будет сформирована через API.")

                    # Parsing name
                    name_from_json = props.get('title')
                    if name_from_json:
                        program_info['name'] = name_from_json
                        logger.info(f"  Название программы из JSON: {program_info['name']}")
                    else:
                        logger.info("  Название программы не найдено в JSON.")

                    # Parsing description
                    desc_from_json = props.get('description')
                    if desc_from_json:
                        program_info['description'] = desc_from_json
                        logger.info(f"  Описание программы из JSON найдено.")
                    else:
                        logger.info("  Описание программы не найдено в JSON.")

                    # Parsing institute
                    institute_from_json = props.get('institute', {}).get('title')
                    if institute_from_json:
                        program_info['institute'] = institute_from_json
                        logger.info(f"  Институт из JSON: {program_info['institute']}")
                    else:
                        logger.info("  Институт не найден в JSON.")

                    # Parsing details
                    details = program_info['details']
                    duration_from_json = props.get('duration')
                    if duration_from_json:
                        details['duration'] = duration_from_json
                        logger.info(f"  Длительность из JSON: {details['duration']}")
                    else:
                        logger.info("  Длительность не найдена в JSON.")

                    form_from_json = props.get('format')
                    if form_from_json:
                        details['form_of_study'] = form_from_json
                        logger.info(f"  Форма обучения из JSON: {details['form_of_study']}")
                    else:
                        logger.info("  Форма обучения не найдена в JSON.")

                    cost_from_json = props.get('cost')
                    if cost_from_json is not None:
                        details['contract_cost'] = f"{cost_from_json} руб."
                        logger.info(f"  Стоимость из JSON: {details['contract_cost']}")
                    else:
                        logger.info("  Стоимость не найдена в JSON.")

                    dormitory_from_json = props.get('dormitory')
                    if dormitory_from_json is not None:
                        details['dormitory'] = "Да" if dormitory_from_json else "Нет"
                        logger.info(f"  Общежитие из JSON: {details['dormitory']}")
                    else:
                        logger.info("  Информация об общежитии не найдена в JSON.")

                    military_center_from_json = props.get('military_center')
                    if military_center_from_json is not None:
                        details['military_center'] = "Да" if military_center_from_json else "Нет"
                        logger.info(f"  Военный центр из JSON: {details['military_center']}")
                    else:
                        logger.info("  Информация о военном центре не найдена в JSON.")

                    # Parsing career
                    career_from_json = props.get('career')
                    if career_from_json:
                        career_list = []
                        for item in career_from_json:
                            career_title = item.get('title')
                            career_description = item.get('description')
                            if career_title and career_description:
                                career_list.append(f"{career_title}: {career_description}")
                            elif career_title:
                                career_list.append(career_title)
                        if career_list:
                            program_info['career'] = "\n".join(career_list)
                            logger.info("  Карьера из JSON найдена.")
                        else:
                            program_info['career'] = "Информация о карьере не найдена."
                            logger.info("  Карьера из JSON пуста.")
                    else:
                        logger.info("  Карьера не найдена в JSON.")

                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Ошибка при парсинге JSON из __NEXT_DATA__ для {url}: {e}. Продолжаю парсинг HTML.")
            else:
                logger.warning(f"Скрипт __NEXT_DATA__ не найден для {url}. Продолжаю парсинг HTML.")

            # --- Резервный парсинг HTML для полей, не найденных в JSON или для более детальной информации ---

            # Название программы (если не найдено через JSON)
            if program_info['name'] == "Название программы не найдено.":
                title_tag = soup.find('h1', class_='Information_information__header__fab3I')
                if title_tag:
                    program_info['name'] = title_tag.text.strip()
                    logger.info(f"  Название программы найдено из HTML: {program_info['name']}")
                else:
                    logger.info("  Название программы не найдено ни в JSON, ни в HTML.")

            # Институт (если не найден через JSON)
            if program_info['institute'] == "Институт не найден.":
                institute_card = soup.find('div', class_='Information_card__info__t4fW_')
                if institute_card:
                    institute_h5 = institute_card.find('h5')
                    if institute_h5:
                        program_info['institute'] = institute_h5.text.strip()
                        logger.info(f"  Институт найден из HTML: {program_info['institute']}")
                else:
                    logger.info("  Институт не найден ни в JSON, ни в HTML.")

            # Детальная информация о программе (форма, длительность, стоимость и т.д.)
            detail_headers = {
                'Форма обучения': 'form_of_study',
                'Длительность': 'duration',
                'Стоимость контрактного обучения (год)': 'contract_cost',
                'Общежитие': 'dormitory',
                'Военный учебный центр': 'military_center'
            }
            for header_text, key in detail_headers.items():
                # Проверяем, если данные еще не были получены из JSON или остались в состоянии по умолчанию
                if not program_info['details'].get(key) or \
                        program_info['details'].get(key) in ["Неизвестно", "Неизвестно/год", "Информация уточняется",
                                                             None]:
                    header_tag = soup.find('h5', string=header_text)
                    if header_tag:
                        value_div = header_tag.find_next_sibling('div', class_='Information_card__text__txwcx')
                        if value_div:
                            value = value_div.text.strip()
                            if key == 'contract_cost':
                                cleaned_cost = ''.join(
                                    filter(lambda x: x.isdigit() or x == '.', value.replace('\xa0', '')))
                                if cleaned_cost:
                                    program_info['details'][key] = f"{int(float(cleaned_cost))} руб."
                                else:
                                    program_info['details'][key] = "Неизвестно/год"
                            else:
                                program_info['details'][key] = value
                            logger.info(f"  '{header_text}' найден из HTML: {program_info['details'][key]}")
                        else:
                            logger.info(f"  Значение для '{header_text}' не найдено в HTML.")
                    else:
                        logger.info(f"  Заголовок '{header_text}' не найден в HTML.")

            # Описание программы
            if program_info['description'] == "Информация о программе не найдена.":
                description_div = soup.find('div', class_='Description_description__text__T5U2W')
                if description_div:
                    program_info['description'] = description_div.text.strip()
                    logger.info(f"  Описание программы найдено из HTML.")
                else:
                    logger.info("  Описание программы не найдено ни в JSON, ни в HTML.")

            # Карьера
            if program_info['career'] == "Информация о карьере не найдена." or not props.get('career'):
                career_items = soup.find_all('div', class_='Career_career__item__oP6_1')
                career_list = []
                for item in career_items:
                    header = item.find('h5', class_='Career_career__itemHeader__N7eYd')
                    text = item.find('span', class_='Career_career__itemText__c2q_g')
                    if header and text:
                        career_list.append(f"{header.text.strip()}: {text.text.strip()}")
                    elif header:
                        career_list.append(header.text.strip())
                if career_list:
                    program_info['career'] = "\n".join(career_list)
                    logger.info("  Карьера найдена из HTML.")
                else:
                    logger.info("  Карьера не найдена ни в JSON, ни в HTML.")

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при HTTP запросе к {url}: {e}. Установка error=True.")
            program_info['error'] = True
        except Exception as e:
            logger.error(f"Произошла непредвиденная ошибка при парсинге {url}: {e}. Установка error=True.")
            program_info['error'] = True

        logger.info(
            f"Завершил парсинг данных для программы: {url}. Финальная ссылка на учебный план: {program_info['study_plan_pdf_link']}")
        return program_info

    def is_relevant_question(self, question: str) -> bool:
        """Проверяет, относится ли вопрос к магистратурам ИТМО по ИИ"""
        relevant_keywords = [
            "магистратура", "итмо", "искусственный интеллект", "ии", "ai",
            "поступление", "учебный план", "программа", "обучение",
            "карьера", "работа", "зарплата", "стоимость", "общежитие",
            "экзамен", "направление", "дисциплина", "курс", "предмет",
            "институт", "длительность", "язык", "аккредитация", "менеджер",
            "соцсети", "партнеры", "команда", "достижения", "стипендии",
            "международные возможности", "faq", "вопросы"
        ]

        question_lower = question.lower()
        return any(keyword in question_lower for keyword in relevant_keywords)

    def get_ai_response(self, user_message: str) -> str:
        """Получает ответ от OpenAI API (через OpenRouter)"""
        if not self.is_relevant_question(user_message):
            return ("Извините, я могу отвечать только на вопросы, связанные с магистерскими "
                    "программами ИТМО по искусственному интеллекту. Пожалуйста, задайте вопрос "
                    "об обучении, поступлении или карьерных возможностях в этих программах.")

        # Убедимся, что данные programs_data корректно сериализуются в JSON
        programs_data_safe = {}
        for program_key, data in self.programs_data.items():
            safe_data = data.copy()
            programs_data_safe[program_key] = safe_data

        system_prompt = f"""
        Вы - помощник абитуриента для выбора между двумя магистерскими программами ИТМО:
        1. "Искусственный интеллект"
        2. "Искусственный интеллект в продуктах"

        Используйте следующую информацию о программах для ответа. Если запрошенная информация отсутствует, укажите это.
        Данные о программах:
        {json.dumps(programs_data_safe, ensure_ascii=False, indent=2)}

        Профиль пользователя:
        {json.dumps(self.user_profile, ensure_ascii=False, indent=2)}

        Отвечайте только на вопросы, связанные с этими программами. Будьте полезным, информативным и дружелюбным.
        Если нужна дополнительная информация о пользователе для рекомендаций, задавайте уточняющие вопросы.
        Если пользователь спрашивает про "список курсов" или "учебный план", всегда напоминайте, что точный список в PDF по ссылке.
        """

        messages = [
            {"role": "system", "content": system_prompt},
            *self.conversation_history,
            {"role": "user", "content": user_message}
        ]

        try:
            # Использование нового клиента OpenAI и модели OpenRouter
            completion = self.client.chat.completions.create(
                model="google/gemini-2.0-flash-exp:free",
                # Модель по вашему запросу. Убедитесь в её доступности на OpenRouter.
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )

            ai_response = completion.choices[0].message.content

            # Обновляем историю разговора
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": ai_response})

            # Ограничиваем историю последними 10 сообщениями (5 пар запрос-ответ)
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]

            return ai_response

        except Exception as e:
            logger.error(f"Ошибка при обращении к OpenRouter API: {e}")
            return f"Извините, произошла ошибка при обработке вашего запроса через AI: {str(e)}"

    def update_user_profile(self, key: str, value: str):
        """Обновляет профиль пользователя"""
        self.user_profile[key] = value

    def get_recommendations(self) -> str:
        """Генерирует рекомендации на основе профиля пользователя и спарсенных данных"""
        if not self.user_profile:
            return ("Для получения персональных рекомендаций расскажите о своем опыте: "
                    "образование, опыт работы, интересы в области ИИ.")

        # Убедимся, что данные programs_data корректно сериализуются в JSON
        programs_data_safe = {}
        for program_key, data in self.programs_data.items():
            safe_data = data.copy()
            programs_data_safe[program_key] = safe_data

        system_prompt = f"""
        На основе профиля пользователя и предоставленных данных о программах ИТМО, дайте рекомендации по выбору между программами 
        "Искусственный интеллект" и "Искусственный интеллект в продуктах".

        Профиль пользователя:
        {json.dumps(self.user_profile, ensure_ascii=False, indent=2)}

        Данные о программах:
        {json.dumps(programs_data_safe, ensure_ascii=False, indent=2)}

        Дайте конкретные рекомендации по:
        1. Какая программа больше подходит
        2. Какие аспекты программы стоит изучать (вместо "выборных дисциплин", так как их нет в деталях)
        3. На какие карьерные позиции стоит ориентироваться

        Если информация о курсах отсутствует, упомяните, что полный учебный план доступен по ссылке на сайте программы.
        """

        try:
            completion = self.client.chat.completions.create(
                model="google/gemini-2.0-flash-exp:free",  # Модель по вашему запросу.
                messages=[{"role": "system", "content": system_prompt}],
                max_tokens=800,
                temperature=0.7
            )

            return completion.choices[0].message.content

        except Exception as e:
            logger.error(f"Ошибка при генерации рекомендаций через OpenRouter AI: {e}")
            return f"Ошибка при генерации рекомендаций: {str(e)}"

    def compare_programs(self) -> str:
        """Сравнивает две программы на основе спарсенных данных."""
        ai_prog = self.programs_data.get("ai", {})
        ai_product_prog = self.programs_data.get("ai_product", {})

        response_parts = ["**СРАВНЕНИЕ ПРОГРАММ МАГИСТРАТУРЫ ИТМО:**\n"]

        # Программа "Искусственный интеллект"
        comparison_parts = [
            f"**1. ИСКУССТВЕННЫЙ ИНТЕЛЛЕКТ:**"
        ]
        if ai_prog.get('error'):
            comparison_parts.append("- Информация не загружена из-за ошибки.")
        else:
            comparison_parts.extend([
                f"- Название: {ai_prog.get('name', 'Неизвестно')}",
                f"- Форма: {ai_prog.get('details', {}).get('form_of_study', 'Неизвестно')}, "
                f"Длительность: {ai_prog.get('details', {}).get('duration', 'Неизвестно')}",
                f"- Стоимость: {ai_prog.get('details', {}).get('contract_cost', 'Неизвестно/год')}",
                f"- Общежитие: {ai_prog.get('details', {}).get('dormitory', 'Неизвестно')}",
                f"- Военный центр: {ai_prog.get('details', {}).get('military_center', 'Неизвестно')}",
                f"- Институт: {ai_prog.get('institute', 'Неизвестно')}",
                f"- Описание: {ai_prog.get('description', 'Информация о программе не найдена....')}",
                f"- Карьера: {ai_prog.get('career', 'Информация о карьере не найдена....')}",
                f"- Учебный план: {ai_prog.get('study_plan_pdf_link', 'Ссылка на учебный план не найдена.')}"
            ])
        response_parts.append("\n".join(comparison_parts))

        response_parts.append("\n")  # Добавляем пустую строку для разделения

        # Программа "Искусственный интеллект в продуктах"
        comparison_parts = [
            f"**2. ИСКУССТВЕННЫЙ ИНТЕЛЛЕКТ В ПРОДУКТАХ:**"
        ]
        if ai_product_prog.get('error'):
            comparison_parts.append("- Информация не загружена из-за ошибки.")
        else:
            comparison_parts.extend([
                f"- Название: {ai_product_prog.get('name', 'Управление ИИ-продуктами/AI Product')}",
                f"- Форма: {ai_product_prog.get('details', {}).get('form_of_study', 'Неизвестно')}, "
                f"Длительность: {ai_product_prog.get('details', {}).get('duration', 'Неизвестно')}",
                f"- Стоимость: {ai_product_prog.get('details', {}).get('contract_cost', 'Неизвестно/год')})",
                f"- Общежитие: {ai_product_prog.get('details', {}).get('dormitory', 'Неизвестно')}",
                f"- Военный центр: {ai_product_prog.get('details', {}).get('military_center', 'Неизвестно')}",
                f"- Институт: {ai_product_prog.get('institute', 'Неизвестно')}",
                f"- Описание: {ai_product_prog.get('description', 'Информация о программе не найдена....')}",
                f"- Карьера: {ai_product_prog.get('career', 'Информация о карьере не найдена....')}",
                f"- Учебный план: {ai_product_prog.get('study_plan_pdf_link', 'Ссылка на учебный план не найдена.')}"
            ])
        response_parts.append("\n".join(comparison_parts))

        response_parts.append("\nДля персональных рекомендаций расскажите о своем опыте и целях.")
        return "\n".join(response_parts)

    def get_study_plans_info(self) -> str:
        """Предоставляет информацию об учебных планах программ."""
        ai_prog = self.programs_data.get("ai", {})
        ai_product_prog = self.programs_data.get("ai_product", {})

        response_parts = ["📚 Учебные планы программ:\n"]

        # Искусственный интеллект
        ai_link = ai_prog.get('study_plan_pdf_link', 'Ссылка на учебный план не найдена.')
        ai_duration = ai_prog.get('details', {}).get('duration', 'Информация уточняется')
        ai_form = ai_prog.get('details', {}).get('form_of_study', 'Информация уточняется')

        response_parts.append(f"🔹 Искусственный интеллект:")
        response_parts.append(f"• Ссылка на учебный план: {ai_link}")
        response_parts.append(f"• Продолжительность: {ai_duration}")
        response_parts.append(f"• Форма обучения: {ai_form}\n")

        # Искусственный интеллект в продуктах
        ai_product_link = ai_product_prog.get('study_plan_pdf_link', 'Ссылка на учебный план не найдена.')
        ai_product_duration = ai_product_prog.get('details', {}).get('duration', 'Информация уточняется')
        ai_product_form = ai_product_prog.get('details', {}).get('form_of_study', 'Информация уточняется')

        response_parts.append(f"🔹 Искусственный интеллект в продуктах:")
        response_parts.append(f"• Ссылка на учебный план: {ai_product_link}")
        response_parts.append(f"• Продолжительность: {ai_product_duration}")
        response_parts.append(f"• Форма обучения: {ai_product_form}\n")

        response_parts.append("Для получения актуальных учебных планов обратитесь к официальным источникам.")
        return "\n".join(response_parts)

    def get_cost_info(self) -> str:
        """Предоставляет информацию о стоимости обучения."""
        ai_prog = self.programs_data.get("ai", {})
        ai_product_prog = self.programs_data.get("ai_product", {})

        response_parts = ["💰 Стоимость обучения:\n"]

        ai_cost = ai_prog.get('details', {}).get('contract_cost', 'Информация уточняется')
        response_parts.append(f"🔹 Искусственный интеллект: {ai_cost}/год")

        ai_product_cost = ai_product_prog.get('details', {}).get('contract_cost', 'Информация уточняется')
        response_parts.append(f"🔹 Искусственный интеллект в продуктах: {ai_product_cost}/год\n")

        response_parts.append("Стоимость может меняться. Актуальную информацию уточняйте на официальном сайте.")
        return "\n".join(response_parts)

    def get_dormitory_info(self) -> str:
        """Предоставляет информацию об общежитии."""
        ai_prog = self.programs_data.get("ai", {})
        ai_product_prog = self.programs_data.get("ai_product", {})

        response_parts = ["🏠 Информация об общежитии:\n"]

        ai_dorm = ai_prog.get('details', {}).get('dormitory', 'Информация уточняется')
        response_parts.append(f"🔹 Искусственный интеллект: Доступно общежитие: {ai_dorm}")

        ai_product_dorm = ai_product_prog.get('details', {}).get('dormitory', 'Информация уточняется')
        response_parts.append(f"🔹 Искусственный интеллект в продуктах: Доступно общежитие: {ai_product_dorm}\n")

        response_parts.append("Для получения подробной информации об общежитиях посетите официальный сайт ИТМО.")
        return "\n".join(response_parts)

    def get_career_opportunities(self) -> str:
        """Предоставляет информацию о карьерных возможностях."""
        ai_prog = self.programs_data.get("ai", {})
        ai_product_prog = self.programs_data.get("ai_product", {})

        response_parts = ["🎯 Карьерные возможности:\n"]

        ai_career = ai_prog.get('career', 'Информация о карьере не найдена.')
        response_parts.append(f"🔹 Искусственный интеллект:\n{ai_career}")

        ai_product_career = ai_product_prog.get('career', 'Информация о карьере не найдена.')
        response_parts.append(f"\n🔹 Искусственный интеллект в продуктах:\n{ai_product_career}\n")

        response_parts.append(
            "Для более детальной информации о карьерных путях, пожалуйста, посетите страницы программ на сайте ИТМО.")
        return "\n".join(response_parts)

    def get_personal_recommendations(self, experience: str, goals: str) -> str:
        """
        Предоставляет персональные рекомендации на основе опыта и целей пользователя.
        Это заглушка, требующая интеграции с реальной логикой рекомендаций.
        """
        self.update_user_profile('background', experience)
        self.update_user_profile('goals', goals)

        return self.get_recommendations()