from typing import Union, Dict, Any
from configparser import ConfigParser
from pathlib import Path
from operator import itemgetter
from datetime import datetime

import requests


class TestBot:
    BASE_URL = 'https://api.telegram.org'

    def __init__(self, token: str) -> None:
        self.token = token
        self.base_url = f'{self.BASE_URL}/bot{token}'

    def _get_offset(self, chat_id: Union[str, int]) -> int:
        get_update_id = itemgetter('update_id')
        current_update = self.get_updates(timeout=3)

        print('current update', current_update)

        update_ids = list(map(get_update_id, current_update['result']))

        if len(update_ids) > 0:
            offset = max(update_ids) + 1
        else:
            offset = 0

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
            # 'allowed_updates': ['callback_query'],
            'timeout': timeout,
            'offset': offset
        }
        response = requests.post(
            f'{self.base_url}/getUpdates', json=payload, timeout=5
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
                                reporter_name='labdmitriy')
print('message response')
print(msg_response)

print('offset')
print(bot.offset)

update_response = bot.get_updates(offset=bot.offset, timeout=3)
print('update response')
print(update_response)

# db_record = filter(lambda x: x)
result = update_response['result']

if len(result) > 0:
    callback_query = result[0]['callback_query']
    db_record = {}
    db_record['chat_id'] = TEST_CHAT_ID
    db_record['username'] = callback_query['from']['id']
    db_record['trigerred_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db_record['event_type'] = 'click'
    db_record['reporter_name'] = callback_query['data']
    print(db_record)
