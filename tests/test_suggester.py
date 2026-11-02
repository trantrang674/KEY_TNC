# -*- coding: utf-8 -*-
"""Test quy tắc 'keyword gợi ý phải là cụm có nghĩa' (theo bảng keyword mẫu của người dùng)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.classifier import is_smartphone_topic
from backend.seo_suggester import suggest_seo_keywords


def A(*titles):
    return [{"title": t, "source_name": "T"} for t in titles]


def kws(keyword, cid, *titles):
    return [s["keyword"] for s in suggest_seo_keywords(keyword, cid, A(*titles))]


class TestMeaningfulSuggestions(unittest.TestCase):
    def test_generic_suffix_rejected(self):
        self.assertEqual(kws("TikTok", "tiktok", "TikTok cập nhật tính năng mới", "Hướng dẫn TikTok"), [])
        self.assertEqual(kws("VNeID", "vneid", "VNeID tính năng mới nhất"), [])

    def test_event_phrase(self):
        r = kws("Windows 11", "windows 11", "Windows 11 26H2 chạy thành công trên máy chỉ có 128 MB RAM")
        self.assertIn("Windows 11 26H2 chạy thành công", r)

    def test_no_truncated_or_bare_verb(self):
        for k in kws("Windows 11", "windows 11", "Bất ngờ Windows 11 26H2 chạy trên dung lượng RAM vỏn vẹn 128 MB"):
            self.assertFalse(k.lower().endswith((" dung", " trên", " chạy")), k)

    def test_no_repeated_words(self):
        for k in kws("Cách tải và chơi Một Ngày Làm", "x", "Cách tải và chơi Một Ngày Làm Chó, game mô phỏng"):
            words = k.lower().split()
            self.assertEqual(len(words), len(set(words)), k)

    def test_person_long_keyword(self):
        r = kws("Sam Altman", "sam altman", "Sam Altman: 'Thật tệ khi RAM nằm trong máy người dùng'")
        self.assertTrue(r and len(r[0].split()) >= 6, r)
        self.assertIn("RAM", r[0])
        self.assertFalse(r[0].endswith(("người", "khi", "trong")), r)

    def test_smartphone_exceptions(self):
        self.assertFalse(is_smartphone_topic("Apple ra mắt iPhone 18 Pro"))
        self.assertFalse(is_smartphone_topic("Cách thêm lịch World Cup vào điện thoại"))
        self.assertTrue(is_smartphone_topic("Redmi Note 15 Pro ra mắt"))


if __name__ == "__main__":
    unittest.main()
