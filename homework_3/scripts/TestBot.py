from typing import Union, Dict, Any
from configparser import ConfigParser
from pathlib import Path
from operator import itemgetter
from datetime import datetime
import json
from collections import defaultdict

import requests


class TestBot:
    BASE_URL = 'https://api.telegram.org'
    OFFSET_FILE_PATH = Path('/home/jupyter/data/bot_offset')

    def __init__(self, token: str) -> None:
        self.token = token
        self.base_url = f'{self.BASE_URL}/bot{token}'

    def _get_offset(self, chat_id: Union[str, int]) -> int:
        get_update_id = itemgetter('update_id')
        current_update = self.get_updates()

        print('current update', current_update)

        # chat_updates = list(filter(lambda x: ))
        update_ids = list(map(get_update_id, current_update['result']))

        if len(update_ids) > 0:
            offset = max(update_ids) + 1
        else:
            offset = 0

        # with open(self.OFFSET_FILE_PATH, 'w') as f:
        #     f.write(str(offset))

        print(offset)
        return offset

    def send_message(
        self,
        chat_id: Union[str, int],
        text: str,
        include_button: bool = False,
        button_text: str = '',
        reporter_name: str = '',
        parse_mode: str = 'Markdown',
        disable_notification: bool = True,
    ) -> Dict:

        self.offset = self._get_offset(chat_id)

        payload: Dict[str, Any] = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_notification': disable_notification
        }

        if include_button:
            go_button = {
                'text': button_text,
                'callback_data': reporter_name
            }
            go_keyboard = {'inline_keyboard': [[go_button]]}
            payload['reply_markup'] = go_keyboard

        response = requests.post(
            f'{self.base_url}/sendMessage', json=payload, timeout=5
        )
        return response.json()

    def get_updates(self, offset: int = 0, timeout: int = 0) -> Dict:
        payload = {
            'allowed_updates': json.dumps(['callback_query']),
            'timeout': timeout,
            'offset': offset
        }
        response = requests.post(
            f'{self.base_url}/getUpdates', json=payload, timeout=5
        )
        return response.json()

    def answer_callback(self, callback_query_id: str) -> Dict:
        payload = {
            'callback_query_id': callback_query_id
        }
        response = requests.post(
            f'{self.base_url}/answerCallbackQuery', json=payload, timeout=5
        )
        return response.json()

    def edit_message(self, chat_id: str, message_id: str, 
                     message_text: str, reply_markup: Dict) -> Dict:
        payload: Dict[str, Any] = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': message_text,
            'reply_markup': reply_markup
        }
        response = requests.post(
            f'{self.base_url}/editMessageText', json=payload, timeout=5
        )
        return response.json()


CONFIG_PATH = Path(__file__).parent.absolute()/Path('../config')

config = ConfigParser()
config.read(CONFIG_PATH/'config.ini')

TEST_TOKEN = config['DEFAULT']['test_token']
TEST_CHAT_ID = config['DEFAULT']['test_chat_id']

bot = TestBot(token=TEST_TOKEN)
msg_response = bot.send_message(TEST_CHAT_ID, text='Привет',
                                include_button=True, button_text='Поехали',
                                reporter_name='labdmitriy_airflow_app')
print('message response')
print(msg_response)

print('offset')
print(bot.offset)

update_response = bot.get_updates(offset=bot.offset, timeout=3)
print('update response')
print(update_response)

result = update_response['result']

if len(result) > 0:
    callback_query = result[0]['callback_query']
    
    chat_id = callback_query['message']['chat']['id']
    message_id = callback_query['message']['message_id']

    reply_markup: Dict = {'inline_keyboard': [[]]}
    message_text = 'Спасибо'
    print(bot.edit_message(chat_id, message_id, message_text, reply_markup))

    callback_query_id = callback_query['id']
    print(bot.answer_callback(callback_query_id))

    db_record: Dict[str, Dict] = defaultdict(dict)
    # db_record = filter(lambda x: x)
    db_record['fields']['chat_id'] = str(callback_query['message']['chat']['id'])
    db_record['fields']['username'] = str(callback_query['from']['username'])
    db_record['fields']['triggered_at'] = datetime.now().isoformat()
    db_record['fields']['event_type'] = 'user_click'
    db_record['fields']['reporter_name'] = callback_query['data']
    print(db_record)

    data = defaultdict(list)
    data['records'].append(dict(db_record))

    print(dict(data))


    # print(headers)

    AIRTABLE_URL = config['DEFAULT']['airtable_url']
    AIRTABLE_API_KEY = config['DEFAULT']['airtable_api_key']
    # print(AIRTABLE_URL, AIRTABLE_API_KEY)

    headers = {
        'Authorization': f'Bearer {AIRTABLE_API_KEY}'
    }

    response = requests.post(AIRTABLE_URL, json=dict(data), headers=headers)
    response.raise_for_status()
    print(response.json())