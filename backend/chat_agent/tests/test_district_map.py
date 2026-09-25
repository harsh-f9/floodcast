import os as _os
import sys as _sys
_BACKEND = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
for _p in (_BACKEND, _os.path.join(_BACKEND, "Flood_prediction")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

import unittest
from chat_agent import district_map


class TestDistrictMap(unittest.TestCase):
    def test_mapping_loads_all_gauges(self):
        m = district_map.gauge_to_district()
        self.assertGreater(len(m), 300, "enriched gauge mapping should cover ~378 gauges")

    def test_districts_list_sane(self):
        ds = district_map.all_districts()
        self.assertGreater(len(ds), 50)
        for known in ("Bijnor", "Lucknow", "Prayagraj"):
            self.assertIn(known, ds)

    def test_stations_resolve_for_known_district(self):
        stations = district_map.stations_for_district("Prayagraj")
        self.assertGreater(len(stations), 0)
        for s in stations:
            self.assertIn("station_id", s)
            self.assertIn("rp_2", s)

    def test_unknown_district_resolves_empty(self):
        self.assertEqual(district_map.stations_for_district("NoSuchDistrict"), [])

    def test_district_of_station(self):
        stations = district_map.stations_for_district("Bijnor")
        self.assertGreater(len(stations), 0)
        self.assertEqual(district_map.district_of_station(stations[0]), "Bijnor")


if __name__ == "__main__":
    unittest.main()
