import json
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from requests.exceptions import HTTPError
from bs4 import BeautifulSoup
import os
import re


VALIDATION_RESULTS_FILE = '/home/jupyter/data/url_validation_results.json'


def filter_urls(valid_results, domain, is_valid=True):
    results = filter(lambda x: x['is_valid'] is is_valid and x['domain'] == domain, 
                     valid_results)
    urls = map(lambda x: x['url'], results)
    return list(urls)


def clean_views_count(raw_views_count):
    units_map = {'k': 1000}
    views_count = raw_views_count.lower().strip()

    if views_count[-1] in units_map:
        unit = views_count[-1]
        num = views_count[:-1]

        views_count = float(re.sub('\D', '', num))
        decimal_seps = re.findall(r'[\.,]', num)

        if len(decimal_seps) > 0:
            decimal_sep = decimal_seps[0]
            decimal_pos = len(num) - num.find(decimal_sep) - 1
        else:
            decimal_pos = 0

        views_count = int(views_count * units_map[unit] / (10**decimal_pos))
    else:
        views_count = int(re.sub('\D', '', views_count))

    return views_count


def get_pikabu_views_count(url, browser):
    parse_results = {}
    parse_results['url'] = url
    parse_results['is_parsed'] = False

    try:
        print('get')
        browser.get(url)
    except HTTPError as e:
        status_code = str(e.response.status_code)
        reason = '_'.join(e.response.reason.lower().split())
        error_code = "_".join([status_code, reason])
        parse_results['error_code'] = error_code
        return parse_results

    try:
        views_count = browser.find_element_by_class_name('story__views-count').text
    except NoSuchElementException as e:
        parse_results['error_code'] = f'element_not_found'
        print(parse_results)
        return parse_results

    parse_results['is_parsed'] = True
    parse_results['raw_views_count'] = views_count
    parse_results['views_count'] = clean_views_count(views_count)

    print(parse_results)

    return parse_results


valid_results = []

with open(VALIDATION_RESULTS_FILE) as f:
    for line in f:
        valid_results.append(json.loads(line))
    
print(valid_results[:10])


pikabu_urls = filter_urls(valid_results, 'pikabu.ru')
print(pikabu_urls[:10])

# os.environ["DBUS_SESSION_BUS_ADDRESS"] = '/dev/null'
chrome_options = Options()
chrome_options.headless = True
# chrome_options.add_argument('--disable-browser-side-navigation')
# chrome_options.add_argument('--verbose')
chrome_options.add_argument('--no-proxy-server') 
chrome_options.add_argument("--proxy-server='direct://'")
chrome_options.add_argument("--proxy-bypass-list=*")
chrome_driver_path = ChromeDriverManager().install()

# browser.set_page_load_timeout(15)
# browser.

for url in pikabu_urls[3:6]:
    print(url)
    browser = webdriver.Chrome(chrome_driver_path, options=chrome_options)
    parse_results = get_pikabu_views_count(url, browser)
    browser.quit()
