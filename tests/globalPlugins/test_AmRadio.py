# -*- coding: utf-8 -*-

import unittest
from unittest.mock import patch, MagicMock
import requests.exceptions

# Adjust the import path according to your project structure.
# This assumes 'addon' is a package and can be found in PYTHONPATH.
# If running from within the 'addon' directory or a parent, this might need adjustment
# or __init__.py files in relevant directories.
# For NVDA addons, the typical structure might involve running tests from the addon root.
try:
    from addon.globalPlugins.AmRadio import GlobalPlugin
    import addon.globalPlugins.logHandler as logHandler # Assuming logHandler is used
except ImportError:
    # This path might be needed if tests are run from the 'tests' directory directly
    # and 'addon' is a sibling directory.
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
    from addon.globalPlugins.AmRadio import GlobalPlugin
    import addon.globalPlugins.logHandler as logHandler

# Sample HTML content for mocking qrz.com responses

# Based on a lookup for KF4MD, simplified, and some data slightly altered for test uniqueness.
SAMPLE_HTML_KF4MD = """
<html>
<head><title>KF4MD on QRZ.com</title></head>
<body>
    <table id="tabCallsignDetail">
        <tr><td id="fname">John Doe</td><td><!-- value cell for name --></td></tr> <!-- Note: QRZ often has value in first cell or complex structure -->
        <tr><td id="addr1">123 Main St</td><td></td></tr>
        <tr><td id="addr2">Anytown, FL 33000</td><td></td></tr>
        <tr><td id="country">USA</td><td></td></tr>
        <tr><td id="grid">EL96aa</td><td></td></tr>
        <tr><td id="class">Extra</td><td></td></tr>
        <tr><td id="email">johndoe@example.com</td><td></td></tr>
        <tr><td>Trustee:</td><td>TrusteeNameHere</td></tr>
    </table>
    <!-- Fallback name structure if not in table -->
    <font size="+2" color="green">John Doe Public</font> 
    <!-- Fallback grid -->
    <td>Grid Square</td><td>EL96ab</td>
</body>
</html>
"""
# Simplified version for testing when tabCallsignDetail is not the primary source or is malformed
SAMPLE_HTML_KF4MD_ALTERNATIVE_STRUCTURE = """
<html>
<head><title>KF4MD on QRZ.com</title></head>
<body>
    <font size="+2" color="green">Jane Doe Alternative</font>
    <table>
        <tr><td>Grid Square</td><td>EM15cd</td></tr>
        <tr><td>Address</td><td>456 Other St</td></tr>
        <tr><td>City, State Zip</td><td>Otherville, TX 75000</td></tr>
        <tr><td>Country</td><td>Canada</td></tr> <!-- Intentionally different for test -->
        <tr><td>Class</td><td>General</td></tr>
    </table>
</body>
</html>
"""

SAMPLE_HTML_NOT_FOUND = """
<html>
<head><title>Callsign Not Found QRZ.com</title></head>
<body>
    <div class="frametitle">Callsign Search</div>
    <p>The callsign you requested, XYZ123, was not found in the database.</p>
    <!-- QRZ sometimes returns this in the body for invalid/not found callsigns -->
    td align=center valign=top width="100%"><b>Invalid Request</b></font></p
</body>
</html>
"""
# Another variant for "not found" where the title might be the main indicator
SAMPLE_HTML_NOT_FOUND_TITLE_ONLY = """
<html>
<head><title>Database error or not found on QRZ.com</title></head>
<body>
    <p>Some generic page content, but the title indicates an issue.</p>
</body>
</html>
"""

SAMPLE_HTML_MINIMAL_DATA = """
<html>
<head><title>MINIMALCS on QRZ.com</title></head>
<body>
    <table id="tabCallsignDetail">
        <tr><td id="fname">Minimal Name</td><td></td></tr>
        <tr><td id="country">Germany</td><td></td></tr>
    </table>
</body>
</html>
"""

