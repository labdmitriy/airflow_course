import re
from pathlib import Path
from typing import Iterable, List

import gspread
from airflow.models.variable import Variable
from oauth2client.service_account import ServiceAccountCredentials as sac


class GoogleSheet:
    def __init__(self, key_name: str) -> None:
        self.secret_key = Variable.get(key_name, deserialize_json=True)

    def get_sheet(self, sheet_url_name: str) -> None:
        google_sheet_url = Variable.get(sheet_url_name)

        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = sac.from_json_keyfile_dict(self.secret_key, scope)
        client = gspread.authorize(creds)

        self.sheet = client.open_by_url(google_sheet_url).sheet1

    def get_column_values(self, column_name: str) -> List:
        head = self.sheet.find(column_name)
        row = head.row
        col = head.col
        values = self.sheet.col_values(col)[row:]
        return values

    def calculate_update_range(
        self,
        column_name: str,
        update_length: int
    ) -> str:
        head = self.sheet.find(column_name)
        head_address = head.address

        row = int(head_address[1:])
        col = head_address[0]

        start_row = row + 1
        end_row = row + update_length

        update_range = f'{col}{start_row}:{col}{end_row}'
        return update_range

    def update(self, update_range: str, update_values: Iterable) -> None:
        self.sheet.update(update_range,
                          [[value] for value in update_values])


GOOGLE_KEY_NAME = 'google_secret_key'
GOOGLE_SHEET_URL_NAME = 'google_sheet_url_test'
URL_COL_NAME = 'ссылка'
TEAM_COL_NAME = 'Лабазкин Дмитрий & Хачатрян Екатерина'

gs = GoogleSheet(GOOGLE_KEY_NAME)
gs.get_sheet(GOOGLE_SHEET_URL_NAME)
urls_list = gs.get_column_values(URL_COL_NAME)
urls_count = len(urls_list)
update_range = gs.calculate_update_range(TEAM_COL_NAME, urls_count)
update_values = range(urls_count)
gs.update(update_range, update_values)


VALID_DOMAINS = ['habr.com', 'pikabu.ru', 'pornhub.com', 'rutube.ru', 'vimeo.com', 'youtube.com']


def is_valid_url(url):
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    if re.match(regex, url) is not None:
        return True
    else:
        return False


invalid_urls = []

for url in urls_list:
    if not is_valid_url(url):
        invalid_urls.append(url)

print(invalid_urls)
print(len(invalid_urls))


