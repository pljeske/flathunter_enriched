"""Expose crawler for WgGesucht"""
import logging
import re
import requests
from bs4 import BeautifulSoup

from flathunter.abstract_crawler import Crawler
from flathunter.string_utils import remove_prefix

class CrawlWgGesucht(Crawler):
    """Implementation of Crawler interface for WgGesucht"""

    __log__ = logging.getLogger('flathunt')
    URL_PATTERN = re.compile(r'https://www\.wg-gesucht\.de')

    def __init__(self, config):
        super().__init__(config)
        logging.getLogger("requests").setLevel(logging.WARNING)
        self.config = config

    # pylint: disable=too-many-locals
    def extract_data(self, soup):
        """Extracts all exposes from a provided Soup object"""
        entries = []

        findings = soup.find_all(lambda e: e.has_attr('id') and e['id'].startswith('liste-'))
        existing_findings = [
          e for e in findings if e.has_attr('class') and not 'display-none' in e['class']
        ]

        base_url = 'https://www.wg-gesucht.de/'
        for row in existing_findings:
            title_row = row.find('h3', {"class": "truncate_title"})
            title = title_row.text.strip()
            url = base_url + remove_prefix(title_row.find('a')['href'], "/")
            image = re.match(r'background-image: url\((.*)\);',
                             row.find('div', {"class": "card_image"}).find('a')['style'])[1]
            detail_string = row.find("div", {"class": "col-xs-11"}).text.strip().split("|")
            details_array = list(map(lambda s: re.sub(' +', ' ',
                                                      re.sub(r'\W', ' ', s.strip())),
                                     detail_string))
            numbers_row = row.find("div", {"class": "middle"})
            price = numbers_row.find("div", {"class": "col-xs-3"}).text.strip()
            rooms_tmp = re.findall(r'\d Zimmer', details_array[0])
            rooms = rooms_tmp[0][:1] if rooms_tmp else 0
            dates = re.findall(r'\d{2}.\d{2}.\d{4}',
                               numbers_row.find("div", {"class": "text-center"}).text)
            if len(dates) == 0:
                self.__log__.warning("No dates found - skipping")
                continue
            size = re.findall(r'\d{1,4}\sm²',
                              numbers_row.find("div", {"class": "text-right"}).text)
            if len(size) == 0:
                self.__log__.warning("No size found - skipping")
                continue

            details = {
                'id': int(url.split('.')[-2]),
                'image': image,
                'url': url,
                'title': f"{title} ab dem {dates[0]}",
                'price': price,
                'size': size[0],
                'rooms': rooms,
                'address': url,
                'crawler': self.get_name()
            }
            if len(dates) == 2:
                details['from'] = dates[0]
                details['to'] = dates[1]
            elif len(dates) == 1:
                details['from'] = dates[0]

            entries.append(details)

        self.__log__.debug('extracted: %s', entries)

        return entries

    def load_address(self, url):
        """Extract address from expose itself"""
        response = self.get_soup_from_url(url)
        try:
            address = ' '.join(response.find('div', {"class": "col-sm-4 mb10"})
                               .find("a", {"href": "#mapContainer"}).text.strip().split())
            return address
        except (TypeError, AttributeError):
            self.__log__.debug("No address in response for URL: %s", url)
            return None

    def get_soup_from_url(
      self,
      url,
      driver=None,
      checkbox=None,
      afterlogin_string=None):
        """
        Creates a Soup object from the HTML at the provided URL

        Overwrites the method inherited from abstract_crawler. This is
        necessary as we need to reload the page once for all filters to
        be applied correctly on wg-gesucht.
        """
        self.rotate_user_agent()
        sess = requests.session()
        # First page load to set filters; response is discarded
        sess.get(url, headers=self.HEADERS)
        # Second page load
        resp = sess.get(url, headers=self.HEADERS)

        if resp.status_code not in (200, 405):
            self.__log__.error("Got response (%i): %s", resp.status_code, resp.content)
        if self.config.use_proxy():
            return self.get_soup_with_proxy(url)
        if driver is not None:
            driver.get(url)
            if re.search("initGeetest", driver.page_source):
                self.resolve_geetest(driver)
            elif re.search("g-recaptcha", driver.page_source):
                self.resolve_recaptcha(driver, checkbox, afterlogin_string)
            return BeautifulSoup(driver.page_source, 'html.parser')
        return BeautifulSoup(resp.content, 'html.parser')
