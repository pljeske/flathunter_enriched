"""Interface for webcrawlers. Crawler implementations should subclass this"""
import re
import logging
from time import sleep
import backoff
import requests
import selenium
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium import webdriver
from bs4 import BeautifulSoup
from random_user_agent.user_agent import UserAgent
from random_user_agent.params import HardwareType, Popularity

from flathunter import proxies
from flathunter.captcha.captcha_solver import CaptchaUnsolvableError

class Crawler:
    """Defines the Crawler interface"""

    __log__ = logging.getLogger('flathunt')
    URL_PATTERN = None

    def __init__(self, config):
        self.config = config
        if config.captcha_enabled():
            self.captcha_solver = config.get_captcha_solver()

    user_agent_rotator = UserAgent(popularity=[Popularity.COMMON.value],
                                   hardware_types=[HardwareType.COMPUTER.value])

    HEADERS = {
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': user_agent_rotator.get_random_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;'
                  'q=0.9,image/webp,image/apng,*/*;q=0.8,'
                  'application/signed-exchange;v=b3;q=0.9',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-User': '?1',
        'Sec-Fetch-Dest': 'document',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    def configure_driver(self, driver_path, driver_arguments):
        """Configure ChromeDriver"""
        chrome_options = Options()
        if driver_arguments is not None:
            for driver_argument in driver_arguments:
                chrome_options.add_argument(driver_argument)
        driver = webdriver.Chrome(executable_path=driver_path, options=chrome_options)
        driver.execute_cdp_cmd('Network.setBlockedURLs', {
          "urls": ["https://api.geetest.com/get.*"]
        })
        driver.execute_cdp_cmd('Network.enable', {})
        return driver

    def rotate_user_agent(self):
        """Choose a new random user agent"""
        self.HEADERS['User-Agent'] = self.user_agent_rotator.get_random_user_agent()

    # pylint: disable=unused-argument
    def get_page(self, search_url, driver=None, page_no=None):
        """Applies a page number to a formatted search URL and fetches the exposes at that page"""
        return self.get_soup_from_url(search_url)

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
            return BeautifulSoup(driver.page_source, 'html.parser')
        return BeautifulSoup(resp.content, 'html.parser')

    def get_soup_with_proxy(self, url):
        """Will try proxies until it's possible to crawl and return a soup"""
        resolved = False
        resp = None

        # We will keep trying to fetch new proxies until one works
        while not resolved:
            proxies_list = proxies.get_proxies()
            for proxy in proxies_list:
                self.rotate_user_agent()

                try:
                    # Very low proxy read timeout, or it will get stuck on slow proxies
                    resp = requests.get(
                      url,
                      headers=self.HEADERS,
                      proxies={"http": proxy, "https": proxy},
                      timeout=(20, 0.1)
                    )

                    if resp.status_code != 200:
                        self.__log__.error("Got response (%i): %s", resp.status_code, resp.content)
                    else:
                        resolved = True
                        break

                except requests.exceptions.ConnectionError:
                    self.__log__.error("Connection failed for proxy %s. Trying new proxy...", proxy)
                except requests.exceptions.Timeout:
                    self.__log__.error(
                      "Connection timed out for proxy %s. Trying new proxy...", proxy
                    )
                except requests.exceptions.RequestException:
                    self.__log__.error("Some error occurred. Trying new proxy...")

        if not resp:
            raise Exception("An error occurred while fetching proxies or content")

        return BeautifulSoup(resp.content, 'html.parser')

    def extract_data(self, soup):
        """Should be implemented in subclass"""
        raise NotImplementedError

    # pylint: disable=unused-argument
    def get_results(self, search_url, max_pages=None):
        """Loads the exposes from the site, starting at the provided URL"""
        self.__log__.debug("Got search URL %s", search_url)

        # load first page
        soup = self.get_page(search_url)

        # get data from first page
        entries = self.extract_data(soup)
        self.__log__.debug('Number of found entries: %d', len(entries))

        return entries

    def crawl(self, url, max_pages=None):
        """Load as many exposes as possible from the provided URL"""
        if re.search(self.URL_PATTERN, url):
            try:
                return self.get_results(url, max_pages)
            except requests.exceptions.ConnectionError:
                self.__log__.warning("Connection to %s failed. Retrying.", url.split('/')[2])
                return []
        return []

    def get_name(self):
        """Returns the name of this crawler"""
        return type(self).__name__

    def get_expose_details(self, expose):
        """Loads additional detalis for an expose. Should be implemented in the subclass"""
        return expose

    @backoff.on_exception(wait_gen=backoff.constant,
                          exception=CaptchaUnsolvableError,
                          max_tries=3)
    def resolve_geetest(self, driver):
        """Resolve GeeTest Captcha"""
        data = re.findall(
            "geetest_validate: obj.geetest_validate,\n.*?data: \"(.*)\"",
            driver.page_source
        )[0]
        result = re.findall(r"initGeetest\({(.*?)}", driver.page_source, re.DOTALL)

        geetest = re.findall("gt: \"(.*?)\"", result[0])[0]
        challenge = re.findall("challenge: \"(.*?)\"", result[0])[0]
        try:
            captcha_response = self.captcha_solver.solve_geetest(
                geetest,
                challenge,
                driver.current_url
            )
            script = (f'solvedCaptcha({{geetest_challenge: "{captcha_response.challenge}",'
                      f'geetest_seccode: "{captcha_response.sec_code}",'
                      f'geetest_validate: "{captcha_response.validate}",'
                      f'data: "{data}"}});')
            driver.execute_script(script)
            sleep(2)
        except CaptchaUnsolvableError:
            driver.refresh()
            raise


    @backoff.on_exception(wait_gen=backoff.constant,
                          exception=CaptchaUnsolvableError,
                          max_tries=3)
    def resolve_recaptcha(self, driver, checkbox: bool, afterlogin_string: str = ""):
        """Resolve Captcha"""
        iframe_present = self._wait_for_iframe(driver)
        if checkbox is False and afterlogin_string == "" and iframe_present:
            google_site_key = driver \
                .find_element_by_class_name("g-recaptcha") \
                .get_attribute("data-sitekey")

            try:
                captcha_result = self.captcha_solver.solve_recaptcha(
                    google_site_key,
                    driver.current_url
                ).result

                driver.execute_script(
                    f'document.getElementById("g-recaptcha-response").innerHTML="{captcha_result}";'
                )

                # TODO: Below function call can be different depending on the websites
                #  implementation. It is responsible for sending the promise that we
                #  get from recaptcha_answer. For now, if it breaks, it is required to
                #  reverse engineer it by hand. Not sure if there is a way to automate it.
                driver.execute_script(f'solvedCaptcha("{captcha_result}")')
                self._wait_until_iframe_disappears(driver)
            except CaptchaUnsolvableError:
                driver.refresh()
                raise
        else:
            if checkbox:
                self._clickcaptcha(driver, checkbox)
            else:
                self._wait_for_captcha_resolution(driver, checkbox, afterlogin_string)

    def _clickcaptcha(self, driver, checkbox: bool):
        driver.switch_to.frame(driver.find_element_by_tag_name("iframe"))
        recaptcha_checkbox = driver.find_element_by_class_name("recaptcha-checkbox-checkmark")
        recaptcha_checkbox.click()
        self._wait_for_captcha_resolution(driver, checkbox)
        driver.switch_to.default_content()

    def _wait_for_captcha_resolution(self, driver, checkbox: bool, afterlogin_string=""):
        if checkbox:
            try:
                WebDriverWait(driver, 120).until(
                    EC.visibility_of_element_located((By.CLASS_NAME, "recaptcha-checkbox-checked"))
                )
            except selenium.common.exceptions.TimeoutException:
                print("Selenium.Timeoutexception")
        else:
            xpath_string = f"//*[contains(text(), '{afterlogin_string}')]"
            try:
                WebDriverWait(driver, 120) \
                  .until(EC.visibility_of_element_located((By.XPATH, xpath_string)))
            except selenium.common.exceptions.TimeoutException:
                print("Selenium.Timeoutexception")

    def _wait_for_iframe(self, driver: selenium.webdriver.Chrome):
        """Wait for iFrame to appear"""
        try:
            iframe = WebDriverWait(driver, 10).until(EC.visibility_of_element_located(
                (By.CSS_SELECTOR, "iframe[src^='https://www.google.com/recaptcha/api2/anchor?']")))
            return iframe
        except NoSuchElementException:
            print("No iframe found, therefore no chaptcha verification necessary")
            return None

    def _wait_until_iframe_disappears(self, driver: selenium.webdriver.Chrome):
        """Wait for iFrame to disappear"""
        try:
            WebDriverWait(driver, 10).until(EC.invisibility_of_element(
                (By.CSS_SELECTOR, "iframe[src^='https://www.google.com/recaptcha/api2/anchor?']")))
        except NoSuchElementException:
            print("Element not found")
