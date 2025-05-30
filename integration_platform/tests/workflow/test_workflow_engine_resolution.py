import unittest
from unittest.mock import patch, MagicMock
from integration_platform.workflow.workflow_engine import WorkflowEngine

# Module-level logger for tests
import logging
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG) # Uncomment to see detailed logs during test runs

class TestWorkflowEngineResolution(unittest.TestCase):

    def setUp(self):
        logger.debug("Setting up TestWorkflowEngineResolution test case.")
        # Initialize engine with no global_config for these specific tests
        self.engine = WorkflowEngine(global_config={}) 
        self.context_data = {
            "trigger": {
                "data": {"text": "Hello World", "id": 123, "value_is_none": None},
                "config": {"sheet_name": "Sheet1"}
            },
            "action1": {
                # Simulating a connector's dict output
                "output_data_key": { # Assuming connector returns a dict like {"output_data_key": actual_result}
                    "summary": "This is a summary.",
                    "details": {"status": "success", "code": 200},
                    "items": [
                        {"name": "item1", "value": 10}, 
                        {"name": "item2", "value": 20}
                    ],
                    "is_processed": True,
                    "empty_list": []
                }
            },
            "action2_error": { # Simulating an error recorded by the engine
                "status": "error",
                "error_message": "Something went wrong"
            }
        }
        # Simulate how workflow_data_cache would look
        self.engine.workflow_data_cache = self.context_data 
        logger.debug(f"Setup complete. Initial context_data: {self.context_data}")

    def test_resolve_value_simple_lookup(self):
        logger.debug("Running test_resolve_value_simple_lookup")
        self.assertEqual(self.engine._resolve_value("{trigger.data.text}", self.context_data), "Hello World")
        self.assertEqual(self.engine._resolve_value("{trigger.data.id}", self.context_data), 123)
        self.assertTrue(self.engine._resolve_value("{action1.output_data_key.is_processed}", self.context_data))
        self.assertIsNone(self.engine._resolve_value("{trigger.data.value_is_none}", self.context_data))


    def test_resolve_value_nested_lookup(self):
        logger.debug("Running test_resolve_value_nested_lookup")
        self.assertEqual(self.engine._resolve_value("{action1.output_data_key.summary}", self.context_data), "This is a summary.")
        self.assertEqual(self.engine._resolve_value("{action1.output_data_key.details.status}", self.context_data), "success")
        self.assertEqual(self.engine._resolve_value("{action1.output_data_key.details.code}", self.context_data), 200)


    def test_resolve_value_list_index_lookup(self):
        """ Test resolution of values from a list using integer index in dot notation """
        logger.debug("Running test_resolve_value_list_index_lookup")
        # The engine's _resolve_value was updated to handle numeric parts as list indices
        self.assertEqual(self.engine._resolve_value("{action1.output_data_key.items.0.name}", self.context_data), "item1")
        self.assertEqual(self.engine._resolve_value("{action1.output_data_key.items.1.value}", self.context_data), 20)

    def test_resolve_value_non_string_returns_as_is(self):
        logger.debug("Running test_resolve_value_non_string_returns_as_is")
        self.assertEqual(self.engine._resolve_value(123, self.context_data), 123)
        self.assertIsNone(self.engine._resolve_value(None, self.context_data))
        test_dict = {"key": "value"}
        self.assertEqual(self.engine._resolve_value(test_dict, self.context_data), test_dict)
        test_list = [1, 2, 3]
        self.assertEqual(self.engine._resolve_value(test_list, self.context_data), test_list)
        
    def test_resolve_value_no_curly_braces_returns_as_is(self):
        logger.debug("Running test_resolve_value_no_curly_braces_returns_as_is")
        self.assertEqual(self.engine._resolve_value("trigger.data.text", self.context_data), "trigger.data.text")
        self.assertEqual(self.engine._resolve_value("just a plain string", self.context_data), "just a plain string")

    @patch('integration_platform.workflow.workflow_engine.logger.warning')
    def test_resolve_value_key_not_found_in_dict(self, mock_logger_warning):
        logger.debug("Running test_resolve_value_key_not_found_in_dict")
        original_template = "{trigger.data.non_existent_key}"
        self.assertEqual(self.engine._resolve_value(original_template, self.context_data), original_template, 
                         "Should return original template string if key is not found.")
        mock_logger_warning.assert_called_once()
        self.assertIn("Could not resolve template key 'trigger.data.non_existent_key'", mock_logger_warning.call_args[0][0])

    @patch('integration_platform.workflow.workflow_engine.logger.warning')
    def test_resolve_value_key_not_found_in_nested_dict(self, mock_logger_warning):
        logger.debug("Running test_resolve_value_key_not_found_in_nested_dict")
        original_template = "{action1.output_data_key.details.non_existent}"
        self.assertEqual(self.engine._resolve_value(original_template, self.context_data), original_template)
        mock_logger_warning.assert_called_once()
        self.assertIn("Could not resolve template key 'action1.output_data_key.details.non_existent'", mock_logger_warning.call_args[0][0])

    @patch('integration_platform.workflow.workflow_engine.logger.warning')
    def test_resolve_value_index_error_for_list(self, mock_logger_warning):
        logger.debug("Running test_resolve_value_index_error_for_list")
        original_template = "{action1.output_data_key.items.5.name}" # Index 5 is out of bounds
        self.assertEqual(self.engine._resolve_value(original_template, self.context_data), original_template,
                         "Should return original template string on IndexError.")
        mock_logger_warning.assert_called_once()
        self.assertIn("Failed to resolve template '{action1.output_data_key.items.5.name}': Index error or invalid index '5'", mock_logger_warning.call_args[0][0])
    
    @patch('integration_platform.workflow.workflow_engine.logger.warning')
    def test_resolve_value_non_numeric_index_for_list(self, mock_logger_warning):
        logger.debug("Running test_resolve_value_non_numeric_index_for_list")
        original_template = "{action1.output_data_key.items.invalid_index.name}"
        self.assertEqual(self.engine._resolve_value(original_template, self.context_data), original_template)
        mock_logger_warning.assert_called_once()
        self.assertIn("Failed to resolve template '{action1.output_data_key.items.invalid_index.name}': Index error or invalid index 'invalid_index'", mock_logger_warning.call_args[0][0])

    @patch('integration_platform.workflow.workflow_engine.logger.warning')
    def test_resolve_value_accessing_attribute_of_list_instead_of_index(self, mock_logger_warning):
        logger.debug("Running test_resolve_value_accessing_attribute_of_list_instead_of_index")
        original_template = "{action1.output_data_key.items.name}" # 'items' is a list, 'name' is not an index
        self.assertEqual(self.engine._resolve_value(original_template, self.context_data), original_template)
        mock_logger_warning.assert_called_once()
        self.assertIn("Path part 'name' not accessible in non-dict/non-list type (<class 'list'>) at path 'action1.output_data_key.items.name'", mock_logger_warning.call_args[0][0])


    def test_prepare_action_params_simple_resolution(self):
        logger.debug("Running test_prepare_action_params_simple_resolution")
        action_config_template = {
            "prompt": "Data: {trigger.data.text}, ID: {trigger.data.id}",
            "static_param": "A static value",
            "is_true": True,
            "count": 100
        }
        resolved_params = self.engine._prepare_action_params(action_config_template, self.context_data)
        self.assertEqual(resolved_params, {
            "prompt": "Data: Hello World, ID: 123",
            "static_param": "A static value",
            "is_true": True,
            "count": 100
        })

    def test_prepare_action_params_nested_resolution(self):
        logger.debug("Running test_prepare_action_params_nested_resolution")
        action_config_template = {
            "details": {
                "summary_ref": "{action1.output_data_key.summary}",
                "trigger_id_ref": "{trigger.data.id}",
                "static_nested": {"value": 42}
            },
            "item_name_ref": "{action1.output_data_key.items.0.name}",
            "list_of_templates": [
                "{trigger.data.text}",
                "static_string",
                "{action1.output_data_key.items.1.name}"
            ]
        }
        resolved_params = self.engine._prepare_action_params(action_config_template, self.context_data)
        self.assertEqual(resolved_params, {
            "details": {
                "summary_ref": "This is a summary.",
                "trigger_id_ref": 123,
                "static_nested": {"value": 42}
            },
            "item_name_ref": "item1",
            "list_of_templates": [
                "Hello World",
                "static_string",
                "item2"
            ]
        })

    def test_prepare_action_params_unresolved_templates(self):
        logger.debug("Running test_prepare_action_params_unresolved_templates")
        action_config_template = {
            "valid_ref": "{trigger.data.text}",
            "invalid_ref": "{trigger.data.non_existent}",
            "nested_invalid": {
                "deep_ref": "{action1.output_data_key.items.5.name}"
            }
        }
        resolved_params = self.engine._prepare_action_params(action_config_template, self.context_data)
        self.assertEqual(resolved_params, {
            "valid_ref": "Hello World",
            "invalid_ref": "{trigger.data.non_existent}", # Should remain as original
            "nested_invalid": {
                "deep_ref": "{action1.output_data_key.items.5.name}" # Should remain as original
            }
        })

if __name__ == '__main__':
    unittest.main()
