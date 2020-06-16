import json
from pathlib import Path

from airflow.models import Connection
from airflow.utils import db

DATA_PATH = Path('/home/jupyter/airflow_backup')

with db.create_session() as session:
    connections = session.query(Connection).all()

conn_dict = [
    {column.name: getattr(c, column.name) 
     for column in Connection.__mapper__.columns}
    for c in connections
]

with open(DATA_PATH/'connections.json', 'w') as f:
    for line in conn_dict:
        line['password'] = None
        f.write(json.dumps(line))
        f.write('\n')
