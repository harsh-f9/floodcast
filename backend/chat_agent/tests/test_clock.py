import os as _os
import sys as _sys
_BACKEND = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
for _p in (_BACKEND, _os.path.join(_BACKEND, "Flood_prediction")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import unittest
from unittest.mock import patch

from chat_agent import agent, clock
from chat_agent import tools


class TestClock(unittest.TestCase):
    def tearDown(self):
        clock._override.set("")

    def test_set_valid_invalid_reset(self):
        tok = clock.set_today("2026-09-27")
        self.assertTrue(tok)
        self.assertEqual(clock.today_ist().isoformat(), "2026-09-27")
        self.assertEqual(clock.set_today("not-a-date"), "")
        self.assertEqual(clock.set_today("2026-13-99"), "")
        clock.reset_today(tok)
        self.assertEqual(clock._override.get(), "")

    def test_prompt_uses_client_date(self):
        tok = clock.set_today("2026-01-15")
        try:
            prompt = agent.build_system_prompt()
        finally:
            clock.reset_today(tok)
        self.assertIn("2026-01-15", prompt)
        self.assertIn("user-local date", prompt)

    def test_run_agent_resets_clock(self):
        with patch.object(agent, "llm_configured", return_value=False):
            agent.run_agent([{"role": "user", "content": "history of station 0"}],
                            client_today="2026-01-15")
        self.assertEqual(clock._override.get(), "")

    def test_run_agent_logs_effective_today(self):
        with patch.object(agent, "llm_configured", return_value=False):
            with self.assertLogs("chat_agent", level="INFO") as cm:
                agent.run_agent([{"role": "user", "content": "history of station 0"}],
                                client_today="2026-01-15")
        blob = "\n".join(cm.output)
        self.assertIn("2026-01-15", blob)


if __name__ == "__main__":
    unittest.main()
