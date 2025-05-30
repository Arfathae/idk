import unittest
from unittest.mock import patch, MagicMock
import os
import smtplib # For exception types
from email.mime.text import MIMEText

from integration_platform.connectors.email_connector import EmailConnector

# Module-level logger for tests
import logging
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG) # Uncomment for detailed logs


class TestEmailConnector(unittest.TestCase):

    def setUp(self):
        self.smtp_config = {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_user": "user@example.com",
            "smtp_password": "password",
            "sender_email": "sender@example.com",
            "use_tls": True
        }
        self.connector = EmailConnector(**self.smtp_config)

    @patch('smtplib.SMTP')
    def test_connect_smtp_tls_success(self, MockSMTP):
        logger.debug("Running test_connect_smtp_tls_success")
        mock_server = MockSMTP.return_value
        
        self.connector.connect()

        MockSMTP.assert_called_once_with(self.smtp_config["smtp_host"], self.smtp_config["smtp_port"], timeout=10)
        mock_server.ehlo.assert_called() # Called before and after starttls
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with(self.smtp_config["smtp_user"], self.smtp_config["smtp_password"])
        self.assertIsNotNone(self.connector.server)

    @patch('smtplib.SMTP_SSL')
    def test_connect_smtp_ssl_success(self, MockSMTP_SSL):
        logger.debug("Running test_connect_smtp_ssl_success")
        mock_server = MockSMTP_SSL.return_value
        
        ssl_config = self.smtp_config.copy()
        ssl_config["smtp_port"] = 465
        ssl_config["use_tls"] = False # Typically STARTTLS is not used with SMTP_SSL
        
        connector_ssl = EmailConnector(**ssl_config)
        connector_ssl.connect()

        MockSMTP_SSL.assert_called_once_with(ssl_config["smtp_host"], ssl_config["smtp_port"], timeout=10)
        mock_server.login.assert_called_once_with(ssl_config["smtp_user"], ssl_config["smtp_password"])
        # starttls should not be called for SMTP_SSL
        mock_server.starttls.assert_not_called()
        self.assertIsNotNone(connector_ssl.server)

    @patch('smtplib.SMTP')
    def test_connect_login_failure(self, MockSMTP):
        logger.debug("Running test_connect_login_failure")
        mock_server = MockSMTP.return_value
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication credentials invalid")

        with self.assertRaises(ConnectionError) as context:
            self.connector.connect()
        self.assertIn("SMTP authentication failed", str(context.exception))

    @patch('smtplib.SMTP')
    def test_send_email_success(self, MockSMTP):
        logger.debug("Running test_send_email_success")
        # Assume connector is connected
        self.connector.server = MockSMTP.return_value 
        
        recipient = "receiver@example.com"
        subject = "Test Subject"
        body = "This is the body."
        
        result_dict = self.connector.execute_action("send_email", {
            "recipient_email": recipient, "subject": subject, "body": body
        })

        self.connector.server.sendmail.assert_called_once()
        args, _ = self.connector.server.sendmail.call_args
        self.assertEqual(args[0], self.smtp_config["sender_email"])
        self.assertEqual(args[1], recipient)
        # Check that args[2] (the message string) contains subject, from, to, body
        message_string = args[2]
        self.assertIn(f"Subject: {subject}", message_string)
        self.assertIn(f"From: {self.smtp_config['sender_email']}", message_string)
        self.assertIn(f"To: {recipient}", message_string)
        self.assertIn(body, message_string)
        self.assertEqual(result_dict, {"status": "sent"})

    @patch('smtplib.SMTP')
    def test_send_email_smtp_exception(self, MockSMTP):
        logger.debug("Running test_send_email_smtp_exception")
        self.connector.server = MockSMTP.return_value
        self.connector.server.sendmail.side_effect = smtplib.SMTPException("Test SMTP error")

        params = {"recipient_email": "r@ex.com", "subject": "S", "body": "B"}
        result = self.connector.execute_action("send_email", params)
        
        self.assertEqual(result["status"], "failed")
        self.assertIn("Test SMTP error", result["error"])

    @patch.dict(os.environ, {"EMAIL_SIMULATE": "true"})
    @patch('smtplib.SMTP') # Mock SMTP so it's not actually used
    def test_send_email_simulation_mode(self, MockSMTP):
        logger.debug("Running test_send_email_simulation_mode")
        # In simulation mode, connect() might not even be called by send_email
        # but if it were, we don't want real SMTP.
        # The actual send_email method should bypass SMTP calls.
        
        params = {"recipient_email": "sim_rec@ex.com", "subject": "Sim Subject", "body": "Sim Body"}
        
        # Capture logger output for simulation
        with self.assertLogs(logger='integration_platform.connectors.email_connector', level='INFO') as cm:
            result = self.connector.execute_action("send_email", params)
        
        self.assertEqual(result, {"status": "sent"}) # Simulation is considered a "success" in terms of execution
        
        # Check logs for simulation details
        self.assertTrue(any("SIMULATING email sending" in log_msg for log_msg in cm.output))
        self.assertTrue(any("From: sender@example.com" in log_msg for log_msg in cm.output)) # Checks sender_email from setUp
        self.assertTrue(any("To: sim_rec@ex.com" in log_msg for log_msg in cm.output))
        self.assertTrue(any("Subject: Sim Subject" in log_msg for log_msg in cm.output))

    def test_execute_action_unknown(self):
        logger.debug("Running test_execute_action_unknown")
        with self.assertRaises(ValueError):
            self.connector.execute_action("unknown_action", {})

    def test_disconnect_while_connected(self):
        logger.debug("Running test_disconnect_while_connected")
        self.connector.server = MagicMock(spec=smtplib.SMTP)
        self.connector.disconnect()
        self.connector.server.quit.assert_called_once()
        self.assertIsNone(self.connector.server)

    def test_disconnect_when_not_connected(self):
        logger.debug("Running test_disconnect_when_not_connected")
        self.connector.server = None # Ensure not connected
        # Should not raise any error
        try:
            self.connector.disconnect()
        except Exception as e:
            self.fail(f"disconnect() raised {type(e).__name__} unexpectedly: {e}")
        self.assertIsNone(self.connector.server)

if __name__ == '__main__':
    unittest.main()
