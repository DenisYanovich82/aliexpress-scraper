# -*- coding: utf-8 -*-
"""
Module to get and parse the product info on Aliexpress
"""

from requests_html import HTMLSession
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import time
import math

from aliexpress.proxy_scrape import get_proxies
from itertools import cycle
from aliexpress.logger import AliexpressLogPrinter as _print

_BASE_URL = "https://www.aliexpress.com/"
_DEFAULT_BEAUTIFULSOUP_PARSER = "html.parser"
_DEFAULT_USER_AGENT = 'Mozilla/5.0 (Linux; Android 7.0; \
SM-A520F Build/NRD90M; wv) AppleWebKit/537.36 \
(KHTML, like Gecko) Version/4.0 \
Chrome/65.0.3325.109 Mobile Safari/537.36'
_CHROME_DESKTOP_USER_AGENT = 'Mozilla/5.0 (Macintosh; \
Intel Mac OS X 10_13_5) AppleWebKit/537.36 (KHTML, like Gecko) \
Chrome/67.0.3396.79 Safari/537.36'

_USER_AGENT_LIST = [
    _DEFAULT_USER_AGENT,
    _CHROME_DESKTOP_USER_AGENT,
]

# Maximum number of requests to do if Al returns a bad page (anti-scraping)
_MAX_TRIAL_REQUESTS = 5
_WAIT_TIME_BETWEEN_REQUESTS = 1

_SEARCH_URL = "https://aliexpress.com/wholesale?catId=0&initiative_id=SB_20201112042158&SearchText={string}"
_PAGE_SEARCH_URL = "https://aliexpress.com/wholesale?catId=0&initiative_id=SB_20201112042158&SearchText={string}&SortType=default&page={page}"  
_ITEM_URL = "https://aliexpress.com/item/{product_id}.html"
_BASE_URL = "https://www.aliexpress.com"


