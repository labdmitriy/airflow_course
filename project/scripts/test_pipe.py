from typing import List

import gspread
from gspread import Worksheet
from oauth2client.service_account import ServiceAccountCredentials as sac

from airflow.models.variable import Variable


class GoogleSheet:
    def __init__(self, key_name: str) -> None:
        self.secret_key = Variable.get(key_name, deserialize_json=True)

    def get_sheet(self, sheet_url_name: str, head: int = 1) -> Worksheet:
        google_sheet_url = Variable.get(sheet_url_name)

        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = sac.from_json_keyfile_dict(self.secret_key, scope)
        client = gspread.authorize(creds)

        self.sheet = client.open_by_url(google_sheet_url).sheet1
        return self.sheet

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
        head = sheet.find(column_name)
        head_address = head.address

        row = int(head_address[1:])
        col = head_address[0]

        start_row = row + 1
        end_row = row + update_length

        update_range = f'{col}{start_row}:{col}{end_row}'
        return update_range

    def update(self, update_range: str, update_values: List) -> None:
        self.sheet.update(update_range, update_values)


GOOGLE_KEY_NAME = 'google_secret_key'
GOOGLE_SHEET_URL_NAME = 'google_sheet_url_test'
URL_COL_NAME = 'ссылка'
TEAM_COL_NAME = 'Лабазкин Дмитрий & Хачатрян Екатерина'

gs = GoogleSheet(GOOGLE_KEY_NAME)
sheet = gs.get_sheet(
    GOOGLE_SHEET_URL_NAME,
    head=2
)
urls = gs.get_column_values(URL_COL_NAME)
urls_count = len(urls)
update_range = gs.calculate_update_range(TEAM_COL_NAME, urls_count)
update_values = [[val] for val in range(urls_count)]
gs.update(update_range, update_values)
