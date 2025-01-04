import unittest
from src.astreum.machine import AstreumMachine

class TestAstreumMachine(unittest.TestCase):
    def setUp(self):
        """Set up the AstreumMachine instance and create a user session."""
        self.machine = AstreumMachine()
        self.session_id = self.machine.create_session()
    
    def tearDown(self):
        """Terminate the user session after each test."""
        self.machine.terminate_session(self.session_id)

    def test_int_addition(self):
        """Test that adding integers evaluates to the correct result."""
        code = '(+ 2 3)'
        result = self.machine.evaluate_code(code, self.session_id)

        self.assertEqual(result.value, 5, "Integer addition result does not match expected output")


    def test_int_definition(self):
        """Test that defining an integer variable works and querying it returns the value."""
        define_code = '(def numero 42)'
        result = self.machine.evaluate_code(define_code, self.session_id)

        query_code = '(numero)'
        result = self.machine.evaluate_code(query_code, self.session_id)

        self.assertEqual(result.value, 42, "Queried variable does not have the expected value")


if __name__ == "__main__":
    unittest.main()
