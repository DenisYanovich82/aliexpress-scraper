# REFERENCE: https://www.scrapehero.com/how-to-rotate-proxies-and-ip-addresses-using-python-3/

import requests
from lxml.html import fromstring

def get_proxies():
    url = 'https://free-proxy-list.net/'
    response = requests.get(url)
    parser = fromstring(response.text)
    proxies = set()

    for i in parser.xpath('//tbody/tr'):
        # print("{}:{} | {}".format(
        #     i.xpath('.//td[1]/text()'),
        #     i.xpath('.//td[2]/text()'),
        #     i.xpath('.//td[7]/text()')
        # ))
        if i.xpath('.//td[7][contains(text(),"yes")]'):
            # Grabbing IP and corresponding PORT
            proxy = ":".join([i.xpath('.//td[1]/text()')[0], i.xpath('.//td[2]/text()')[0]])
            proxies.add(proxy)
    return proxies