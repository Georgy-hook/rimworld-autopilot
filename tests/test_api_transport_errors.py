"""An incomplete HTTP startup response must stay an explicit API error."""
import unittest
from http.client import BadStatusLine, IncompleteRead, RemoteDisconnected
from unittest.mock import patch

import rimworld_laya as bridge


class ApiTransportErrors(unittest.TestCase):
    def test_invalid_host_status_is_not_an_unhandled_protocol_exception(self):
        error = BadStatusLine('<h1>Bad Request (Invalid host)</h1>HTTP/1.1 400 Bad Request')
        with patch.object(bridge, 'urlopen', side_effect=error):
            with self.assertRaisesRegex(bridge.RimApiError, 'Invalid host') as caught:
                bridge.RimApiClient().get('/api/v1/game/state')
        self.assertIs(caught.exception.__cause__, error)

    def test_truncated_response_is_not_an_empty_success(self):
        error = IncompleteRead(b'{"success":', 20)
        with patch.object(bridge, 'urlopen', side_effect=error):
            with self.assertRaisesRegex(bridge.RimApiError, '/api/v1/game/state') as caught:
                bridge.RimApiClient().get('/api/v1/game/state')
        self.assertIs(caught.exception.__cause__, error)

    def test_remote_disconnect_is_an_explicit_api_failure(self):
        error = RemoteDisconnected('peer closed before its status line')
        with patch.object(bridge, 'urlopen', side_effect=error):
            with self.assertRaisesRegex(bridge.RimApiError, 'peer closed') as caught:
                bridge.RimApiClient().get('/api/v1/game/state')
        self.assertIs(caught.exception.__cause__, error)


if __name__ == '__main__':
    unittest.main()