class AliexpressClient(object):
    """Do the requests with the Amazon servers"""

    def __init__(self, proxy_limit=10):
        """ Init of the client """
        self.session = HTMLSession()
        self.current_proxy = ""
        self.headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36'
                    }

        self._proxies = list(get_proxies())
        self._proxies = self._get_working_proxies(limit=proxy_limit)
        #test start
        # self._proxies = ['51.178.140.134:443', '68.183.181.139:8118', '198.50.163.192:3129']
        # self._proxies = self._get_working_proxies(limit=3)
        # self.proxy_limit = 3
        #test end

        self.proxies = cycle(self._proxies)
        # _print("PROXIES: {}".format(self._proxies))
        self.new_proxy = None
        self._change_session_proxy()

        self.product_dict_list = []
        self.html_pages = []

    def _get_search_url(self, string):
        res = _SEARCH_URL.format(string = string)
        return res

    def _get_page_search_url(self, string, page):
        res = _PAGE_SEARCH_URL.format(string = string, page = page)
        return res

    def _get_item_url(self, product_id):
        res = _ITEM_URL.format(product_id = product_id)
        return res

    def _get_working_proxies(self, limit=-1):
        test_url = "https://www.aliexpress.com"
        working_proxies = []

        self.proxy_limit = limit

        # TODO: repeat this until a working proxy has been found

        _print("Finding {} proxies...".format(limit))
        for _proxy in self._proxies:
            # self.session = HTMLSession(browser_args=["--proxy-server=" + _proxy])
            # self.session.proxies.update({'http': _proxy, 'https': _proxy})
            try:
                proxy = {'http': _proxy, 'https': _proxy}
                response = self.session.get(test_url, proxies = proxy, timeout=10)
                response.html.render(timeout = 20)
                if response != None:
                    working_proxies.append(_proxy)
                    if limit >= 0 and len(working_proxies) >= limit:
                        break
                _print("{}.....PASSED".format(_proxy))
            except Exception:
                _print("{}.....FAILED".format(_proxy))
        _print("Found {} working proxies : {}".format(len(working_proxies), working_proxies))


        if len(working_proxies) == 0:
            raise Exception("ERROR: No working proxies found!")
        return working_proxies

    def _change_session_proxy(self):
        _proxy = next(self.proxies)
        self.current_proxy = _proxy
        self.new_proxy = _proxy
        # self.session = HTMLSession(browser_args=["--proxy-server=" + _proxy])

        # TODO: test if proxy is working, if not remove from cycle
        # check if cycle is non-empty, if empty get new proxies
        # this should make it more resilient for when proxies start failing
        # and new ones have to be used

    def _remove_current_proxy(self):
        cur_prox_index = self._proxies.index(self.current_proxy)
        _print("Removing current proxy")
        if len(self._proxies) > 1:
            if cur_prox_index == len(self._proxies) - 1:
                self._proxies = self._proxies[:-1]
                self.proxies = cycle(self._proxies)
            else:
                self._proxies = self._proxies[cur_prox_index+1:] + self._proxies[:cur_prox_index]
                self.proxies = cycle(self._proxies)
        else:
            _print("Proxy pool depleted, replenishing...")
            self.proxies = cycle(self._get_working_proxies(limit=self.proxy_limit))
        # _print("Current proxies: {}".format(self._proxies))
        time.sleep(5)

    def _get(self, url, timeout = 10, scrolldown = -1, retries=0, retry_limit=5, rotate_proxies=False ):
        """ GET request with the proper headers """
        try:
            if rotate_proxies:
                self._change_session_proxy()
            _print("Attempting to get {}".format(url))
            proxy = {'http': self.new_proxy, 'https': self.new_proxy}
            response = self.session.get(url, proxies = proxy)
            if scrolldown == -1:
                response.html.render(timeout = timeout)
            else:
                response.html.render(timeout = timeout, scrolldown = scrolldown)
            if response.status_code != 200:
                retries = retry_limit
                raise ConnectionError(
                    'Status code {status} for url {url}'.format(
                        status=response.status_code, url=url))
            time.sleep(300)
            return response
        except Exception as e:
            _print("Proxy error, changing proxies and retrying [Attempt: {}/{}] | {}".format(retries, retry_limit, e))
            self._remove_current_proxy()
            self._change_session_proxy()
        if retries < retry_limit:
            return self._get(url, retries+1, retry_limit)
        else:
            raise Exception("Failed to fetch {} within the given retry limit({})!".format(url, retry_limit))


    def _check_page(self, html_content):
        """Check if the page is a valid result page
        (even if there is no result) """
        if "Sign in for the best experience" in html_content:
            valid_page = False
            error = "sign_in"
        elif "The request could not be satisfied." in html_content:
            valid_page = False
            error = "request_error"
        elif "Robot Check" in html_content:
            valid_page = False
            error = "automation_block"
        # elif "api-services-support@amazon.com" in html_content:
        #     valid_page = False
        #     error = "automation_block"
        else:
            return {'valid_page': True}
            valid_page = True
        return {'valid_page': valid_page, "error": error}

    def _get_products_page(self, page, keywords="", search_url="", max_product_nb=100):
        page_url = self._get_page_search_url(keywords, page)
        response = self.session._get(url, 40, 15)
        if response == None:
            return
        for item in response.html.find('li.list-item > div'):
            # get product url in shop category
            soup = BeautifulSoup(item.raw_html, "html.parser")
            e = soup.find('div', attrs = { 'class', 'gallery product-card middle-place'})
            if e == None:
                continue
            product_id = e.attrs['data-product-id']

            item_title = ''
            e = soup.find('a', attrs = {'class', 'item-title'})
            if e != None:
                item_title = e.attrs['title']

            price_current = ''
            e = soup.find('span', attrs = {'class', 'price-current'})
            if e != None:
                price_current = e.text.strip()

            price_original = ''
            e = soup.find('span', attrs = {'class', 'price-original'})
            if e != None:
                price_original = e.text.strip()

            product_url = self.item_url.format(product_id = product_id)

            item_response = self.session._get(product_url, 20)
            soup = BeautifulSoup(item_response.html.raw_html, "html.parser")
            image = ''
            for e_img in soup.find_all('div', attrs = {'images-view-item'}):
                tmp = e_img.find('img')
                image += tmp.attrs['src'] + '\n'
            
            color = ''
            for e_img in soup.find_all('li', attrs = {'sku-property-item'}):
                tmp = e_img.find('img')
                if tmp != None:
                    color += tmp.attrs['src']
                else:
                    color += e_img.text.strip()

            product_spec = ''
            e_product_spec = soup.find('div', attrs = {'class', 'product-specs'})
            for e_spec in e_product_spec.find_all('li'):
                product_spec += e_spec.text.strip() + ' '
            
            product_detail_image = ''
            for e_module_image in soup.find_all('div', attrs = {'class', 'detailmodule_image'}):
                for e in e_module_image.find_all('img'):
                    product_detail_image += e.attrs['src'] + ' '
            for e_module_image in soup.find_all('div', attrs = {'class', 'detailmodule_text-image'}):
                for e in e_module_image.find_all('img'):
                    product_detail_image += e.attrs['src'] + ' '

            product_detail_text = ''
            for e in soup.find_all('div', attrs = {'class', 'detailmodule_text'}):
                product_detail_text += e.text.strip() + ' '
            
            # get item data
            new = {
                'id' : product_id,
                'title' : item_title,
                'price_current' : price_current,
                'price_original' : price_original,
                'image' : image,
                'color' : color,
                # 'specific' : product_spec,
                # 'detail_text' : product_detail_text,
                # 'detail_image' : product_detail_image
            }
            self.product_dict_list.append(new)

    def _get_products(self, keywords="", search_url="", max_product_nb=100):

        if search_url == "":
            search_url = self._get_search_url(keywords)

        response = self._get(search_url, 20)
        
        e_pagenums = response.html.find('div.next-breadcrumb > div.next-breadcrumb-item')
        page_cnt = 0
        if len(e_pagenums) > 1:
            tmp = e_pagenums[1].text
            res = [int(i) for i in re.split(' |\(|\)|\,|\;', tmp) if i.isdigit()] 
            if len(res) > 0:
                page_cnt = math.ceil(res[0]/60)
        
        product_count = 0
        page_number = 1
        if max_product_nb < 0:
            max_product_nb = 999999

        # search all pages and write
        for page in range(1, page_cnt+1): #page_cnt+1
            if len(self.product_dict_list) > max_product_nb:
                break
            self._get_products_page(page, keywords)
        print('end')
        
        while len(self.product_dict_list) < max_product_nb:

            # TODO: make this part interruptible
            # also, temporarily store pages in files so that we can process this by chunks

            # get the html of the specified page
            page = self._get_page_html(search_url)

            # extract the needed products from the page and return the url of
            # the next page

            # if "page=" in search_url:
            #     page_number = int(re.match(r'.*page=([0-9]+)', search_url).groups()[0])
            _print("Scraping page {}".format(page_number))

            _print("Attempting to get URL for page {} |".format(page_number + 1))
            try:
                search_url = self._extract_page(page, max_product_nb=max_product_nb)
            except ValueError as e:
                # _print("Failed to get next url | {}".format(e))
                if "page=" in search_url:
                    search_url =  re.sub(r'(.*page=)([0-9]+)(.*)', r"\g<1>{}\g<3>".format(page_number+1), search_url)
                else:
                    search_url += "&page={}".format(page_number + 1)
                # _print("Attempting to build URL manually: {}".format(search_url))
            _print("Products found on page {}: {}".format(page_number, len(self.product_dict_list) - product_count))
            page_number += 1
            if len(self.product_dict_list) == product_count:
                _print("No more results found")
                break
            product_count = len(self.product_dict_list)

        _print("Found {} products".format(len(self.product_dict_list)))
        return self.product_dict_list

