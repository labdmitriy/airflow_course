import requests
from requests_html import HTMLSession
from bs4 import BeautifulSoup
 
url = 'https://pikabu.ru/story/kak_ya_uznal_ob_izmene_ili_lyogkiy_sposob_brosit_shutit_7471791'
 
try:
    session = HTMLSession()
    response = session.get(url)
    print(response.html.render())
    text = response.text
    
    # print(text)
     
except requests.exceptions.RequestException as e:
    print(e)

soup = BeautifulSoup(text, 'lxml')
print(soup.find('span', class_="story__views-count"))
