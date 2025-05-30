"""
Main Flask application file for the Integration Platform.
This file initializes the Flask app and defines basic routes,
including an API endpoint to run workflows.
"""
import os
import logging
from json import JSONDecodeError # More specific import
from flask import Flask, render_template, jsonify # request might be needed later for POST body
# from flask import request # Uncomment if you need to access request.json or request.form

from integration_platform.workflow.workflow_engine import WorkflowEngine
from integration_platform.core.logging_config import setup_logging

# Configure logging for the Flask app
# This will use the root logger configured by setup_logging()
setup_logging() # Call once at the application start
logger = logging.getLogger(__name__) # Get a logger specific to this module (app.py)

# Initialize the Flask application
app = Flask(__name__)

@app.route('/')
def home():
    """
    Serves the home page of the Integration Platform.
    It renders the main index.html template.
    """
    return render_template('index.html')

# Example of another route (can be removed if not needed for this step)
@app.route('/status')
def status():
    """A simple status endpoint to check if the app is running."""
    return {"status": "running", "message": "Integration Platform is operational."}

if __name__ == '__main__':
    # Runs the Flask development server.
    # For production, a proper WSGI server (like Gunicorn or uWSGI) should be used.
    # Debug mode is set to False for this initial setup.
    # Host '127.0.0.1' makes it accessible only locally.
    # Use host='0.0.0.0' to make it accessible on your network (e.g., for testing from other devices).
    app.run(debug=False, host='127.0.0.1', port=5000)


@app.route('/api/workflow/run', methods=['POST'])
def run_workflow_api():
    """
    API endpoint to trigger the execution of a predefined workflow.
    Loads configuration, instantiates WorkflowEngine, runs the workflow,
    and returns the results or an error.
    """
    logger.info("API call received: POST /api/workflow/run")
    try:
        # 1. Load Global Config from Environment Variables
        # These keys should match what WorkflowEngine and connectors expect from global_config
        env_keys_for_global_config = [
            "GOOGLE_CLIENT_SECRET_FILE", "GOOGLE_TOKEN_FILE_PATH", # Corrected from GOOGLE_TOKEN_FILE
            "OPENAI_API_KEY",
            "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SENDER_EMAIL", # Corrected from SMTP_SENDER_EMAIL
            # Simulation flags that the engine or connectors might check via os.getenv if not in global_config
            # The engine's _get_connector logic already prioritizes os.getenv if not in global/connector config.
            # So, explicitly passing them here from os.getenv to global_config is good for clarity
            # and ensures they are part of the engine's config if needed elsewhere.
            "OPENAI_API_SIMULATE",
            "EMAIL_SIMULATE",
            "GOOGLE_SHEETS_SIMULATE_API_CALLS"
        ]
        global_config = {key: os.getenv(key) for key in env_keys_for_global_config if os.getenv(key) is not None}

        logger.debug(f"Loaded global_config for WorkflowEngine (sensitive values may be masked by logger): { {k: (v if not any(s in k for s in ['KEY', 'PASSWORD', 'SECRET']) else '******') for k,v in global_config.items()} }")

        # 2. Instantiate WorkflowEngine
        engine = WorkflowEngine(global_config=global_config)

        # 3. Define workflow path
        # app.py is in integration_platform/, so paths should be relative to the project root,
        # or calculated based on __file__.
        # Assuming the script/Flask app is run from the project root (parent of integration_platform directory)
        # If integration_platform/app.py is the entry point, then this path is relative to where app.py is.
        script_dir = os.path.dirname(os.path.abspath(__file__)) # Directory of app.py
        # workflow_file_path = os.path.join(script_dir, "workflow/workflow_definition_example.json")
        # The default workflow path in main.py is "integration_platform/workflow/workflow_definition_example.json"
        # If running Flask from project root: "integration_platform/workflow/workflow_definition_example.json"
        # If app.py is considered to be at integration_platform/app.py, then:
        workflow_file_path = os.path.join(script_dir, "workflow/workflow_definition_example.json")

        # Check if the default workflow file exists at the constructed path
        if not os.path.exists(workflow_file_path):
            # Fallback for cases where CWD is project root, and app.py is in integration_platform
            alt_workflow_path = os.path.join(os.getcwd(), "integration_platform", "workflow", "workflow_definition_example.json")
            if os.path.exists(alt_workflow_path):
                workflow_file_path = alt_workflow_path
            else:
                # If still not found, this will be caught by engine.run_workflow's FileNotFoundError
                logger.warning(f"Default workflow file not found at primary path: {workflow_file_path}. Will try to load as is.")


        logger.info(f"Attempting to run workflow definition: {workflow_file_path}")
        # 4. Run the workflow
        # For now, this API runs a predefined workflow.
        # Future extension: could accept workflow definition path or content via POST request body.
        results = engine.run_workflow(workflow_file_path)
        logger.info("Workflow executed successfully via API call.")

        # Return JSON response. Use default=str to handle potential non-serializable data (like datetime in some complex cases)
        return jsonify(results), 200

    except FileNotFoundError as e:
        logger.error(f"API Error: Workflow definition file not found at '{workflow_file_path}'. Details: {e}", exc_info=True)
        return jsonify({"status": "error", "error_message": "Workflow definition file not found.", "details": str(e)}), 404
    except JSONDecodeError as e:
        logger.error(f"API Error: Error decoding workflow definition JSON file. Details: {e.msg} at line {e.lineno} col {e.colno}", exc_info=True)
        return jsonify({"status": "error", "error_message": "Error decoding workflow definition file.", "details": f"{e.msg} (line {e.lineno}, col {e.colno})"}), 400
    except ConnectionError as e:
        logger.error(f"API Error: A connection error occurred during workflow execution. Details: {e}", exc_info=True)
        return jsonify({"status": "error", "error_message": "Failed to connect to an external service.", "details": str(e)}), 500
    except ValueError as e:
        logger.error(f"API Error: A value or configuration error occurred during workflow execution. Details: {e}", exc_info=True)
        return jsonify({"status": "error", "error_message": "Invalid configuration or parameters for workflow/connector.", "details": str(e)}), 400
    except Exception as e: # Catch-all for any other unexpected errors
        logger.error(f"API Error: An unexpected error occurred on endpoint /api/workflow/run. Details: {e}", exc_info=True)
        return jsonify({"status": "error", "error_message": "An unexpected server error occurred.", "details": str(e)}), 500
