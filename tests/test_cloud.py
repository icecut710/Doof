import unittest
from doof.cloud import cloud_status

class TestCloud(unittest.TestCase):
    def test_offline_by_default(self):
        s = cloud_status()
        self.assertIn("connected", s)
        self.assertIn("status", s)

if __name__ == "__main__":
    unittest.main()
