"""Regression tests for multilingual YouTube title/thumbnail linting."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "title.py"
SPEC = importlib.util.spec_from_file_location("title_linter", SCRIPT)
title_linter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(title_linter)


def issue_codes(result):
    return {code for code, _ in result["issues"]}


class UnicodeTitleTests(unittest.TestCase):
    def test_unicode_words_preserve_arabic_and_mixed_text(self):
        self.assertEqual(
            title_linter.words("ليه Docker بيقع على السيرفر؟"),
            ["ليه", "docker", "بيقع", "على", "السيرفر"],
        )

    def test_unicode_words_cover_other_scripts_and_combining_marks(self):
        self.assertEqual(
            title_linter.words("Café cafe\u0301 東京 हिन्दी"),
            ["café", "café", "東京", "हिन्दी"],
        )

    def test_arabic_diacritics_and_tatweel_do_not_break_matching(self):
        self.assertEqual(title_linter.words("السِّيـرفر"), ["السيرفر"])
        self.assertEqual(title_linter.words("الكِتاب"), ["الكتاب"])

    def test_apostrophes_and_english_casefold_are_preserved(self):
        self.assertEqual(title_linter.words("It's a Creator’s GUIDE"), ["it's", "a", "creator's", "guide"])

    def test_fully_arabic_title_not_mistaken_for_empty_filler(self):
        result = title_linter.check("ليه التطبيق واقع على السيرفر؟", "السيرفر واقع")
        self.assertNotIn("front-load", issue_codes(result))
        self.assertIn("duplicate", issue_codes(result))
        self.assertTrue(any("السيرفر" in message and "واقع" in message for code, message in result["issues"] if code == "duplicate"))

    def test_common_arabic_function_words_not_flagged_as_duplicate(self):
        result = title_linter.check("إمتى تستخدم Docker في مشروعك؟", "في Production")
        self.assertNotIn("duplicate", issue_codes(result))

    def test_arabic_mixed_language_duplicate_matches_case_insensitively(self):
        result = title_linter.check("Docker في Production", "DOCKER على السيرفر")
        self.assertIn("duplicate", issue_codes(result))

    def test_arabic_question_mark_counts_as_open_question(self):
        result = title_linter.check("ليه السيرفر واقع؟")
        self.assertIn("open question in the title", result["good"])

    def test_arabic_thumbnail_length_counts_words(self):
        result = title_linter.check("أخطاء بتضيع وقتك", "خمس كلمات موجودة في الصورة")
        self.assertIn("thumb-length", issue_codes(result))

    def test_arabic_indic_digit_counts_as_concrete_number(self):
        result = title_linter.check("٣ أخطاء في السيرفر")
        self.assertNotIn("no-number", issue_codes(result))

    def test_english_duplicate_and_vagueness_still_work(self):
        result = title_linter.check("The ultimate Docker guide", "Docker deploy")
        self.assertIn("duplicate", issue_codes(result))
        self.assertIn("vague", issue_codes(result))

    def test_english_title_length_and_nonduplicate_still_work(self):
        result = title_linter.check("x" * 101, "something else")
        self.assertIn("length", issue_codes(result))
        self.assertNotIn("duplicate", issue_codes(result))

    def test_json_output_contains_readable_arabic(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--title", "السيرفر واقع", "--thumb", "السيرفر", "--json"],
            capture_output=True, text=True, check=True, encoding="utf-8",
        )
        self.assertIn("السيرفر", completed.stdout)
        self.assertNotIn("\\u0627", completed.stdout)
        self.assertIn("duplicate", issue_codes(json.loads(completed.stdout)[0]))

    def test_bom_encoded_input_is_read_as_utf8(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "titles.txt"
            file.write_text("ليه السيرفر واقع؟\nDocker على Production\n", encoding="utf-8-sig")
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), str(file), "--json"],
                capture_output=True, text=True, check=True, encoding="utf-8",
            )
            self.assertEqual({r["title"] for r in json.loads(completed.stdout)},
                             {"ليه السيرفر واقع؟", "Docker على Production"})


if __name__ == "__main__":
    unittest.main()
