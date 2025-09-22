"""Unit tests for the trade signal parser."""

import unittest
import sys
from pathlib import Path

# Add project root to sys.path so `trading` package can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trading.signal_parser import parse_discord_message, SignalParserError


class TestSignalParser(unittest.TestCase):
    def test_parse_valid_message(self):
        msg = "AAPL - $250 CALLS EXPIRATION 10/10 $1.29 STOP LOSS AT $1.00"
        signal = parse_discord_message(msg)
        self.assertEqual(signal.symbol, "AAPL")
        self.assertEqual(signal.strike, 250.0)
        self.assertEqual(signal.option_type, "Call")
        # Expiration date should be in the future; we just assert month/day
        self.assertEqual(signal.expiration_date.month, 10)
        self.assertEqual(signal.expiration_date.day, 10)
        self.assertAlmostEqual(signal.entry_price, 1.29)
        self.assertAlmostEqual(signal.stop_price, 1.00)

    def test_parse_invalid_message(self):
        msg = "Invalid format"
        with self.assertRaises(SignalParserError):
            parse_discord_message(msg)


if __name__ == "__main__":
    unittest.main()
