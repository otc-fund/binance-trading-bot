"""
Notification Module
Handles email and other notifications for the trading bot
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List
import json
import os


class NotificationSystem:
    def __init__(self, smtp_server: str = "smtp.gmail.com", smtp_port: int = 587):
        """
        Initialize the notification system
        
        Args:
            smtp_server: SMTP server address (default: Gmail)
            smtp_port: SMTP server port (default: 587 for TLS)
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = os.getenv("SENDER_EMAIL", "")
        self.sender_password = os.getenv("SENDER_PASSWORD", "")
        
    def configure_smtp(self, sender_email: str, sender_password: str, smtp_server: str = "smtp.gmail.com", smtp_port: int = 587):
        """
        Configure SMTP settings
        
        Args:
            sender_email: Email address to send notifications from
            sender_password: Password or app password for the email account
            smtp_server: SMTP server address
            smtp_port: SMTP server port
        """
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
    
    def send_email(self, recipient_emails: List[str], subject: str, body: str, is_html: bool = False):
        """
        Send an email notification
        
        Args:
            recipient_emails: List of email addresses to send to
            subject: Subject of the email
            body: Body of the email
            is_html: Whether the body is HTML formatted
        """
        if not self.sender_email or not self.sender_password:
            print("Email not configured. Please set sender email and password.")
            return False
        
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = ", ".join(recipient_emails)
            
            # Add body to email
            if is_html:
                part = MIMEText(body, "html")
            else:
                part = MIMEText(body, "plain")
            
            message.attach(part)
            
            # Create secure connection and send email
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, recipient_emails, message.as_string())
            
            print(f"Email notification sent successfully to {recipient_emails}")
            return True
            
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return False
    
    def send_trade_notification(self, recipient_emails: List[str], trade_data: Dict):
        """
        Send a notification about a trade
        
        Args:
            recipient_emails: List of email addresses to send to
            trade_data: Dictionary containing trade information
        """
        subject = f"Trade Alert: {trade_data.get('symbol', 'N/A')} {trade_data.get('signal', 'N/A')}"
        
        body = f"""
        Trade Alert!
        
        Symbol: {trade_data.get('symbol', 'N/A')}
        Signal: {trade_data.get('signal', 'N/A')}
        Entry Price: {trade_data.get('entry_price', 'N/A')}
        Exit Price: {trade_data.get('exit_price', 'N/A')}
        Quantity: {trade_data.get('quantity', 'N/A')}
        P&L: {trade_data.get('pnl', 'N/A')}
        P&L %: {trade_data.get('pnl_percent', 'N/A')}
        Reason: {trade_data.get('reason', 'N/A')}
        Timestamp: {trade_data.get('timestamp', 'N/A')}
        
        Best regards,
        Binance Trading Bot
        """
        
        return self.send_email(recipient_emails, subject, body)
    
    def send_performance_notification(self, recipient_emails: List[str], performance_data: Dict):
        """
        Send a performance summary notification
        
        Args:
            recipient_emails: List of email addresses to send to
            performance_data: Dictionary containing performance metrics
        """
        subject = f"Performance Report: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        body = f"""
        Daily Performance Report
        
        Total Trades: {performance_data.get('total_trades', 0)}
        Winning Trades: {performance_data.get('winning_trades', 0)}
        Losing Trades: {performance_data.get('losing_trades', 0)}
        Win Rate: {performance_data.get('win_rate', 0):.2f}%
        Total P&L: {performance_data.get('total_pnl', 0):.4f}
        Average Win: {performance_data.get('avg_win', 0):.4f}
        Average Loss: {performance_data.get('avg_loss', 0):.4f}
        Largest Win: {performance_data.get('largest_win', 0):.4f}
        Largest Loss: {performance_data.get('largest_loss', 0):.4f}
        Sharpe Ratio: {performance_data.get('sharpe_ratio', 0):.2f}
        Max Drawdown: {performance_data.get('max_drawdown', 0):.4f}
        Profit Factor: {performance_data.get('profit_factor', 0):.2f}
        
        Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        Best regards,
        Binance Trading Bot
        """
        
        return self.send_email(recipient_emails, subject, body)
    
    def send_alert_notification(self, recipient_emails: List[str], alert_type: str, message: str):
        """
        Send an alert notification
        
        Args:
            recipient_emails: List of email addresses to send to
            alert_type: Type of alert (e.g., 'error', 'warning', 'info')
            message: Alert message
        """
        subject = f"Bot Alert [{alert_type.upper()}]: {message[:50]}..."
        
        body = f"""
        Bot Alert
        
        Type: {alert_type.upper()}
        Message: {message}
        Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        Please check the bot status.
        
        Best regards,
        Binance Trading Bot
        """
        
        return self.send_email(recipient_emails, subject, body)