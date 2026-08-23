import unittest
from doof.api import hardware

class TestHardware(unittest.TestCase):
    def test_hardware_keys(self):
        h = hardware()
        self.assertIn("device", h)
        self.assertIn("cuda_available", h)
        self.assertIn("torch_version", h)

if __name__ == "__main__":
    unittest.main()
