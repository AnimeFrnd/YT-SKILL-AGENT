"""Regression smoke tests for the standalone ChatGPT/Codex hook scorer.

Run with: python3 -m unittest discover -s openai/yt-script/tests -v
Python 3 stdlib only.
"""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "hookscore.py"
FORMULAS = ROOT / "references" / "hooks.json"

spec = importlib.util.spec_from_file_location("openai_yt_hookscore", SCRIPT)
hookscore = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hookscore)


class FormulaTests(unittest.TestCase):
    def test_contains_21_distinct_formulas(self):
        data = json.loads(FORMULAS.read_text(encoding="utf-8"))
        self.assertEqual(len(data["hooks"]), 21)
        self.assertEqual(len({h["id"] for h in data["hooks"]}), 21)
        for formula in data["hooks"]:
            self.assertIn("name", formula)
            self.assertIn("shape", formula)
            self.assertIsInstance(formula["match"], list)

    def test_english_hook_dimensions(self):
        item = hookscore.score(
            "Why does your Docker application fail on a production server?"
        )
        self.assertEqual(item["language"], "English")
        self.assertEqual(len(item["properties"]), 5)
        self.assertTrue(all(0 <= p <= 100 for p in item["properties"].values()))
        self.assertGreaterEqual(item["verdict"], 0)
        self.assertLessEqual(item["verdict"], 100)
        self.assertEqual(item["formula"], "The Question")

    def test_arabic_hook_and_question_mark(self):
        item = hookscore.score(
            "ليه تطبيق Docker شغال عندك لكن على الـ VPS مش بيفتح؟"
        )
        self.assertEqual(item["language"], "Arabic/mixed")
        self.assertEqual(item["formula"], "The Question")
        self.assertGreater(item["properties"]["CURIOSITY"], 24)

    def test_scores_do_not_claim_performance_prediction(self):
        item = hookscore.score("What happens if you skip the backup?")
        self.assertIn("not a measured retention", item["note"])


class CLITests(unittest.TestCase):
    def run_cli(self, *args, cwd=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            cwd=cwd,
            text=True,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    def test_json_single_hook_from_unrelated_workdir(self):
        with tempfile.TemporaryDirectory() as directory:
            process = self.run_cli(
                "--json", "--hook", "Why does your Docker build fail?", cwd=directory
            )
        self.assertEqual(process.returncode, 0, process.stderr)
        data = json.loads(process.stdout)
        self.assertEqual(len(data), 1)
        self.assertIn("verdict", data[0])

    def test_file_ranking_and_blank_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            filepath = Path(directory) / "hooks.txt"
            filepath.write_text(
                "Why does your Docker deploy fail?\n\n"
                "ليه تطبيقك مش بيشتغل على السيرفر؟\n",
                encoding="utf-8",
            )
            process = self.run_cli("--json", filepath)
        self.assertEqual(process.returncode, 0, process.stderr)
        scores = json.loads(process.stdout)
        self.assertEqual(len(scores), 2)
        self.assertGreaterEqual(scores[0]["verdict"], scores[1]["verdict"])

    def test_empty_file_exits_cleanly_with_message(self):
        with tempfile.TemporaryDirectory() as directory:
            filepath = Path(directory) / "empty.txt"
            filepath.write_text("  \n\n", encoding="utf-8")
            process = self.run_cli("--json", filepath)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("no nonblank hooks", process.stderr)

    def test_english_report_hints_are_in_english(self):
        process = self.run_cli("--hook", "Why does your Docker build fail?")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("weakest", process.stdout)
        self.assertFalse(any("\u0600" <= c <= "\u06ff" for c in process.stdout))

    def test_requires_single_input_mode(self):
        process = self.run_cli()
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("provide --hook TEXT or FILE", process.stderr)


if __name__ == "__main__":
    unittest.main()
