import os
import smtplib
from email.mime.text import MIMEText
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.email_user = os.getenv("EMAIL_USER")
        self.email_pass = os.getenv("EMAIL_PASS")
        self.email_target = os.getenv("EMAIL_TARGET")
        
    def send_email_notification(self, subject, message):
        """Send email notification for leads"""
        logger.info(f"📧 Attempting to send email...")
        logger.info(f"Subject: {subject}")
        logger.debug(f"Content:\n{message}")
        logger.debug(f"From: {self.email_user} → To: {self.email_target}")

        try:
            msg = MIMEText(message)
            msg["Subject"] = subject
            msg["From"] = self.email_user
            msg["To"] = self.email_target

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.email_user, self.email_pass)
                server.send_message(msg)

            logger.info("✅ Email sent successfully!")
            return True
        except Exception as e:
            logger.error(f"❌ Error sending email: {e}")
            return False
    
    def send_lead_notification(self, lead_text):
        """Send notification for new lead"""
        return self.send_email_notification(
            subject="🗣️ New Lead Details from Bot",
            message=f"User left details:\n\n{lead_text}"
        )