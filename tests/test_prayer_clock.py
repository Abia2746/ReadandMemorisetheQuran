"""No-GPS, city-level prayer-time ambience tests."""
import unittest
from unittest.mock import patch, Mock
import prayer_clock


class PrayerClockTests(unittest.TestCase):
    def setUp(self):
        prayer_clock._remote_times.cache_clear()

    def test_london_defaults_without_location(self):
        example = {
            "Fajr":"05:40","Sunrise":"07:20","Dhuhr":"11:55",
            "Asr":"14:10","Maghrib":"16:35","Isha":"18:10",
        }
        with patch.object(prayer_clock, "_remote_times", return_value=example) as fetch:
            data = prayer_clock.room_prayer_times()
        self.assertEqual(data["city"],"London")
        self.assertEqual(data["timezone"],"Europe/London")
        self.assertTrue(data["available"])
        self.assertEqual(data["times"]["Maghrib"],"16:35")
        self.assertIn("approximate",data["note"].lower())
        self.assertEqual(fetch.call_args.args[0],"London")
        self.assertIn(fetch.call_args.args[2],(0,1,2,3))

    def test_invalid_city_never_sent_to_remote(self):
        with patch.object(prayer_clock,"_remote_times",return_value={}):
            data=prayer_clock.room_prayer_times("secret address")
        self.assertEqual(data["city"],"London")
        self.assertFalse(data["available"])
        self.assertIn("without", "without GPS data")

    def test_remote_api_fields_sanitized_and_method_explicit(self):
        response=Mock()
        response.raise_for_status=Mock()
        response.json.return_value={
            "data":{"timings":{
                "Fajr":"05:01 (BST)","Sunrise":"07:12","Dhuhr":"12:18",
                "Asr":"14:40","Maghrib":"16:17","Isha":"17:59"
            }}
        }
        with patch.object(prayer_clock.requests,"get",return_value=response) as get:
            timings=prayer_clock._remote_times.__wrapped__("London","19-11-2026",1)
        self.assertEqual(timings["Fajr"],"05:01")
        self.assertEqual(timings["Maghrib"],"16:17")
        self.assertEqual(get.call_args.kwargs["params"]["method"],3)
        self.assertEqual(get.call_args.kwargs["params"]["city"],"London")
        self.assertNotIn("latitude",get.call_args.kwargs["params"])
        self.assertNotIn("longitude",get.call_args.kwargs["params"])

    def test_rejects_incomplete_times(self):
        response=Mock()
        response.json.return_value={"data":{"timings":{"Fajr":"25:99"}}}
        with patch.object(prayer_clock.requests,"get",return_value=response):
            self.assertEqual(prayer_clock._remote_times.__wrapped__("London","19-11-2026",0),{})


if __name__ == "__main__":
    unittest.main()
