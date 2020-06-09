from typing import Union, Dict

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
        parse_mode: str = 'Markdown',
        disable_notification: bool = True,
    ) -> Dict:
        go_button = {
            'text': 'Поехали',
            'callback_data': 'Приехали'
        }
        go_keyboard = {'inline_keyboard': [[go_button]]}

        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode,
            'disable_notification': disable_notification,
            'reply_markup': go_keyboard
        }

        response = requests.post(
            f'{self.base_url}/sendMessage', json=payload, timeout=3
        )
        return response.json()

    def get_updates(self) -> Dict:
        payload = {
            'timeout': 1,
            'allowed_updates': ['callback_query']
        }
        response = requests.post(
            f'{self.base_url}/getUpdates', json=payload, timeout=3
        )
        return response.json()


TEST_TOKEN = '1225243566:AAENZYHtb0agjuliYHymI2-VzOKqiZh8q9k'
TEST_CHAT_ID = '381731749'

bot = TestBot(token=TEST_TOKEN)
msg_response = bot.send_message(TEST_CHAT_ID, 'Hello')
print('message response')
print(msg_response)

update_response = bot.get_updates()
print('update response')
print(update_response)
