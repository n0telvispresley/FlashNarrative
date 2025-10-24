import os
import requests
import base64
from slack_sdk import WebClient
import smtplib
from email.mime.text import MIMEText

def create_servicenow_ticket(title, description, urgency='2', impact='2'):
    """
    Create a ServiceNow incident ticket.
    Falls back to mock print if credentials are missing or request fails.
    """
    instance = os.getenv('SERVICENOW_INSTANCE')
    user = os.getenv('SERVICENOW_USER')
    password = os.getenv('SERVICENOW_PASSWORD')
    
    if not all([instance, user, password]):
        print(f"[Mock ServiceNow Ticket] {title} - {description}")
        return
    
    try:
        auth = base64.b64encode(f"{user}:{password}".encode()).decode()
        headers = {
            'Authorization': f'Basic {auth}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        url = f"https://{instance}.service-now.com/api/now/table/incident"
        body = {
            'short_description': title,
            'description': description,
            'urgency': urgency,
            'impact': impact
        }
        response = requests.post(url, headers=headers, json=body, timeout=10)
        response.raise_for_status()
        ticket_num = response.json().get('result', {}).get('number', 'UNKNOWN')
        print(f"[ServiceNow Ticket Created] {ticket_num}")
        return ticket_num
    except Exception as e:
        print(f"[ServiceNow Error] {e}")
        print(f"[Mock ServiceNow Ticket] {title} - {description}")

def send_alert(msg, channel='#alerts', to_email=None):
    """
    Send alert message via Slack or Email.
    Falls back to print if both fail.
    """
    sent = False

    # Attempt Slack
    token = os.getenv('SLACK_TOKEN')
    if token:
        try:
            client = WebClient(token=token)
            client.chat_postMessage(channel=channel, text=msg)
            sent = True
        except Exception as e:
            print(f"[Slack Error] {e}")

    # Attempt Email if Slack fails or no token
    if not sent:
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', 587))
        smtp_user = os.getenv('SMTP_USER')
        smtp_pass = os.getenv('SMTP_PASS')
        if smtp_user and smtp_pass and to_email:
            try:
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
                server.starttls()
                server.login(smtp_user, smtp_pass)
                email_msg = MIMEText(msg)
                email_msg['Subject'] = 'PR Alert'
                email_msg['From'] = smtp_user
                email_msg['To'] = to_email
                server.send_message(email_msg)
                server.quit()
                sent = True
            except Exception as e:
                print(f"[Email Error] {e}")

    # Fallback
    if not sent:
        print(f"[Alert Fallback] {msg}")
