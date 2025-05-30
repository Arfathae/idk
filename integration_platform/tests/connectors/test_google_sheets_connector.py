import unittest
from unittest.mock import patch, MagicMock, mock_open
import os

from integration_platform.connectors.google_sheets_connector import GoogleSheetsConnector

# Attempt to import Google API errors, or create dummy versions if not installed
try:
    from googleapiclient.errors import HttpError
    from google.auth.exceptions import RefreshError
except ImportError:
    # Define dummy exceptions if google libs are not installed,
    # allowing tests to be parsed and run, though they might fail if these are critical.
    class HttpError(IOError):  # Inherit from a common built-in error
        def __init__(self, resp, content, uri=None):
            self.resp = resp
            self.content = content
            self.uri = uri
            super().__init__(content)

    class RefreshError(Exception): pass


# Module-level logger for tests
import logging
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG) # Uncomment for detailed logs

class TestGoogleSheetsConnector(unittest.TestCase):

    def setUp(self):
        self.connector_params = {
            "client_secret_file": "dummy_credentials.json",
            "token_file_path": "dummy_token.json"
        }
        # Create dummy credential files for tests that might check for their existence
        # before mocking os.path.exists
        with open(self.connector_params["client_secret_file"], 'w') as f:
            f.write('{"installed":{"client_id":"dummy","project_id":"dummy","auth_uri":"dummy","token_uri":"dummy","auth_provider_x509_cert_url":"dummy","client_secret":"dummy","redirect_uris":["http://localhost"]}}')
        with open(self.connector_params["token_file_path"], 'w') as f:
            f.write('{"token": "dummy_token", "refresh_token": "dummy_refresh", "scopes": ["https://www.googleapis.com/auth/spreadsheets"]}')


    def tearDown(self):
        # Clean up dummy files
        if os.path.exists(self.connector_params["client_secret_file"]):
            os.remove(self.connector_params["client_secret_file"])
        if os.path.exists(self.connector_params["token_file_path"]):
            os.remove(self.connector_params["token_file_path"])

    @patch('integration_platform.connectors.google_sheets_connector.Credentials')
    @patch('integration_platform.connectors.google_sheets_connector.build')
    @patch('os.path.exists')
    def test_connect_with_existing_valid_token(self, mock_os_exists, mock_build, MockCredentials):
        logger.debug("Running test_connect_with_existing_valid_token")
        mock_os_exists.return_value = True  # Assume token file exists
        
        mock_creds_instance = MockCredentials.from_authorized_user_file.return_value
        mock_creds_instance.valid = True
        mock_creds_instance.expired = False
        mock_creds_instance.refresh_token = "some_refresh_token"

        mock_service = mock_build.return_value
        
        connector = GoogleSheetsConnector(**self.connector_params)
        connector.connect()

        MockCredentials.from_authorized_user_file.assert_called_once_with(
            self.connector_params["token_file_path"], connector.SCOPES
        )
        mock_build.assert_called_once_with('sheets', 'v4', credentials=mock_creds_instance)
        self.assertIsNotNone(connector.service)

    @patch('integration_platform.connectors.google_sheets_connector.Credentials')
    @patch('integration_platform.connectors.google_sheets_connector.build')
    @patch('os.path.exists')
    def test_connect_with_expired_token_refresh_success(self, mock_os_exists, mock_build, MockCredentials):
        logger.debug("Running test_connect_with_expired_token_refresh_success")
        mock_os_exists.return_value = True # Token file exists
        
        mock_creds_instance = MockCredentials.from_authorized_user_file.return_value
        mock_creds_instance.valid = False # Initially invalid
        mock_creds_instance.expired = True
        mock_creds_instance.refresh_token = "a_refresh_token"
        mock_creds_instance.refresh = MagicMock() # Mock the refresh method

        # Simulate refresh making credentials valid
        def side_effect_refresh(request):
            mock_creds_instance.valid = True
        mock_creds_instance.refresh.side_effect = side_effect_refresh
        
        connector = GoogleSheetsConnector(**self.connector_params)
        connector.connect()

        mock_creds_instance.refresh.assert_called_once()
        mock_build.assert_called_once_with('sheets', 'v4', credentials=mock_creds_instance)
        self.assertTrue(connector.creds.valid) # Check that creds became valid

    @patch('integration_platform.connectors.google_sheets_connector.Credentials')
    @patch('integration_platform.connectors.google_sheets_connector.InstalledAppFlow')
    @patch('integration_platform.connectors.google_sheets_connector.build')
    @patch('os.path.exists')
    def test_connect_no_token_new_flow_aborted_in_worker(self, mock_os_exists, mock_build, MockInstalledAppFlow, MockCredentials):
        logger.debug("Running test_connect_no_token_new_flow_aborted_in_worker")
        # Simulate token file does not exist, but credentials.json does
        mock_os_exists.side_effect = lambda path: path == self.connector_params["client_secret_file"]

        mock_flow_instance = MockInstalledAppFlow.from_client_secrets_file.return_value
        # Connector raises ConnectionAbortedError because run_local_server would block/require interaction
        
        connector = GoogleSheetsConnector(**self.connector_params)
        with self.assertRaises(ConnectionAbortedError):
            connector.connect()
        
        MockInstalledAppFlow.from_client_secrets_file.assert_called_once_with(
            self.connector_params["client_secret_file"], connector.SCOPES
        )
        mock_build.assert_not_called() # Build should not be called if auth is aborted

    @patch('os.path.exists', return_value=False) # client_secret_file does not exist
    def test_connect_client_secret_file_missing(self, mock_os_exists):
        logger.debug("Running test_connect_client_secret_file_missing")
        connector = GoogleSheetsConnector(**self.connector_params)
        with self.assertRaises(FileNotFoundError):
            connector.connect()

    def _setup_connected_connector(self, mock_build_sheets):
        """Helper to get a connector instance that appears connected and has a mock service."""
        # This helper assumes Credentials and os.path.exists are also patched by the caller if needed for connect()
        mock_service = MagicMock()
        mock_build_sheets.return_value = mock_service # mock_build('sheets', 'v4').return_value = mock_service
        
        # Mock credentials part of connect() to avoid full auth flow
        with patch('integration_platform.connectors.google_sheets_connector.Credentials') as MockCreds, \
             patch('os.path.exists', return_value=True): # Assume token file exists and is valid
            
            mock_creds_instance = MockCreds.from_authorized_user_file.return_value
            mock_creds_instance.valid = True
            mock_creds_instance.expired = False

            connector = GoogleSheetsConnector(**self.connector_params)
            connector.connect() # This will now use the mocked Credentials and build
            return connector, mock_service


    @patch('integration_platform.connectors.google_sheets_connector.build')
    def test_get_sheet_data_success(self, mock_build_sheets_module_level):
        logger.debug("Running test_get_sheet_data_success")
        connector, mock_service = self._setup_connected_connector(mock_build_sheets_module_level)
        
        mock_sheet_values = mock_service.spreadsheets().values().get().execute
        mock_sheet_values.return_value = {"values": [["Data1", "Data2"]]}

        sheet_id = "test_sheet"
        range_name = "Sheet1!A1:B1"
        result = connector.execute_action("get_sheet_data", {"sheet_id": sheet_id, "range_name": range_name})

        mock_service.spreadsheets().values().get.assert_called_once_with(
            spreadsheetId=sheet_id, range=range_name
        )
        self.assertEqual(result, {"values": [["Data1", "Data2"]]})

    @patch('integration_platform.connectors.google_sheets_connector.build')
    def test_get_sheet_data_http_error(self, mock_build_sheets):
        logger.debug("Running test_get_sheet_data_http_error")
        connector, mock_service = self._setup_connected_connector(mock_build_sheets)
        
        # Simulate HttpError
        # The HttpError needs a `resp` (like a dict with 'status') and `content`
        mock_resp = MagicMock()
        mock_resp.status = 403
        mock_service.spreadsheets().values().get().execute.side_effect = HttpError(
            resp=mock_resp, content=b'{"error": {"message": "Permission Denied"}}'
        )

        with self.assertRaises(Exception) as context:
            connector.execute_action("get_sheet_data", {"sheet_id": "test_sheet", "range_name": "Sheet1!A1"})
        self.assertIn("Permission Denied", str(context.exception))
        self.assertIn("Status 403", str(context.exception))


    @patch('integration_platform.connectors.google_sheets_connector.build')
    def test_append_row_success(self, mock_build_sheets):
        logger.debug("Running test_append_row_success")
        connector, mock_service = self._setup_connected_connector(mock_build_sheets)
        
        mock_append_response = {"updates": {"updatedRange": "Sheet1!A10:B10"}}
        mock_service.spreadsheets().values().append().execute.return_value = mock_append_response
        
        params = {"sheet_id": "s_id", "tab_name": "Sheet1", "values": [["val1", "val2"]]}
        result = connector.execute_action("append_row", params)

        mock_service.spreadsheets().values().append.assert_called_once_with(
            spreadsheetId="s_id",
            range="Sheet1", 
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body={'values': [["val1", "val2"]]}
        )
        self.assertEqual(result, {"append_response": mock_append_response})

    @patch('integration_platform.connectors.google_sheets_connector.build')
    def test_update_cell_success(self, mock_build_sheets):
        logger.debug("Running test_update_cell_success")
        connector, mock_service = self._setup_connected_connector(mock_build_sheets)

        mock_update_response = {"updatedCells": 1}
        mock_service.spreadsheets().values().update().execute.return_value = mock_update_response

        params = {"sheet_id": "s_id", "range_name": "Sheet1!A1", "value": "NewValue"}
        result = connector.execute_action("update_cell", params)
        
        mock_service.spreadsheets().values().update.assert_called_once_with(
            spreadsheetId="s_id",
            range="Sheet1!A1",
            valueInputOption='USER_ENTERED',
            body={'values': [["NewValue"]]}
        )
        self.assertEqual(result, {"update_response": mock_update_response})

    @patch('os.environ', {"GOOGLE_SHEETS_SIMULATE_API_CALLS": "true"})
    @patch('integration_platform.connectors.google_sheets_connector.build') # Still need to mock build for connect
    def test_get_sheet_data_simulation_mode(self, mock_build_sheets):
        logger.debug("Running test_get_sheet_data_simulation_mode")
        # Need to ensure connect() can run, even if it's just setting up a mock service
        connector, _ = self._setup_connected_connector(mock_build_sheets)

        # Test a specific simulation case defined in the connector
        params = {"sheet_id": "YOUR_GOOGLE_SHEET_ID_PLACEHOLDER", "range_name": "Sheet1!A1:A1"}
        result = connector.execute_action("get_sheet_data", params)
        self.assertEqual(result, {"values": [["Simulated Text for Summary"]]})

        # Test a generic simulation case
        params2 = {"sheet_id": "any_other_sheet", "range_name": "Range1"}
        result2 = connector.execute_action("get_sheet_data", params2)
        self.assertEqual(result2, {"values": []}) # Default simulation returns empty list

if __name__ == '__main__':
    unittest.main()
