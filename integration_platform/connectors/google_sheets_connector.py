# Required libraries:
# google-api-python-client
# google-auth-oauthlib
# Add these to your requirements.txt
import os
import logging
from .base_connector import BaseConnector

# Try to import Google libraries, raise ImportError if not found
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    # This allows the module to be imported and inspected even if Google libs are not installed yet,
    # but methods relying on them will fail.
    logging.error(
        "Google API libraries not found. Please install 'google-api-python-client google-auth-oauthlib'."
    )
    # You could raise an ImportError here if you want to prevent the module from loading at all
    # raise ImportError("Google API libraries not found. Please install 'google-api-python-client google-auth-oauthlib'.")
    # This allows the module to be imported and inspected even if Google libs are not installed yet,
    # but methods relying on them will fail.
    # logging.error( # This is already handled by the module-level logger if it's used before setup
    #     "Google API libraries not found. Please install 'google-api-python-client google-auth-oauthlib'."
    # )
    # You could raise an ImportError here if you want to prevent the module from loading at all
    # raise ImportError("Google API libraries not found. Please install 'google-api-python-client google-auth-oauthlib'.")
    pass # Keep pass, actual error handling will be in methods trying to use these.

# SCOPES defines the level of access requested.
# For read-only access: SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
# For read-write access:
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

logger = logging.getLogger(__name__) # Module-level logger


