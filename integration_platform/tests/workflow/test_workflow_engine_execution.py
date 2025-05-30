import unittest
from unittest.mock import patch, MagicMock, call
import os
import json

from integration_platform.workflow.workflow_engine import WorkflowEngine
# Assuming connector classes are imported in workflow_engine for patching
# from integration_platform.connectors.google_sheets_connector import GoogleSheetsConnector
# from integration_platform.connectors.openai_connector import OpenAIConnector
# from integration_platform.connectors.email_connector import EmailConnector

# Module-level logger for tests
import logging
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG) # Uncomment for detailed logs

class TestWorkflowEngineExecution(unittest.TestCase):

    def setUp(self):
        self.sample_workflow_def = {
            "name": "Test Workflow",
            "trigger": {
                "id": "test_trigger",
                "service": "simulated_service", # Not a real connector, just for trigger structure
                "event": "new_event",
                "config": {"initial_param": "trigger_value"}
            },
            "actions": [
                {
                    "id": "action_openai",
                    "service": "openai",
                    "action": "generate_text",
                    "connector_id": "openai_default",
                    "connector_config": {"api_key": "override_openai_key_in_action"}, # Example of action-specific connector config
                    "config": {
                        "prompt": "Summarize: {test_trigger.data.message}",
                        "model": "gpt-test"
                    }
                },
                {
                    "id": "action_email",
                    "service": "email",
                    "action": "send_email",
                    "connector_id": "email_default", # Reuses default if no specific connector_id
                    "config": {
                        "recipient_email": "test@example.com",
                        "subject": "Summary: {action_openai.generated_text}",
                        "body": "The summary is: {action_openai.generated_text} based on {test_trigger.data.message}"
                    }
                }
            ]
        }
        self.global_config = {
            "OPENAI_API_KEY": "global_openai_key",
            "SMTP_HOST": "smtp.global.com",
            "SMTP_PORT": "587", # Engine or connector should handle int conversion
            "SMTP_USER": "global_user",
            "SMTP_PASSWORD": "global_password"
            # Simulation flags can also be here or as env vars
        }
        # Patch os.getenv for consistent testing of config priority
        self.getenv_patcher = patch.dict(os.environ, {
            "OPENAI_API_KEY": "env_openai_key", # This would be overridden by global/action normally
            "SMTP_HOST": "smtp.env.com" 
            # Other env vars for connectors if needed
        }, clear=True) # Clear other env vars that might interfere
        self.mock_getenv = self.getenv_patcher.start()

    def tearDown(self):
        self.getenv_patcher.stop()

    # Patch all known connector classes imported by WorkflowEngine
    @patch('integration_platform.workflow.workflow_engine.EmailConnector')
    @patch('integration_platform.workflow.workflow_engine.OpenAIConnector')
    @patch('integration_platform.workflow.workflow_engine.GoogleSheetsConnector')
    def test_run_workflow_success(self, MockGoogleSheets, MockOpenAI, MockEmail):
        logger.debug("Running test_run_workflow_success")

        # Configure mocks for connector instances
        mock_openai_instance = MockOpenAI.return_value
        mock_openai_instance.connect.return_value = True
        mock_openai_instance.execute_action.return_value = {"generated_text": "Mocked AI Summary"}

        mock_email_instance = MockEmail.return_value
        mock_email_instance.connect.return_value = True
        mock_email_instance.execute_action.return_value = {"status": "sent"}

        engine = WorkflowEngine(global_config=self.global_config)
        results = engine.run_workflow(self.sample_workflow_def)

        # Assertions for OpenAI connector
        # _get_connector will be called for 'openai_default'
        # Check if OpenAIConnector was instantiated with the action-specific key
        MockOpenAI.assert_called_once_with(api_key="override_openai_key_in_action")
        mock_openai_instance.connect.assert_called_once()
        mock_openai_instance.execute_action.assert_called_once_with(
            "generate_text",
            {"prompt": "Summarize: Simulated trigger data for 'test_trigger'", "model": "gpt-test"}
        )
        
        # Assertions for Email connector
        # _get_connector for 'email_default'
        # Email connector should use global_config then os.getenv for its params
        MockEmail.assert_called_once_with(
            smtp_host="smtp.global.com", # From global_config
            smtp_port=587,              # From global_config (engine converts to int)
            smtp_user="global_user",    # From global_config
            smtp_password="global_password", # From global_config
            sender_email="global_user", # Defaults to smtp_user
            use_tls=True                # Default
        )
        mock_email_instance.connect.assert_called_once()
        mock_email_instance.execute_action.assert_called_once_with(
            "send_email",
            {
                "recipient_email": "test@example.com",
                "subject": "Summary: Mocked AI Summary",
                "body": "The summary is: Mocked AI Summary based on Simulated trigger data for 'test_trigger'"
            }
        )

        # Check workflow_data_cache content
        self.assertIn("test_trigger", results)
        self.assertEqual(results["test_trigger"]["data"]["message"], "Simulated trigger data for 'test_trigger'")
        self.assertIn("action_openai", results)
        self.assertEqual(results["action_openai"], {"generated_text": "Mocked AI Summary"})
        self.assertIn("action_email", results)
        self.assertEqual(results["action_email"], {"status": "sent"})


    @patch('integration_platform.workflow.workflow_engine.EmailConnector')
    @patch('integration_platform.workflow.workflow_engine.OpenAIConnector')
    @patch('integration_platform.workflow.workflow_engine.GoogleSheetsConnector')
    @patch('integration_platform.workflow.workflow_engine.traceback.format_exc') # Mock traceback
    def test_run_workflow_action_failure(self, mock_format_exc, MockGoogleSheets, MockOpenAI, MockEmail):
        logger.debug("Running test_run_workflow_action_failure")
        mock_format_exc.return_value = "Mocked Traceback"

        mock_openai_instance = MockOpenAI.return_value
        mock_openai_instance.connect.return_value = True
        # Simulate failure in the first action (OpenAI)
        mock_openai_instance.execute_action.side_effect = Exception("Mocked OpenAI Action Error")

        mock_email_instance = MockEmail.return_value # This will still be prepared
        mock_email_instance.connect.return_value = True 
        
        engine = WorkflowEngine(global_config=self.global_config)
        results = engine.run_workflow(self.sample_workflow_def)

        # OpenAI action should have failed
        self.assertIn("action_openai", results)
        self.assertEqual(results["action_openai"]["status"], "error")
        self.assertEqual(results["action_openai"]["error_message"], "Mocked OpenAI Action Error")
        self.assertEqual(results["action_openai"]["details"], "Mocked Traceback")

        # Email action should still be attempted because it doesn't depend on a successful OpenAI output
        # for all its template variables (subject uses it, body uses it AND trigger).
        # The _resolve_value will return the original template string for {action_openai.generated_text}
        mock_email_instance.execute_action.assert_called_once_with(
            "send_email",
            {
                "recipient_email": "test@example.com",
                "subject": "Summary: {action_openai.generated_text}", # Unresolved due to error
                "body": "The summary is: {action_openai.generated_text} based on Simulated trigger data for 'test_trigger'"
            }
        )
        # The email action itself would then likely succeed or fail based on its own execution,
        # assuming its connector is fine. Here we mock it as successful.
        self.assertIn("action_email", results) 
        # If email execute_action was successful despite unresolved template (which it might be if it just sends the string as is)
        # Or, it could fail if the email connector tries to validate the content.
        # For this test, we assume it proceeds and the mock returns success.
        # Modify this if EmailConnector's execute_action would fail on unresolved templates.
        # mock_email_instance.execute_action.return_value = {"status": "sent"} # Already set by default mock

    @patch('builtins.open', new_callable=mock_open, read_data='{"name": "Loaded Workflow", "trigger": {"id":"t"}, "actions":[]}')
    @patch('json.load')
    def test_load_workflow_from_file_success(self, mock_json_load, mock_file_open):
        logger.debug("Running test_load_workflow_from_file_success")
        mock_json_load.return_value = {"name": "Loaded Workflow", "trigger": {"id":"t"}, "actions":[]}
        
        engine = WorkflowEngine()
        definition = engine.load_workflow_definition("dummy_path.json")

        mock_file_open.assert_called_once_with("dummy_path.json", 'r')
        mock_json_load.assert_called_once()
        self.assertEqual(definition["name"], "Loaded Workflow")

    @patch('builtins.open', side_effect=FileNotFoundError("File not found"))
    def test_load_workflow_file_not_found(self, mock_file_open):
        logger.debug("Running test_load_workflow_file_not_found")
        engine = WorkflowEngine()
        with self.assertRaises(FileNotFoundError):
            engine.load_workflow_definition("non_existent.json")
    
    @patch('builtins.open', new_callable=mock_open, read_data='invalid json')
    @patch('json.load', side_effect=json.JSONDecodeError("Decode error", "doc", 0))
    def test_load_workflow_invalid_json(self, mock_json_load, mock_file_open):
        logger.debug("Running test_load_workflow_invalid_json")
        engine = WorkflowEngine()
        with self.assertRaises(json.JSONDecodeError):
            engine.load_workflow_definition("invalid.json")

    @patch('integration_platform.workflow.workflow_engine.OpenAIConnector')
    def test_get_connector_caching(self, MockOpenAI):
        logger.debug("Running test_get_connector_caching")
        mock_openai_instance = MockOpenAI.return_value
        mock_openai_instance.connect.return_value = True

        engine = WorkflowEngine(global_config=self.global_config)
        
        # First call for a connector_id
        connector1 = engine._get_connector("openai", "my_shared_openai", {"api_key": "key1"})
        MockOpenAI.assert_called_once_with(api_key="key1") # Instantiated with specific config
        connector1.connect.assert_called_once()
        
        # Second call for the same connector_id
        connector2 = engine._get_connector("openai", "my_shared_openai", {"api_key": "key2"}) # Config ignored
        
        self.assertIs(connector1, connector2) # Should be the same instance
        MockOpenAI.assert_called_once() # Still only one instantiation
        connector1.connect.assert_called_once() # Connect should not be called again if already connected (depends on connector's connect)
                                                # Current engine calls connect() each time _get_connector creates *new*.
                                                # If connector is cached, connect() on it isn't re-called by _get_connector.
                                                # This test is fine.

if __name__ == '__main__':
    unittest.main()
