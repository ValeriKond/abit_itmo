import requests
from bs4 import BeautifulSoup
import re
import os


def parse_program_data(url):
    data = {
        "name": None,
        "form": None,
        "duration": None,
        "cost": None,
        "dormitory": None,
        "military_center": None,
        "directions": [],
        "description": None,
        "career_positions": [],
        "salary_range": None,
        "academic_plan_path": None
    }

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Название программы
        name_tag = soup.find('h1')
        if name_tag:
            data['name'] = name_tag.get_text(strip=True)

        all_text = soup.get_text()

        # Форма обучения
        if 'очная' in all_text.lower():
            data['form'] = 'Очная'
        elif 'заочная' in all_text.lower():
            data['form'] = 'Заочная'

        # Длительность
        duration_match = re.search(r'(\d+)\s*год', all_text, re.IGNORECASE)
        if duration_match:
            years = duration_match.group(1)
            data['duration'] = f"{years} года" if years == '2' else f"{years} лет"

        # Стоимость
        cost_match = re.search(r'(\d+\s*\d*\s*\d*)\s*₽', all_text)
        if cost_match:
            data['cost'] = cost_match.group(1).replace(' ', '') + ' ₽'

        # Общежитие и военный центр
        if 'общежитие' in all_text.lower() and 'да' in all_text.lower():
            data['dormitory'] = True
        if 'военный' in all_text.lower() and 'центр' in all_text.lower() and 'да' in all_text.lower():
            data['military_center'] = True

        # Направления подготовки
        direction_codes = re.findall(r'(\d{2}\.\d{2}\.\d{2})', all_text)
        for code in direction_codes:
            if {"code": code} not in data['directions']:
                data['directions'].append({"code": code})

        # Описание программы - ищем первый большой абзац
        paragraphs = soup.find_all('p')
        for p in paragraphs:
            text = p.get_text(strip=True)
            if len(text) > 100 and (
                    'программ' in text.lower() or 'обучени' in text.lower() or 'магистр' in text.lower()):
                data['description'] = text[:500] + '...' if len(text) > 500 else text
                break

        # Карьерные позиции
        career_keywords = ['engineer', 'analyst', 'developer', 'инженер', 'аналитик', 'разработчик']
        for keyword in career_keywords:
            if keyword.lower() in all_text.lower():
                pattern = rf'([A-Za-zА-Яа-я\s]*{keyword}[A-Za-zА-Яа-я\s]*)'
                matches = re.findall(pattern, all_text, re.IGNORECASE)
                for match in matches[:3]:
                    clean_match = re.sub(r'[^\w\s]', '', match).strip()
                    if len(clean_match) > 5 and clean_match not in data['career_positions']:
                        data['career_positions'].append(clean_match)

        # Зарплата
        salary_match = re.search(r'(\d+\s*\d*\s*до\s*\d+\s*\d*\s*рублей)', all_text, re.IGNORECASE)
        if salary_match:
            data['salary_range'] = salary_match.group(1)

        # Получаем programId из скриптов
        program_id = None
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'programId' in script.string:
                match = re.search(r'programId\s*[:=]\s*(\d+)', script.string)
                if match:
                    program_id = match.group(1)
                    break

        if program_id:
            pdf_url = f'https://api.itmo.su/constructor-ep/api/v1/static/programs/{program_id}/plan/abit/pdf'
            # Скачиваем PDF
            pdf_response = requests.get(pdf_url, headers=headers)
            if pdf_response.status_code == 200:
                filename = f"{program_id}-abit.pdf"
                with open(filename, 'wb') as f:
                    f.write(pdf_response.content)
                data['academic_plan_path'] = os.path.abspath(filename)
            else:
                data['academic_plan_path'] = f"Не удалось скачать PDF, статус: {pdf_response.status_code}"
        else:
            data['academic_plan_path'] = "programId не найден"

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при доступе к сайту {url}: {e}")
    except Exception as e:
        print(f"Произошла ошибка при парсинге {url}: {e}")

    return data


if __name__ == "__main__":
    urls = [
        "https://abit.itmo.ru/program/master/ai",
        "https://abit.itmo.ru/program/master/ai_product"
    ]

    for url in urls:
        print(f"Парсинг: {url}")
        data = parse_program_data(url)
        for key, value in data.items():
            print(f"{key}: {value}")
        print("\n" + "-" * 60 + "\n")
