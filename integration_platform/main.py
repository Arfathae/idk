"""
Main entry point for the Integration Platform.
This script loads configurations, initializes the WorkflowEngine,
and executes a specified workflow definition.
"""
import os
import argparse
import json
import logging

from integration_platform.workflow.workflow_engine import WorkflowEngine
# from integration_platform.core.logging_config import setup_logging # Assuming you might use this later

from integration_platform.core.logging_config import setup_logging

# Configure logging as early as possible
# The setup_logging function now configures the root logger.
# We can still get a specific logger for this module if desired,
# or directly use logging.info, logging.error etc. which will use the root logger's config.
setup_logging() # Defaults to INFO level
logger = logging.getLogger(__name__) # Get a logger specific to this module

def main():
    """
    Main execution function for the integration platform.
    - Parses command-line arguments for the workflow definition file.
    - Loads global configurations from environment variables.
    - Initializes and runs the WorkflowEngine.
    - Prints the results of the workflow execution.
    """
    parser = argparse.ArgumentParser(description="Integration Platform Workflow Runner")
    parser.add_argument(
        "--workflow",
        type=str,
        default="integration_platform/workflow/workflow_definition_example.json",
        help="Path to the workflow definition JSON file."
    )
    args = parser.parse_args()
    workflow_file_path = args.workflow

    logger.info(f"Attempting to run workflow from: {workflow_file_path}")

    if not os.path.exists(workflow_file_path):
        logger.error(f"Workflow definition file not found: {workflow_file_path}")
        # Keep user-facing print for direct CLI feedback on critical startup error
        print(f"Error: Workflow file '{workflow_file_path}' not found. Please provide a valid path.")
        return

    # Populate global_config from environment variables
    # This makes configurations external and flexible.
    global_config = {
        # Google Sheets Connector Config
        "GOOGLE_CLIENT_SECRET_FILE": os.getenv("GOOGLE_CLIENT_SECRET_FILE"), # e.g., "credentials.json"
        "GOOGLE_TOKEN_FILE_PATH": os.getenv("GOOGLE_TOKEN_FILE_PATH"),          # e.g., "token.json"

        # OpenAI Connector Config
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),

        # Email Connector Config
        "SMTP_HOST": os.getenv("SMTP_HOST"),
        "SMTP_PORT": os.getenv("SMTP_PORT"), # Ensure this is cast to int in the engine or connector
        "SMTP_USER": os.getenv("SMTP_USER"),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD"),
        "SENDER_EMAIL": os.getenv("SENDER_EMAIL", os.getenv("SMTP_USER")), # Default sender to SMTP_USER

        # Simulation Flags (read as strings, connectors/engine should handle conversion to bool)
        "OPENAI_API_SIMULATE": os.getenv("OPENAI_API_SIMULATE", "false"),
        "EMAIL_SIMULATE": os.getenv("EMAIL_SIMULATE", "false"),
        "GOOGLE_SHEETS_SIMULATE_API_CALLS": os.getenv("GOOGLE_SHEETS_SIMULATE_API_CALLS", "false"), # For GSheets connector specific simulation
    }

    # Filter out None values to only pass explicitly set environment variables or workflow-defined defaults
    global_config = {k: v for k, v in global_config.items() if v is not None}

    logger.info("Global configuration loaded from environment variables (values are masked for security if sensitive):")
    for key, value in global_config.items():
        if "API_KEY" in key.upper() or "PASSWORD" in key.upper() or "SECRET" in key.upper():
            logger.info(f"  {key}: ****** (sensitive)")
        else:
            logger.info(f"  {key}: {value}")

    # Note: The WorkflowEngine and connectors will now directly use os.getenv for simulation flags
    # if not provided via connector_config or global_config.
    # Setting them in os.environ here based on global_config might be redundant if connectors
    # already have a clear priority (connector_config -> global_config -> os.getenv).
    # Let's remove this block as the engine's _get_connector and individual connectors should handle this.
    # Example: OpenAIConnector checks self.api_key (from global_config) then os.getenv().
    # Simulation flags in connectors also check os.getenv().

    engine = WorkflowEngine(global_config=global_config)

    try:
        logger.info(f"Initializing WorkflowEngine and running workflow: {workflow_file_path}")
        workflow_results = engine.run_workflow(workflow_file_path)

        logger.info("Workflow execution completed.")
        print("\n--- Workflow Execution Results ---")
        try:
            print(json.dumps(workflow_results, indent=2, default=str))
        except TypeError as e:
            logger.error(f"Could not serialize workflow results to JSON directly: {e}. Printing raw result object.")
            print(workflow_results) # User-facing print for the raw output

        # Check for errors in the results for user feedback
        has_errors = False
        if isinstance(workflow_results, dict):
            for step_id, result_data in workflow_results.items(): # Renamed 'result' to 'result_data' to avoid conflict
                if isinstance(result_data, dict) and "error" in result_data: # Check 'result_data'
                    logger.error(f"Error reported in workflow step '{step_id}': {result_data['error']}")
                    has_errors = True

        if has_errors:
            logger.warning("Workflow execution completed with one or more errors reported by steps.")
            # User-facing print for this important status
            print("\nWARNING: Workflow completed, but one or more steps reported errors. Please check the logs and output above.")
        else:
            logger.info("Workflow execution completed successfully with no errors reported by steps in the final cache.")
            # User-facing print for success
            print("\nWorkflow finished successfully.")

    except FileNotFoundError:
        logger.critical(f"Workflow definition file '{workflow_file_path}' not found during engine run.")
        # User-facing print for this critical startup error
        print(f"Error: Workflow file '{workflow_file_path}' could not be processed by the engine because it was not found.")
    except json.JSONDecodeError as e:
        logger.critical(f"Invalid JSON in workflow file '{workflow_file_path}': {e.msg} at line {e.lineno} col {e.colno}")
        print(f"Error: Invalid JSON in workflow file '{workflow_file_path}'. Details: {e.msg} at line {e.lineno} col {e.colno}")
    except ConnectionError as e:
        logger.critical(f"A Connection Error occurred during workflow execution: {e}", exc_info=True)
        print(f"Error: A connection attempt failed during workflow execution. Details: {e}")
    except ValueError as e:
        logger.critical(f"A Value Error (e.g., missing configuration) occurred during workflow execution: {e}", exc_info=True)
        print(f"Error: A configuration or value error occurred. Details: {e}")
    except Exception as e:
        logger.critical(f"An unexpected critical error occurred during workflow execution: {e}", exc_info=True)
        # User-facing print for unexpected errors
        print(f"An unexpected critical error occurred: {e}. Check logs for detailed traceback.")

if __name__ == "__main__":
    # To run this:
    # 1. Ensure your connectors are correctly implemented.
    # 2. Make sure 'workflow_definition_example.json' is in the 'workflow' subdirectory relative to this script,
    #    or provide the correct path using --workflow argument.
    # 3. Set necessary environment variables for credentials (e.g., OPENAI_API_KEY)
    #    OR set simulation flags (e.g., OPENAI_API_SIMULATE=true) to avoid real API calls.
    #
    # Example execution from the project root:
    # python -m integration_platform.main --workflow integration_platform/workflow/workflow_definition_example.json
    #
    # To enable simulation for all relevant connectors:
    # export OPENAI_API_SIMULATE="true"
    # export EMAIL_SIMULATE="true"
    # export GOOGLE_SHEETS_SIMULATE_API_CALLS="true"
    # python -m integration_platform.main

    main()
