"""
Tests for flight_tracker.py (Amadeus API)
"""
import json
import os
import tempfile
import unittest
from requests.exceptions import RequestException
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from flight_tracker import (
    AmadeusAuth,
    FlightTracker,
    StatusHandler,
    calculate_total_api_requests,
    get_config_mtime,
    load_config,
    validate_config_change,
)
import flight_tracker as ft_module


# ── Helpers ───────────────────────────────────────────────────────────────────

def _amadeus_offer(price: float, carrier: str = "UA", carrier_name: str = "UNITED") -> dict:
    return {
        "id": "offer-1",
        "price": {"total": str(price)},
        "itineraries": [
            {
                "duration": "PT2H30M",
                "segments": [
                    {
                        "carrierCode": carrier,
                        "departure": {"at": "2026-12-20T08:00:00"},
                        "arrival": {"at": "2026-12-20T10:30:00"},
                    }
                ],
            }
        ],
    }


def _amadeus_response(offers: list, carriers: dict = None) -> dict:
    return {
        "data": offers,
        "dictionaries": {"carriers": carriers or {"UA": "UNITED"}},
    }


def _near_date(offset_days: int = 30) -> str:
    return (datetime.now() + timedelta(days=offset_days)).strftime("%Y-%m-%d")


# ── AmadeusAuth ───────────────────────────────────────────────────────────────

class TestAmadeusAuth(unittest.TestCase):

    def _auth(self):
        return AmadeusAuth("key", "secret")

    @patch("flight_tracker.requests.post")
    def test_get_access_token_success(self, mock_post):
        mock_post.return_value.json.return_value = {"access_token": "tok123", "expires_in": 1799}
        mock_post.return_value.raise_for_status = MagicMock()

        token = self._auth().get_access_token()
        self.assertEqual(token, "tok123")
        mock_post.assert_called_once()

    @patch("flight_tracker.requests.post")
    def test_get_access_token_cached(self, mock_post):
        mock_post.return_value.json.return_value = {"access_token": "tok123", "expires_in": 1799}
        mock_post.return_value.raise_for_status = MagicMock()

        auth = self._auth()
        auth.get_access_token()
        auth.get_access_token()
        mock_post.assert_called_once()  # second call uses cache

    @patch("flight_tracker.requests.post")
    def test_get_access_token_expired_refetches(self, mock_post):
        mock_post.return_value.json.return_value = {"access_token": "tok-new", "expires_in": 1799}
        mock_post.return_value.raise_for_status = MagicMock()

        auth = self._auth()
        auth.access_token = "tok-old"
        auth.token_expires_at = datetime.now() - timedelta(seconds=10)

        token = auth.get_access_token()
        self.assertEqual(token, "tok-new")
        mock_post.assert_called_once()

    @patch("flight_tracker.requests.post", side_effect=Exception("timeout"))
    def test_get_access_token_raises_on_error(self, _):
        with self.assertRaises(Exception):
            self._auth().get_access_token()


# ── FlightTracker.get_all_flights / get_best_flight ───────────────────────────

class TestGetAllFlights(unittest.TestCase):

    def setUp(self):
        auth = MagicMock(spec=AmadeusAuth)
        auth.get_access_token.return_value = "tok"
        self.tracker = FlightTracker(auth, "https://webhook.example.com")

    def test_empty_response(self):
        self.assertEqual(self.tracker.get_all_flights({}), [])
        self.assertEqual(self.tracker.get_all_flights({"data": []}), [])

    def test_single_offer_parsed(self):
        data = _amadeus_response([_amadeus_offer(300.0)])
        flights = self.tracker.get_all_flights(data)
        self.assertEqual(len(flights), 1)
        self.assertAlmostEqual(flights[0]["price"], 300.0)
        self.assertEqual(flights[0]["airline"], "UNITED")

    def test_sorted_by_price(self):
        offers = [_amadeus_offer(500.0), _amadeus_offer(200.0), _amadeus_offer(350.0)]
        flights = self.tracker.get_all_flights(_amadeus_response(offers))
        prices = [f["price"] for f in flights]
        self.assertEqual(prices, sorted(prices))

    def test_airline_filter_by_name(self):
        offers = [_amadeus_offer(300.0, "UA", "UNITED"), _amadeus_offer(250.0, "DL", "DELTA")]
        data = _amadeus_response(offers, {"UA": "UNITED", "DL": "DELTA"})
        flights = self.tracker.get_all_flights(data, allowed_airlines=["delta"])
        self.assertEqual(len(flights), 1)
        self.assertEqual(flights[0]["airline"], "DELTA")

    def test_airline_filter_by_code(self):
        offers = [_amadeus_offer(300.0, "UA", "UNITED"), _amadeus_offer(250.0, "DL", "DELTA")]
        data = _amadeus_response(offers, {"UA": "UNITED", "DL": "DELTA"})
        flights = self.tracker.get_all_flights(data, allowed_airlines=["UA"])
        self.assertEqual(len(flights), 1)
        self.assertEqual(flights[0]["airline_code"], "UA")

    def test_get_best_flight_returns_cheapest(self):
        offers = [_amadeus_offer(500.0), _amadeus_offer(200.0)]
        best = self.tracker.get_best_flight(_amadeus_response(offers))
        self.assertAlmostEqual(best["price"], 200.0)

    def test_get_best_flight_empty(self):
        self.assertIsNone(self.tracker.get_best_flight({}))


