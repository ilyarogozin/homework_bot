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


class UnexpectedAcceptedValueError(Exception):
    """Кастомная ошибка при неожиданном принятом значении."""

    pass


class DenialOfServiceError(Exception):
    """Кастомная ошибка при отказе сервера в обслуживании."""

    pass


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
HEADERS = {'Authorization': f'OAuth { PRACTICUM_TOKEN }'}
ENV_VAR_IS_NONE = 'Отсутствует переменная окружения - {}'
ENDPOINT_REQUEST_ERROR = ('Ошибка запроса к эндпоинту:\n'
                          'status={status}\n'
                          'url={url}\n'
                          'headers={headers}\n'
                          'params={params}')
STATUS_IS_CHANGED = (
    'Изменился статус проверки работы "{homework_name}". {verdict}'
)
UNKNOWN_STATUS = 'У домашней работы неизвестный статус: {}'
FAILURE_IN_PROGRAM = 'Сбой в работе программы: {}'
MESSAGE_SENT_SUCCESSFULLY = 'Сообщение "{}" отправлено успешно'
ERROR_SENDING_MESSAGE = 'Ошибка при отправке сообщения: {}'
UNSECCESSFUL_REQUEST_TO_API = ('Неуспешный запрос к API:\n'
                               'status={status}\n'
                               'error={error}\n'
                               'url={url}\n'
                               'headers={headers}\n'
                               'params={params}')
RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
VERDICTS = {
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
    except telegram.error.TelegramError as e:
        raise telegram.error.TelegramError(ERROR_SENDING_MESSAGE.format(e))
    else:
        logging.info(MESSAGE_SENT_SUCCESSFULLY.format(message))


def get_api_answer(url, current_timestamp):
    """Отправляет запрос к API домашки на эндпоинт."""
    payload = {'from_date': current_timestamp}
    params = dict(url=url, headers=HEADERS, params=payload)
    try:
        response = requests.get(**params)
    except ConnectionError as e:
        logging.exception(e)
    response_json = response.json()
    if 'code' in response_json or 'error' in response_json:
        raise DenialOfServiceError(
            UNSECCESSFUL_REQUEST_TO_API.format(status=response_json['code'],
                                               error=response_json['error'],
                                               **params)
        )
    status = response.status_code
    if status != 200:
        raise ConnectionError(
            ENDPOINT_REQUEST_ERROR.format(status=status, **params)
        )
    return response_json


def check_response(response):
    """Проверяет полученный ответ на корректность.
    Проверяет, не изменился ли статус.
    """
    homework = response['homeworks'][0]
    status = homework['status']
    if status not in VERDICTS:
        raise UnexpectedAcceptedValueError(UNKNOWN_STATUS.format(status))
    return homework


def parse_status(homework):
    """Если статус изменился — анализирует его."""
    verdict = VERDICTS[homework['status']]
    homework_name = homework['homework_name']
    return STATUS_IS_CHANGED.format(homework_name=homework_name,
                                    verdict=verdict)


def main():
    """Бот-ассистент в бесконечном цикле выполняет ожидаемые операции."""
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
            current_timestamp = (response.get('current_date')
                                 or int(time.time()))
        except Exception as e:
            logging.exception(FAILURE_IN_PROGRAM.format(e))
            send_message(bot, FAILURE_IN_PROGRAM.format(e))
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format=('%(asctime)s [%(levelname)s] %(message)s,'
                ' %(name)s, line %(lineno)d'),
        handlers=[logging.StreamHandler(stream=sys.stdout),
                  logging.FileHandler(filename=__file__ + '.log')]
    )
    main()
