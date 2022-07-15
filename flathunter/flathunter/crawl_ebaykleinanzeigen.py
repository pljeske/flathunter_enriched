"""Expose crawler for Ebay Kleinanzeigen"""
import logging
import re
import datetime

from flathunter.abstract_crawler import Crawler

class CrawlEbayKleinanzeigen(Crawler):
    """Implementation of Crawler interface for Ebay Kleinanzeigen"""

    __log__ = logging.getLogger('flathunt')
    USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0'
    URL_PATTERN = re.compile(r'https://www\.ebay-kleinanzeigen\.de')
    MONTHS = {
        "Januar": "01",
        "Februar": "02",
        "März": "03",
        "April": "04",
        "Mai": "05",
        "Juni": "06",
        "Juli": "07",
        "August": "08",
        "September": "09",
        "Oktober": "10",
        "November": "11",
        "Dezember": "12"
    }

    def __init__(self, config):
        super().__init__(config)
        logging.getLogger("requests").setLevel(logging.WARNING)
        self.config = config

    def get_page(self, search_url, driver=None, page_no=None):
        """Applies a page number to a formatted search URL and fetches the exposes at that page"""
        return self.get_soup_from_url(search_url)

    def get_expose_details(self, expose):
        soup = self.get_page(expose['url'])
        for detail in soup.find_all('li', {"class": "addetailslist--detail"}):
            if re.match(r'Verfügbar ab', detail.text):
                date_string = re.match(r'(\w+) (\d{4})', detail.text)
                if date_string is not None:
                    expose['from'] = "01." + self.MONTHS[date_string[1]] + "." + date_string[2]
        if 'from' not in expose:
            expose['from'] = datetime.datetime.now().strftime('%02d.%02m.%Y')
        return expose

    # pylint: disable=too-many-locals
    def extract_data(self, soup):
        """Extracts all exposes from a provided Soup object"""
        entries = []
        soup = soup.find(id="srchrslt-adtable")
        try:
            title_elements = soup.find_all(lambda e: e.has_attr('class')
                                           and 'ellipsis' in e['class'])
        except AttributeError:
            return entries
        expose_ids = soup.find_all("article", class_="aditem")

        # soup.find_all(lambda e: e.has_attr('data-adid'))
        # print(expose_ids)
        for idx, title_el in enumerate(title_elements):
            try:
                price = expose_ids[idx].find(class_="aditem-main--middle--price").text.strip()
                tags = expose_ids[idx].find_all(class_="simpletag tag-small")
                address = expose_ids[idx].find("div", {"class": "aditem-main--top--left"})
                image_element = expose_ids[idx].find("div", {"class": "galleryimage-element"})
            except AttributeError as error:
                self.__log__.warning("Unable to process Ebay expose: %s", str(error))
                continue

            if image_element is not None:
                image = image_element["data-imgsrc"]
            else:
                image = None
            self.__log__.debug(address.text.strip())
            address = address.text.strip()
            address = address.replace('\n', ' ').replace('\r', '')
            address = " ".join(address.split())
            try:
                self.__log__.debug(tags[1].text)
                rooms = re.match(r'(\d+)', tags[1].text)[1]
            except (IndexError, TypeError):
                self.__log__.debug("Keine Zimmeranzahl gegeben")
                rooms = "Nicht gegeben"
            try:
                self.__log__.debug(tags[0].text)
                size = tags[0].text
            except (IndexError, TypeError):
                size = "Nicht gegeben"
                self.__log__.debug("Quadratmeter nicht angegeben")
            details = {
                'id': int(expose_ids[idx].get("data-adid")),
                'image': image,
                'url': ("https://www.ebay-kleinanzeigen.de" + title_el.get("href")),
                'title': title_el.text.strip(),
                'price': price,
                'size': size,
                'rooms': rooms,
                'address': address,
                'crawler': self.get_name()
            }
            entries.append(details)

        self.__log__.debug('extracted: %d', len(entries))

        return entries

    def load_address(self, url):
        """Extract address from expose itself"""
        expose_soup = self.get_page(url)
        try:
            street_raw = expose_soup.find(id="street-address").text
        except AttributeError:
            street_raw = ""
        try:
            address_raw = expose_soup.find(id="viewad-locality").text
        except AttributeError:
            address_raw = ""
        address = address_raw.strip().replace("\n", "") + " " + street_raw.strip()

        return address
