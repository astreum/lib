import unittest
from src.astreum.machine import AstreumMachine
from src.astreum.machine.expression import Expr

class TestAstreumMachine(unittest.TestCase):
    def setUp(self):
        """Set up the AstreumMachine instance and create a user session."""
        self.machine = AstreumMachine()
        self.session_id = self.machine.create_session()
    
    def tearDown(self):
        """Terminate the user session after each test."""
        self.machine.terminate_session(self.session_id)
    
    def test_string_in_brackets(self):
        """Test that a simple string in brackets evaluates to the string."""
        code = '("hello world")'
        result, error = self.machine.evaluate_code(code, self.session_id)
        self.assertEqual(result.value, '("hello world")', "String value does not match expected output")

    def test_int_in_brackets(self):
        """Test that a simple integer in brackets evaluates to the integer."""
        code = '(42)'
        result, error = self.machine.evaluate_code(code, self.session_id)
        self.assertIsNone(error, "Error occurred while evaluating code")
        self.assertEqual(result.value, "(42)", "Integer value does not match expected output")

    def test_int_addition(self):
        """Test that adding integers evaluates to the correct result."""
        code = '(+ 2 3)'
        result, error = self.machine.evaluate_code(code, self.session_id)

        # Assert that there is no error
        self.assertIsNone(error, "Error occurred while evaluating code")

        # Assert that the result is the correct sum
        self.assertEqual(result.value, 5, "Integer addition result does not match expected output")


if __name__ == "__main__":
    unittest.main()
