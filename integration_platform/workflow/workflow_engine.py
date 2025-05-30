import json
import os
import logging
import re # For template resolution

# Import connector classes
from ..connectors.google_sheets_connector import GoogleSheetsConnector
from ..connectors.openai_connector import OpenAIConnector
from ..connectors.email_connector import EmailConnector
# Import BaseConnector for type hinting if needed, though not strictly required for this impl
# from ..connectors.base_connector import BaseConnector
import traceback # For capturing tracebacks in error reporting

# logger = logging.getLogger(__name__) # Already exists, ensure it's used.
# This file already has 'logger = logging.getLogger(__name__)'

class WorkflowEngine:
    """
    Orchestrates the execution of workflows defined in JSON format.
    Manages connector instantiation, data flow, and template resolution.
    """

    def __init__(self, global_config: dict = None):
        """
        Initializes the WorkflowEngine.

        Args:
            global_config (dict, optional): A dictionary containing global configurations,
                                            such as API keys or paths, that can be used by connectors.
                                            Example: {'OPENAI_API_KEY': '...', 'GOOGLE_CREDENTIALS_PATH': '...' }
                                            Defaults to an empty dictionary if None.
        """
        self.global_config = global_config if global_config is not None else {}
        self.connectors = {}  # Stores instantiated connector objects, keyed by a unique connector_id from workflow
        self.workflow_data_cache = {} # Stores outputs from trigger and actions, keyed by their ID
        logger.info("WorkflowEngine initialized.")
        if self.global_config:
            logger.info(f"Global config loaded: {list(self.global_config.keys())}") # Log only keys for security

    def load_workflow_definition(self, definition_path: str) -> dict:
        """
        Loads a workflow definition from a JSON file.

        Args:
            definition_path (str): The path to the JSON workflow definition file.

        Returns:
            dict: The parsed workflow definition.

        Raises:
            FileNotFoundError: If the definition file is not found.
            json.JSONDecodeError: If the file is not valid JSON.
            Exception: For other I/O errors.
        """
        logger.info(f"Loading workflow definition from: {definition_path}")
        try:
            with open(definition_path, 'r') as f:
                definition = json.load(f)
            logger.info(f"Successfully loaded workflow: {definition.get('name', 'Unnamed Workflow')}")
            return definition
        except FileNotFoundError:
            logger.error(f"Workflow definition file not found at {definition_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in workflow definition file {definition_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading workflow definition file {definition_path}: {e}", exc_info=True)
            raise

    def _get_connector(self, service_name: str, connector_id: str, connector_config_from_workflow: dict):
        """
        Retrieves an existing connector instance or creates, configures, and connects a new one.

        Args:
            service_name (str): The type of service (e.g., "openai", "google_sheets").
            connector_id (str): A unique identifier for this connector instance within the workflow.
            connector_config_from_workflow (dict): Configuration specific to this connector instance,
                                                   defined in the workflow action.

        Returns:
            An instance of the requested connector, already connected.

        Raises:
            ValueError: If the service_name is unknown or required configuration is missing.
            ConnectionError: If the connector fails to connect.
        """
        if connector_id in self.connectors:
            logger.info(f"Returning existing connector instance for ID: {connector_id}")
            return self.connectors[connector_id]

        logger.info(f"Creating new connector for service: '{service_name}', ID: '{connector_id}'")
        connector = None
        
        # Configuration priority:
        # 1. connector_config_from_workflow (specific to this action's connector instance)
        # 2. self.global_config (workflow-wide settings)
        # 3. os.getenv() (environment variables)

        if service_name == "openai":
            api_key = connector_config_from_workflow.get('api_key') or \
                      self.global_config.get('OPENAI_API_KEY') or \
                      os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError(f"OpenAI API key not found for connector '{connector_id}'. Provide in workflow, global_config, or OPENAI_API_KEY env var.")
            connector = OpenAIConnector(api_key=api_key)

        elif service_name == "google_sheets":
            # Default paths can be defined here or rely on connector defaults if sensible
            default_creds_path = "credentials.json" # Could also come from global_config
            default_token_path = "token.json"       # Could also come from global_config

            client_secret_file = connector_config_from_workflow.get('client_secret_file_path') or \
                                 self.global_config.get('GOOGLE_CLIENT_SECRET_FILE') or \
                                 os.getenv('GOOGLE_CLIENT_SECRET_FILE') or \
                                 default_creds_path
            token_file_path = connector_config_from_workflow.get('token_file_path') or \
                              self.global_config.get('GOOGLE_TOKEN_FILE_PATH') or \
                              os.getenv('GOOGLE_TOKEN_FILE_PATH') or \
                              default_token_path
            
            if not os.path.exists(client_secret_file):
                 # Note: This check is done here, but connector's connect() also checks.
                 # Redundant but can provide earlier feedback in workflow engine.
                 logger.warning(f"Google Sheets client_secret_file ('{client_secret_file}') not found for connector '{connector_id}'. Authentication will likely fail if token doesn't exist.")
            
            connector = GoogleSheetsConnector(client_secret_file=client_secret_file, token_file_path=token_file_path)

        elif service_name == "email":
            smtp_host = connector_config_from_workflow.get('smtp_host') or \
                        self.global_config.get('SMTP_HOST') or \
                        os.getenv('SMTP_HOST')
            smtp_port_str = str(connector_config_from_workflow.get('smtp_port') or \
                            self.global_config.get('SMTP_PORT') or \
                            os.getenv('SMTP_PORT'))
            smtp_user = connector_config_from_workflow.get('smtp_user') or \
                        self.global_config.get('SMTP_USER') or \
                        os.getenv('SMTP_USER')
            smtp_password = connector_config_from_workflow.get('smtp_password') or \
                            self.global_config.get('SMTP_PASSWORD') or \
                            os.getenv('SMTP_PASSWORD')
            sender_email = connector_config_from_workflow.get('sender_email') or \
                           self.global_config.get('SENDER_EMAIL') or \
                           os.getenv('SENDER_EMAIL') or \
                           smtp_user # Default sender to smtp_user if not specified

            if not all([smtp_host, smtp_port_str, smtp_user, smtp_password]):
                raise ValueError(f"SMTP configuration (host, port, user, password) missing for connector '{connector_id}'.")
            try:
                smtp_port = int(smtp_port_str)
            except ValueError:
                raise ValueError(f"Invalid SMTP port '{smtp_port_str}' for connector '{connector_id}'. Must be an integer.")

            use_tls = connector_config_from_workflow.get('use_tls', True) # Default to True
            if isinstance(use_tls, str): use_tls = use_tls.lower() == 'true'


            connector = EmailConnector(smtp_host=smtp_host, smtp_port=smtp_port, 
                                       smtp_user=smtp_user, smtp_password=smtp_password,
                                       sender_email=sender_email, use_tls=use_tls)
        else:
            raise ValueError(f"Unknown service name: '{service_name}' for connector '{connector_id}'")

        if connector:
            try:
                connector.connect() # Attempt to connect the newly created connector
                self.connectors[connector_id] = connector
                logger.info(f"Connector '{connector_id}' for service '{service_name}' created and connected.")
                return connector
            except ConnectionError as e:
                logger.error(f"Failed to connect connector '{connector_id}' for service '{service_name}': {e}", exc_info=True)
                # Don't store it if connection failed.
                # Let's ensure the original exception context is preserved if we re-raise.
                # raise ConnectionError(f"Failed to connect connector '{connector_id}' for service '{service_name}'") from e
                # The current 'raise' without arguments already preserves context.
                raise 
        else:
            # This case should ideally be caught by the "Unknown service name" error above.
            # However, if it's reached, it indicates a logic flaw in the connector selection.
            err_msg = f"Failed to instantiate connector for service '{service_name}' (connector object is None after attempt)."
            logger.error(err_msg)
            raise Exception(err_msg)


    def _resolve_value(self, value, context_data: dict):
        """
        Resolves a value that might be a template string (e.g., "{trigger.data.text}").

        Args:
            value: The value to resolve (can be any type, but templating only applies to strings).
            context_data (dict): The workflow data cache (self.workflow_data_cache).

        Returns:
            The resolved value. If the original value was not a string or not a template,
            it's returned as is. If a template key is not found, the original template string
            is returned with a warning.
        """
        if not isinstance(value, str):
            return value

        # Regex to find patterns like {action_id.key1.key2[0].key3}
        # This version is simplified and looks for {step_id.path.to.value}
        # A more robust regex would handle list indices like [0] and nested dicts.
        # For now, we split by '.' for path traversal.
        match = re.fullmatch(r"\{([\w.-]+)\}", value)
        if not match:
            return value # Not a template string of the expected format

        template_key = match.group(1)
        keys = template_key.split('.')
        
        current_val = context_data
        try:
            for i, key_part in enumerate(keys):
                if isinstance(current_val, dict):
                    current_val = current_val[key_part]
                elif isinstance(current_val, list):
                    try:
                        idx = int(key_part)
                        current_val = current_val[idx]
                    except (ValueError, IndexError) as list_e:
                        # Path part is not a valid index or out of bounds
                        path_so_far = ".".join(keys[:i+1])
                        logger.warning(f"Failed to resolve template '{value}': Index error or invalid index '{key_part}' for list at path '{path_so_far}'. Error: {list_e}")
                        return value # Return original template string
                else:
                    # Path part cannot be resolved on current_val type
                    path_so_far = ".".join(keys[:i+1])
                    logger.warning(f"Failed to resolve template '{value}': Path part '{key_part}' not accessible in non-dict/non-list type ({type(current_val)}) at path '{path_so_far}'.")
                    return value # Return original template string
            
            # Successfully resolved the entire path
            logger.debug(f"Resolved template '{value}' to: {current_val}")
            return current_val
        except (KeyError, TypeError) as e: # KeyError for dicts, TypeError for unexpected types during access
            path_so_far = ".".join(keys) # This might not show the exact failing part easily without iterating keys again
            logger.warning(f"Could not resolve template key '{template_key}' (path: {path_so_far}) from '{value}'. Error: {e}. Returning original string.")
            return value # Return original template string if resolution fails

    def _prepare_action_params(self, action_config_template: dict, context_data: dict) -> dict:
        """
        Prepares parameters for an action by resolving any template strings in its config.

        Args:
            action_config_template (dict): The action's configuration dictionary, potentially containing template strings.
            context_data (dict): The current workflow data cache.

        Returns:
            dict: A new dictionary with all template strings resolved to their actual values.
        """
        resolved_params = {}
        if not isinstance(action_config_template, dict):
            logger.warning(f"Action config template is not a dictionary: {action_config_template}. Returning empty params.")
            return resolved_params

        for key, val_template in action_config_template.items():
            if isinstance(val_template, str):
                resolved_params[key] = self._resolve_value(val_template, context_data)
            elif isinstance(val_template, list): # Handle lists of templates (simple case)
                resolved_params[key] = [self._resolve_value(item, context_data) if isinstance(item, str) else item for item in val_template]
            elif isinstance(val_template, dict): # Handle nested dicts of templates
                resolved_params[key] = self._prepare_action_params(val_template, context_data) # Recursive call
            else:
                resolved_params[key] = val_template # Not a string, list or dict, so pass as is
        logger.debug(f"Prepared action params: {resolved_params}")
        return resolved_params

    def run_workflow(self, definition_path_or_dict):
        """
        Runs a workflow based on a definition (either a file path or a pre-loaded dictionary).

        Args:
            definition_path_or_dict (str or dict): Path to the JSON file defining the workflow,
                                                   or the workflow definition as a dictionary.
        Returns:
            dict: The final workflow data cache containing outputs from all steps.
        
        Raises:
            Exception: If critical errors occur during workflow loading or execution.
        """
        logger.info("Starting workflow run...")
        self.workflow_data_cache = {} # Reset data cache for this run
        # Do not reset self.connectors here if you want them to persist across calls to run_workflow
        # with the same engine instance. For isolated runs, resetting is fine.
        # For now, let's assume connectors can be reused if connector_ids are the same.
        # A more robust approach might involve a dedicated cleanup/reset method or explicit connector management.
        
        try:
            if isinstance(definition_path_or_dict, str):
                workflow_definition = self.load_workflow_definition(definition_path_or_dict)
            elif isinstance(definition_path_or_dict, dict):
                workflow_definition = definition_path_or_dict
            else:
                raise TypeError("Workflow definition must be a file path (str) or a dictionary.")

            logger.info(f"Executing workflow: {workflow_definition.get('name', 'Unnamed Workflow')}")

            # --- Trigger Processing (Simulation for now) ---
            trigger_config = workflow_definition.get('trigger')
            if not trigger_config:
                logger.warning("Workflow definition has no trigger. Proceeding with empty trigger data.")
                # Allow workflows without explicit triggers, or handle as error if required.
                self.workflow_data_cache['trigger'] = {"data": {"message": "No trigger defined"}}
            else:
                trigger_id = trigger_config.get('id', 'trigger') # Default ID if not specified
                # In a real scenario, this would involve:
                # 1. Getting the trigger connector (self._get_connector for trigger_config.get('service'))
                # 2. Listening for or polling an event via the connector.
                # 3. The connector would return data upon event occurrence.
                # For now, simulate with placeholder data.
                # This structure should align with what downstream actions expect from the trigger.
                trigger_data_field = {
                    "message": f"Simulated trigger data for '{trigger_id}' (e.g., new row detected).",
                    "new_row_number": 1,  # Example: Simulate that the new data is in row 1 (or a specific row number)
                    "sheet_id_from_trigger_event": trigger_config.get('config', {}).get('sheet_id', 'unknown_sheet_id_in_trigger_sim'), # Example data from event
                    # Add any other data a real trigger for this service/event might provide
                }
                simulated_trigger_output_for_cache = {
                    "data": trigger_data_field,
                    "config": trigger_config.get('config', {}) # Make the trigger's own configuration available under its ID
                }
                self.workflow_data_cache[trigger_id] = simulated_trigger_output_for_cache
                logger.info(f"Simulated trigger '{trigger_id}' executed. Output stored in cache: {simulated_trigger_output_for_cache}")

            # --- Action Execution Loop ---
            actions = workflow_definition.get('actions', [])
            if not actions:
                logger.info("Workflow has no actions to execute.")
            
            for action_def in actions:
                action_id = action_def.get('id')
                if not action_id:
                    logger.error(f"Action definition is missing 'id'. Skipping: {action_def}")
                    # Or raise ValueError("Action ID is mandatory")
                    continue 
                
                service_name = action_def.get('service')
                action_name = action_def.get('action') # Specific method on the connector
                
                if not service_name or not action_name:
                    logger.error(f"Action '{action_id}' is missing 'service' or 'action' name. Skipping.")
                    self.workflow_data_cache[action_id] = {
                        "status": "error", 
                        "error_message": "Missing service or action name in definition",
                        "details": f"Action definition: {action_def}"
                    }
                    continue

                connector_id_from_def = action_def.get('connector_id', action_id) 
                action_config_template = action_def.get('config', {}) 
                connector_specific_config = action_def.get('connector_config', {})

                logger.info(f"--- Preparing action: '{action_id}' (Service: {service_name}, Action: {action_name}, Connector ID: {connector_id_from_def}) ---")

                try:
                    connector = self._get_connector(service_name, connector_id_from_def, connector_specific_config)
                    
                    logger.debug(f"Action '{action_id}' - Original params template from workflow: {action_config_template}")
                    execute_action_params = self._prepare_action_params(action_config_template, self.workflow_data_cache)
                    logger.info(f"Action '{action_id}' - Resolved params for connector.execute_action: {execute_action_params}")
                    
                    current_action_output = connector.execute_action(action_name, execute_action_params)
                    
                    # Ensure output is serializable and consistent (dict)
                    if not isinstance(current_action_output, dict):
                        logger.warning(f"Output from action '{action_id}' (service: {service_name}, action: {action_name}) is not a dictionary: {type(current_action_output)}. Wrapping it.")
                        current_action_output = {"result": current_action_output}
                    
                    self.workflow_data_cache[action_id] = current_action_output
                    logger.info(f"Action '{action_id}' executed successfully. Output stored in workflow_data_cache.")
                    logger.debug(f"Action '{action_id}' - Output data: {current_action_output}")

                except ValueError as ve: 
                    err_msg = f"Configuration or Value error for action '{action_id}': {str(ve)}"
                    logger.error(err_msg, exc_info=True)
                    self.workflow_data_cache[action_id] = {"status": "error", "error_message": err_msg, "details": traceback.format_exc()}
                except ConnectionError as ce:
                    err_msg = f"Connection error for action '{action_id}' with service '{service_name}': {str(ce)}"
                    logger.error(err_msg, exc_info=True)
                    self.workflow_data_cache[action_id] = {"status": "error", "error_message": err_msg, "details": traceback.format_exc()}
                except Exception as e: # Catch any other exceptions from connector.execute_action or param preparation
                    err_msg = f"Unexpected error executing action '{action_id}': {str(e)}"
                    logger.error(err_msg, exc_info=True)
                    self.workflow_data_cache[action_id] = {"status": "error", "error_message": err_msg, "details": traceback.format_exc()}
                
                logger.info(f"--- Finished action: '{action_id}' ---")


            logger.info("Workflow run completed.")
            return self.workflow_data_cache

        except Exception as e:
            logger.error(f"Critical error during workflow execution: {e}", exc_info=True)
            # Optionally, re-raise or return a specific error object/status
            raise # Re-raise the caught exception to signal overall failure

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # For the example to run, you might need to:
    # 1. Create a dummy 'credentials.json' and 'token.json' if Google Sheets connector is used.
    #    (The connector itself has notes on this for its __main__ block).
    # 2. Set environment variables for API keys/SMTP details if not hardcoded in global_config
    #    or workflow definition (which is not recommended for secrets).
    #    Example: export OPENAI_API_KEY="your_openai_key"
    #             export SMTP_HOST="..." SMTP_PORT="..." etc.
    #
    # For simulation of connector API calls (to avoid actual external calls):
    #    export OPENAI_API_SIMULATE="true"
    #    export EMAIL_SIMULATE="true" 
    #    (GoogleSheetsConnector has its own simulation notes, currently simulates get_sheet_data for a specific ID)

    engine = WorkflowEngine(global_config={
        # Example of global configs - these could be overridden by connector_config in workflow or env vars
        # "OPENAI_API_KEY": "sk-global_config_key_example", 
        # "SMTP_USER": "global_user@example.com",
        # "SMTP_PASSWORD": "global_password"
    })

    # Path to the example workflow definition
    # Assumes this script is run from the project root (e.g., `python -m integration_platform.workflow.workflow_engine`)
    # Or adjust path accordingly if run directly. Example:
    # definition_file = "integration_platform/workflow/workflow_definition_example.json"
    # Ensure the path is correct based on where you run the script from.
    # If running `python -m integration_platform.workflow.workflow_engine` from project root:
    definition_file_from_module_run = "workflow_definition_example.json" # Path relative to this file's dir
    
    # If running `python integration_platform/workflow/workflow_engine.py` from project root:
    definition_file_from_script_run = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 
        "workflow_definition_example.json"
    )

    # Choose the appropriate path
    definition_file = definition_file_from_script_run 
    if not os.path.exists(definition_file):
        definition_file = definition_file_from_module_run # Fallback for -m execution

    logger.info(f"Attempting to run example workflow: {definition_file}")
    if not os.path.exists(definition_file):
        logger.error(f"ERROR: Workflow definition example not found at {definition_file} (and fallback).")
        logger.error("Please ensure the file exists or adjust the path.")
    else:
        try:
            # Create dummy credentials files for Google Sheets if they don't exist AND
            # if "google_sheets" is mentioned in the workflow (basic check)
            # This is for the __main__ example to pass _get_connector file checks in simulation.
            try:
                with open(definition_file, 'r') as f_check:
                    workflow_content_for_check = f_check.read()
            except Exception:
                 workflow_content_for_check = "" # Default if file read fails (shouldn't happen if path check passed)

            if "google_sheets" in workflow_content_for_check:
                if not os.path.exists("credentials.json"):
                    logger.warning("Creating dummy 'credentials.json' for WorkflowEngine __main__ example.")
                    with open("credentials.json", "w") as f:
                        f.write('{"installed":{"client_id":"dummy","project_id":"dummy","auth_uri":"dummy","token_uri":"dummy","auth_provider_x509_cert_url":"dummy","client_secret":"dummy","redirect_uris":["http://localhost"]}}')
                if not os.path.exists("token.json"):
                    logger.warning("Creating dummy 'token.json' for WorkflowEngine __main__ example.")
                    with open("token.json", "w") as f:
                        f.write('{"token": "dummy", "refresh_token": "dummy", "token_uri": "https://oauth2.googleapis.com/token", "client_id": "dummy", "client_secret": "dummy", "scopes": ["https://www.googleapis.com/auth/spreadsheets"]}')

            final_data_cache = engine.run_workflow(definition_file)
            logger.info("\n--- Workflow Execution Finished ---")
            logger.info("Final Workflow Data Cache (output from engine.run_workflow):")
            try:
                # Pretty print the JSON output using logger for consistency
                logged_output = json.dumps(final_data_cache, indent=2, default=str)
                for line in logged_output.splitlines():
                    logger.info(line) # Log each line of the JSON
            except TypeError:
                logger.error(f"Could not serialize workflow results to JSON directly. Raw data: {final_data_cache}")


            # Check for errors in specific actions
            if isinstance(final_data_cache, dict):
                for action_id, result_data in final_data_cache.items():
                    if isinstance(result_data, dict) and result_data.get("status") == "error":
                        logger.warning(f"Error occurred in action '{action_id}': {result_data.get('error_message')}")
                        if result_data.get('details'):
                            logger.debug(f"Error details for '{action_id}':\n{result_data['details']}")
            
        except FileNotFoundError:
            logger.error(f"Example workflow definition not found. Ensure '{definition_file}' exists.")
        except Exception as e:
            logger.critical(f"An error occurred during the example workflow run in __main__: {e}", exc_info=True)

    # Clean up dummy files if created (optional, good for testing)
    # Be cautious with this in real environments.
    # if os.path.exists("credentials.json") and 'dummy' in open("credentials.json").read():
    #     os.remove("credentials.json")
    # if os.path.exists("token.json") and "dummy" in open("token.json").read():
    #     os.remove("token.json")
