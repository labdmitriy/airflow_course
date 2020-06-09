from typing import Union, Dict, Any
from configparser import ConfigParser

import requests


class TestBot:
    BASE_URL = 'https://api.telegram.org'

    def __init__(self, token: str) -> None:
        self.token = token
        self.base_url = f'{self.BASE_URL}/bot{token}'

    def send_message(
        self,
        chat_id: Union[str, int],
        text: str,
        include_button: bool = False,
        button_text: str = '',
        parse_mode: str = 'Markdown',
        disable_notification: bool = True,
    ) -> Dict:

        payload: Dict[str, Any] = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_notification': disable_notification
        }

        if include_button:
            go_button = {
                'text': button_text,
                'callback_data': 'callback data'
            }
            go_keyboard = {'inline_keyboard': [[go_button]]}
            payload['reply_markup'] = go_keyboard

        print(payload)

        response = requests.post(
            f'{self.base_url}/sendMessage', json=payload, timeout=3
        )
        return response.json()

    def get_updates(self) -> Dict:
        payload = {
            'allowed_updates': ['callback_query'],
            # 'limit': 2
        }
        response = requests.post(
            f'{self.base_url}/getUpdates', json=payload, timeout=3
        )
        return response.json()


config = ConfigParser()
config.read('./config/config.ini')

TEST_TOKEN = config['default']['TEST_TOKEN']
TEST_CHAT_ID = config['default']['TEST_CHAT_ID']

bot = TestBot(token=TEST_TOKEN)
msg_response = bot.send_message(TEST_CHAT_ID, text='Привет',
                                include_button=True, button_text='Поехали')
print('message response')
print(msg_response)

update_response = bot.get_updates()
print('update response')
print(update_response)
