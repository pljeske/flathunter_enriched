import pytest
import json
import os

from flathunter.crawl_immobilienscout import CrawlImmobilienscout
from flathunter.config import Config

DUMMY_CONFIG = """
urls:
  - https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten?numberofrooms=2.0-&price=-1500.0&livingspace=70.0-&sorting=2&pagenumber=1
    """


TEST_URL = 'https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten?numberofrooms=2.0-&price=-1500.0&livingspace=70.0-&sorting=2&pagenumber=1'

@pytest.fixture
def crawler():
    return CrawlImmobilienscout(Config(string=DUMMY_CONFIG))

def test_parse_exposes_from_json(crawler):
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "fixtures", "immo-scout-IS24-object.json")) as fixture:
        data = json.load(fixture)
    entries = crawler.get_entries_from_json(data)
    assert len(entries) > 0

def test_crawl_works(crawler):
    soup = crawler.get_page(TEST_URL, page_no=1)
    assert soup is not None
    entries = crawler.extract_data(soup)
    assert entries is not None
    assert len(entries) > 0
    assert entries[0]['id'] > 0
    assert entries[0]['url'].startswith("https://www.immobilienscout24.de/expose")
    for attr in [ 'title', 'price', 'size', 'rooms', 'address' ]:
        assert entries[0][attr] is not None

def test_process_expose_fetches_details(crawler):
    soup = crawler.get_page(TEST_URL, page_no=1)
    assert soup is not None
    entries = crawler.extract_data(soup)
    assert entries is not None
    assert len(entries) > 0
    updated_entries = [ crawler.get_expose_details(expose) for expose in entries ]
    for expose in updated_entries:
        for attr in [ 'title', 'price', 'size', 'rooms', 'address', 'from' ]:
            assert expose[attr] is not None
