import unittest
from unittest.mock import MagicMock, patch
from laya_gui import services


class ProcessLiveness(unittest.TestCase):
    def kernel(self, exit_code, opened=12345, query=True):
        api = MagicMock()
        api.OpenProcess.return_value = opened
        def get_exit(handle, pointer):
            pointer._obj.value = exit_code
            return query
        api.GetExitCodeProcess.side_effect = get_exit
        return api

    def check(self, api):
        with patch.object(services.os, 'name', 'nt'), patch.object(services.ctypes, 'windll', MagicMock(kernel32=api), create=True):
            return services.process_running(123)

    def test_retained_terminated_process_handle_is_not_live(self):
        api = self.kernel(0)
        self.assertFalse(self.check(api))
        api.CloseHandle.assert_called_once_with(12345)

    def test_only_still_active_status_is_live(self):
        api = self.kernel(259, opened=0x123456789)
        self.assertTrue(self.check(api))
        api.CloseHandle.assert_called_once_with(0x123456789)

    def test_missing_process_never_queries_exit_status(self):
        api = self.kernel(259, opened=0)
        self.assertFalse(self.check(api))
        api.GetExitCodeProcess.assert_not_called()
        api.CloseHandle.assert_not_called()

    def test_failed_exit_query_is_not_a_live_worker(self):
        api = self.kernel(259, query=False)
        self.assertFalse(self.check(api))
        api.CloseHandle.assert_called_once_with(12345)


if __name__ == '__main__':
    unittest.main()
