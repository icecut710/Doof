"""Update client: version compare, checksum reject, no blind execute."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from doof.updates.client import UpdateStatus, _newer, _parse_ver, check_for_update, current_version


class VersionTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(_parse_ver("0.3.0")[:3], (0, 3, 0))
        self.assertEqual(_parse_ver("v1.2.3-beta")[:3], (1, 2, 3))

    def test_newer(self):
        self.assertTrue(_newer("0.3.0", "0.2.1"))
        self.assertFalse(_newer("0.2.1", "0.3.0"))
        self.assertFalse(_newer("0.3.0", "0.3.0"))

    def test_current(self):
        v = current_version()
        self.assertTrue(v.startswith("3."))


class CheckTests(unittest.TestCase):
    def test_no_update_when_equal(self):
        manifest = {
            "releases": [
                {
                    "version": current_version(),
                    "channel": "stable",
                    "platform": "windows",
                    "notes_human": "Same",
                }
            ]
        }
        with patch("doof.updates.client._fetch_json", return_value=manifest):
            st = check_for_update()
        self.assertFalse(st.available)
        self.assertIsNone(st.error)

    def test_update_available(self):
        manifest = {
            "releases": [
                {
                    "version": "9.9.9",
                    "channel": "stable",
                    "platform": "windows",
                    "notes_human": "DOOF got less stupid.",
                    "download_url": "https://example.com/doof.zip",
                    "sha256": "abc",
                }
            ]
        }
        with patch("doof.updates.client._fetch_json", return_value=manifest):
            st = check_for_update()
        self.assertTrue(st.available)
        self.assertEqual(st.latest, "9.9.9")
        self.assertIn("less stupid", st.notes_human)

    def test_incompatible_forces_mandatory(self):
        manifest = {
            "releases": [
                {
                    "version": "9.9.9",
                    "channel": "stable",
                    "platform": "windows",
                    "min_supported": "9.0.0",
                    "notes_human": "Too old",
                }
            ]
        }
        with patch("doof.updates.client._fetch_json", return_value=manifest):
            st = check_for_update()
        self.assertTrue(st.incompatible)
        self.assertTrue(st.mandatory)


if __name__ == "__main__":
    unittest.main()
