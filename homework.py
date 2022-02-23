import os
import sys
import requests
import logging
import telegram
import time
from exceptions import APIstatusCodeNot200
from logging import StreamHandler
from dotenv import load_dotenv

load_dotenv(override=True)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

LAST_MESSAGE = ''

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - [%(levelname)s] - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def sleeping():
    """Ожидать "RETRY_TIME" секунд."""
    time.sleep(RETRY_TIME)


def last_error_message(message):
    """Исключение повторной отправки одинаковых сообщений об ошибках."""
    if message == LAST_MESSAGE:
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение через Бота Telegram."""
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logger.info('Cообщение в Telegram было отправлено')
    global LAST_MESSAGE
    LAST_MESSAGE = message


def get_api_answer(current_timestamp):
    """Запрос к ENDPOINT API-Яндекс.Практикум.Домашка."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    # Проверяем что ENDPOINT по параметрам доступен
    request = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if request.status_code != 200:
        if isinstance(request.json(), dict):
            api_ya_answer = request.json().get('message')
            logger.warning(f'Ответ API Яндекс: {api_ya_answer}')
        err_msg = f'Код запроса не 200 и равен: {request.status_code}.'
        raise APIstatusCodeNot200(err_msg)
    else:
        return request.json()


def check_response(response):
    """Проверяет корректность ответа API и возвращает список домашних работ."""
    # Если есть, извлекаем содержимое словаря по ключу 'homeworks'
    if not isinstance(response, dict):
        raise TypeError('Ответ API не словарь')
    check_list_homeworks = response.get('homeworks')
    if check_list_homeworks is None:
        raise KeyError('Ключ "homeworks" не доступен')
    if not isinstance(check_list_homeworks, list):
        raise TypeError('Ответ API  оключу "homeworks" не список')
    # В ответе API отсутствуют статусы Д\З
    if check_list_homeworks != []:
        return check_list_homeworks
    else:
        logger.debug('В текущей проверке новые статусы ДЗ отсутсвуют')


def parse_status(homework):
    """Извлекает из информации о конкретном ДЗ его статус."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    # Проверяем что переменные не пусты
    if (PRACTICUM_TOKEN is None
            or TELEGRAM_TOKEN is None or TELEGRAM_CHAT_ID is None):
        return False
    return True


def main():
    """Основная логика работы бота."""
    # Нотификация запуска
    logger.info('Вы запустили Бота')
    # Проверяем наличие переменных окружения
    if check_tokens() is False:
        er_txt = (
            'Обязательные переменные окружения отсутствуют. '
            'Принудительная остановка Бота'
        )
        logger.critical(er_txt)
        return None
    # Инициализация
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    # Проверка статуса домашней работы с определенной переодичностью
    while True:
        try:
            # Делаем запрос
            response = get_api_answer(current_timestamp)
            # Если запрос ожидаемый словарь, бывший json:
            if isinstance(response, dict):
                check_response_hw = check_response(response)
                if isinstance(check_response_hw, list):
                    for hw in check_response_hw:
                        if isinstance(response, dict):
                            # Извлекаем статус домашки
                            message = parse_status(hw)
                            send_message(bot, message)
                        else:
                            logger.error('Домашняя работа не словарь')
            else:
                logger.error('Ответ API.Ya не корректен')
            # Берем дату из запроса для следующей провекри статусов ДЗ
            current_timestamp = response.get('current_date')
            # Спим после итерации
            sleeping()
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if last_error_message(message):
                send_message(bot, message)
            sleeping()


if __name__ == '__main__':
    main()
