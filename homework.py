import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


class EnvVarIsNoneError(Exception):
    """Кастомная ошибка при отсутствии ожидаемой переменной окружения."""

    pass


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
HEADERS = {'Authorization': f'OAuth { PRACTICUM_TOKEN }'}
ENV_VAR_IS_NONE = 'Отсутствует переменная окружения - {}'
ENDPOINT_IS_NOT_AVAILABLE = 'Эндпоинт недоступен'
STATUS_HOMEWORK_IS_CHANGED = (
    'Изменился статус проверки работы "{homework_name}". {verdict}'
)
STATUS_HOMEWORK_IS_NOT_CHANGED = 'Статус домашней работы не изменился'
UNKNOWN_STATUS_OF_HOMEWORK = 'У домашней работы неизвестный статус: {}'
FAILURE_IN_PROGRAM = 'Сбой в работе программы: {}'
NO_EXPECTED_KEY = 'Отсутствует ожидаемый ключ: {}'
MESSAGE_SENT_SUCCESSFULLY = 'Сообщение отправлено успешно'
ERROR_SENDING_MESSAGE = 'Ошибка при отправке сообщения'
UNSECCESSFUL_STATUS_TO_API = 'Неуспешный статус запроса к API: {}, ошибка: {}'
RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена, в ней нашлись ошибки.'
}


def send_message(bot, message):
    """Отправляет в Telegram сообщение."""
    try:
        bot.send_message(
            chat_id=CHAT_ID,
            text=message
        )
    except telegram.error.TelegramError:
        raise telegram.error.TelegramError(ERROR_SENDING_MESSAGE)


def get_api_answer(url, current_timestamp):
    """Отправляет запрос к API домашки на эндпоинт."""
    payload = {'from_date': current_timestamp}
    response = requests.get(
        url=url, headers=HEADERS, params=payload
    )
    if response.status_code != 200:
        raise requests.exceptions.RequestException(
            ENDPOINT_IS_NOT_AVAILABLE
        )
    response = response.json()
    if 'code' in response or 'error' in response:
        raise requests.exceptions.HTTPError(
            UNSECCESSFUL_STATUS_TO_API.format(response['code'],
                                              response['error'])
        )
    return response


def check_response(response):
    """Проверяет полученный ответ на корректность.
    Проверяет, не изменился ли статус.
    """
    try:
        homework = response.get('homeworks')[0]
    except IndexError:
        raise IndexError(STATUS_HOMEWORK_IS_NOT_CHANGED)
    except KeyError:
        raise KeyError(NO_EXPECTED_KEY.format('homeworks'))
    if homework['status'] not in HOMEWORK_VERDICTS:
        raise KeyError(UNKNOWN_STATUS_OF_HOMEWORK.format(homework['status']))
    return homework


def parse_status(homework):
    """Если статус изменился — анализирует его."""
    try:
        verdict = HOMEWORK_VERDICTS[homework['status']]
    except KeyError:
        raise KeyError(NO_EXPECTED_KEY.format('status'))
    try:
        homework_name = homework.get('homework_name')
    except KeyError:
        raise KeyError(NO_EXPECTED_KEY.format('homework_name'))
    return STATUS_HOMEWORK_IS_CHANGED.format(homework_name=homework_name,
                                             verdict=verdict)


def main(): # noqa: ignore=C901
    """Бот-ассистент в бесконечном цикле выполняет ожидаемые операции."""
    logging.basicConfig(
        level=logging.INFO,
        format=('%(asctime)s [%(levelname)s] %(message)s,'
                ' %(name)s, line %(lineno)d'),
        handlers=[logging.StreamHandler(stream=sys.stdout),
                  logging.FileHandler(filename=__file__ + '.log')]
    )
    ENV_VARS = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'CHAT_ID': CHAT_ID,
    }
    for var in ENV_VARS:
        if ENV_VARS[var] is None:
            raise EnvVarIsNoneError(ENV_VAR_IS_NONE.format(var))
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(ENDPOINT, current_timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)
            logging.info(MESSAGE_SENT_SUCCESSFULLY)
            current_timestamp = response['current_date']
        except EnvVarIsNoneError:
            logging.critical(ENV_VAR_IS_NONE.format(var), exc_info=True)
        except IndexError:
            logging.info(STATUS_HOMEWORK_IS_NOT_CHANGED, exc_info=True)
            send_message(bot, STATUS_HOMEWORK_IS_NOT_CHANGED)
        except telegram.error.TelegramError:
            logging.error(ERROR_SENDING_MESSAGE, exc_info=True)
        except Exception as error:
            logging.error(FAILURE_IN_PROGRAM.format(error), exc_info=True)
            try:
                send_message(bot, FAILURE_IN_PROGRAM.format(error))
            except telegram.error.TelegramError:
                logging.error(ERROR_SENDING_MESSAGE, exc_info=True)
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
