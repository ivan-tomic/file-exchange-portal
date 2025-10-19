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
    # Build HTML email
    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 0; }}
            .header {{ 
                background-color: #d10a10; 
                color: #ffffff; 
                padding: 20px; 
                text-align: left; 
                border-radius: 8px 8px 0 0;
                display: flex;
                align-items: center;
                gap: 15px;
            }}
            .header img {{
                max-height: 60px;
                width: auto;
            }}
            .header h2 {{
                margin: 0;
                font-size: 22px;
                color: #ffffff;
                font-weight: 600;
            }}
            .content {{ 
                background-color: #f9f9f9; 
                padding: 30px 20px; 
                border-radius: 0 0 8px 8px; 
            }}
            .file-info {{ 
                background-color: white; 
                padding: 20px; 
                margin: 20px 0; 
                border-left: 4px solid #d10a10; 
                border-radius: 4px;
            }}
            .file-info p {{
                margin: 8px 0;
            }}
            .urgency-high {{ color: #ff4d4f; font-weight: bold; }}
            .urgency-normal {{ color: #4caf50; font-weight: bold; }}
            .cta-button {{
                display: inline-block;
                padding: 12px 30px;
                background-color: #d10a10;
                color: #ffffff !important;
                text-decoration: none;
                border-radius: 6px;
                font-weight: 600;
                margin: 20px 0;
            }}
            .cta-button:hover {{
                background-color: #b00808;
            }}
            .footer {{ 
                margin-top: 30px; 
                padding-top: 20px; 
                border-top: 1px solid #ddd; 
                font-size: 12px; 
                color: #666; 
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFAAAABQCAIAAAABc2X6AAAFm2lUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4KPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iWE1QIENvcmUgNS41LjAiPgogPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4KICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIgogICAgeG1sbnM6dGlmZj0iaHR0cDovL25zLmFkb2JlLmNvbS90aWZmLzEuMC8iCiAgICB4bWxuczpleGlmPSJodHRwOi8vbnMuYWRvYmUuY29tL2V4aWYvMS4wLyIKICAgIHhtbG5zOnBob3Rvc2hvcD0iaHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIKICAgIHhtbG5zOnhtcD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wLyIKICAgIHhtbG5zOnhtcE1NPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvbW0vIgogICAgeG1sbnM6c3RFdnQ9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9zVHlwZS9SZXNvdXJjZUV2ZW50IyIKICAgdGlmZjpJbWFnZUxlbmd0aD0iODAiCiAgIHRpZmY6SW1hZ2VXaWR0aD0iODAiCiAgIHRpZmY6UmVzb2x1dGlvblVuaXQ9IjIiCiAgIHRpZmY6WFJlc29sdXRpb249IjcyLzEiCiAgIHRpZmY6WVJlc29sdXRpb249IjcyLzEiCiAgIGV4aWY6UGl4ZWxYRGltZW5zaW9uPSI4MCIKICAgZXhpZjpQaXhlbFlEaW1lbnNpb249IjgwIgogICBleGlmOkNvbG9yU3BhY2U9IjEiCiAgIHBob3Rvc2hvcDpDb2xvck1vZGU9IjMiCiAgIHBob3Rvc2hvcDpJQ0NQcm9maWxlPSJzUkdCIElFQzYxOTY2LTIuMSIKICAgeG1wOk1vZGlmeURhdGU9IjIwMjUtMTAt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" alt="Business Reporter">
                <h2>Business Reporter - File Exchange Portal</h2>
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
                
                <p>
                    <a href="https://businessreporter-ab.com/login" class="cta-button">Log in to the portal</a>
                </p>
                
                <p style="font-size: 14px; color: #666;">
                    Or copy and paste this link into your browser:<br>
                    <a href="https://businessreporter-ab.com/login" style="color: #d10a10;">https://businessreporter-ab.com/login</a>
                </p>
                
                <div class="footer">
                    <p>This is an automated notification from Business Reporter File Exchange Portal.</p>
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