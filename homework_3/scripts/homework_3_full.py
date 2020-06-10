import json
from typing import Union, Dict, List
from operator import itemgetter
from collections import defaultdict
from datetime import datetime

import requests

from airflow import DAG
from airflow.operators import BaseOperator
from airflow.operators.sensors import BaseSensorOperator
from airflow.utils.decorators import apply_defaults
from airflow.utils.dates import days_ago
from airflow.models import Variable


class TelegramBot:
    BASE_URL = 'https://api.telegram.org'
    STATE_FILE_PATH = '/home/jupyter/data/message_state.json'
    CALLBACK_FILE_PATH = '/home/jupyter/data/callback_data.json'

    def __init__(self, token: str) -> None:
        self.token = token
        self.base_url = f'{self.BASE_URL}/bot{token}'

    def _save_message_state(self, message_id: int) -> None:
        get_update_id = itemgetter('update_id')
        current_updates = self.get_updates()

        print('current update', current_updates)
        update_ids = list(map(get_update_id, current_updates['result']))

        if len(update_ids) > 0:
            offset = max(update_ids) + 1
        else:
            offset = 0

        print('offset', offset)

        message_state = {}
        message_state['message_id'] = message_id
        message_state['offset'] = offset

        with open(self.STATE_FILE_PATH, 'w') as f:
            f.write(json.dumps(message_state))

    def _load_message_state(self) -> Dict:
        try:
            with open(self.STATE_FILE_PATH, 'r') as f:
                message_state = json.loads(f.read())
        except FileNotFoundError:
            message_state = {}
            message_state['message_id'] = 0
            message_state['offset'] = 0

        return message_state

    def save_callback_query(self, callback_query: Dict) -> None:
        callback_query['timestamp'] = datetime.now().isoformat()
        with open(self.CALLBACK_FILE_PATH, 'w') as f:
            f.write(json.dumps(callback_query))

    def load_callback_query(self) -> Dict:
        with open(self.CALLBACK_FILE_PATH, 'r') as f:
            callback_query = json.loads(f.read())
        return callback_query

    def send_message(
        self,
        chat_id: Union[str, int],
        message_text: str,
        include_button: bool = False,
        button_text: str = '',
        reporter_name: str = '',
        parse_mode: str = 'Markdown',
        disable_notification: bool = True,
    ) -> Dict:

        payload: Dict = {
            'chat_id': chat_id,
            'text': message_text,
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
        print(response)

        message_info = response.json()
        message_id = message_info['result']['message_id']
        self._save_message_state(message_id)

        return response.json()

    def get_updates(self, offset: int = 0, timeout: int = 0,
                    allowed_updates: Union[List, None] = None) -> Dict:
        payload: Dict = {
            'timeout': timeout,
            'offset': offset,
        }

        if allowed_updates is None:
            payload['allowed_updates'] = json.dumps([])
        else:
            payload['allowed_updates'] = json.dumps(allowed_updates)

        print('payload', payload)

        response = requests.post(
            f'{self.base_url}/getUpdates', json=payload, timeout=5
        )
        return response.json()

    def answer_callback(self, callback_query_id: str) -> Dict:
        payload: Dict = {
            'callback_query_id': callback_query_id
        }
        response = requests.post(
            f'{self.base_url}/answerCallbackQuery', json=payload, timeout=5
        )
        return response.json()

    def edit_message(self, chat_id: str, message_id: str,
                     reply_markup: Dict, message_text: str = '') -> Dict:
        payload: Dict = {
            'chat_id': chat_id,
            'message_id': message_id,
            'reply_markup': reply_markup
        }

        if message_text:
            payload['text'] = message_text

        response = requests.post(
            f'{self.base_url}/editMessageText', json=payload, timeout=5
        )
        return response.json()


class TelegramSendMessageOperator(BaseOperator):
    @apply_defaults
    def __init__(self, token: str, chat_id: Union[str, int], message_text: str,
                 include_button: bool, button_text: str, reporter_name: str,
                 *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.telegram_bot = TelegramBot(token)
        self.chat_id = chat_id
        self.message_text = message_text
        self.include_button = include_button
        self.button_text = button_text
        self.reporter_name = reporter_name

    def execute(self, context) -> None:
        message_info = self.telegram_bot.send_message(
            chat_id=self.chat_id,
            message_text=self.message_text,
            include_button=self.include_button,
            button_text=self.button_text,
            reporter_name=self.reporter_name
        )
        print(message_info)
        return


class TelegramActionsIncrementSensor(BaseSensorOperator):
    @apply_defaults
    def __init__(self, token: str, allowed_updates: Union[List, None] = None,
                 answer_text: str = '',
                 *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.telegram_bot = TelegramBot(token)
        self.message_state = self.telegram_bot._load_message_state()
        self.allowed_updates = allowed_updates
        self.answer_text = answer_text

    def _get_message_id(self, update: Dict) -> int:
        return update['callback_query']['message']['message_id']

    def poke(self, context: Dict) -> bool:
        offset = self.message_state['offset']
        updates = self.telegram_bot.get_updates(
            offset=offset,
            timeout=3,
            allowed_updates=self.allowed_updates
        )

        result = updates['result']
        message_id = self.message_state['message_id']
        message_update = [update for update in result
                          if self._get_message_id(update) == message_id]
        print(message_update)

        if len(message_update) > 0:
            callback_query = message_update[0]['callback_query']
            chat_id = callback_query['message']['chat']['id']

            reply_markup: Dict = {'inline_keyboard': [[]]}
            self.telegram_bot.edit_message(chat_id, message_id,
                                           reply_markup, self.answer_text)

            callback_query_id = callback_query['id']
            self.telegram_bot.answer_callback(callback_query_id)
            self.telegram_bot.save_callback_query(callback_query)

            return True

        return False


class TelegramEventSaveOperator(BaseOperator):
    @apply_defaults
    def __init__(self, token: str, airtable_url: str, airtable_api_key: str,
                 event_type: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.telegram_bot = TelegramBot(token)
        self.airtable_url = airtable_url
        self.airtable_api_key = airtable_api_key
        self.event_type = event_type

    def _generate_db_record(self, callback_query: Dict) -> Dict:
        data: Dict[str, Dict] = defaultdict(dict)
        fields = {
            'chat_id': str(callback_query['message']['chat']['id']),
            'username': str(callback_query['from']['username']),
            'triggered_at': callback_query['timestamp'],
            'event_type': self.event_type,
            'reporter_name': callback_query['data']
        }

        data['fields'] = fields

        db_record: Dict = {}
        db_record['records'] = []
        db_record['records'].append(dict(data))
        print(db_record)

        return db_record

    def _save_db_record(self, db_record: Dict) -> None:
        headers = {
            'Authorization': f'Bearer {self.airtable_api_key}'
        }

        requests.post(self.airtable_url, json=db_record, headers=headers)

    def execute(self, context) -> None:
        callback_query = self.telegram_bot.load_callback_query()
        db_record = self._generate_db_record(callback_query)
        self._save_db_record(db_record)


default_args = {
    'start_date': days_ago(1)
}

dag = DAG(
    dag_id='homework_3',
    schedule_interval='@once',
    default_args=default_args,
    catchup=False
)

send_message = TelegramSendMessageOperator(
    token=Variable.get('HW3_TELEGRAM_BOT_TOKEN'),
    chat_id=Variable.get('HW3_TELEGRAM_CHAT_ID'),
    message_text='Привет',
    include_button=True,
    button_text='Поехали',
    reporter_name='labdmitriy_airflow_app',
    task_id='send_message',
    dag=dag
)

wait_for_clicks = TelegramActionsIncrementSensor(
    token=Variable.get('HW3_TELEGRAM_BOT_TOKEN'),
    allowed_updates=['callback_query'],
    answer_text='Спасибо',
    task_id='wait_for_clicks',
    poke_interval=1,
    dag=dag
)

save_clicks_data = TelegramEventSaveOperator(
    token=Variable.get('HW3_TELEGRAM_BOT_TOKEN'),
    airtable_url=Variable.get('HW3_AIRTABLE_URL'),
    airtable_api_key=Variable.get('HW3_AIRTABLE_API_KEY'),
    event_type='user_click',
    task_id='save_clicks_data',
    dag=dag
)

send_message >> wait_for_clicks >> save_clicks_data
