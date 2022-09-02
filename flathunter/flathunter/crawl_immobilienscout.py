"""Expose crawler for ImmobilienScout"""
import logging
import re
import datetime
import time

import requests
from bs4 import BeautifulSoup
from selenium.common.exceptions import JavascriptException
from jsonpath_ng import parse
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By

from flathunter.abstract_crawler import Crawler

class CrawlImmobilienscout(Crawler):
    """Implementation of Crawler interface for ImmobilienScout"""

    __log__ = logging.getLogger('flathunt')
    URL_PATTERN = re.compile(r'https://www\.immobilienscout24\.de')
    RESULT_LIMIT = 50

    def __init__(self, config):
        super().__init__(config)
        logging.getLogger("requests").setLevel(logging.WARNING)
        self.config = config
        self.driver = None
        self.checkbox = None
        self.afterlogin_string = None

        if config.captcha_enabled():
            captcha_config = config.get('captcha')
            self.driver_executable_path = captcha_config.get('driver_path', '')
            self.driver_arguments = captcha_config.get('driver_arguments', [])
            if captcha_config.get('checkbox', '') == "":
                self.checkbox = False
            else:
                self.checkbox = captcha_config.get('checkbox', '')
            if captcha_config.get('afterlogin_string', '') == "":
                self.afterlogin_string = ""
            else:
                self.afterlogin_string = captcha_config.get('afterlogin_string', '')
            if self.captcha_solver:
                self.driver = self.configure_driver(
                    self.driver_executable_path,
                    self.driver_arguments
                )

    def get_results(self, search_url, max_pages=None):
        """Loads the exposes from the ImmoScout site, starting at the provided URL"""
        # convert to paged URL
        # if '/P-' in search_url:
        #     search_url = re.sub(r"/Suche/(.+?)/P-\d+", "/Suche/\1/P-{0}", search_url)
        # else:
        #     search_url = re.sub(r"/Suche/(.+?)/", r"/Suche/\1/P-{0}/", search_url)
        if '&pagenumber' in search_url:
            search_url = re.sub(r"&pagenumber=[0-9]", "&pagenumber={0}", search_url)
        else:
            search_url = search_url + '&pagenumber={0}'
        self.__log__.debug("Got search URL %s", search_url)

        # load first page to get number of entries
        page_no = 1
        soup = self.get_page(search_url, self.driver, page_no)

        # If we are using Selenium, just parse the results from the JSON in the page response
        if self.driver is not None:
            return self.get_entries_from_javascript()

        try:
            no_of_results = int(
                soup.find_all(lambda e: e.has_attr('data-is24-qa') and \
                                        e['data-is24-qa'] == 'resultlist-resultCount')[0] \
                    .text.replace('.', ''))
        except IndexError:
            self.__log__.debug('Index Error occurred')
            no_of_results = 0

        # get data from first page
        entries = self.extract_data(soup)

        # iterate over all remaining pages
        while len(entries) < min(no_of_results, self.RESULT_LIMIT) and \
                (max_pages is None or page_no < max_pages):
            self.__log__.debug(
                'Next Page, Number of entries : %d, no of results: %d',
                len(entries), no_of_results)
            page_no += 1
            soup = self.get_page(search_url, self.driver, page_no)
            cur_entry = self.extract_data(soup)
            if isinstance(cur_entry, list):
                break
            entries.extend(cur_entry)
        return entries

    def get_soup_from_url(self, url, driver=None, checkbox=None, afterlogin_string=None):
        """Creates a Soup object from the HTML at the provided URL"""

        self.rotate_user_agent()
        resp = requests.get(url, headers=self.HEADERS)
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

            self.__log__.info("Login function currently broken. Continuing without login")
            # try:
            #     result_json = driver.execute_script('return window.IS24.resultList;')
            #     is_logged_id = result_json['isUserLoggedId']
            # except Exception as e:
            #     self.__log__.debug("Exception occurred: %s", e)
            #     is_logged_id = False
            # if not is_logged_id:
            #     self.__log__.info("User is not logged in. Trying to login...")
            #     self.login(driver)
            #     return self.get_soup_from_url(url, driver, checkbox, afterlogin_string)
            # else:
            #     self.__log__.info("User is logged in. Continuing...")
            return BeautifulSoup(driver.page_source, 'html.parser')
        return BeautifulSoup(resp.content, 'html.parser')

    def get_entries_from_javascript(self):
        """Get entries from JavaScript"""
        try:
            result_json = self.driver.execute_script('return window.IS24.resultList;')
        except JavascriptException:
            self.__log__.warning("Unable to find IS24 variable in window")
            return []
        return self.get_entries_from_json(result_json)

    def get_entries_from_json(self, json):
        """Get entries from JSON"""
        jsonpath_expr = parse("$..['resultlist.realEstate']")
        return [
          self.extract_entry_from_javascript(entry.value) for entry in jsonpath_expr.find(json)
        ]

    def extract_entry_from_javascript(self, entry: dict):
        """Get single entry from JavaScript"""
        is_premium = False
        if entry.get("paywallListing", {}) and entry["paywallListing"].get("isPremium"):
            is_premium = True
        image_path = parse("$..galleryAttachments..['@xlink.href']")
        expose = {
            'id': int(entry["@id"]),
            'url': ("https://www.immobilienscout24.de/expose/" + str(entry["@id"])),
            'image': next(
                iter([galleryImage.value for galleryImage in image_path.find(entry)]),
                ("https://www.static-immobilienscout24.de/"
                    "statpic/placeholder_house/496c95154de31a357afa978cdb7f15f0_placeholder_medium.png")
            ),
            'title': entry["title"],
            'address': entry["address"]["description"]["text"],
            'crawler': self.get_name(),
            'price': str(entry["price"]["value"]),
            'size': str(entry["livingSpace"]),
            'rooms': str(entry["numberOfRooms"]),
            'is_premium': is_premium
        }

        try:
            expose['rent_warm'] = str(entry['calculatedTotalRent']['totalRent']['value'])
        except Exception as e:
            self.__log__.warning("Unable to find rent warm value: ", e)

        try:
            image_urls = []

            for attachment in entry['galleryAttachments']['attachment']:
                try:
                    full_url = attachment['urls'][0]['url']['@href']
                    image_urls.append(full_url.split("/ORIG")[0])
                except Exception as e:
                    print("Unable to add image url")
                # full_url = attachment['urls'][0]['url']['@href']
                # image_urls.append(full_url.split("/ORIG")[0])
            expose['images'] = image_urls
        except Exception as e:
            self.__log__.warning("Unable to find image urls: ", e)
            expose['images'] = []

        self.driver.get(expose['url'])
        try:
            description_texts = self.driver.execute_script("let list = []; document.querySelectorAll("
                                                           "'pre.text-content').forEach(el => "
                                                           "list.push(el.childNodes[0])); return list;")
            expose['description'] = "\n".join([description['textContent'] for description in description_texts])
        except Exception as e:
            self.__log__.warning("Unable to find description: ", e)

        return expose

    def get_page(self, search_url, driver=None, page_no=None):
        """Applies a page number to a formatted search URL and fetches the exposes at that page"""
        return self.get_soup_from_url(
            search_url.format(page_no),
            driver=driver,
            checkbox=self.checkbox,
            afterlogin_string=self.afterlogin_string
        )

    def get_expose_details(self, expose):
        """Loads additional details for an expose by processing the expose detail URL"""
        soup = self.get_soup_from_url(expose['url'])
        date = soup.find('dd', {"class": "is24qa-bezugsfrei-ab"})
        expose['from'] = datetime.datetime.now().strftime("%2d.%2m.%Y")
        if date is not None:
            if not re.match(r'.*sofort.*', date.text):
                expose['from'] = date.text.strip()
        return expose

    # pylint: disable=too-many-locals
    # pylint: disable=too-many-branches
    def extract_data(self, soup):
        """Extracts all exposes from a provided Soup object"""
        entries = []

        results_list = soup.find(id="resultListItems")
        title_elements = results_list.find_all(
            lambda e: e.name == 'a' and e.has_attr('class') and \
                      'result-list-entry__brand-title-container' in e['class']
        ) if results_list else []
        expose_ids = []
        expose_urls = []
        for link in title_elements:
            expose_id = int(link.get('href').split('/')[-1].replace('.html', ''))
            expose_ids.append(expose_id)
            if len(str(expose_id)) > 5:
                expose_urls.append('https://www.immobilienscout24.de/expose/' + str(expose_id))
            else:
                expose_urls.append(link.get('href'))
        self.__log__.debug(expose_ids)

        attr_container_els = soup.find_all(
          lambda e: e.has_attr('data-is24-qa') and \
                    e['data-is24-qa'] == "attributes"
          )
        address_fields = soup.find_all(
          lambda e: e.has_attr('class') and \
                    'result-list-entry__address' in e['class']
          )
        gallery_elements = soup.find_all(
          lambda e: e.has_attr('class') and \
                    'result-list-entry__gallery-container' in e['class']
        )
        for idx, title_el in enumerate(title_elements):
            attr_els = attr_container_els[idx].find_all('dd')
            try:
                address = address_fields[idx].text.strip()
            except AttributeError:
                address = "No address given"

            gallery_tag = gallery_elements[idx].find("div", {"class": "gallery-container"})
            if gallery_tag is not None:
                image_tag = gallery_tag.find("img")
                try:
                    image = image_tag["src"]
                except KeyError:
                    image = image_tag["data-lazy-src"]
            else:
                image = None

            details = {
                'id': expose_ids[idx],
                'url': expose_urls[idx],
                'image': image,
                'title': title_el.text.strip().replace('NEU', ''),
                'address': address,
                'crawler': self.get_name()
            }
            if len(attr_els) > 2:
                details['price'] = attr_els[0].text.strip().split(' ')[0].strip()
                details['size'] = attr_els[1].text.strip().split(' ')[0].strip() + " qm"
                details['rooms'] = attr_els[2].text.strip().split(' ')[0].strip()
            else:
                # If there are less than three elements, it is unclear which is what.
                details['price'] = ''
                details['size'] = ''
                details['rooms'] = ''

            exist = False
            for expose in entries:
                if expose_id == expose["id"]:
                    exist = True
                    break
            if not exist:
                entries.append(details)

        self.__log__.debug('extracted: %d', len(entries))
        return entries

    def login(self, driver: WebDriver):
        """Logs in to the website"""
        self.__log__.info("Logging in to immobilienscout24.de")
        current_url = driver.current_url
        driver.get("https://www.immobilienscout24.de/geschlossenerbereich/start.html?source=meinkontodropdown-login")
        driver.find_element(By.ID, "username").send_keys(self.config.get("immoscout", {}).get("user"))
        driver.execute_script("document.getElementById('submit').click()")
        driver.find_element(By.ID, "password").send_keys(self.config.get("immoscout", {}).get("password"))
        driver.execute_script("document.getElementById('loginOrRegistration').click()")
        time.sleep(5)
        driver.get(current_url)
        self.__log__.info("Logged in to immobilienscout24.de")