class GoogleSheetsConnector(BaseConnector):
    """
    Connector for interacting with Google Sheets API.
    Handles authentication and provides methods for data retrieval.
    """

    def __init__(self, client_secret_file: str = 'credentials.json', token_file_path: str = 'token.json'):
        """
        Initializes the GoogleSheetsConnector.

        Args:
            client_secret_file (str): Path to the Google Cloud client secret JSON file.
                                      This file is obtained from Google Cloud Console.
                                      It's recommended to load this path from a config file.
            token_file_path (str): Path to store/load the OAuth token JSON file.
                                   This file is generated after successful user authentication.
                                   It's recommended to load this path from a config file.
        """
        self.client_secret_file = client_secret_file
        self.token_file_path = token_file_path
        self.service = None
        self.creds = None
        logger.info(f"GoogleSheetsConnector initialized. Client Secret File: '{client_secret_file}', Token File: '{token_file_path}'")

    def connect(self):
        """
        Establishes a connection to Google Sheets API using OAuth2.
        Loads existing tokens or initiates the OAuth flow if necessary.
        """
        logger.info("Attempting to connect to Google Sheets API...")
        self.creds = None

        # Check if Google libraries were imported successfully at the module level
        # This check is more for code clarity; if they weren't, hasattr below would fail anyway.
        try:
            Credentials_imported = Credentials # Check if Credentials name is available
        except NameError:
            logger.error("Google API client libraries (Credentials) not imported. Cannot connect. Please install 'google-api-python-client google-auth-oauthlib'.")
            raise ImportError("Google API client libraries (Credentials) not imported. Run pip install google-api-python-client google-auth-oauthlib.")

        # Check if token file exists
        if os.path.exists(self.token_file_path):
            try:
                self.creds = Credentials.from_authorized_user_file(self.token_file_path, SCOPES)
                logger.info(f"Loaded credentials from {self.token_file_path}")
            except ValueError as e:
                logger.warning(f"Error loading credentials from token file ({self.token_file_path}): {e}. Will attempt to re-authenticate.")
                self.creds = None # Ensure creds is None if file is malformed
            except Exception as e:
                logger.error(f"Unexpected error loading token file {self.token_file_path}: {e}")
                self.creds = None


        # If no valid credentials, try to refresh or start new auth flow
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                logger.info("Credentials expired, attempting to refresh...")
                try:
                    self.creds.refresh(Request())
                    logger.info("Credentials refreshed successfully.")
                except Exception as e:
                    logger.error(f"Failed to refresh token: {e}. Need to re-authenticate.")
                    # Fall through to re-authentication
                    self.creds = None
            else:
                logger.info("No valid token found or refresh failed. Starting new authentication flow.")
                if not os.path.exists(self.client_secret_file):
                    logger.error(f"Client secret file not found: {self.client_secret_file}")
                    raise FileNotFoundError(
                        f"Client secret file ('{self.client_secret_file}') not found. "
                        "Please download it from Google Cloud Console and ensure the path is correct."
                    )
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(self.client_secret_file, SCOPES)
                    # WORKER_NOTE: The following lines requiring user interaction (run_local_server or run_console)
                    # cannot be executed directly by the worker in a non-interactive environment.
                    # This setup assumes that the user will run a script that calls this connect() method
                    # in an environment where they can complete the OAuth2 flow in a browser.
                    logger.warning("WORKER_NOTE: User interaction required for OAuth2 flow.")
                    logger.warning(f"WORKER_NOTE: Please run this application in an environment where you can authorize access via a web browser.")
                    logger.warning(f"WORKER_NOTE: The application will attempt to start a local server for authentication. Follow the instructions in your browser.")

                    # Option 1: Run local server (opens browser, user authenticates, server gets token)
                    # self.creds = flow.run_local_server(port=0)

                    # Option 2: Run console (prints URL, user visits, pastes auth code back)
                    # self.creds = flow.run_console()

                    # For this automated subtask, we cannot complete the flow.
                    # We will log this and assume the user will perform this step manually.
                    # The token file (e.g., token.json) should be generated by this manual step.
                    logger.error("WORKER_ACTION_REQUIRED: Manual OAuth2 authentication needed.")
                    print("****************************************************************************************************************************")
                    print("ACTION REQUIRED: To complete Google Sheets authentication:")
                    print("1. Ensure you have a 'credentials.json' (or your specified client_secret_file) from Google Cloud Console.")
                    print(f"2. Run a Python script that calls this connect() method interactively. It will guide you through browser authentication.")
                    print(f"3. A '{self.token_file_path}' will be created. This file should then be available for subsequent runs.")
                    print("****************************************************************************************************************************")
                    # We cannot proceed to build the service without credentials.
                    # Raising an exception to indicate that authentication is pending.
                    # This error is specific and helps the WorkflowEngine understand the state.
                    raise ConnectionAbortedError(
                        "OAuth2 authentication required. Please run interactively to generate token file."
                    )

                except FileNotFoundError as fnf_error: # Specifically for client_secret_file
                    logger.error(f"OAuth2 Flow Error - Client Secret File Not Found: {fnf_error}", exc_info=True)
                    raise # Re-raise to signal critical failure
                except Exception as e:
                    logger.error(f"Error during OAuth2 flow: {e}", exc_info=True)
                    raise ConnectionError(f"Could not initiate OAuth2 flow: {e}") from e

            # Save the credentials for the next run (if newly obtained/refreshed and valid)
            if self.creds and self.creds.valid:
                try:
                    with open(self.token_file_path, 'w') as token_file:
                        token_file.write(self.creds.to_json())
                    logger.info(f"Credentials saved to token file: {self.token_file_path}")
                except IOError as e:
                    logger.error(f"IOError saving token file to {self.token_file_path}: {e}", exc_info=True)
                    # If we can't save the token, the user might have to authenticate again next time.
                    # However, the current session might still work with self.creds in memory.

        # Build the service object if credentials are valid
        if self.creds and self.creds.valid:
            try:
                # Check if 'build' function is available from googleapiclient.discovery
                if 'build' not in globals() or not callable(build):
                     logger.error("Google API client 'build' function not available. Check imports.")
                     raise NameError("Google API client 'build' function not available.")
                self.service = build('sheets', 'v4', credentials=self.creds)
                logger.info("Successfully built Google Sheets service object and connected.")
            except HttpError as e:
                logger.error(f"Failed to build Google Sheets service due to HttpError: {e.resp.status} - {e.content}", exc_info=True)
                self.service = None
                raise ConnectionError(f"Failed to build Google Sheets service: {e.resp.status} - {e.content}") from e
            except Exception as e:
                logger.error(f"An unexpected error occurred while building Google Sheets service: {e}", exc_info=True)
                self.service = None
                raise ConnectionError(f"Unexpected error building Google Sheets service: {e}") from e
        else:
            logger.error("Could not obtain valid credentials for Google Sheets after all attempts.")
            self.service = None # Ensure service is None
            raise ConnectionError(
                "Failed to obtain valid Google Sheets credentials. "
                f"Ensure token file '{self.token_file_path}' is valid or run authentication again."
            )
        return True

    def disconnect(self):
        """Disconnects from Google Sheets by clearing the service object."""
        self.service = None
        self.creds = None
        logger.info("Disconnected from Google Sheets. Service and credentials have been cleared.")

    def get_sheet_data(self, sheet_id: str, range_name: str) -> list[list[str]]:
        """
        Fetches data from a specified Google Sheet and range.

        Args:
            sheet_id: The ID of the Google Spreadsheet.
            range_name: The A1 notation of the range to retrieve (e.g., "Sheet1!A1:B5").

        Returns:
            A list of lists containing the data from the sheet.
            Returns an empty list if an error occurs or no data is found.

        Raises:
            ConnectionError: If the connector is not connected (self.service is None).
            Exception: For other API-related errors.
        """
        if not self.service:
            logger.error("Not connected to Google Sheets. Call connect() first.")
            raise ConnectionError("Not connected to Google Sheets. Call connect() before fetching data.")

        logger.info(f"Fetching data from sheet_id='{sheet_id}', range='{range_name}'")
        try:
            # Placeholder for the actual API call
            # result = self.service.spreadsheets().values().get(
            #     spreadsheetId=sheet_id,
            #     range=range_name
            # ).execute()
            # values = result.get('values', [])

            # Check if we are in a simulated environment or if we should attempt real calls
            # This flag is set by the main script or can be set directly for testing.
            is_simulation = os.environ.get("GOOGLE_SHEETS_SIMULATE_API_CALLS", "false").lower() == "true"

            if is_simulation:
                logger.info(f"SIMULATING API call to get_sheet_data for sheet_id='{sheet_id}', range='{range_name}'.")
                # Specific simulation for testing workflow templating
                if sheet_id == "YOUR_GOOGLE_SHEET_ID_PLACEHOLDER" and \
                   (range_name == "Sheet1!A1:A1" or (isinstance(range_name, str) and range_name.startswith("Sheet1!A1:A1"))): # Allow for dynamic range like A1:monitor_colum1
                    logger.info("Matched simulation condition for placeholder sheet and range A1.")
                    return [["Simulated Text for Summary"]]
                elif sheet_id == "test_sheet_id" and range_name == "Sheet1!A1:B2": # Original test case
                    logger.info("Matched simulation condition for 'test_sheet_id'.")
                    return [["Header1", "Header2"], ["Data1", "Data2"]]
                else:
                    logger.info(f"No specific simulation case matched for get_sheet_data({sheet_id}, {range_name}). Returning empty list.")
                    return []

            # Actual API call if not simulating
            logger.info(f"Executing actual API call to get sheet data for sheet_id='{sheet_id}', range='{range_name}'")
            result = self.service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_name
            ).execute()
            values = result.get('values', [])

            if not values:
                logger.info(f"No data found for sheet_id='{sheet_id}', range='{range_name}'.")
            else:
                logger.info(f"Successfully fetched {len(values)} rows.")
            return values
        except HttpError as e:
            logger.error(f"Google API HttpError while fetching sheet data: {e.resp.status} - {e.content}", exc_info=True)
            error_content = e.content.decode('utf-8') if isinstance(e.content, bytes) else str(e.content)
            raise Exception(f"API error fetching data from sheet '{sheet_id}' range '{range_name}': Status {e.resp.status}, Details: {error_content}") from e
        except ConnectionError: # Re-raise if it's a connection issue passed up (e.g. from self.connect())
            logger.error("ConnectionError encountered during get_sheet_data, likely service not available.", exc_info=True)
            raise
        except Exception as e: # Catch any other unexpected errors
            logger.error(f"Unexpected error fetching sheet data for sheet '{sheet_id}', range '{range_name}': {e}", exc_info=True)
            raise Exception(f"Unexpected error fetching data from sheet '{sheet_id}' range '{range_name}': {e}") from e

    def get_new_rows(self, sheet_id: str, tab_name: str, last_processed_row_index: int = 0) -> tuple[list[list[str]], int]:
        """
        Fetches new rows from a sheet after a given row index.

        Args:
            sheet_id: The ID of the Google Spreadsheet.
            tab_name: The name of the tab/sheet (e.g., "Sheet1").
            last_processed_row_index: The last row index that was processed.
                                      Defaults to 0 (fetches all rows if 0).

        Returns:
            A tuple containing:
                - A list of lists representing the new rows.
                - The new last_processed_row_index (which is the count of total rows fetched including new ones).

        Raises:
            ConnectionError: If not connected.
            Exception: For API or other errors.
        """
        if not self.service:
            logger.error("Not connected to Google Sheets. Call connect() first.")
            raise ConnectionError("Not connected. Call connect() before fetching new rows.")

        # Define the range to fetch. Fetches all columns (A:Z) from the row after last_processed_row_index.
        # Google Sheets rows are 1-indexed.
        start_row = last_processed_row_index + 1
        range_to_fetch = f"{tab_name}!A{start_row}:Z" # Assuming data up to column Z

        logger.info(f"Getting new rows from sheet_id='{sheet_id}', tab='{tab_name}', starting after row {last_processed_row_index} (range: {range_to_fetch})")

        try:
            new_rows_data = self.get_sheet_data(sheet_id, range_to_fetch)

            current_total_rows_in_fetched_range = len(new_rows_data)
            # The new last_processed_row_index will be the original index + number of new rows found.
            new_last_processed_index = last_processed_row_index + current_total_rows_in_fetched_range

            if new_rows_data:
                logger.info(f"Fetched {len(new_rows_data)} new rows. New last_processed_row_index: {new_last_processed_index}")
            else:
                logger.info(f"No new rows found after row {last_processed_row_index}.")

            return new_rows_data, new_last_processed_index
        except Exception as e:
            logger.error(f"Error in get_new_rows for sheet '{sheet_id}', tab '{tab_name}': {e}")
            # Re-raise the exception to be handled by the caller
            raise

    def append_row(self, sheet_id: str, tab_name: str, values: list[list[any]]) -> dict:
        """
        Appends a row (or multiple rows) of values to a sheet.

        Args:
            sheet_id: The ID of the Google Spreadsheet.
            tab_name: The name of the tab/sheet (e.g., "Sheet1").
                      The method will append after the last row with data in this tab.
            values: A list of lists representing the row(s) to append.
                    Example: [["ValueA1", "ValueB1"], ["ValueA2", "ValueB2"]]

        Returns:
            The API response from Google Sheets, typically includes information
            about the updated range.

        Raises:
            ConnectionError: If not connected.
            HttpError: For errors from the Google Sheets API.
            Exception: For other unexpected errors.
        """
        if not self.service:
            logger.error("Not connected to Google Sheets. Call connect() first.")
            raise ConnectionError("Not connected. Call connect() before appending data.")

        range_name = tab_name # For append, just the tab name is usually enough.
                              # API appends after the table it detects in that sheet.
                              # Or specify a range like 'Sheet1!A1' to append after that range's detected table.
        body = {
            'values': values
        }
        logger.info(f"Appending {len(values)} row(s) to sheet_id='{sheet_id}', tab='{tab_name}'. Data: {str(values)[:100]}...") # Log snippet of data

        try:
            is_simulation = os.environ.get("GOOGLE_SHEETS_SIMULATE_API_CALLS", "false").lower() == "true"
            if is_simulation:
                logger.info(f"SIMULATING API call to append_row for sheet_id='{sheet_id}', tab_name='{tab_name}'. Data: {str(values)[:100]}...")
                # Simulate a successful response structure
                sim_updated_range = f"{tab_name}!A{100}:Z{100 + len(values) -1}" # Example simulated range
                return {
                    "spreadsheetId": sheet_id,
                    "tableRange": range_name, # The range specified for append, often just tab_name
                    "updates": {
                        "spreadsheetId": sheet_id,
                        "updatedRange": sim_updated_range,
                        "updatedRows": len(values),
                        "updatedColumns": len(values[0]) if values and values[0] else 0,
                        "updatedCells": sum(len(row) for row in values)
                    }
                }

            logger.info(f"Executing actual API call to append {len(values)} row(s) to sheet_id='{sheet_id}', tab='{tab_name}'.")
            result = self.service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED', # Or 'RAW'
                insertDataOption='INSERT_ROWS', # Appends new rows
                body=body
            ).execute()
            logger.info(f"Successfully appended rows. Response: {result}")
            return result
        except HttpError as e:
            logger.error(f"Google API HttpError while appending row: {e.resp.status} - {e.content}", exc_info=True)
            error_content = e.content.decode('utf-8') if isinstance(e.content, bytes) else str(e.content)
            raise Exception(f"API error appending data to sheet '{sheet_id}' tab '{tab_name}': Status {e.resp.status}, Details: {error_content}") from e
        except Exception as e:
            logger.error(f"Unexpected error appending row to sheet '{sheet_id}', tab '{tab_name}': {e}", exc_info=True)
            raise Exception(f"Unexpected error appending data to sheet '{sheet_id}' tab '{tab_name}': {e}") from e

    def update_cell(self, sheet_id: str, range_name: str, value: any) -> dict:
        """
        Updates a specific cell (or a range of cells) with a new value.

        Args:
            sheet_id: The ID of the Google Spreadsheet.
            range_name: The A1 notation of the cell or range to update (e.g., "Sheet1!A1", "Sheet1!B2:C3").
            value: The value to set for the cell. If updating a range, this should be a list of lists
                   matching the dimensions of the range_name. For a single cell, a single value is fine.

        Returns:
            The API response from Google Sheets.

        Raises:
            ConnectionError: If not connected.
            HttpError: For errors from the Google Sheets API.
            Exception: For other unexpected errors.
        """
        if not self.service:
            logger.error("Not connected to Google Sheets. Call connect() first.")
            raise ConnectionError("Not connected. Call connect() before updating cell.")

        # The API expects a list of lists for values.
        if not isinstance(value, list) or not (all(isinstance(row, list) for row in value) if value else False):
             body_values = [[value]] # Wrap single value in list of lists
        else:
            body_values = value # Assume value is already correctly formatted as list of lists

        body = {
            'values': body_values
        }
        logger.info(f"Updating cell(s) at sheet_id='{sheet_id}', range='{range_name}' with value: {str(body_values)[:100]}...")

        try:
            is_simulation = os.environ.get("GOOGLE_SHEETS_SIMULATE_API_CALLS", "false").lower() == "true"
            if is_simulation:
                logger.info(f"SIMULATING API call to update_cell for sheet_id='{sheet_id}', range='{range_name}'. Value: {str(body_values)[:100]}...")
                # Simulate a successful response structure
                return {
                    "spreadsheetId": sheet_id,
                    "updatedRange": range_name,
                    "updatedRows": len(body_values),
                    "updatedColumns": len(body_values[0]) if body_values and body_values[0] else 0,
                    "updatedCells": sum(len(row) for row in body_values)
                }

            logger.info(f"Executing actual API call to update cell(s) at sheet_id='{sheet_id}', range='{range_name}'.")
            result = self.service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED', # Or 'RAW'
                body=body
            ).execute()
            logger.info(f"Successfully updated cell(s). Response: {result}")
            return result
        except HttpError as e:
            logger.error(f"Google API HttpError while updating cell: {e.resp.status} - {e.content}", exc_info=True)
            error_content = e.content.decode('utf-8') if isinstance(e.content, bytes) else str(e.content)
            raise Exception(f"API error updating cell(s) at '{range_name}' in sheet '{sheet_id}': Status {e.resp.status}, Details: {error_content}") from e
        except Exception as e:
            logger.error(f"Unexpected error updating cell(s) at '{range_name}' in sheet '{sheet_id}': {e}", exc_info=True)
            raise Exception(f"Unexpected error updating cell(s) at '{range_name}' in sheet '{sheet_id}': {e}") from e

    def execute_action(self, action_name: str, params: dict):
        """
        Executes a specific action on Google Sheets.
        This is a generic method that can be expanded.

        Args:
            action_name (str): The name of the action to execute.
                               Examples: "get_data", "get_new_rows", "append_data", "update_data".
            params (dict): A dictionary of parameters for the action.
                           - For "get_data": {"sheet_id": "id", "range_name": "Sheet1!A1:B5"}
                           - For "get_new_rows": {"sheet_id": "id", "tab_name": "Sheet1", "last_processed_row_index": 0}
                           (Add more actions and their params as needed)
        Returns:
            The result of the action, type depends on the action.

        Raises:
            ValueError: If action_name is unknown or params are invalid.
            ConnectionError: If not connected.
            Exception: For API or other errors during action execution.
        """
        if not self.service:
            logger.error("Not connected to Google Sheets. Call connect() first.")
            raise ConnectionError("Not connected. Call an action on Google Sheets.")

        logger.info(f"Executing Google Sheets action: '{action_name}' with params: {params}")

        if action_name == "get_sheet_data":
            if not all(k in params for k in ["sheet_id", "range_name"]):
                raise ValueError("Missing 'sheet_id' or 'range_name' for get_sheet_data action.")
            data = self.get_sheet_data(params["sheet_id"], params["range_name"])
            return {"values": data}

        elif action_name == "get_new_rows":
            if not all(k in params for k in ["sheet_id", "tab_name"]):
                raise ValueError("Missing 'sheet_id' or 'tab_name' for get_new_rows action.")
            new_rows_data, new_last_index = self.get_new_rows(
                params["sheet_id"],
                params["tab_name"],
                params.get("last_processed_row_index", 0) # .get provides default
            )
            return {"new_rows": new_rows_data, "last_row_index": new_last_index}

        elif action_name == "append_row":
            if not all(k in params for k in ["sheet_id", "tab_name", "values"]):
                raise ValueError("Missing 'sheet_id', 'tab_name', or 'values' for append_row action.")
            response = self.append_row(params["sheet_id"], params["tab_name"], params["values"])
            return {"append_response": response} # Wrap API response

        elif action_name == "update_cell":
            if not all(k in params for k in ["sheet_id", "range_name", "value"]):
                raise ValueError("Missing 'sheet_id', 'range_name', or 'value' for update_cell action.")
            response = self.update_cell(params["sheet_id"], params["range_name"], params["value"])
            return {"update_response": response} # Wrap API response

        else:
            logger.error(f"Unknown action: {action_name}")
            raise ValueError(f"Unknown action: {action_name} for GoogleSheetsConnector.")


