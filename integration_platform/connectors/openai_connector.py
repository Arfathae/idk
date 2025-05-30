# Required library:
# openai
# Add this to your requirements.txt: `openai`
import os
import logging
from .base_connector import BaseConnector

# Try to import OpenAI library
try:
    import openai
except ImportError:
    logging.error("OpenAI library not found. Please install 'openai'.")
    # To allow module inspection, we don't raise here, but methods will fail.
    # logging.error("OpenAI library not found. Please install 'openai'.") # This is handled by module logger if used before setup.
    pass # Keep pass, actual error handling will be in methods trying to use these.

# logger = logging.getLogger(__name__) # This is already present and correct.

class OpenAIConnector(BaseConnector):
    """
    Connector for interacting with the OpenAI API.
    Handles authentication and provides methods for text generation.
    """

    def __init__(self, api_key: str = None):
        """
        Initializes the OpenAIConnector.

        The API key is crucial for connecting to OpenAI. It can be provided directly
        or loaded from the environment variable OPENAI_API_KEY.

        Args:
            api_key (str, optional): The OpenAI API key. If None, the connector
                                     will attempt to load it from the environment
                                     variable OPENAI_API_KEY during the connect phase.
        """
        self.api_key = api_key
        self.client = None

        if self.api_key:
            try:
                if not hasattr(openai, 'OpenAI'): # Check if the class itself is available
                    logger.error("OpenAI library attribute 'OpenAI' not found. Library might be old or not fully imported.")
                    raise AttributeError("OpenAI library attribute 'OpenAI' not found. Is the 'openai' package installed and up to date?")
                self.client = openai.OpenAI(api_key=self.api_key)
                logger.info("OpenAI client initialized with explicitly provided API key.")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client with provided API key: {e}", exc_info=True)
                self.client = None 
        else:
            logger.info("OpenAI API key not provided during init. Will attempt to load from environment during connect phase.")

    def connect(self) -> bool:
        """
        Ensures the OpenAI client is initialized and ready to use.

        If the client was not initialized in __init__ (e.g., API key was not provided),
        this method attempts to load the API key from the OPENAI_API_KEY environment
        variable and initialize the client.

        Returns:
            bool: True if connected/client is available, False otherwise.

        Raises:
            ConnectionError: If the API key is missing or client initialization fails.
        """
        if self.client:
            logger.info("OpenAI client is already initialized.")
            return True

        logger.info("Attempting to connect to OpenAI (initialize client)...")
        if not self.api_key:
            logger.info("API key not provided in constructor, attempting to load from OPENAI_API_KEY environment variable.")
            self.api_key = os.environ.get("OPENAI_API_KEY")
            if not self.api_key:
                logger.error("OpenAI API key not found in constructor or OPENAI_API_KEY environment variable.")
                raise ConnectionError(
                    "OpenAI API key is required. Set via OPENAI_API_KEY environment variable or pass to constructor."
                )
            logger.info("Successfully loaded OpenAI API key from environment variable.")
        
        try:
            # Ensure openai module and OpenAI class are available
            if 'openai' not in globals() or not hasattr(openai, 'OpenAI'):
                 logger.error("OpenAI library or OpenAI class not available. Ensure 'openai' is installed and imported.")
                 raise ImportError("OpenAI library or OpenAI class not available.")
            self.client = openai.OpenAI(api_key=self.api_key)
            # Test connection with a simple call if there's a lightweight one, e.g., list models (optional)
            # For now, successful client instantiation is considered connected for OpenAI.
            logger.info("OpenAI client initialized successfully. Connection established.")
            return True
        except openai.AuthenticationError as e:
            logger.error(f"OpenAI Authentication Error: {e}. Please check your API key.", exc_info=True)
            self.client = None # Ensure client is None on auth failure
            raise ConnectionError(f"OpenAI Authentication Failed. Ensure API key is correct and valid.") from e
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client during connect: {e}", exc_info=True)
            self.client = None
            raise ConnectionError(f"Could not connect to OpenAI due to an unexpected error: {e}") from e

    def disconnect(self):
        """
        Disconnects from OpenAI by clearing the client.
        For the OpenAI library, this typically means nullifying the client instance.
        """
        self.client = None
        logger.info("OpenAI client has been cleared. Effectively disconnected from OpenAI.")

    def generate_text(self, prompt: str, model: str = "gpt-3.5-turbo", max_tokens: int = 150, temperature: float = 0.7) -> str:
        """
        Generates text using the OpenAI API (ChatCompletion).

        Args:
            prompt (str): The user's prompt or input text.
            model (str): The model to use (e.g., "gpt-3.5-turbo", "gpt-4").
            max_tokens (int): The maximum number of tokens to generate.
            temperature (float): Controls randomness (0.0 to 2.0). Lower values are more deterministic.

        Returns:
            str: The generated text content.

        Raises:
            ConnectionError: If the client is not connected.
            ValueError: If prompt is empty.
            Exception: For API errors or other issues.
        """
        if not self.client:
            logger.warning("OpenAI client not available. Attempting to connect.")
            try:
                self.connect()
            except ConnectionError as ce:
                # Propagate connection error if connect() fails
                raise ConnectionError("Cannot generate text: OpenAI client not connected and connection attempt failed.") from ce
            if not self.client: # If connect still didn't establish client
                 raise ConnectionError("Cannot generate text: OpenAI client is not connected.")


        if not prompt:
            raise ValueError("Prompt cannot be empty.")

        logger.info(f"Generating text with model='{model}', max_tokens={max_tokens}, temperature={temperature}. Prompt: '{prompt[:50]}...'")

        # Simulate API call if in worker/CI environment and API key might not be present/valid
        # Set OPENAI_API_SIMULATE="true" to enable simulation
        is_simulation = os.environ.get("OPENAI_API_SIMULATE", "false").lower() == "true"
        if is_simulation:
            logger.info(f"SIMULATING OpenAI API call for generate_text. Prompt: '{prompt[:50]}...'")
            return f"This is a simulated response for the prompt: '{prompt}' using model {model}."

        try:
            logger.debug(f"Making actual OpenAI API call to chat.completions.create with model {model}.")
            completion = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                # n=1, # Number of completions to generate
                # stop=None, # Sequence where the API will stop generating further tokens
            )
            # The response structure for chat completions:
            # response.choices[0].message.content
            # The response structure for chat completions: response.choices[0].message.content
            if completion.choices and completion.choices[0].message and completion.choices[0].message.content:
                generated_text = completion.choices[0].message.content.strip()
                logger.info(f"Successfully generated text using model {model}. Output length: {len(generated_text)}.")
                return generated_text 
            else:
                logger.error("OpenAI API response structure is invalid: Missing choices, message, or content.")
                raise Exception("Invalid response structure from OpenAI API: choices, message, or content missing.")

        except openai.APIConnectionError as e:
            logger.error(f"OpenAI API Connection Error: {e}", exc_info=True)
            raise ConnectionError(f"Failed to connect to OpenAI API during text generation: {e}") from e
        except openai.RateLimitError as e:
            logger.error(f"OpenAI API Rate Limit Exceeded: {e}", exc_info=True)
            raise Exception(f"OpenAI API request exceeded rate limit: {e}") from e # Consider a custom exception
        except openai.AuthenticationError as e: 
            logger.error(f"OpenAI API Authentication Error during text generation: {e}. Key may have been revoked or is invalid.", exc_info=True)
            self.client = None # Force re-authentication attempt on next call
            raise ConnectionError(f"OpenAI API authentication failed: {e}. Check your API key.") from e
        except openai.APIError as e: # General OpenAI API error (e.g. server errors)
            logger.error(f"OpenAI API Error (APIError): Status {e.status_code}, Type: {e.type}, Message: {e.message}", exc_info=True)
            raise Exception(f"An OpenAI API error occurred: Status {e.status_code}, Type: {e.type}, Message: {e.message}") from e
        except Exception as e: 
            logger.error(f"Unexpected error during OpenAI text generation: {e}", exc_info=True)
            raise Exception(f"An unexpected error occurred while generating text with OpenAI: {e}") from e

    def execute_action(self, action_name: str, params: dict):
        """
        Executes a specific action supported by the OpenAI connector.

        Args:
            action_name (str): The name of the action to execute.
                               Currently supports: "generate_text".
            params (dict): A dictionary of parameters for the action.
                           - For "generate_text": {"prompt": "str", "model": "str" (opt),
                             "max_tokens": int (opt), "temperature": float (opt)}

        Returns:
            The result of the action (e.g., generated text as a string).

        Raises:
            ValueError: If the action_name is unknown or required parameters are missing.
            ConnectionError: If the client is not connected.
            Exception: For API errors or other issues during action execution.
        """
        logger.info(f"Executing OpenAI action: '{action_name}' with params: {params}")

        if action_name == "generate_text":
            if "prompt" not in params:
                raise ValueError("Missing 'prompt' parameter for 'generate_text' action.")
            
            prompt = params["prompt"]
            model = params.get("model", "gpt-3.5-turbo") # Default model
            max_tokens = params.get("max_tokens", 150)
            temperature = params.get("temperature", 0.7)

            # Call generate_text and get the string result
            result_text = self.generate_text(
                prompt=prompt,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature
            )
            # Wrap the string result in a dictionary
            return {"generated_text": result_text}
        else:
            logger.error(f"Unknown action: {action_name} for OpenAIConnector.")
            raise ValueError(f"Unknown action: {action_name} for OpenAIConnector.")