class TestScrapeQrzData(unittest.TestCase):

    def setUp(self):
        self.plugin_instance = GlobalPlugin()
        # Suppress log messages during tests unless specifically testing for them
        # To see logs for debugging, comment out the next two lines
        # logHandler.messages.ायला = MagicMock() 
        # logHandler.error = MagicMock()
        # logHandler.debug = MagicMock()
        # logHandler.info = MagicMock()


    def _mock_response(self, status=200, content="", text="", exception=None):
        mock_resp = MagicMock()
        if exception:
            mock_resp.raise_for_status.side_effect = exception
            mock_resp.get.side_effect = exception # if requests.get is directly used
        else:
            mock_resp.status_code = status
            mock_resp.content = content.encode('utf-8')
            mock_resp.text = text if text else content
        return mock_resp

    @patch('requests.get')
    def test_successful_extraction_kf4md(self, mock_get):
        mock_get.return_value = self._mock_response(content=SAMPLE_HTML_KF4MD)
        
        expected_data = {
            "callsign": "KF4MD",
            "Name": "John Doe Public", # Fallback name is taken due to current parser logic priority
            "Address": "123 Main St, Anytown, FL 33000", # Combined from addr1 and addr2
            "Grid Sq": "EL96ab", # Fallback grid is taken
            "Country": "USA",
            "License Class": "Extra",
            "Email": "johndoe@example.com"
            # "Address (Combined)" might appear if the other address logic doesn't fully populate
        }
        
        result = self.plugin_instance.scrape_qrz_data("KF4MD")
        self.assertIsNotNone(result)
        # Check for subset, as there might be "Address (Combined)"
        for key, value in expected_data.items():
            self.assertEqual(result.get(key), value, f"Field {key} mismatch")
        self.assertEqual(result["callsign"], "KF4MD")

    @patch('requests.get')
    def test_successful_extraction_alternative_structure(self, mock_get):
        mock_get.return_value = self._mock_response(content=SAMPLE_HTML_KF4MD_ALTERNATIVE_STRUCTURE)
        expected_data = {
            "callsign": "ALTCS",
            "Name": "Jane Doe Alternative",
            "Grid Sq": "EM15cd",
            "Address (Combined)": "456 Other St, Otherville, TX 75000, Canada", # Address parts combined
            "Country": "Canada", # From the table
            "License Class": "General"
        }
        result = self.plugin_instance.scrape_qrz_data("ALTCS")
        self.assertIsNotNone(result)
        for key, value in expected_data.items():
            self.assertEqual(result.get(key), value, f"Field {key} mismatch for ALTCS")
        self.assertEqual(result["callsign"], "ALTCS")


    @patch('requests.get')
    @patch('addon.globalPlugins.AmRadio.logHandler.info') # Patch where logHandler is used
    def test_callsign_not_found_by_content(self, mock_log_info, mock_get):
        mock_get.return_value = self._mock_response(content=SAMPLE_HTML_NOT_FOUND, status=200)
        result = self.plugin_instance.scrape_qrz_data("XYZ123")
        self.assertIsNone(result, "Expected None for callsign not found by content")
        # Check if specific logging messages occurred
        # Example: mock_log_info.assert_any_call("Callsign XYZ123 not found in QRZ.com database.")
        # Or check based on title:
        mock_log_info.assert_any_call("Callsign XYZ123 does not appear to be in the QRZ.com database (based on page title).")


    @patch('requests.get')
    @patch('addon.globalPlugins.AmRadio.logHandler.info')
    def test_callsign_not_found_by_title_only(self, mock_log_info, mock_get):
        mock_get.return_value = self._mock_response(content=SAMPLE_HTML_NOT_FOUND_TITLE_ONLY, status=200)
        result = self.plugin_instance.scrape_qrz_data("BADTITLE")
        self.assertIsNone(result, "Expected None for callsign not found by title content")
        mock_log_info.assert_any_call("Callsign BADTITLE does not appear to be in the QRZ.com database (based on page title).")


    @patch('requests.get')
    @patch('addon.globalPlugins.AmRadio.logHandler.error')
    def test_callsign_not_found_by_status_404(self, mock_log_error, mock_get):
        mock_get.return_value = self._mock_response(status=404, content="Page not found")
        result = self.plugin_instance.scrape_qrz_data("NOCS404")
        self.assertIsNone(result)
        mock_log_error.assert_called_with("Error fetching data for NOCS404: Status code 404")

    @patch('requests.get')
    @patch('addon.globalPlugins.AmRadio.logHandler.error')
    def test_network_timeout(self, mock_log_error, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
        result = self.plugin_instance.scrape_qrz_data("TIMEOUTCS")
        self.assertIsNone(result)
        mock_log_error.assert_called_with("Timeout while fetching data for TIMEOUTCS from QRZ.com.")

    @patch('requests.get')
    @patch('addon.globalPlugins.AmRadio.logHandler.error')
    def test_network_request_exception(self, mock_log_error, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("Generic network error")
        result = self.plugin_instance.scrape_qrz_data("REQEXCCS")
        self.assertIsNone(result)
        mock_log_error.assert_called_with("Network error fetching data for REQEXCCS from QRZ.com: Generic network error")

    @patch('requests.get')
    def test_minimal_data_extraction(self, mock_get):
        mock_get.return_value = self._mock_response(content=SAMPLE_HTML_MINIMAL_DATA)
        expected_data = {
            "callsign": "MINIMALCS",
            "Name": "Minimal Name",
            "Country": "Germany",
        }
        result = self.plugin_instance.scrape_qrz_data("MINIMALCS")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("callsign"), "MINIMALCS")
        self.assertEqual(result.get("Name"), "Minimal Name")
        self.assertEqual(result.get("Country"), "Germany")
        self.assertIsNone(result.get("Grid Sq")) # This field shouldn't be present
        self.assertIsNone(result.get("Address"))

    @patch('requests.get')
    @patch('addon.globalPlugins.AmRadio.logHandler.info')
    def test_empty_response_content(self, mock_log_info, mock_get):
        mock_get.return_value = self._mock_response(content="") # Empty HTML
        result = self.plugin_instance.scrape_qrz_data("EMPTYCS")
        # Depending on implementation, it might return None if title check fails, or basic dict
        # Current implementation relies on title for "not found", so empty content without specific title might pass if not handled
        # The code checks `if len(data) == 1` and title.
        # If title is not "not found", it would return the dict with just callsign.
        # Let's assume an empty page has a generic title.
        mock_get.return_value = self._mock_response(content="<html><head><title>Generic Page</title></head><body></body></html>")
        result = self.plugin_instance.scrape_qrz_data("EMPTYCS")

        self.assertIsNotNone(result, "Result should not be None for empty content with generic title")
        self.assertEqual(result.get("callsign"), "EMPTYCS")
        # Check that no other data was spuriously extracted
        self.assertEqual(len(result), 1, "Only callsign should be present for effectively empty data page")
        mock_log_info.assert_any_call("No detailed data extracted for EMPTYCS. Page structure might have changed or data is not available.")


if __name__ == "__main__":
    # This allows running the tests directly from this file:
    # python tests/globalPlugins/test_AmRadio.py
    # Ensure that the Python path is set up correctly for imports if run this way,
    # especially for 'addon.globalPlugins.AmRadio'.
    # One way is to run from the addon's root directory:
    # python -m unittest tests.globalPlugins.test_AmRadio
    
    # The following lines are to help Python find the 'addon' module if running the script directly
    # from the 'tests/globalPlugins' directory, or if 'addon' is not in PYTHONPATH.
    if not any(p for p in sys.path if os.path.basename(p) == 'addon' or os.path.basename(p) == os.path.join('..', '..')):
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
        
    unittest.main(verbosity=2)

# To run from the addon root directory:
# python -m unittest tests.globalPlugins.test_AmRadio
# or if you want to discover all tests:
# python -m unittest discover tests
# Ensure __init__.py files are present in 'tests' and 'tests/globalPlugins' if using discover.
# I will add them.
