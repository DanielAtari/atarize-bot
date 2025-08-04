import smtplib
from email.mime.text import MIMEText
import logging
from config.settings import Config

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.email_user = Config.EMAIL_USER
        self.email_pass = Config.EMAIL_PASS
        self.email_target = Config.EMAIL_TARGET
    
    def send_email_notification(self, subject, message):
        """Send email notification for leads or contacts"""
        logger.info(f"[EMAIL_ATTEMPT] 🚀 Starting email send process...")
        logger.info(f"[EMAIL_ATTEMPT] Subject: '{subject}'")
        logger.info(f"[EMAIL_ATTEMPT] Message length: {len(message)} characters")
        
        try:
            # Check email configuration
            logger.debug(f"[EMAIL_CONFIG] Checking email configuration...")
            logger.debug(f"[EMAIL_CONFIG] EMAIL_USER: {'✅ SET' if self.email_user else '❌ MISSING'}")
            logger.debug(f"[EMAIL_CONFIG] EMAIL_PASS: {'✅ SET' if self.email_pass else '❌ MISSING'}")
            logger.debug(f"[EMAIL_CONFIG] EMAIL_TARGET: {'✅ SET' if self.email_target else '❌ MISSING'}")
            
            if not all([self.email_user, self.email_pass, self.email_target]):
                logger.error("[EMAIL] ❌ Email configuration incomplete!")
                logger.error(f"[EMAIL] Missing: {[k for k, v in {'EMAIL_USER': self.email_user, 'EMAIL_PASS': self.email_pass, 'EMAIL_TARGET': self.email_target}.items() if not v]}")
                return False
            
            logger.info(f"[EMAIL] ✅ Email configuration valid")
            logger.info(f"[EMAIL] From: {self.email_user}")
            logger.info(f"[EMAIL] To: {self.email_target}")
            
            # Create message
            logger.debug(f"[EMAIL] Creating email message...")
            msg = MIMEText(message, 'plain', 'utf-8')
            msg['Subject'] = subject
            msg['From'] = self.email_user
            msg['To'] = self.email_target
            
            # Send email
            logger.info(f"[EMAIL] 📤 Connecting to Gmail SMTP server...")
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                logger.debug(f"[EMAIL] Starting TLS encryption...")
                server.starttls()
                
                logger.debug(f"[EMAIL] Logging in with user: {self.email_user}")
                server.login(self.email_user, self.email_pass)
                
                logger.info(f"[EMAIL] 📨 Sending message...")
                server.send_message(msg)
            
            logger.info(f"[EMAIL] ✅ EMAIL SENT SUCCESSFULLY!")
            logger.info(f"[EMAIL] 📧 Subject: {subject}")
            logger.info(f"[EMAIL] 📬 To: {self.email_target}")
            logger.info(f"[EMAIL] 🕐 Time: {logger.handlers[0].formatter.formatTime(logger.makeRecord('', 0, '', 0, '', (), None)) if logger.handlers else 'Unknown'}")
            
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"[EMAIL] ❌ SMTP Authentication failed: {e}")
            logger.error(f"[EMAIL] Check if EMAIL_PASS is a valid Gmail App Password")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"[EMAIL] ❌ SMTP Error: {e}")
            return False
        except Exception as e:
            logger.error(f"[EMAIL] ❌ Unexpected error sending email: {e}")
            logger.error(f"[EMAIL] Error type: {type(e).__name__}")
            return False