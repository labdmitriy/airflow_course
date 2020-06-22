import sys
sys.path.insert(1, '/home/jupyter/lib/scrape')

import csv
import json
from pathlib import Path

from merch.db import PostgresDB
from scrape.sheets import GoogleSheet
from scrape.validators import URLValidator


GOOGLE_KEY_NAME = 'google_secret_key'
GOOGLE_SHEET_URL_NAME = 'google_sheet_url_test'
URL_COL_NAME = 'ссылка'
TEAM_COL_NAME = 'Лабазкин Дмитрий & Хачатрян Екатерина'

gs = GoogleSheet(GOOGLE_KEY_NAME)
gs.get_sheet(GOOGLE_SHEET_URL_NAME)
urls_list = gs.get_column_values(URL_COL_NAME)
urls_count = len(urls_list)
# update_range = gs.calculate_update_range(TEAM_COL_NAME, urls_count)
# update_values = range(urls_count)
# gs.update(update_range, update_values)


VALID_DOMAINS = {
    'habr.com', 'pikabu.ru', 'pornhub.com',
    'rutube.ru', 'vimeo.com', 'youtube.com'
}
PROJECT_DB_CONN_ID = 'project_db'
DATA_PATH = Path('/home/jupyter/data')

with open(DATA_PATH/'get_blacklist.sql') as f:
    blacklist_query = f.read()

url_validator = URLValidator(
    VALID_DOMAINS,
    PROJECT_DB_CONN_ID,
    blacklist_query
)

validation_results = []

with open(DATA_PATH/'url_validation_results.json', 'w') as f:
    for url in urls_list:
        result = url_validator.validate_url(url)
        validation_results.append(result)
        f.write(json.dumps(result) + '\n')

valid_urls = [result['url'] for result in validation_results
              if result['is_valid'] is True]

with open(DATA_PATH/'valid_urls.csv', 'w') as f:
    field_names = ['url']
    writer = csv.DictWriter(f, fieldnames=field_names)

    writer.writeheader()

    for url in set(valid_urls):
        writer.writerow({'url': url})


with open(DATA_PATH/'url_update_history_tmp.json') as f:
    temp_table_info = json.loads(f.read())

with open(DATA_PATH/'url_update_history.json') as f:
    target_table_info = json.loads(f.read())

with open(DATA_PATH/'load_data.sql') as f:
    load_data_query = f.read()

PROJECT_DB_CONN_ID = 'project_db'
pg_db = PostgresDB(PROJECT_DB_CONN_ID)

TEMP_TABLE_NAME = 'url_update_history_tmp'
TARGET_TABLE_NAME = 'url_update_history'

pg_db.drop_table(TEMP_TABLE_NAME)
pg_db.drop_table(TARGET_TABLE_NAME)
pg_db.create_table(temp_table_info)
pg_db.create_table(target_table_info)
pg_db.load_table_from_file(TEMP_TABLE_NAME, DATA_PATH/'valid_urls.csv')
pg_db.execute(load_data_query)