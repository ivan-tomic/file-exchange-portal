"""
Email notification utilities for File Exchange Portal
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List
import logging

from config import (
    SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
    SMTP_FROM_EMAIL, SMTP_FROM_NAME, EMAIL_NOTIFICATIONS_ENABLED, APP_NAME
)

logger = logging.getLogger(__name__)


def send_email(to_emails: List[str], subject: str, body_html: str, body_text: str = None) -> bool:
    """
    Send an email notification.
    
    Args:
        to_emails: List of recipient email addresses
        subject: Email subject
        body_html: HTML body of the email
        body_text: Plain text body (optional, will use stripped HTML if not provided)
    
    Returns:
        True if email sent successfully, False otherwise
    """
    if not EMAIL_NOTIFICATIONS_ENABLED:
        logger.info("Email notifications are disabled")
        return False
    
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured, skipping email")
        return False
    
    # Filter out empty emails
    to_emails = [email.strip() for email in to_emails if email and email.strip()]
    
    if not to_emails:
        logger.info("No valid recipient emails provided")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg['To'] = ", ".join(to_emails)
        msg['Subject'] = subject
        
        # Add plain text version
        if body_text:
            part1 = MIMEText(body_text, 'plain')
            msg.attach(part1)
        
        # Add HTML version
        part2 = MIMEText(body_html, 'html')
        msg.attach(part2)
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {', '.join(to_emails)}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return False


def notify_file_upload(filename: str, uploader: str, uploader_role: str, recipient_emails: List[str], urgency: str = "Normal", stage: str = "") -> bool:
    """
    Send notification when a file is uploaded.
    
    Args:
        filename: Name of uploaded file
        uploader: Username who uploaded the file
        uploader_role: Role of the uploader (user, admin, super)
        recipient_emails: List of email addresses to notify
        urgency: File urgency (High/Normal)
        stage: File stage
    
    Returns:
        True if email sent successfully, False otherwise
    """
    # Determine who uploaded for better messaging
    if uploader_role == "user":
        uploader_label = "Amazon Business"
    else:
        uploader_label = f"{uploader} ({uploader_role})"
    
    subject = f"New File Upload: {filename}"
    
    # Build HTML email
    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #0b0c10; color: #f6f7fb; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
            .content {{ background-color: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }}
            .file-info {{ background-color: white; padding: 15px; margin: 15px 0; border-left: 4px solid #00a8e1; }}
            .urgency-high {{ color: #ff4d4f; font-weight: bold; }}
            .urgency-normal {{ color: #4caf50; font-weight: bold; }}
            .footer {{ margin-top: 20px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>{APP_NAME}</h2>
            </div>
            <div class="content">
                <p>Hello,</p>
                <p>A new file has been uploaded to the File Exchange Portal.</p>
                
                <div class="file-info">
                    <p><strong>File:</strong> {filename}</p>
                    <p><strong>Uploaded by:</strong> {uploader_label}</p>
                    <p><strong>Urgency:</strong> <span class="urgency-{urgency.lower()}">{urgency}</span></p>
                    {f'<p><strong>Stage:</strong> {stage}</p>' if stage else ''}
                </div>
                
                <p>Please log in to the portal to review and download the file.</p>
                
                <div class="footer">
                    <p>This is an automated notification from {APP_NAME}.</p>
                    <p>Please do not reply to this email.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Plain text version
    body_text = f"""
{APP_NAME}

A new file has been uploaded to the File Exchange Portal.

File: {filename}
Uploaded by: {uploader_label}
Urgency: {urgency}
{f'Stage: {stage}' if stage else ''}

Please log in to the portal to review and download the file.

---
This is an automated notification from {APP_NAME}.
Please do not reply to this email.
    """
    
    return send_email(recipient_emails, subject, body_html, body_text)