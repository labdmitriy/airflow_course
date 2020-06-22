import sys
import json
from typing import Dict, List
from pathlib import Path

from airflow import DAG
from airflow.models import Variable
from airflow.utils.dates import days_ago

from merch.operators import TemplatedPythonOperator
sys.path.insert(1, '/home/jupyter/lib/scrape')
from scrape.sheets import GoogleSheet
from scrape.validators import URLValidator


DATA_SOURCES = Variable.get('project_data_sources', deserialize_json=True)
DATA_PATH = Path(DATA_SOURCES['data_path'])
PROJECT_DB_CONN_ID = DATA_SOURCES['project_db_conn_id']

GOOGLE_SECRET_KEY = Variable.get('google_secret_key', deserialize_json=True)
GOOGLE_SHEET_URL = Variable.get('google_sheet_url_test')
URL_COL_NAME = 'ссылка'
TEAM_COL_NAME = 'Лабазкин Дмитрий & Хачатрян Екатерина'

VALIDATION_RESULTS_PATH = DATA_PATH/'url_validation_results.json'

VALID_DOMAINS = {
    'habr.com', 'pikabu.ru', 'pornhub.com',
    'rutube.ru', 'vimeo.com', 'youtube.com'
}


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


process_urls_task = TemplatedPythonOperator(
    task_id='process_urls',
    python_callable=process_urls,
    op_kwargs={
        'google_secret_key': GOOGLE_SECRET_KEY,
        'google_sheet_url': GOOGLE_SHEET_URL,
        'url_col_name': URL_COL_NAME,
        'valid_domains': VALID_DOMAINS,
        'blacklist_conn_id': PROJECT_DB_CONN_ID,
        'validation_results_path': VALIDATION_RESULTS_PATH
    },
    templates_dict={
        'blacklist_query': 'get_blacklist.sql'
    },
    provide_context=True,
    dag=dag
)

if __name__ == '__main__':
    dag.clear(reset_dag_runs=True)
    dag.run()
