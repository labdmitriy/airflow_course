from airflow import DAG
from airflow.utils.dates import days_ago
from airflow.models import Variable

from telegram_interactions.operators import (
    TelegramSendMessageOperator,
    TelegramEventSaveOperator
)

from telegram_interactions.sensors import (
    TelegramActionsIncrementSensor
)

default_args = {
    'start_date': days_ago(1)
}

dag = DAG(
    dag_id='homework_3_test',
    schedule_interval='@once',
    default_args=default_args,
    catchup=False
)

send_message = TelegramSendMessageOperator(
    token=Variable.get('HW3_TELEGRAM_BOT_TOKEN_TEST'),
    chat_id=Variable.get('HW3_TELEGRAM_CHAT_ID_TEST'),
    message_text='Привет',
    include_button=True,
    button_text='Поехали',
    reporter_name='labdmitriy_airflow_app',
    task_id='send_message',
    dag=dag
)

wait_for_clicks = TelegramActionsIncrementSensor(
    token=Variable.get('HW3_TELEGRAM_BOT_TOKEN_TEST'),
    allowed_updates=['callback_query'],
    answer_text='Спасибо',
    task_id='wait_for_clicks',
    poke_interval=1,
    dag=dag
)

save_clicks_data = TelegramEventSaveOperator(
    token=Variable.get('HW3_TELEGRAM_BOT_TOKEN_TEST'),
    airtable_url=Variable.get('HW3_AIRTABLE_URL_TEST'),
    airtable_api_key=Variable.get('HW3_AIRTABLE_API_KEY_TEST'),
    event_type='user_click',
    task_id='save_clicks_data',
    dag=dag
)

send_message >> wait_for_clicks >> save_clicks_data
