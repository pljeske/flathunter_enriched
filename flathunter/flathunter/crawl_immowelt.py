"""Expose crawler for ImmoWelt"""
import logging
import re
import datetime
import hashlib

from flathunter.abstract_crawler import Crawler

class CrawlImmowelt(Crawler):
    """Implementation of Crawler interface for ImmoWelt"""

    __log__ = logging.getLogger('flathunt')
    URL_PATTERN = re.compile(r'https://www\.immowelt\.de')

    def __init__(self, config):
        super().__init__(config)
        logging.getLogger("requests").setLevel(logging.WARNING)
        self.config = config

    def get_expose_details(self, expose):
        """Loads additional details for an expose by processing the expose detail URL"""
        soup = self.get_page(expose['url'])
        date = datetime.datetime.now().strftime("%2d.%2m.%Y")

        immo_div = soup.find("app-estate-object-informations")
        if immo_div is not None:
            immo_div = soup.find("div", {"class": "equipment ng-star-inserted"})
            if immo_div is not None:
                details = immo_div.find_all("p")

                for detail in details:
                    if detail.text.strip() == "Bezug":
                        date = detail.findNext("p").text.strip()
                        no_exact_date_given = re.match(
                          r'.*sofort.*|.*Nach Vereinbarung.*',
                          date,
                          re.MULTILINE|re.DOTALL|re.IGNORECASE
                        )
                        if no_exact_date_given:
                            date = datetime.datetime.now().strftime("%2d.%2m.%Y")
                        break
        expose['from'] = date
        return expose

    # pylint: disable=too-many-locals
    def extract_data(self, soup):
        """Extracts all exposes from a provided Soup object"""
        entries = []
        soup = soup.find("main")

        try:
            title_elements = soup.find_all("h2")
        except AttributeError:
            return entries
        expose_ids = soup.find_all("a", id=True)

        for idx, title_el in enumerate(title_elements):

            try:
                price = expose_ids[idx].find(
                    "div", attrs={"data-test": "price"}).text
            except IndexError:
                self.__log__.error("Kein Preis angegeben")
                price = "Auf Anfrage"

            try:
                size = expose_ids[idx].find(
                    "div", attrs={"data-test": "area"}).text
            except IndexError:
                size = "Nicht gegeben"
                self.__log__.error("Quadratmeter nicht angegeben")

            try:
                rooms = expose_ids[idx].find(
                    "div", attrs={"data-test": "rooms"}).text
            except IndexError:
                self.__log__.error("Keine Zimmeranzahl gegeben")
                rooms = "Nicht gegeben"

            url = expose_ids[idx].get("href")

            picture = expose_ids[idx].find("picture")
            image = None
            if picture:
                src = picture.find("source")
                if src:
                    image = src.get("data-srcset")

            try:
                address = expose_ids[idx].find(
                    "div", attrs={"class": re.compile("IconFact.*")}
                  )
                address = address.find("span").text
            except IndexError:
                self.__log__.error("Keine Addresse gegeben")
                address = "Nicht gegeben"

            processed_id = int(
              hashlib.sha256(expose_ids[idx].get("id").encode('utf-8')).hexdigest(), 16
            ) % 10**16

            details = {
                'id': processed_id,
                'image': image,
                'url': url,
                'title': title_el.text.strip(),
                'rooms': rooms,
                'price': price,
                'size': size,
                'address': address,
                'crawler': self.get_name()
            }
            entries.append(details)

        self.__log__.debug('extracted: %d', len(entries))

        return entries
