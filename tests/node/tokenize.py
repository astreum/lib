import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astreum.machine import ParseError, tokenize  # noqa: E402


class TestTokenize(unittest.TestCase):
    def test_basic_tokens(self):
        self.assertEqual(tokenize("(1 2 add)"), ["(", "1", "2", "add", ")"])

    def test_whitespace_and_newlines(self):
        src = """
        (  7\n  x   def )
        """
        toks = tokenize(src)
        self.assertEqual(toks, ["(", "7", "x", "def", ")"])

    # Strings are not supported; current tokenizer treats them as raw tokens.
    # This ensures quotes are not dropped silently.
    def test_quotes_are_tokenized(self):
        toks = tokenize('("abc")')
        self.assertIn('"abc"', toks)


if __name__ == "__main__":
    unittest.main()
