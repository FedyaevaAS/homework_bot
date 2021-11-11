import datetime as dt
import logging
import os
import sys
import time
from http import HTTPStatus
from logging import StreamHandler

import requests
import telegram
from dotenv import load_dotenv

from exceptions import CustomException

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

logging.basicConfig(
    format=log_format,
    level=logging.INFO)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
handler.setFormatter(logging.Formatter(log_format))


RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отпровка сообщений в Telegram чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
    except Exception as error:
        error_message = f'Сбой при отправке сообщения в Telegram: {error}'
        logging.error(error_message)
        raise CustomException(error_message)
    else:
        logging.info(f'Бот отправил сообщение "{message}"')


def get_api_answer(current_timestamp):
    """Отправка запроса к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != HTTPStatus.OK:
        error_message = (f'Эндпоинт {ENDPOINT} недоступен. '
                         f'Код ответа API: {response.status_code}')
        logging.error(error_message)
        raise CustomException(error_message)
    return response.json()


def check_response(response):
    """Проверка ответа API на корректность."""
    homeworks = response['homeworks']
    statuses = list(map(lambda homework: homework.get('status'), homeworks))
    for status in statuses:
        if status not in HOMEWORK_STATUSES:
            logging.error('Статус домашней работы недокументрован')
    return homeworks


def parse_status(homework):
    """Извлечение из информации о конкретной
    домашней работе статус этой работы.
    """
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    variables = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    result = []
    for name, value in variables.items():
        if value is None:
            result.append(False)
            logging.critical('Отсутствует обязательная переменная '
                             f'окружения {name}')
    return False if False in result else True


def main():
    """Основная логика работы бота."""
    if check_tokens() is False:
        exit()
    else:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        current_timestamp = int(time.time())
        last_message = ''
        while True:
            try:
                response = get_api_answer(current_timestamp)
                homeworks = check_response(response)
                if len(homeworks) > 0:
                    last_homework = homeworks[0]
                    status = parse_status(last_homework)
                    send_message(bot, status)
                    time_last_homework_str = last_homework.get('date_updated')
                    current_timestamp = int(
                        dt.datetime.strptime(
                            time_last_homework_str,
                            "%Y-%m-%dT%H:%M:%SZ"
                        ).timestamp()
                    )
                    time.sleep(RETRY_TIME)
                else:
                    logging.debug('Статус домашней работы не изменился')
            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                split_message = message.split('from_date')[0]
                if last_message != split_message:
                    send_message(bot, message)
                last_message = split_message
                print(f'Последнее сообщение: {last_message}')
                logging.error(message)
                time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
