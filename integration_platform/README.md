# Integration Platform

This project aims to create a platform to integrate various software services.

## Overview/Purpose

The Integration Platform is a Python-based system for orchestrating workflows by integrating various services like Google Sheets, OpenAI, and Email (via SMTP). Its primary goal is to automate tasks by connecting different APIs and services through a configurable, JSON-defined workflow system. It allows users to define a sequence of actions, where data from one step can be used as input for subsequent steps.

## Features

*   **Service Integration:**
    *   **Google Sheets:** Read data from sheets, append rows, and update cells. Handles OAuth2 authentication.
    *   **OpenAI:** Generate text using models like GPT-3.5-turbo and GPT-4.
    *   **Email (SMTP):** Send emails via any standard SMTP server.
*   **Workflow Engine:** Executes sequences of actions defined in JSON files. Manages connector instantiation and data flow between actions.
*   **Data Templating:** Pass data between workflow trigger and actions using a simple `{step_id.path.to.value}` syntax (e.g., `{trigger.data.message}`, `{action1.output.summary}`).
*   **Configuration:** Primarily through environment variables for API keys, credentials, and service details. Workflow-specific configurations can also be embedded in the JSON definition.
*   **Simulation Modes:** Each connector supports a simulation mode (enabled by environment variables) for testing workflow logic without making actual external API calls.
*   **Basic Web Interface:** A Flask-based web application allows triggering a predefined workflow and viewing results in the browser.
*   **Logging:** Comprehensive logging throughout the platform for execution tracing and debugging.
*   **Error Handling:** Structured error reporting within the workflow execution, capturing issues from connectors or the engine itself.
*   **Unit Tested:** Core components, including connectors and workflow data resolution, are covered by unit tests.

## Directory Structure

*   `integration_platform/`
    *   `app.py`: Main Flask application file for the web interface.
    *   `connectors/`: Modules for connecting to external services (e.g., `GoogleSheetsConnector`, `OpenAIConnector`, `EmailConnector`). Each connector inherits from `BaseConnector`.
    *   `core/`: Core components like data mapping logic (`data_mapper.py` - currently a placeholder) and logging configuration (`logging_config.py`).
    *   `static/`: Static files for the web application (CSS, JavaScript).
        *   `style.css`: Basic stylesheet for the web interface.
    *   `templates/`: HTML templates used by the Flask application.
        *   `index.html`: The main page for the web interface.
    *   `workflow/`: Modules for defining and executing workflows, including the `WorkflowEngine` and example workflow definitions (`workflow_definition_example.json`).
    *   `tests/`: Unit tests for the platform's components.
        *   `connectors/`: Tests specific to each connector.
        *   `workflow/`: Tests for the workflow engine and related utilities.
    *   `main.py`: Command-line script to initialize the `WorkflowEngine` and run workflows.
    *   `requirements.txt`: Lists project dependencies.
    *   `README.md`: This file.
    *   `config.py.example`: An example of how a Python-based config file could look (not currently used, environment variables are preferred).

## Setup and Installation

### Prerequisites

*   Python 3.8 or newer.

