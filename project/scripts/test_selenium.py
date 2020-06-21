from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

chrome_options = Options()
chrome_options.headless = True
chrome_options.add_argument('--no-proxy-server') 
chrome_options.add_argument("--proxy-server='direct://'")
chrome_options.add_argument("--proxy-bypass-list=*")

browser = webdriver.Chrome(ChromeDriverManager().install(),
                           options=chrome_options)
url = 'https://pikabu.ru/story/budet_li_otvet_ot_kospleyshchikov_7366977'
browser.get(url)
print(browser.find_element_by_class_name('story__views-count').text)
browser.quit()
