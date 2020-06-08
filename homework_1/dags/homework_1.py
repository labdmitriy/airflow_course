from pathlib import Path
from datetime import datetime
from operator import itemgetter, add
from itertools import product, chain, cycle, zip_longest
from functools import reduce

import requests
import pandas as pd

from airflow import DAG
from airflow.operators.python_operator import PythonOperator

# Prepare get-functions for region data parsing
get_cases = itemgetter('cases')
get_cured = itemgetter('cured')
get_deaths = itemgetter('deaths')
get_value = itemgetter('v')

# Add column to data
def concat_cols(data):
    return (data[0],) + data[1]

# Parse data for specific region
def parse_region_data(data):
    # Get region name
    region = data['info']['name']

    # If file format is new (counts are dictionaries)
    if isinstance(get_cases(data)[0], dict):
        counts = zip_longest(map(get_value, get_cases(data)),
                             map(get_value, get_cured(data)),
                             map(get_value, get_deaths(data)), fillvalue=0)
    # else if format is old (counts are lists)
    else:
        counts = zip_longest(get_cases(data),
                             get_cured(data),
                             get_deaths(data), fillvalue=0)
    
    # Add region name to each record
    parsed_data = product([region], counts)
    
    # Flatten records
    parsed_data = map(concat_cols, parsed_data)
    
    return parsed_data

def parse_russian_data(data):
    # Get data for regions in Russia
    russian_data = data['russia_stat_struct']
    
    # Get dates provided in data
    dates = russian_data['dates']
    
    # Get region data
    region_data = russian_data['data'].values()
    
    # Calculate data size (number of regions)
    data_size = len(region_data)
    
    # Prepare dates column
    all_dates = cycle(dates)
    
    # Parse each region data
    parsed_data = map(parse_region_data, region_data)
    parsed_data = chain.from_iterable(parsed_data)
    
    # Add dates column to parsed data
    parsed_data = zip(all_dates, parsed_data)
    parsed_data = map(concat_cols, parsed_data)
    
    return parsed_data

def download_file(url):
    # Get file by url
    r = requests.get(url)
    
    # Check for network errors
    r.raise_for_status()
    
    # Get JSON data representation
    data = r.json()
    
    return data

def combine_results(acc, nxt):
    key = nxt[0]
    values = nxt[1]
    
    # Add key as separate column
    result = product([key], values)
    result = map(concat_cols, result)
    
    return acc | set(result)

def combine_data(results):
    # Combine all results 
    full_results = reduce(combine_results, results.items(), set())
    
    # Sort data by file_num, date, region
    full_results = sorted(full_results, key=itemgetter(0, 1, 2))
    
    return full_results

def calculate_stats(data):
    columns=['file_num', 'date', 'region', 'infected', 'recovered', 'dead']
    
    # Create DataFrame from data
    stats_df = pd.DataFrame.from_records(data, columns=columns, index='file_num')
    
    # Remove non-region data
    stats_df = stats_df[stats_df['region'] != 'Россия']
    
    # Get only last (by file_num) record if there are multiple files 
    # for the same date and region in different files
    stats_df = stats_df.groupby(['date', 'region'], as_index=False).last()
    
    return stats_df 

def save_data(df, file_path):
    # Save data to csv
    df.to_csv(file_path, index=False)
    
def gather_russian_stats(file_path, history_type='standard'):
    # Define 2 types of coronavirus history
    # 'standard' - provided in homework by default 
    # 'deep' - data with complete history (including March)
    history_types = {
        'standard':'https://yastat.net/s3/milab/2020/covid19-stat/data/data_struct_{num}.json?v=timestamp',
        'deep': 'https://yastat.net/s3/milab/2020/covid19-stat/data/deep_history_struct_{num}.json?v=1591117446'
    }
    
    # Define used URL template
    url_template = history_types[history_type]

    i = 1
    results = {}

    # While there is correct URL
    while True:
        print(str(i))
        
        # Generate URL
        url = url_template.format(num=i)
        try:
            # Download file using generated URL
            data = download_file(url)
        except requests.exceptions.HTTPError as err:
            # If this URL is not correct - stop downloading
            print(err)
            break

        try:
            # Parse russian data from downloaded file
            results[i] = tuple(parse_russian_data(data))
        except KeyError as err:
            # If there is no russion data in the file - skip this file
            print('Russian data is not found', err)
        
        # Increment file number 
        i += 1
    
    # Combine data from all downloaded files
    full_results = combine_data(results)
    
    # Calculate statistics from full data
    stats_df = calculate_stats(full_results)
    
    # Save data to csv file
    save_data(stats_df, file_path)
    
    return stats_df

# Define default args
default_args = {

}

# Define DAG
dag = DAG(
    'homework_1',
    default_args=default_args,
    description='Homework 1',
    schedule_interval='0 12 * * *', 
    start_date=datetime(2020, 6, 2), 
    catchup=False
)

# Define output data directory
DATA_DIR = Path('/home/jupyter/data')
# If directory does not exists - create all subfolders
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Define task with PythonOperator
python_task = PythonOperator(
    task_id='calculate_stats',
    dag=dag,
    python_callable=gather_russian_stats,
    op_args=[DATA_DIR/'russian_stats.csv', 'standard']
)

python_task