### Installation Steps

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Create and activate a Python virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r integration_platform/requirements.txt
    ```

### Configuration

Configuration is primarily managed through environment variables. Set these in your shell, a `.env` file (if using a library like `python-dotenv`, not included by default), or your deployment environment.

**Required Environment Variables:**

*   **Google Sheets:**
    *   `GOOGLE_CLIENT_SECRET_FILE`: Path to your `credentials.json` file obtained from Google Cloud Console.
        *   *Example:* `GOOGLE_CLIENT_SECRET_FILE="credentials.json"` (if placed in the root or `integration_platform` directory).
    *   `GOOGLE_TOKEN_FILE_PATH`: Path where the `token.json` (generated after successful OAuth2 flow) will be stored and read.
        *   *Example:* `GOOGLE_TOKEN_FILE_PATH="token.json"`
    *   *Guidance:*
        1.  Enable the Google Sheets API in your Google Cloud Platform project.
        2.  Create OAuth 2.0 credentials for a "Desktop app" and download the `credentials.json` file.
        3.  Place `credentials.json` at the path specified by `GOOGLE_CLIENT_SECRET_FILE`.
        4.  The first time a workflow uses Google Sheets (and `token.json` is not present or invalid, and simulation is off), the application will log messages guiding you through a browser-based authentication flow. This will generate/update `token.json`. For non-interactive environments, ensure `token.json` is pre-generated or use simulation mode.

*   **OpenAI:**
    *   `OPENAI_API_KEY`: Your API key from OpenAI.
        *   *Example:* `OPENAI_API_KEY="sk-yourkeyhere"`

*   **Email (SMTP):**
    *   `SMTP_HOST`: Hostname of your SMTP server (e.g., `smtp.gmail.com`).
    *   `SMTP_PORT`: Port for the SMTP server (e.g., `587` for TLS, `465` for SSL).
    *   `SMTP_USER`: Your SMTP username (often your email address).
    *   `SMTP_PASSWORD`: Your SMTP password. **For services like Gmail, it's highly recommended to use an "App Password"** instead of your main account password.
    *   `SENDER_EMAIL` (or `SMTP_SENDER_EMAIL`): The email address to send emails from. If not set, defaults to `SMTP_USER`.
        *   *Example:* `SENDER_EMAIL="notifications@example.com"`

**Simulation Flags (Optional - for testing without live API calls):**

Set these environment variables to `"true"` to enable simulation mode for the respective connectors. In simulation mode, connectors log their intended actions and return mock data instead of making actual external calls.

*   `GOOGLE_SHEETS_SIMULATE_API_CALLS=true`
*   `OPENAI_API_SIMULATE=true`
*   `EMAIL_SIMULATE=true`

## Running Workflows (Command Line)

Workflows can be executed directly from the command line using the `main.py` script. This is useful for testing, batch processing, or integrating with other shell-based automation.

*   **Run a specific workflow definition:**
    ```bash
    python -m integration_platform.main --workflow path/to/your/workflow_definition.json
    ```
    (If running from the project root, the path might be `integration_platform/path/to/your/workflow_definition.json`)

*   **Run the default example workflow:**
    ```bash
    python -m integration_platform.main
    ```
    This will run `integration_platform/workflow/workflow_definition_example.json`.

The script will print the final `workflow_data_cache` to the console, showing the outputs of the trigger and each action. Detailed logs are also printed to the console during execution.

## Running the Web Application

This project includes a basic web interface built with Flask to allow triggering workflows and viewing their results through your browser.

### 1. Environment Variables
Ensure all necessary environment variables for the services you intend to use in your workflows are set. This includes credentials for Google Sheets, OpenAI, Email (SMTP), and any simulation flags. Refer to the "Configuration" section above for details on required variables.

### 2. Start the Flask Development Server
Navigate to the root directory of the project (the one containing the `integration_platform` directory) and run:
```bash
python integration_platform/app.py
```
This will start the Flask development server.
**Note:** For production environments, use a proper WSGI server like Gunicorn or uWSGI.

### 3. Access the Web Interface
Open your web browser and go to:
[http://127.0.0.1:5000/](http://127.0.0.1:5000/)

You should see the home page with a button to run the example workflow. Click the button to execute the workflow and see the results displayed on the page.

## Web API Endpoints

The web application exposes the following API endpoints:

### Run Workflow

*   **Endpoint:** `POST /api/workflow/run`
*   **Description:** Triggers the execution of the predefined example workflow currently located at `integration_platform/workflow/workflow_definition_example.json`.
*   **Request Body:** None.
*   **Success Response (`200 OK`):**
    *   A JSON object representing the `workflow_data_cache`, containing the results and status of each step in the executed workflow.
    ```json
    {
      "trigger_id": { "...trigger data and config..." },
      "action_id_1": { "status": "success", "...action output..." },
      "action_id_2": { "status": "error", "error_message": "...", "details": "..." }
      // ... etc.
    }
    ```
*   **Error Responses:**
    *   `400 Bad Request`: If there's an issue with the workflow definition (e.g., JSON decoding error) or invalid parameters if the endpoint were to accept them. Example: `{"status": "error", "error_message": "Error decoding workflow definition file.", "details": "..."}`
    *   `404 Not Found`: If the `workflow_definition_example.json` file is not found by the server. Example: `{"status": "error", "error_message": "Workflow definition file not found.", "details": "..."}`
    *   `500 Internal Server Error`: For general server-side errors during workflow execution (e.g., connection errors to external services, unexpected issues in the engine). Example: `{"status": "error", "error_message": "An unexpected server error occurred.", "details": "..."}` or `{"status": "error", "error_message": "Failed to connect to an external service.", "details": "..."}`

## Defining Workflows (Basic Guide)

Workflows are defined in JSON files with the following key sections:

*   `name` (string): A descriptive name for the workflow.
*   `trigger` (object): Defines the event that initiates the workflow.
    *   `id` (string): A unique identifier for the trigger's output (e.g., "my_trigger").
    *   `service` (string): The service that provides the trigger event (e.g., "google_sheets"). *Currently, triggers are simulated by the engine based on this configuration.*
    *   `event` (string): The specific event (e.g., "new_row").
    *   `config` (object): Configuration parameters for the trigger (e.g., sheet ID, tab name).
*   `actions` (list of objects): An ordered list of actions to be executed. Each action object has:
    *   `id` (string): A unique identifier for this action step. Output of this action will be stored under this ID. **Required.**
    *   `service` (string): The name of the service to use (e.g., "openai", "google_sheets", "email"). **Required.**
    *   `action` (string): The specific method to call on the connector (e.g., "generate_text", "get_sheet_data", "send_email"). **Required.**
    *   `connector_id` (string, optional): A custom ID for the connector instance. If you need multiple instances of the same connector type (e.g., two different OpenAI accounts), use different `connector_id`s. Defaults to `action.id` if not provided (meaning a new connector instance per action unless shared).
    *   `config` (object, optional): Parameters to be passed to the connector's `execute_action` method. Values here can use templating to reference outputs from previous steps.
    *   `connector_config` (object, optional): Configuration specific to this connector instance (e.g., overriding global API keys or file paths). This is useful if an action needs to use a different account/credential than what's globally configured.

**Templating Data:**

You can reference output from the trigger or previous actions in the `config` section of an action. Use the syntax `{step_id.path.to.value}`.
*   `step_id`: The `id` of the trigger or a preceding action.
*   `path.to.value`: A dot-separated path to navigate the dictionary structure of the step's output. List elements can be accessed using numeric indices (e.g., `my_action.data.items.0.name`).

**Example:**
If `get_gsheet_data` action (with `id: "sheet_reader"`) returns `{"values": [["Cell A1 data", "Cell B1 data"]]}`, you can reference "Cell A1 data" in a subsequent action's config like this: `"{sheet_reader.values.0.0}"`.

Refer to `integration_platform/workflow/workflow_definition_example.json` for a practical example.

## Running Tests

Unit tests are located in the `integration_platform/tests/` directory. To run all tests, navigate to the project's root directory (the one containing the `integration_platform` folder) and execute:

```bash
python -m unittest discover -s integration_platform/tests -p "test_*.py"
```

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests. If you plan to add significant features, please open an issue for discussion first.

(Further details on development setup, coding standards, and PR process can be added here later.)
