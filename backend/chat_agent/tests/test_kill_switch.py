import os as _os
import sys as _sys
_BACKEND = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
for _p in (_BACKEND, _os.path.join(_BACKEND, "Flood_prediction")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import os
import unittest
from chat_agent import kill_switch


class TestKillSwitch(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.pop("CHAT_ENABLED", None)
        kill_switch.CHAT_ENABLED = True

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("CHAT_ENABLED", None)
        else:
            os.environ["CHAT_ENABLED"] = self._prev
        kill_switch.CHAT_ENABLED = True

    def test_enabled_by_default(self):
        self.assertTrue(kill_switch.is_enabled())

    def test_flag_off_disables(self):
        kill_switch.CHAT_ENABLED = False
        self.assertFalse(kill_switch.is_enabled())

    def test_env_overrides_flag(self):
        for v in ("0", "false", "off", "no"):
            os.environ["CHAT_ENABLED"] = v
            self.assertFalse(kill_switch.is_enabled(), v)
        os.environ["CHAT_ENABLED"] = "1"
        self.assertTrue(kill_switch.is_enabled())


if __name__ == "__main__":
    unittest.main()
