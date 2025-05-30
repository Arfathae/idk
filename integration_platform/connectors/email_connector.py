# Uses Python's built-in smtplib and email.mime modules.
# No external libraries required for basic email sending.
import smtplib
import logging
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart # For more complex emails if needed later

from .base_connector import BaseConnector

# logger = logging.getLogger(__name__) # This is already present and correct.

class EmailConnector(BaseConnector):
    """
    Connector for sending emails using SMTP.
    Handles connection, authentication, and email sending.
    """

    def __init__(self, smtp_host: str, smtp_port: int, smtp_user: str, smtp_password: str,
                 sender_email: str = None, use_tls: bool = True):
        """
        Initializes the EmailConnector.

        Args:
            smtp_host (str): The hostname or IP address of the SMTP server.
            smtp_port (int): The port number for the SMTP server.
            smtp_user (str): The username for SMTP authentication.
            smtp_password (str): The password for SMTP authentication.
                                 (Consider using app passwords for services like Gmail).
            sender_email (str, optional): The email address to use as the 'From' field.
                                          If None, smtp_user will be used.
            use_tls (bool): Whether to use STARTTLS for encrypting the connection.
                            Defaults to True. If smtp_port is 465 (SMTPS), TLS/SSL
                            is often implicit, and starttls might not be needed or used.
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password # Security note: Handle with care.
        self.sender_email = sender_email if sender_email else self.smtp_user
        self.use_tls = use_tls
        self.server = None
        logger.info(f"EmailConnector initialized for user '{self.smtp_user}' at {self.smtp_host}:{self.smtp_port}, Sender: '{self.sender_email}'")

    def connect(self) -> bool:
        """
        Connects to the SMTP server and logs in.

        Returns:
            bool: True if connection and login are successful.

        Raises:
            ConnectionError: If connection, TLS negotiation, or login fails.
        """
        if self.server and self.is_connected(): # is_connected uses NOOP which can confirm login status too
             logger.info(f"Already connected and appears responsive to SMTP server {self.smtp_host}:{self.smtp_port}.")
             return True

        logger.info(f"Attempting to connect to SMTP server {self.smtp_host}:{self.smtp_port}...")
        try:
            if self.smtp_port == 465: # Typically SSL from the start
                self.server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=10)
                logger.info(f"SMTP_SSL connection initiated to {self.smtp_host}:{self.smtp_port}.")
                # For SMTP_SSL, ehlo might be called after connection, before login if needed,
                # but often login is the next step. Some servers might not need explicit ehlo here.
            else: # Standard SMTP, potentially with STARTTLS
                self.server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10)
                logger.info(f"SMTP connection initiated to {self.smtp_host}:{self.smtp_port}.")
                self.server.ehlo() # Identify client to server
                if self.use_tls:
                    logger.info("Attempting STARTTLS...")
                    self.server.starttls()
                    logger.info("STARTTLS successful.")
                    self.server.ehlo() # Re-identify after TLS

            logger.info(f"Attempting to login as user '{self.smtp_user}'...")
            self.server.login(self.smtp_user, self.smtp_password)
            logger.info(f"Successfully logged in as '{self.smtp_user}'. SMTP connection established.")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP Authentication Error for user '{self.smtp_user}' on {self.smtp_host}:{self.smtp_port}. Code: {e.smtp_code}, Error: {e.smtp_error}", exc_info=True)
            if self.server: try: self.server.quit() # Attempt to close connection if partially open
            except: pass
            self.server = None
            raise ConnectionError(f"SMTP authentication failed for user '{self.smtp_user}': {e.smtp_code} - {e.smtp_error}") from e
        except smtplib.SMTPHeloError as e: # Server didn't respond to HELO/EHLO
            logger.error(f"SMTP Helo/Ehlo Error with {self.smtp_host}:{self.smtp_port}. Code: {e.smtp_code}, Error: {e.smtp_error}", exc_info=True)
            if self.server: try: self.server.quit()
            except: pass
            self.server = None
            raise ConnectionError(f"SMTP server did not respond properly to HELO/EHLO: {e.smtp_code} - {e.smtp_error}") from e
        except smtplib.SMTPException as e: # Other SMTP specific errors
            logger.error(f"SMTP Exception during connection/login to {self.smtp_host}:{self.smtp_port}: {e}", exc_info=True)
            if self.server: try: self.server.quit()
            except: pass
            self.server = None
            raise ConnectionError(f"SMTP error connecting or logging in to {self.smtp_host}:{self.smtp_port}: {e}") from e
        except ConnectionRefusedError as e:
            logger.error(f"Connection refused by SMTP server {self.smtp_host}:{self.smtp_port}: {e}", exc_info=True)
            self.server = None
            raise ConnectionError(f"Connection refused by SMTP server {self.smtp_host}:{self.smtp_port}.") from e
        except OSError as e: # Catches broader OS errors like "No route to host" or network down
            logger.error(f"OS error connecting to SMTP server {self.smtp_host}:{self.smtp_port}: {e}", exc_info=True)
            self.server = None
            raise ConnectionError(f"OS error prevented connection to SMTP server {self.smtp_host}:{self.smtp_port}: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error connecting to SMTP server {self.smtp_host}:{self.smtp_port}: {e}", exc_info=True)
            if self.server: try: self.server.quit()
            except: pass
            self.server = None
            raise ConnectionError(f"An unexpected error occurred while connecting to SMTP: {e}") from e

    def is_connected(self) -> bool:
        """Checks if the SMTP server connection is active by sending a NOOP."""
        """Checks if the SMTP server connection is active by sending a NOOP."""
        if not self.server:
            logger.debug("is_connected: No server object exists.")
            return False
        try:
            logger.debug("is_connected: Sending NOOP to server.")
            status = self.server.noop()[0]
            is_ok = (status == 250) # 250 is the success code for NOOP
            logger.debug(f"is_connected: NOOP status: {status}, connection is_ok: {is_ok}")
            return is_ok
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPNotSupportedError, smtplib.SMTPException) as e:
            logger.warning(f"is_connected: NOOP command failed or server disconnected: {e}", exc_info=True)
            self.server = None # Assume disconnected if NOOP fails badly
            return False


    def disconnect(self):
        """
        Disconnects from the SMTP server.
        """
        if self.server:
            logger.info(f"Attempting to disconnect from SMTP server {self.smtp_host}...")
            try:
                self.server.quit()
                logger.info(f"Successfully disconnected from SMTP server {self.smtp_host}.")
            except smtplib.SMTPException as e: # e.g. SMTPServerDisconnected if already closed
                logger.warning(f"SMTPException during disconnect from {self.smtp_host}: {e}. Server might have already closed connection.", exc_info=True)
            except Exception as e: # Other unexpected errors
                logger.error(f"Unexpected error during SMTP disconnect from {self.smtp_host}: {e}", exc_info=True)
            finally:
                self.server = None # Ensure server object is cleared
        else:
            logger.info("No active SMTP server connection to disconnect or already disconnected.")


    def send_email(self, recipient_email: str, subject: str, body: str, is_html: bool = False) -> bool:
        """
        Sends an email.

        Args:
            recipient_email (str): The email address of the recipient.
            subject (str): The subject line of the email.
            body (str): The main content of the email (plain text or HTML).
            is_html (bool): Set to True if the body is HTML, False for plain text. Defaults to False.

        Returns:
            bool: True if the email was sent successfully, False otherwise.

        Raises:
            ConnectionError: If not connected and cannot reconnect.
            ValueError: If recipient_email, subject, or body is empty.
            Exception: For SMTP errors during sending.
        """
        if not recipient_email or not subject or not body:
            raise ValueError("Recipient email, subject, and body cannot be empty.")

        if not self.server or not self.is_connected():
            logger.warning("Not connected to SMTP server. Attempting to connect before sending email.")
            try:
                self.connect()
            except ConnectionError as ce:
                logger.error(f"Failed to connect before sending email: {ce}")
                raise # Re-raise the connection error to the caller

        logger.info(f"Attempting to send email to: {recipient_email}, Subject: '{subject}'")

        msg = MIMEMultipart() if is_html else MIMEText(body, 'plain' if not is_html else 'html', 'utf-8')

        if is_html: # If MIMEMultipart was chosen for HTML
            msg.attach(MIMEText(body, 'html', 'utf-8'))

        msg['Subject'] = subject
        msg['From'] = self.sender_email
        msg['To'] = recipient_email

        # Simulation mode for environments where actual email sending is not desired/configured
        is_simulation = os.environ.get("EMAIL_SIMULATE", "false").lower() == "true"
        if is_simulation:
            logger.info(f"SIMULATING email sending to: {recipient_email}, Subject: '{subject}'")
            logger.info("--- SIMULATED EMAIL ---")
            logger.info(f"From: {self.sender_email}")
            logger.info(f"To: {recipient_email}")
            logger.info(f"Subject: {subject}")
            logger.info(f"Body:\n{body}")
            logger.info("--- END SIMULATED EMAIL ---")
            return True

        try:
            self.server.sendmail(self.sender_email, recipient_email, msg.as_string())
            logger.info(f"Email successfully sent to {recipient_email} via {self.smtp_host}.")
            return True
        except smtplib.SMTPRecipientsRefused as e:
            # Log each refused recipient
            for rcpt, err_code_msg in e.recipients.items():
                logger.error(f"SMTP Recipient Refused: {rcpt}, Code: {err_code_msg[0]}, Message: {err_code_msg[1].decode('utf-8', 'replace') if isinstance(err_code_msg[1], bytes) else err_code_msg[1]}", exc_info=True)
            raise Exception(f"Server refused one or more recipient email addresses: {list(e.recipients.keys())}") from e
        except smtplib.SMTPHeloError as e:
            logger.error(f"SMTP Helo/Ehlo Error while sending email via {self.smtp_host}: {e.smtp_code} - {e.smtp_error}", exc_info=True)
            raise Exception(f"Server didn't reply properly to HELO/EHLO during send: {e.smtp_code} - {e.smtp_error}") from e
        except smtplib.SMTPSenderRefused as e:
            logger.error(f"SMTP Sender Refused: {self.sender_email} by server {self.smtp_host}. Code: {e.smtp_code}, Error: {e.smtp_error}", exc_info=True)
            raise Exception(f"Sender email address {self.sender_email} refused by server: {e.smtp_code} - {e.smtp_error}") from e
        except smtplib.SMTPDataError as e:
            logger.error(f"SMTP Data Error (unexpected server reply to DATA command) for {self.smtp_host}: {e.smtp_code} - {e.smtp_error}", exc_info=True)
            raise Exception(f"Server replied with an unexpected error code during data transmission: {e.smtp_code} - {e.smtp_error}") from e
        except smtplib.SMTPServerDisconnected as e: # More specific than general SMTPException
            logger.error(f"SMTPServerDisconnected during send mail via {self.smtp_host}. Attempting to clear server.", exc_info=True)
            self.server = None # Mark as disconnected, connection will be re-attempted if method is called again
            raise ConnectionError(f"Server disconnected unexpectedly during send mail. Please try again.") from e
        except smtplib.SMTPException as e: # Catch other SMTP specific exceptions
            logger.error(f"An SMTPException occurred while sending email via {self.smtp_host}: {e}", exc_info=True)
            raise Exception(f"An SMTP error occurred: {e}") from e
        except Exception as e: # Catch any other non-SMTP exceptions
            logger.error(f"Unexpected error sending email via {self.smtp_host}: {e}", exc_info=True)
            raise Exception(f"An unexpected error occurred while sending email: {e}") from e


    def execute_action(self, action_name: str, params: dict):
        """
        Executes a specific email action.

        Args:
            action_name (str): The name of the action to execute.
                               Currently supports: "send_email".
            params (dict): A dictionary of parameters for the action.
                           - For "send_email": {"recipient_email": "str", "subject": "str", "body": "str", "is_html": bool (opt)}
        Returns:
            The result of the action (e.g., True for successful email send).

        Raises:
            ValueError: If action_name is unknown or required params are missing.
            ConnectionError: If connection fails.
            Exception: For SMTP errors or other issues.
        """
        logger.info(f"Executing Email action: '{action_name}' with params: {params}")

        if action_name == "send_email":
            if not all(k in params for k in ["recipient_email", "subject", "body"]):
                raise ValueError("Missing 'recipient_email', 'subject', or 'body' for 'send_email' action.")

            try:
                success = self.send_email(
                    recipient_email=params["recipient_email"],
                    subject=params["subject"],
                    body=params["body"],
                    is_html=params.get("is_html", False) # Optional parameter
                )
                if success:
                    return {"status": "sent"}
                else:
                    # This path might not be commonly hit if send_email raises exceptions on failure
                    return {"status": "failed", "error": "Email sending reported failure without exception."}
            except Exception as e:
                # If send_email raises an exception, catch it and report failure
                logger.error(f"Error during send_email action execution: {e}", exc_info=True)
                return {"status": "failed", "error": str(e)}
        else:
            logger.error(f"Unknown action: {action_name} for EmailConnector.")
            raise ValueError(f"Unknown action: {action_name} for EmailConnector.")


if __name__ == '__main__':
    # This is example usage code.
    # For it to run, you need to set environment variables for your SMTP server details:
    # export SMTP_HOST="your_smtp_host"
    # export SMTP_PORT="your_smtp_port" (e.g., 587 for TLS, 465 for SSL, 25 for unencrypted)
    # export SMTP_USER="your_smtp_username"
    # export SMTP_PASSWORD="your_smtp_password_or_app_password"
    # export SENDER_EMAIL_FOR_TEST="your_sender_email@example.com" (optional, defaults to SMTP_USER)
    # export RECIPIENT_EMAIL_FOR_TEST="recipient@example.com"
    #
    # To run in simulation mode (prints email to console instead of sending):
    # export EMAIL_SIMULATE="true"

    # If run via `python -m integration_platform.main`, logging is already set up.
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.info("Starting EmailConnector __main__ example...")

    is_simulation_main = os.environ.get("EMAIL_SIMULATE", "false").lower() == "true"

    smtp_host_main = os.environ.get("SMTP_HOST")
    smtp_port_str_main = os.environ.get("SMTP_PORT")
    smtp_user_main = os.environ.get("SMTP_USER")
    smtp_password_main = os.environ.get("SMTP_PASSWORD")
    sender_email_main = os.environ.get("SENDER_EMAIL_FOR_TEST", smtp_user_main)
    recipient_email_test_main = os.environ.get("RECIPIENT_EMAIL_FOR_TEST")

    connector_main_email = None # Ensure defined for finally
    if is_simulation_main:
        logger.info("__main__: Running in SIMULATION MODE for Email.")
        connector_main_email = EmailConnector(
            smtp_host=smtp_host_main or "dummy.smtp.host",
            smtp_port=int(smtp_port_str_main) if smtp_port_str_main else 587,
            smtp_user=smtp_user_main or "dummy_user",
            smtp_password=smtp_password_main or "dummy_password",
            sender_email=sender_email_main or "dummy_sender@example.com"
        )
    elif not all([smtp_host_main, smtp_port_str_main, smtp_user_main, smtp_password_main, recipient_email_test_main]):
        logger.warning("__main__: One or more SMTP environment variables missing for actual email sending.")
        logger.warning("__main__: Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, RECIPIENT_EMAIL_FOR_TEST.")
        logger.warning("__main__: Or set EMAIL_SIMULATE='true' to run in simulation mode.")
    else:
        try:
            smtp_port_main = int(smtp_port_str_main)
            connector_main_email = EmailConnector(
                smtp_host=smtp_host_main,
                smtp_port=smtp_port_main,
                smtp_user=smtp_user_main,
                smtp_password=smtp_password_main,
                sender_email=sender_email_main,
                use_tls=(smtp_port_main != 465)
            )
        except ValueError:
            logger.error(f"__main__: Invalid SMTP_PORT: '{smtp_port_str_main}'. Must be an integer.", exc_info=True)

    if connector_main_email:
        try:
            # Explicit connect test (only if not simulating and all params are notionally present)
            if not is_simulation_main and all([smtp_host_main, smtp_port_str_main, smtp_user_main, smtp_password_main]):
                logger.info("__main__: Attempting to connect to SMTP server explicitly...")
                connector_main_email.connect()
                logger.info("__main__: Explicit connection successful.")

            test_subject = "Integration Platform Test Email"
            test_body = "This is a test email from the EmailConnector's __main__ block."

            logger.info(f"__main__: Attempting 'send_email' action to '{recipient_email_test_main or 'sim_recipient@example.com'}'...")

            result = connector_main_email.execute_action(
                "send_email",
                {
                    "recipient_email": recipient_email_test_main or "sim_recipient@example.com",
                    "subject": test_subject,
                    "body": test_body
                }
            )
            logger.info(f"__main__: 'send_email' action result: {result}")

        except ConnectionError as e_conn:
            logger.error(f"__main__: Connection error: {e_conn}", exc_info=True)
            if not is_simulation_main:
                 logger.warning("__main__: Please check your SMTP credentials and server details in environment variables.")
        except ValueError as e_val: # e.g. missing params for execute_action
            logger.error(f"__main__: Value error: {e_val}", exc_info=True)
        except Exception as e_main_exc:
            logger.error(f"__main__: An unexpected error occurred: {e_main_exc}", exc_info=True)
        finally:
            if connector_main_email: # Check if it was initialized
                logger.info("__main__: Attempting to disconnect EmailConnector in finally block.")
                connector_main_email.disconnect()
    else:
        if not is_simulation_main:
            logger.info("__main__: EmailConnector not initialized due to missing/invalid configuration. Example cannot run in non-simulation mode.")

    logger.info("EmailConnector __main__ example finished.")
