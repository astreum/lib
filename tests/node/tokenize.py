import unittest
import importlib.util
from pathlib import Path


# Load src/astreum/_node.py directly to access its tokenizer
_node_path = Path(__file__).resolve().parents[2] / "src" / "astreum" / "_node.py"
_spec = importlib.util.spec_from_file_location("_astreum_low_node", str(_node_path))
_mod = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_mod)

tokenize = getattr(_mod, "tokenize")
ParseError = getattr(_mod, "ParseError")


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