# ── FlightTracker.search_flights ──────────────────────────────────────────────

class TestSearchFlights(unittest.TestCase):

    def setUp(self):
        auth = MagicMock(spec=AmadeusAuth)
        auth.get_access_token.return_value = "tok"
        self.tracker = FlightTracker(auth, "https://webhook.example.com")

    @patch("flight_tracker.requests.get")
    def test_one_way_params(self, mock_get):
        mock_get.return_value.json.return_value = {"data": []}
        mock_get.return_value.raise_for_status = MagicMock()

        self.tracker.search_flights("DEN", "ORD", "2026-12-20")
        params = mock_get.call_args[1]["params"]
        self.assertEqual(params["originLocationCode"], "DEN")
        self.assertEqual(params["destinationLocationCode"], "ORD")
        self.assertNotIn("returnDate", params)

    @patch("flight_tracker.requests.get")
    def test_round_trip_params(self, mock_get):
        mock_get.return_value.json.return_value = {"data": []}
        mock_get.return_value.raise_for_status = MagicMock()

        self.tracker.search_flights("DEN", "ORD", "2026-12-20", return_date="2026-12-28")
        params = mock_get.call_args[1]["params"]
        self.assertEqual(params["returnDate"], "2026-12-28")

    @patch("flight_tracker.requests.get", side_effect=RequestException("network error"))
    def test_returns_empty_on_error(self, _):
        self.assertEqual(self.tracker.search_flights("DEN", "ORD", "2026-12-20"), {})


# ── FlightTracker.send_webhook_notification ───────────────────────────────────

class TestSendWebhookNotification(unittest.TestCase):

    def setUp(self):
        auth = MagicMock(spec=AmadeusAuth)
        self.tracker = FlightTracker(auth, "https://webhook.example.com")

    @patch("flight_tracker.requests.post")
    def test_payload_fields(self, mock_post):
        mock_post.return_value.raise_for_status = MagicMock()
        flight_info = {
            "price": 299.0, "airline": "UNITED",
            "departure_time": "08:00", "arrival_time": "10:30",
            "duration": "PT2H30M", "segments": 1,
        }
        route_info = {
            "departure": "DEN", "destination": "ORD",
            "date": "2026-12-20", "return_date": "2026-12-28",
            "trip_length": 8, "adults": 1, "max_price": 400,
        }
        self.tracker.send_webhook_notification(flight_info, route_info)
        payload = mock_post.call_args[1]["json"]
        self.assertEqual(payload["route"], "DEN → ORD")
        self.assertEqual(payload["price"], 299.0)
        self.assertEqual(payload["threshold"], 400)

    @patch("flight_tracker.requests.post", side_effect=RequestException("timeout"))
    def test_handles_error_gracefully(self, _):
        # Should not raise
        self.tracker.send_webhook_notification(
            {"price": 100, "airline": "UA", "departure_time": None,
             "arrival_time": None, "duration": None, "segments": 1},
            {"departure": "A", "destination": "B", "date": "2026-01-01",
             "return_date": None, "trip_length": None, "adults": 1, "max_price": 200},
        )


# ── FlightTracker.check_flight_route ─────────────────────────────────────────

