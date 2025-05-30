import logging
import sys

def setup_logging(level=logging.INFO):
    """
    Configures basic logging for the application.

    Args:
        level: The logging level (e.g., logging.INFO, logging.DEBUG).
    """
    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Prevent multiple handlers if called multiple times, especially for the root logger
    # Check if a handler of the same type with the same formatter is already added.
    # A simpler check for now: if handlers already exist, assume it's configured.
    if not root_logger.handlers:
        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        # Set handler level explicitly, otherwise it might default to NOTSET or WARNING
        console_handler.setLevel(level) 

        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)

        root_logger.addHandler(console_handler)
        # Use the root_logger or a specific logger for this initial message
        logging.info("Root logger configured.") 
    else:
        logging.info("Root logger already configured or has handlers.")
    
    # Return a specific logger for convenience if needed, or just let modules use getLogger(__name__)
    return logging.getLogger("IntegrationPlatform") # Or return root_logger

if __name__ == '__main__':
    # Example usage:
    # Call setup_logging early in your application's lifecycle
    logger = setup_logging(logging.DEBUG)
    logger.debug("This is a debug message.")
    logger.info("This is an info message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")
    logger.critical("This is a critical message.")

    # Example of getting the logger elsewhere in the code
    # import logging
    # logger = logging.getLogger("IntegrationPlatform")
    # logger.info("Another message from a different part of the app.")