if __name__ == '__main__':
    # This is example usage code, primarily for manual testing.
    # It requires 'credentials.json' and will create 'token.json'.

    # Configure basic logging for the example
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.info("Starting GoogleSheetsConnector example...")

    # These paths would typically come from a global config object/file
    # Ensure 'credentials.json' is in the same directory as this script, or provide the correct path.
    # If 'credentials.json' is in 'integration_platform/connectors/', use that path.
    # For testing, let's assume it's in the root of integration_platform for now.
    # Or better, relative to this file.
    script_dir = os.path.dirname(__file__)
    CLIENT_SECRET_FILE_PATH = os.path.join(script_dir, '..', '..', 'credentials.json') # Assuming it's in project root
    TOKEN_FILE_PATH = os.path.join(script_dir, '..', '..', 'token.json') # Assuming it's in project root

    # To make this example runnable if this file is executed directly,
    # and credentials.json is expected in the project root:
    # current_file_dir = os.path.dirname(os.path.abspath(__file__))
    # project_root = os.path.abspath(os.path.join(current_file_dir, '../../..')) # Adjust if structure changes
    # CLIENT_SECRET_FILE_PATH = os.path.join(project_root, 'credentials.json')
    # TOKEN_FILE_PATH = os.path.join(project_root, 'token.json')

    # Simplified for now, assuming credentials.json might be placed in the connectors dir for testing
    # or more realistically, paths are managed by a config system.
    # Let's use placeholder names that clearly indicate they need to be correctly set up.
    # For a real run, replace 'path/to/your/credentials.json'
    # CLIENT_SECRET_FILE_PATH = 'path/to/your/credentials.json'
    # TOKEN_FILE_PATH = 'gs_token.json'

    # This environment variable is referenced by the simulation logic within the methods
    IS_SIMULATION_MODE = os.environ.get("GOOGLE_SHEETS_SIMULATE_API_CALLS", "false").lower() == "true"
    if IS_SIMULATION_MODE:
        logger.info("GoogleSheetsConnector __main__: Running in API call SIMULATION MODE.")

    CREDENTIALS_FILE = 'credentials.json' # Default name expected by connector
    TOKEN_FILE = 'token.json'         # Default name expected by connector

    # Create dummy credentials.json for the __main__ example if it doesn't exist AND
    # a specific env var IS_WORKER_ENV_CREATE_DUMMY_CREDS is set (e.g. in CI for structural tests).
    # This is to help the example run structurally without real files in certain automated environments.
    # For actual use, real credentials.json is needed.
    if not os.path.exists(CREDENTIALS_FILE) and os.environ.get("IS_WORKER_ENV_CREATE_DUMMY_CREDS") == "true":
        logger.warning(f"__main__: Creating dummy '{CREDENTIALS_FILE}' for example run. Replace with real file for actual use.")
        try:
            with open(CREDENTIALS_FILE, 'w') as f:
                # A minimal structure that from_client_secrets_file might expect
                f.write('{"installed":{"client_id":"dummy_client_id","project_id":"dummy_project","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_secret":"dummy_client_secret","redirect_uris":["http://localhost"]}}')
        except IOError as e_io:
            logger.error(f"__main__: Failed to create dummy credentials file: {e_io}")

    # Instantiate with default credential file names
    connector = GoogleSheetsConnector(client_secret_file=CREDENTIALS_FILE, token_file_path=TOKEN_FILE)

    try:
        # The connect() call might raise ConnectionAbortedError in non-interactive environments
        # if token.json is not found or invalid, as it expects user interaction for OAuth.
        # This is normal in such environments for the first run.
        logger.info("__main__: Attempting to connect connector...")
        connector.connect()
        logger.info("__main__: Connector connect() call completed.")

        if connector.service or IS_SIMULATION_MODE: # If service exists or we are simulating calls
            logger.info("__main__: Google Sheets Service is available or in simulation mode. Proceeding with example actions.")

            sheet_id_to_test = "YOUR_GOOGLE_SHEET_ID_PLACEHOLDER" if IS_SIMULATION_MODE else "your_ACTUAL_sheet_id_here_for_read"
            range_to_test_read = "Sheet1!A1:A1" if IS_SIMULATION_MODE else "Sheet1!A1:B2" # Adjust for real tests

            logger.info(f"__main__: Attempting 'get_sheet_data' action for sheet: {sheet_id_to_test}, range: {range_to_test_read}")
            try:
                data_result = connector.execute_action("get_sheet_data", {"sheet_id": sheet_id_to_test, "range_name": range_to_test_read})
                logger.info(f"__main__: 'get_sheet_data' result: {data_result}")
            except Exception as e_action:
                logger.error(f"__main__: Error during 'get_sheet_data' action: {e_action}", exc_info=True)

            # Write operations - use with extreme caution if not in simulation mode.
            # These examples are typically commented out or use specific test sheets.
            sheet_id_to_test_write = "YOUR_TEST_SPREADSHEET_ID_FOR_WRITES" # IMPORTANT: Use a test sheet ID!
            tab_name_to_write = "Sheet1"

            if not IS_SIMULATION_MODE:
                logger.warning("__main__: Write operations (append, update) are disabled by default in __main__ for safety if not in simulation mode.")
                logger.warning("__main__: To test live writes, uncomment the relevant sections and ensure 'sheet_id_to_test_write' is a safe target.")
            else: # In simulation mode, it's safe to "execute" these
                logger.info("__main__: Simulating 'append_row' action.")
                try:
                    append_result = connector.execute_action(
                        "append_row",
                        {"sheet_id": sheet_id_to_test_write, "tab_name": tab_name_to_write, "values": [["SimulatedAppend1", "SimulatedAppend2"]]}
                    )
                    logger.info(f"__main__: Simulated 'append_row' result: {append_result}")
                except Exception as e_action:
                     logger.error(f"__main__: Error during simulated 'append_row' action: {e_action}", exc_info=True)

                logger.info("__main__: Simulating 'update_cell' action.")
                try:
                    update_result = connector.execute_action(
                        "update_cell",
                        {"sheet_id": sheet_id_to_test_write, "range_name": f"{tab_name_to_write}!C1", "value": "SimulatedUpdate"}
                    )
                    logger.info(f"__main__: Simulated 'update_cell' result: {update_result}")
                except Exception as e_action:
                    logger.error(f"__main__: Error during simulated 'update_cell' action: {e_action}", exc_info=True)
        else:
            logger.warning("__main__: Google Sheets service not available and not in simulation mode. Skipping example actions.")

    except ConnectionAbortedError as e_auth:
        logger.warning(f"__main__: Authentication required and could not be completed automatically: {e_auth}")
        logger.warning("__main__: This is expected in non-interactive environments if 'token.json' is missing/invalid.")
    except FileNotFoundError as e_fnf:
        logger.error(f"__main__: Configuration file error: {e_fnf}. Ensure '{CREDENTIALS_FILE}' (or specified path) is present.", exc_info=True)
    except ConnectionError as e_conn:
        logger.error(f"__main__: Connection failed: {e_conn}", exc_info=True)
    except ImportError as e_imp:
        logger.error(f"__main__: Import error: {e_imp}. Ensure Google client libraries are installed.", exc_info=True)
    except HttpError as e_http:
        logger.error(f"__main__: Google API HTTP Error: {e_http.resp.status} - {e_http.content}", exc_info=True)
    except Exception as e_main:
        logger.error(f"__main__: An unexpected error occurred: {e_main}", exc_info=True)
    finally:
        if connector:
            logger.info("__main__: Attempting to disconnect connector in finally block.")
            connector.disconnect()

    logger.info("GoogleSheetsConnector __main__ example finished.")