class TestCheckFlightRoute(unittest.TestCase):

    def _tracker(self):
        auth = MagicMock(spec=AmadeusAuth)
        auth.get_access_token.return_value = "tok"
        return FlightTracker(auth, "https://webhook.example.com")

    @patch("flight_tracker.time.sleep")
    @patch("flight_tracker.requests.post")
    @patch("flight_tracker.requests.get")
    def test_price_below_threshold_sends_webhook(self, mock_get, mock_post, _sleep):
        mock_get.return_value.json.return_value = _amadeus_response([_amadeus_offer(199.0)])
        mock_get.return_value.raise_for_status = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()

        route = {"departure": "DEN", "destination": "ORD",
                 "date": _near_date(30), "max_price": 300, "adults": 1}
        result = self._tracker().check_flight_route(route, store_all_flights=False)
        self.assertTrue(result)
        mock_post.assert_called_once()

    @patch("flight_tracker.time.sleep")
    @patch("flight_tracker.requests.post")
    @patch("flight_tracker.requests.get")
    def test_price_above_threshold_no_webhook(self, mock_get, mock_post, _sleep):
        mock_get.return_value.json.return_value = _amadeus_response([_amadeus_offer(500.0)])
        mock_get.return_value.raise_for_status = MagicMock()

        route = {"departure": "DEN", "destination": "ORD",
                 "date": _near_date(30), "max_price": 300, "adults": 1}
        result = self._tracker().check_flight_route(route, store_all_flights=False)
        self.assertFalse(result)
        mock_post.assert_not_called()

    def test_excluded_return_date_returns_false(self):
        ret = _near_date(38)
        route = {
            "departure": "DEN", "destination": "ORD",
            "date": _near_date(30), "return_date": ret,
            "exclude_return_dates": [ret], "max_price": 500,
        }
        self.assertFalse(self._tracker().check_flight_route(route, store_all_flights=False))

    def test_departure_more_than_one_year_away_skipped(self):
        route = {
            "departure": "DEN", "destination": "ORD",
            "date": (datetime.now() + timedelta(days=400)).strftime("%Y-%m-%d"),
            "max_price": 500,
        }
        self.assertFalse(self._tracker().check_flight_route(route, store_all_flights=False))

    def test_date_range_more_than_one_year_away_skipped(self):
        far = (datetime.now() + timedelta(days=400)).strftime("%Y-%m-%d")
        route = {
            "departure": "DEN", "destination": "ORD",
            "date_range": {"start": far, "end": far},
            "trip_length_days": 7, "trip_flex_days": 0,
            "max_price": 500,
        }
        self.assertFalse(self._tracker().check_flight_route(route, store_all_flights=False))

    @patch("flight_tracker.time.sleep")
    @patch("flight_tracker.requests.get")
    def test_empty_search_results_returns_false(self, mock_get, _sleep):
        mock_get.return_value.json.return_value = {}
        mock_get.return_value.raise_for_status = MagicMock()

        route = {"departure": "DEN", "destination": "ORD",
                 "date": _near_date(30), "max_price": 500}
        self.assertFalse(self._tracker().check_flight_route(route, store_all_flights=False))

    @patch("flight_tracker.time.sleep")
    @patch("flight_tracker.requests.post")
    @patch("flight_tracker.requests.get")
    def test_date_range_makes_one_call_per_outbound_date(self, mock_get, mock_post, _sleep):
        mock_get.return_value.json.return_value = _amadeus_response([_amadeus_offer(150.0)])
        mock_get.return_value.raise_for_status = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()

        start = _near_date(10)
        end = _near_date(12)  # 3 outbound dates
        route = {
            "departure": "DEN", "destination": "ORD",
            "date_range": {"start": start, "end": end},
            "trip_length_days": 7, "trip_flex_days": 0,
            "max_price": 300, "adults": 1,
        }
        self._tracker().check_flight_route(route, store_all_flights=False)
        self.assertEqual(mock_get.call_count, 3)

    def test_must_include_dates_filters_incompatible_trips(self):
        """Trips that don't span a required date should be skipped with no API calls."""
        start = _near_date(10)
        end = _near_date(12)
        must_date = _near_date(30)
        route = {
            "departure": "DEN", "destination": "ORD",
            "date_range": {"start": start, "end": end},
            "trip_length_days": 3, "trip_flex_days": 0,
            "must_include_dates": [must_date],
            "max_price": 500,
        }
        with patch("flight_tracker.requests.get") as mock_get:
            self._tracker().check_flight_route(route, store_all_flights=False)
            mock_get.assert_not_called()

    def test_fixed_dates_not_covering_required_dates_returns_false(self):
        route = {
            "departure": "DEN", "destination": "ORD",
            "date": _near_date(10), "return_date": _near_date(15),
            "must_include_dates": [_near_date(30)],
            "max_price": 500,
        }
        self.assertFalse(self._tracker().check_flight_route(route, store_all_flights=False))

    @patch("flight_tracker.time.sleep")
    @patch("flight_tracker.requests.post")
    @patch("flight_tracker.requests.get")
    def test_only_best_price_triggers_single_webhook(self, mock_get, mock_post, _sleep):
        """Multiple cheap dates should still only fire one webhook (the cheapest)."""
        mock_get.return_value.json.return_value = _amadeus_response([_amadeus_offer(150.0)])
        mock_get.return_value.raise_for_status = MagicMock()
        mock_post.return_value.raise_for_status = MagicMock()

        start = _near_date(10)
        end = _near_date(12)
        route = {
            "departure": "DEN", "destination": "ORD",
            "date_range": {"start": start, "end": end},
            "trip_length_days": 7, "trip_flex_days": 0,
            "max_price": 300, "adults": 1,
        }
        self._tracker().check_flight_route(route, store_all_flights=False)
        mock_post.assert_called_once()


