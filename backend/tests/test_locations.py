import unittest

from app.locations import normalize_location, BUCKET_ORDER


class TestNormalizeLocation(unittest.TestCase):
    def test_uae_cities(self):
        for city in ["Dubai", "Abu Dhabi", "Sharjah", "UAE"]:
            with self.subTest(city=city):
                self.assertEqual(normalize_location(city), "UAE")

    def test_india_cities(self):
        for city in ["Bangalore", "Mumbai", "Delhi", "Pune", "Bengaluru"]:
            with self.subTest(city=city):
                self.assertEqual(normalize_location(city), "India")

    def test_germany_cities(self):
        for city in ["Berlin", "Munich", "Frankfurt"]:
            with self.subTest(city=city):
                self.assertEqual(normalize_location(city), "Germany")

    def test_uk_cities(self):
        for city in ["London", "UK", "United Kingdom"]:
            with self.subTest(city=city):
                self.assertEqual(normalize_location(city), "UK")

    def test_remote(self):
        self.assertEqual(normalize_location("Remote"), "Remote")

    def test_unknown_falls_back_to_other(self):
        self.assertEqual(normalize_location("Nowhereville"), "Other")

    def test_none_and_empty_are_other(self):
        self.assertEqual(normalize_location(None), "Other")
        self.assertEqual(normalize_location(""), "Other")

    def test_compound_location_string(self):
        self.assertEqual(normalize_location("Berlin, Germany"), "Germany")
        self.assertEqual(normalize_location("Dubai, UAE"), "UAE")

    def test_bucket_order_constant(self):
        self.assertEqual(BUCKET_ORDER, ["All", "UAE", "India", "Germany", "UK", "Remote", "Other"])


if __name__ == "__main__":
    unittest.main()
