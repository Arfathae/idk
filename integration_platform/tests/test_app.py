import unittest
import json
import os
from unittest.mock import patch, MagicMock, ANY # Import ANY

# Ensure 'app' can be imported. This might require adjusting PYTHONPATH if tests are run from root.
# Assuming 'integration_platform' is on the PYTHONPATH or tests are run in a way that handles it.
from integration_platform.app import app
from integration_platform.workflow.workflow_engine import WorkflowEngine # For type hinting if needed, not strictly for mocking

# Module-level logger for tests
import logging
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG) # Uncomment for detailed logs during test runs

class TestAppEndpoints(unittest.TestCase):

    def setUp(self):
        """Set up the test client and testing configuration."""
        app.config['TESTING'] = True
        app.config['DEBUG'] = False # Ensure debug mode is off for consistent error handling
        self.client = app.test_client()

        # It's good practice to patch os.getenv for all tests if app.py uses it to build global_config
        # This ensures tests are isolated from the actual environment variables.
        self.getenv_patcher = patch.dict(os.environ, {
            # Provide default mocks for env vars used in app.py to build global_config
            "OPENAI_API_KEY": "test_openai_key_from_env_for_app_test",
            # Add other env vars that app.py specifically loads for global_config
            # If an env var is checked but not present, it won't be in global_config, which is fine.
        })
        self.mock_env = self.getenv_patcher.start()

    def tearDown(self):
        """Clean up after tests."""
        self.getenv_patcher.stop()

    @patch('integration_platform.app.WorkflowEngine')
    def test_run_workflow_api_success(self, MockWorkflowEngine):
        """Test successful workflow execution via the API."""
        logger.debug("Running test_run_workflow_api_success")

        mock_engine_instance = MockWorkflowEngine.return_value
        expected_results = {"trigger": {"status": "success"}, "action1": {"status": "success", "output": "Test output"}}
        mock_engine_instance.run_workflow.return_value = expected_results

        response = self.client.post('/api/workflow/run')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'application/json')
        data = json.loads(response.data)
        self.assertEqual(data, expected_results)

        # Check that WorkflowEngine was instantiated (once)
        # The global_config passed will be derived from os.getenv, which is patched.
        MockWorkflowEngine.assert_called_once_with(global_config=ANY)

        # Check that run_workflow was called (once)
        # Verifying the exact path can be tricky due to os.path manipulations.
        # Using ANY for the path argument is safer if the path construction is complex or varies by environment.
        # Or, if app.py normalizes it, you can try to match that.
        # For now, let's assert it was called with a string (path).
        mock_engine_instance.run_workflow.assert_called_once_with(ANY)
        # If more specific path check is needed and app.py calculates it like this:
        # script_dir = os.path.dirname(os.path.abspath(app.__file__)) # app.__file__ gives path to app.py
        # expected_workflow_path = os.path.join(script_dir, "workflow/workflow_definition_example.json")
        # mock_engine_instance.run_workflow.assert_called_once_with(expected_workflow_path)


    @patch('integration_platform.app.WorkflowEngine')
    def test_run_workflow_api_engine_general_exception(self, MockWorkflowEngine):
        """Test API response when WorkflowEngine raises a generic Exception."""
        logger.debug("Running test_run_workflow_api_engine_general_exception")

        mock_engine_instance = MockWorkflowEngine.return_value
        mock_engine_instance.run_workflow.side_effect = Exception("Something broke in engine")

        response = self.client.post('/api/workflow/run')

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.content_type, 'application/json')
        data = json.loads(response.data)
        self.assertEqual(data.get("status"), "error")
        self.assertEqual(data.get("error_message"), "An unexpected server error occurred.")
        self.assertEqual(data.get("details"), "Something broke in engine")

    @patch('integration_platform.app.WorkflowEngine')
    def test_run_workflow_api_engine_file_not_found(self, MockWorkflowEngine):
        """Test API response when WorkflowEngine raises FileNotFoundError."""
        logger.debug("Running test_run_workflow_api_engine_file_not_found")

        # This error can be raised by engine.run_workflow if the file isn't found by it.
        mock_engine_instance = MockWorkflowEngine.return_value
        mock_engine_instance.run_workflow.side_effect = FileNotFoundError("Workflow file gone")

        response = self.client.post('/api/workflow/run')

        self.assertEqual(response.status_code, 404) # As per app.py error handling
        self.assertEqual(response.content_type, 'application/json')
        data = json.loads(response.data)
        self.assertEqual(data.get("status"), "error")
        self.assertEqual(data.get("error_message"), "Workflow definition file not found.")
        self.assertEqual(data.get("details"), "Workflow file gone")

    @patch('integration_platform.app.WorkflowEngine')
    def test_run_workflow_api_engine_connection_error(self, MockWorkflowEngine):
        """Test API response when WorkflowEngine raises ConnectionError."""
        logger.debug("Running test_run_workflow_api_engine_connection_error")

        mock_engine_instance = MockWorkflowEngine.return_value
        mock_engine_instance.run_workflow.side_effect = ConnectionError("Failed to connect to service")

        response = self.client.post('/api/workflow/run')

        self.assertEqual(response.status_code, 500) # As per app.py error handling
        self.assertEqual(response.content_type, 'application/json')
        data = json.loads(response.data)
        self.assertEqual(data.get("status"), "error")
        self.assertEqual(data.get("error_message"), "Failed to connect to an external service.")
        self.assertEqual(data.get("details"), "Failed to connect to service")

    @patch('integration_platform.app.WorkflowEngine')
    def test_run_workflow_api_engine_value_error(self, MockWorkflowEngine):
        """Test API response when WorkflowEngine raises ValueError."""
        logger.debug("Running test_run_workflow_api_engine_value_error")

        mock_engine_instance = MockWorkflowEngine.return_value
        mock_engine_instance.run_workflow.side_effect = ValueError("Bad param in engine")

        response = self.client.post('/api/workflow/run')

        self.assertEqual(response.status_code, 400) # As per app.py error handling
        self.assertEqual(response.content_type, 'application/json')
        data = json.loads(response.data)
        self.assertEqual(data.get("status"), "error")
        self.assertEqual(data.get("error_message"), "Invalid configuration or parameters for workflow/connector.")
        self.assertEqual(data.get("details"), "Bad param in engine")

    @patch('integration_platform.app.os.path.exists') # Mock os.path.exists specifically for this test
    @patch('integration_platform.app.WorkflowEngine')
    def test_run_workflow_api_workflow_file_path_logic(self, MockWorkflowEngine, mock_os_path_exists):
        """Test the workflow file path logic in the API endpoint."""
        logger.debug("Running test_run_workflow_api_workflow_file_path_logic")

        mock_engine_instance = MockWorkflowEngine.return_value
        mock_engine_instance.run_workflow.return_value = {"status": "success from path test"}

        # Scenario 1: File exists at the primary constructed path
        # app_script_dir = os.path.dirname(os.path.abspath(app.__file__))
        # primary_path = os.path.join(app_script_dir, "workflow/workflow_definition_example.json")
        # alt_path = os.path.join(os.getcwd(), "integration_platform", "workflow", "workflow_definition_example.json")

        # The path logic in app.py is:
        # script_dir = os.path.dirname(os.path.abspath(__file__)) # Directory of app.py
        # workflow_file_path = os.path.join(script_dir, "workflow/workflow_definition_example.json")
        # if not os.path.exists(workflow_file_path): alt_path...

        # Let's determine the path app.py *would* construct first.
        # Assuming app.py is in integration_platform/app.py
        # This means __file__ inside app.py points to integration_platform/app.py
        # So, script_dir becomes integration_platform/
        # And workflow_file_path becomes integration_platform/workflow/workflow_definition_example.json

        # We need to find where app.py is actually located relative to the test execution context to mock correctly.
        # For simplicity, we'll assume the test runner context allows `app.__file__` to resolve.
        app_module_path = app.__file__ # This is integration_platform/app.py
        expected_primary_path = os.path.join(os.path.dirname(app_module_path), "workflow", "workflow_definition_example.json")

        mock_os_path_exists.side_effect = lambda path: path == expected_primary_path

        response = self.client.post('/api/workflow/run')
        self.assertEqual(response.status_code, 200)
        mock_engine_instance.run_workflow.assert_called_with(expected_primary_path)

        # Scenario 2: File does not exist at primary, but exists at alternative path
        mock_os_path_exists.reset_mock()
        mock_engine_instance.run_workflow.reset_mock()

        alt_path_expected = os.path.join(os.getcwd(), "integration_platform", "workflow", "workflow_definition_example.json")
        mock_os_path_exists.side_effect = lambda path: path == alt_path_expected

        response = self.client.post('/api/workflow/run')
        self.assertEqual(response.status_code, 200)
        mock_engine_instance.run_workflow.assert_called_with(alt_path_expected)


if __name__ == '__main__':
    unittest.main()
