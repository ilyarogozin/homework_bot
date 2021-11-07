import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


class DenialOfServiceError(Exception):
    """Кастомная ошибка при отказе сервера в обслуживании."""

    pass


class EndpointUnexpectedStatusError(Exception):
    """Кастомная ошибка при неожидаемом статусе запроса к эндпоинту."""

    pass


class SendMessageError(Exception):
    """Кастомная ошибка при неотправленном сообщении."""

    pass


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
HEADERS = {'Authorization': f'OAuth { PRACTICUM_TOKEN }'}
MISSING_ENV_VAR = 'Отсутствует переменная окружения - {}'
UNEXPECTED_STATUS_OF_ENDPOINT = ('Неожидаемый статус эндпоинта:\n'
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
NETWORK_FAILURE = ('Произошёл сбой сети: {error}'
                   'url={url}\n'
                   'headers={headers}\n'
                   'params={params}')
DENIAL_OF_SERVICE = ('Отказ в обслуживании:\n'
                     'code={code}\n'
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
    except telegram.error.TelegramError as error:
        raise SendMessageError(ERROR_SENDING_MESSAGE.format(error))
    else:
        logging.info(MESSAGE_SENT_SUCCESSFULLY.format(message))


def get_api_answer(url, current_timestamp):
    """Отправляет запрос к API домашки на эндпоинт."""
    params = dict(url=url, headers=HEADERS,
                  params={'from_date': current_timestamp})
    try:
        response = requests.get(**params)
    except requests.ConnectionError as error:
        raise ConnectionError(NETWORK_FAILURE.format(error=error, **params))
    response_json = response.json()
    if 'code' in response_json or 'error' in response_json:
        raise DenialOfServiceError(
            DENIAL_OF_SERVICE.format(code=response_json['code'],
                                     error=response_json['error'],
                                     **params)
        )
    status = response.status_code
    if status != 200:
        raise EndpointUnexpectedStatusError(
            UNEXPECTED_STATUS_OF_ENDPOINT.format(status=status, **params)
        )
    return response_json


def check_response(response):
    """Проверяет наличие домашней работы и корректность её статуса.
    Возвращает домашнюю работу, если статус изменился.
    """
    homework = response['homeworks'][0]
    status = homework['status']
    if status not in VERDICTS:
        raise ValueError(UNKNOWN_STATUS.format(status))
    return homework


def parse_status(homework):
    """Если статус изменился - возвращает сообщение.
    В сообщении имя и вердикт работы.
    """
    return STATUS_IS_CHANGED.format(homework_name=homework['homework_name'],
                                    verdict=VERDICTS[homework['status']])


def main():
    """Бот-ассистент в бесконечном цикле выполняет ожидаемые операции."""
    for name in ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'CHAT_ID'):
        if globals()[name] is None:
            logging.critical(MISSING_ENV_VAR.format(name))
            raise NameError(MISSING_ENV_VAR.format(name))
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(ENDPOINT, timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            send_message(bot, message)
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            logging.exception(FAILURE_IN_PROGRAM.format(error))
            send_message(bot, FAILURE_IN_PROGRAM.format(error))
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format=('%(asctime)s [%(levelname)s] %(name)s,'
                ' line %(lineno)d, %(message)s,'),
        handlers=[logging.StreamHandler(stream=sys.stdout),
                  logging.FileHandler(filename=__file__ + '.log')]
    )
    main()
