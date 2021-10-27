import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
import telegram.ext
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s, %(name)s',
    handlers=[logging.StreamHandler(stream=sys.stdout)]
)

try:
    PRACTICUM_TOKEN = os.environ['PRACTICUM_TOKEN']
    TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
    CHAT_ID = os.environ['TELEGRAM_CHAT_ID']
except Exception:
    message = 'Отсутствуют одна или более переменные окружения'
    logging.critical(message)
    raise SystemExit(message)
BOT = telegram.Bot(token=TELEGRAM_TOKEN)
RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
try:
    requests.get(url=ENDPOINT)
except Exception:
    message = 'Эндпоинт недоступен'
    logging.error(message)
    raise SystemExit(message)
HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена, в ней нашлись ошибки.'
}


def send_message(bot, message):
    """Отправляет в Telegram сообщение."""
    bot.send_message(
        chat_id=CHAT_ID,
        text=message
    )


def get_api_answer(url, current_timestamp):
    """Отправляет запрос к API домашки на эндпоинт."""
    headers = {'Authorization': f'OAuth { PRACTICUM_TOKEN }'}
    payload = {'from_date': current_timestamp}
    response = requests.get(url=url, headers=headers, params=payload)
    if response.status_code != HTTPStatus.OK:
        message = f'Статус запроса к API - {response.status_code}'
        logging.error(message)
        raise Exception(message)
    return response.json()


def parse_status(homework):
    """Если статус изменился — анализирует его."""
    try:
        verdict = HOMEWORK_STATUSES[homework['status']]
        homework_name = homework['homework_name']
    except TypeError:
        message = 'Отсутствуют ожидаемые ключи'
        logging.error(message)
        return send_message(BOT, message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_response(response):
    """Проверяет полученный ответ на корректность.
    Проверяет, не изменился ли статус.
    """
    try:
        homework = response.get('homeworks')[0]
    except IndexError as error:
        logging.error(f'Пустой список: {error}')
        message = 'Ни у одной из домашних работ не появился новый статус'
        return send_message(BOT, message)
    except KeyError:
        message = 'Отсутствует ожидаемый ключ: "homeworks"'
        logging.error(message)
        return send_message(BOT, message)

    if homework['status'] not in HOMEWORK_STATUSES:
        message = f'У домашней работы неизвестный статус: {homework["status"]}'
        logging.error(message)
        send_message(BOT, message)
        raise Exception(message)
    return homework


def main():
    """Бот-ассистент в бесконечном цикле выполняет ожидаемые операции."""
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(ENDPOINT, current_timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            try:
                send_message(BOT, message)
                logging.info('Сообщение отправлено успешно')
            except Exception:
                message = 'Сбой при отправке сообщения'
                logging.error(message)
                send_message(BOT, message)
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(BOT, message)
            time.sleep(RETRY_TIME)
            continue


if __name__ == '__main__':
    main()
