import os as _os
import sys as _sys
_BACKEND = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
for _p in (_BACKEND, _os.path.join(_BACKEND, "Flood_prediction")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import json
import logging
import unittest

from chat_agent import log as chat_log


class TestRequestLogging(unittest.TestCase):
    def test_event_carries_request_id_as_json(self):
        chat_log.bind("test1234")
        with self.assertLogs("chat_agent", level="INFO") as cm:
            chat_log.event("unit.probe", foo="bar", n=3)
        line = cm.output[0]
        payload = json.loads(line.split("INFO:chat_agent:", 1)[1])
        self.assertEqual(payload["rid"], "test1234")
        self.assertEqual(payload["stage"], "unit.probe")
        self.assertEqual(payload["foo"], "bar")
        self.assertIn("ts", payload)

    def test_default_id_when_unbound(self):
        chat_log.bind("-")
        self.assertEqual(chat_log.rid(), "-")

    def test_non_serializable_values_coerced(self):
        chat_log.bind("t")
        with self.assertLogs("chat_agent", level="INFO"):
            chat_log.event("unit.probe", weird={"a", "set"})
        # no raise = pass

    def test_never_raises(self):
        chat_log.event("unit.probe", level="not-a-level", x=object())
        # pass if no exception escapes


if __name__ == "__main__":
    unittest.main()
