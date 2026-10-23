# -*- coding: utf-8 -*-
"""Chạy: python -m unittest discover -s tests -v   (từ thư mục gốc dự án)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.engine import keywords_match, phrase_in  # noqa: E402
from backend.serpapi_client import UNKNOWN_AGE_HOURS, parse_hours_ago  # noqa: E402


class ParseHoursAgo(unittest.TestCase):
    def test_english_and_vietnamese(self):
        self.assertEqual(parse_hours_ago("5 hours ago"), 5.0)
        self.assertEqual(parse_hours_ago("2 ngày trước"), 48.0)
        self.assertEqual(parse_hours_ago("30 minutes ago"), 0.5)

    def test_unknown_is_not_fresh(self):
        self.assertEqual(parse_hours_ago("Oct 21, 2026"), UNKNOWN_AGE_HOURS)
        self.assertEqual(parse_hours_ago(""), UNKNOWN_AGE_HOURS)


class KeywordMatch(unittest.TestCase):
    def test_phrase_boundary(self):
        self.assertTrue(phrase_in("windows 11", "cách cài windows 11 mới"))
        self.assertFalse(phrase_in("ai", "mail về"))

    def test_generic_word_does_not_match(self):
        self.assertFalse(keywords_match("lỗi đăng nhập facebook", "windows 11 lỗi"))

    def test_real_overlap_matches(self):
        self.assertTrue(keywords_match("chatgpt", "chatgpt 5 ra mắt"))
        self.assertTrue(keywords_match("rtx 5090 giá", "card rtx 5090"))


if __name__ == "__main__":
    unittest.main()