if __name__ == '__main__':
    # This is example usage code.
    # For it to run, you need to:
    # 1. Have the `openai` library installed (`pip install openai`).
    # 2. Set your OpenAI API key as an environment variable: `export OPENAI_API_KEY="your_key_here"`
    #    OR pass it directly to the OpenAIConnector constructor.
    # 3. To run in simulation mode without making actual API calls (e.g., in CI/worker):
    #    `export OPENAI_API_SIMULATE="true"`

    #    `export OPENAI_API_SIMULATE="true"`

    # Note: Logging for __main__ should be configured by the script that runs this,
    # or by a global logging setup if this module is part of a larger application.
    # For standalone testing, we can add a basicConfig here.
    # If run via `python -m integration_platform.main`, logging is already set up by main.py.
    if not logging.getLogger().hasHandlers(): # Check if root logger has handlers
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    logger.info("Starting OpenAIConnector __main__ example...")

    api_key_from_env = os.environ.get("OPENAI_API_KEY")
    is_simulation_mode_main = os.environ.get("OPENAI_API_SIMULATE", "false").lower() == "true"

    connector_main = None # Ensure connector is defined for finally block
    if is_simulation_mode_main:
        logger.info("__main__: Running in SIMULATION MODE for OpenAI.")
        connector_main = OpenAIConnector(api_key="dummy_simulated_key") # Can use a dummy key for simulation
    elif api_key_from_env:
        logger.info("__main__: Attempting to use OpenAI API key from environment variable.")
        connector_main = OpenAIConnector(api_key=api_key_from_env)
    else:
        logger.warning("__main__: OPENAI_API_KEY not found in environment. Text generation will likely fail unless simulation is enabled globally by other means.")
        logger.warning("__main__: To run this example with actual API calls, set OPENAI_API_KEY='your_key'.")
        logger.warning("__main__: To run in simulation, set OPENAI_API_SIMULATE='true'.")
        connector_main = OpenAIConnector() # Will try to load from env in connect() or fail

    if connector_main:
        try:
            logger.info("__main__: Attempting to connect OpenAI connector...")
            connector_main.connect() 
            logger.info("__main__: OpenAI connector connect() call completed.")

            # Check if client is available OR if simulation is globally on (via env var that generate_text checks)
            if connector_main.client or os.environ.get("OPENAI_API_SIMULATE", "false").lower() == "true":
                prompt_to_test = "Describe the benefits of using Python for automation in three bullet points."
                logger.info(f"__main__: Attempting 'generate_text' action with prompt: \"{prompt_to_test[:30]}...\"")
                
                generated_text_dict = connector_main.execute_action(
                    "generate_text",
                    {"prompt": prompt_to_test, "model": "gpt-3.5-turbo"}
                )
                logger.info(f"__main__: 'generate_text' (via execute_action) result: {generated_text_dict}")
            else:
                logger.warning("__main__: OpenAI client not available after connect attempt and not in simulation mode. Skipping text generation example.")
                if not is_simulation_mode_main: # If not explicitly simulating via this script's flag
                     logger.warning("__main__: Ensure your OPENAI_API_KEY is correctly set and valid if not intending to simulate.")

        except ConnectionError as e_conn:
            logger.error(f"__main__: Connection error: {e_conn}", exc_info=True)
            if not is_simulation_mode_main and not api_key_from_env:
                logger.info("__main__: This connection error is expected if OPENAI_API_KEY is not set and not in simulation mode.")
        except openai.APIError as e_api: # Catching specific OpenAI errors if they propagate
            logger.error(f"__main__: OpenAI API Error: {e_api}", exc_info=True)
        except Exception as e_main_exc:
            logger.error(f"__main__: An unexpected error occurred: {e_main_exc}", exc_info=True)
        finally:
            logger.info("__main__: Attempting to disconnect OpenAI connector in finally block.")
            connector_main.disconnect()
    else:
        logger.error("__main__: OpenAIConnector could not be initialized.")

    logger.info("OpenAIConnector __main__ example finished.")