# ── StatusHandler ─────────────────────────────────────────────────────────────

class TestStatusHandler(unittest.TestCase):

    def _make_handler(self, path: str):
        handler = StatusHandler.__new__(StatusHandler)
        handler.path = path
        handler.wfile = MagicMock()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        return handler

    def test_root_returns_200(self):
        self._make_handler("/").do_GET()

    def test_status_endpoint_returns_200(self):
        h = self._make_handler("/status")
        h.do_GET()
        h.send_response.assert_called_with(200)

    def test_flights_endpoint_returns_200(self):
        h = self._make_handler("/flights")
        h.do_GET()
        h.send_response.assert_called_with(200)

    def test_unknown_path_returns_404(self):
        h = self._make_handler("/unknown")
        h.do_GET()
        h.send_response.assert_called_with(404)

    def test_status_endpoint_returns_valid_json(self):
        h = self._make_handler("/status")
        h.do_GET()
        written = b"".join(call.args[0] for call in h.wfile.write.call_args_list)
        parsed = json.loads(written.decode())
        self.assertIn("status", parsed)


# ── Utility functions ─────────────────────────────────────────────────────────

class TestUtilityFunctions(unittest.TestCase):

    def test_load_config_valid(self):
        data = {"amadeus_api_key": "k", "routes": []}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name
        try:
            self.assertEqual(load_config(path)["amadeus_api_key"], "k")
        finally:
            os.unlink(path)

    def test_load_config_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_config("/nonexistent/config.json")

    def test_get_config_mtime_existing_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            self.assertIsNotNone(get_config_mtime(path))
        finally:
            os.unlink(path)

    def test_get_config_mtime_nonexistent_returns_none(self):
        self.assertIsNone(get_config_mtime("/nonexistent/path.json"))

    def test_validate_config_change_valid(self):
        good = {
            "amadeus_api_key": "k", "amadeus_api_secret": "s",
            "webhook_url": "https://wh",
            "routes": [{"departure": "A", "destination": "B"}],
        }
        self.assertTrue(validate_config_change({}, good))

    def test_validate_config_change_missing_key(self):
        bad = {"amadeus_api_secret": "s", "webhook_url": "https://wh", "routes": [{}]}
        self.assertFalse(validate_config_change({}, bad))

    def test_validate_config_change_no_routes(self):
        bad = {"amadeus_api_key": "k", "amadeus_api_secret": "s",
               "webhook_url": "u", "routes": []}
        self.assertFalse(validate_config_change({}, bad))

    def test_validate_config_change_env_override(self):
        cfg = {"amadeus_api_secret": "s", "webhook_url": "u", "routes": [{"x": 1}]}
        with patch.dict(os.environ, {"AMADEUS_API_KEY": "env-key"}):
            self.assertTrue(validate_config_change({}, cfg))

    def test_calculate_total_api_requests(self):
        routes = [
            {"departure": "A", "destination": "B",
             "outbound_dates": ["d1", "d2"], "return_dates": ["r1", "r2"]},
            {"departure": "C", "destination": "D",
             "outbound_dates": ["d1"], "return_dates": []},
        ]
        result = calculate_total_api_requests(routes)
        self.assertEqual(result["total_per_check"], 5)  # 2*2 + 1*1
        self.assertEqual(len(result["per_route"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
