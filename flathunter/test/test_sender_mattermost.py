import unittest

import requests_mock

from flathunter.sender_mattermost import SenderMattermost


class SenderMattermostTest(unittest.TestCase):

    @requests_mock.Mocker()
    def test_send_message(self, m):
        sender = SenderMattermost({"mattermost": {
            "webhook_url": "http://example.com/dummy_webhook_url"}})

        m.post('http://example.com/dummy_webhook_url')
        self.assertEqual(None, sender.send_msg("result"),
                         "Expected message to be sent")
