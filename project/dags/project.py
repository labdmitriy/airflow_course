import json
import sys
from pathlib import Path
from typing import Dict, List

from airflow import DAG
from airflow.models import Variable
from airflow.utils.dates import days_ago
from airflow.operators.python_operator import PythonOperator

from merch.operators import TemplatedPythonOperator
sys.path.insert(1, '/home/jupyter/lib/telegram_interactions')
from telegram_interactions.bot import TelegramBot
sys.path.insert(1, '/home/jupyter/lib/scrape')
from scrape.parsers import get_domain_counts
from scrape.sheets import GoogleSheet
from scrape.validators import URLValidator
from scrape.reporters import calculate_processing_stats, generate_report


DATA_SOURCES = Variable.get('project_data_sources', deserialize_json=True)
DATA_PATH = Path(DATA_SOURCES['data_path'])
PROJECT_DB_CONN_ID = DATA_SOURCES['project_db_conn_id']

GOOGLE_SECRET_KEY = Variable.get('google_secret_key', deserialize_json=True)
GOOGLE_SHEET_URL = Variable.get('google_sheet_url_test')
URL_COL_NAME = 'ссылка'
TEAM_COL_NAME = 'Лабазкин Дмитрий & Хачатрян Екатерина'

VALIDATION_RESULTS_PATH = DATA_PATH/'url_validation_results.json'
PARSE_RESULTS_PATH = DATA_PATH/'url_parse_results.json'
ERROR_STATS_PATH = DATA_PATH/'url_error_stats.csv'

VALID_DOMAINS = [
    'habr.com', 'pikabu.ru', 'pornhub.com',
    'rutube.ru', 'vimeo.com', 'youtube.com'
]

SLEEP_TIMES = [
    0, 0, 0,
    0, 0, 1
]

default_args = {
    'start_date': days_ago(1)
}

dag = DAG(
    dag_id='project',
    schedule_interval='@once',
    default_args=default_args,
    catchup=False,
    template_searchpath='/home/jupyter/airflow_course/project/templates'
)


def process_urls(
    google_secret_key: Dict,
    google_sheet_url: str,
    url_col_name: str,
    valid_domains: List,
    blacklist_conn_id: str,
    validation_results_path: Path,
    **context
) -> None:
    gs = GoogleSheet(google_secret_key)
    gs.get_sheet(google_sheet_url)
    urls_list = gs.get_column_values(url_col_name)
    blacklist_query = context['templates_dict']['blacklist_query']

    url_validator = URLValidator(
        valid_domains,
        blacklist_conn_id,
        blacklist_query
    )

    validation_results = []

    with open(validation_results_path, 'w') as f:
        for url in urls_list:
            result = url_validator.validate_url(url)
            validation_results.append(result)
            f.write(json.dumps(result) + '\n')


def parse_urls(
    domains: List,
    sleep_times: List,
    validation_results_path: Path,
    parse_results_path: Path
) -> None:
    valid_results = []

    with open(validation_results_path) as f:
        for line in f:
            valid_results.append(json.loads(line))

    args = [(valid_results, domain, sleep_time)
            for domain, sleep_time
            in zip(domains, sleep_times)]

    parse_results = []

    for arg in args:
        parse_results.extend(get_domain_counts(*arg))

    with open(parse_results_path, 'w') as f:
        for result in parse_results:
            f.write(json.dumps(result) + '\n')


def calculate_stats(
    validation_results_path: Path,
    parse_results_path: Path,
    error_stats_path: Path
) -> str:
    valid_results = []
    parse_results = []

    with open(validation_results_path) as f:
        for line in f:
            valid_results.append(json.loads(line))

    with open(parse_results_path) as f:
        for line in f:
            parse_results.append(json.loads(line))

    processing_stats = calculate_processing_stats(
        valid_results,
        parse_results
    )

    summary_message = generate_report(processing_stats, error_stats_path)

    return summary_message


def send_report(
    token_id: str,
    chat_id: str,
    error_stats_path: Path,
    **context
) -> None:
    tg_bot = TelegramBot(token_id)

    task_instance = context['ti']
    summary_message = task_instance.xcom_pull(task_ids='calculate_stats')

    tg_bot.send_document(
        chat_id=chat_id,
        caption=summary_message,
        document_path=error_stats_path
    )



# process_urls_task = TemplatedPythonOperator(
#     task_id='process_urls',
#     python_callable=process_urls,
#     op_kwargs={
#         'google_secret_key': GOOGLE_SECRET_KEY,
#         'google_sheet_url': GOOGLE_SHEET_URL,
#         'url_col_name': URL_COL_NAME,
#         'valid_domains': VALID_DOMAINS,
#         'blacklist_conn_id': PROJECT_DB_CONN_ID,
#         'validation_results_path': VALIDATION_RESULTS_PATH
#     },
#     templates_dict={
#         'blacklist_query': 'get_blacklist.sql'
#     },
#     provide_context=True,
#     dag=dag
# )

# parse_urls_task = PythonOperator(
#     task_id='parse_urls',
#     python_callable=parse_urls,
#     op_kwargs={
#         'domains': VALID_DOMAINS,
#         'sleep_times': SLEEP_TIMES,
#         'validation_results_path': VALIDATION_RESULTS_PATH,
#         'parse_results_path': PARSE_RESULTS_PATH
#     },
#     dag=dag
# )

calculate_stats_task = PythonOperator(
    task_id='calculate_stats',
    python_callable=calculate_stats,
    op_kwargs={
        'validation_results_path': VALIDATION_RESULTS_PATH,
        'parse_results_path': PARSE_RESULTS_PATH,
        'error_stats_path': ERROR_STATS_PATH
    },
    dag=dag
)

send_report_task = PythonOperator(
    task_id='send_report',
    python_callable=send_report,
    op_kwargs={
        'token_id': Variable.get('HW3_TELEGRAM_BOT_TOKEN'),
        'chat_id': Variable.get('HW3_TELEGRAM_CHAT_ID'),
        'error_stats_path': ERROR_STATS_PATH
    },
    provide_context=True,
    dag=dag
)

# process_urls_task >> parse_urls_task
calculate_stats_task >> send_report_task

if __name__ == '__main__':
    dag.clear(reset_dag_runs=True)
    dag.run()
