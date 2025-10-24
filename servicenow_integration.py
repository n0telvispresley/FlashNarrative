import os
import requests
import base64
from slack_sdk import WebClient
import smtplib
from email.mime.text import MIMEText

def create_servicenow_ticket(title, description):
    """Create ServiceNow ticket; mock with print if no creds."""
    instance = os.getenv('SERVICENOW_INSTANCE')
    user = os.getenv('SERVICENOW_USER')
    password = os.getenv('SERVICENOW_PASSWORD')
    
    if not all([instance, user, password]):
        print(f"Mock ServiceNow Ticket: {title} - {description}")
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
            'urgency': '2',
            'impact': '2'
        }
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        ticket_num = response.json()['result']['number']
        print(f"Created ServiceNow Ticket: {ticket_num}")
    except Exception as e:
        print(f"ServiceNow error: {e}")
        print(f"Mock: {title} - {description}")

def send_alert(msg, channel='#alerts', to_email='user@email.com'):
    """Send alert via Slack or email; fallback to print."""
    sent = False
    
    # Try Slack
    token = os.getenv('SLACK_TOKEN')
    if token:
        try:
            client = WebClient(token=token)
            client.chat_postMessage(channel=channel, text=msg)
            sent = True
        except:
            pass
    
    # Try Email if Slack fails or no token
    if not sent:
        smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', 587))
        smtp_user = os.getenv('SMTP_USER')
        smtp_pass = os.getenv('SMTP_PASS')
        if smtp_user and smtp_pass:
            try:
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
                server.login(smtp_user, smtp_pass)
                email_msg = MIMEText(msg)
                email_msg['Subject'] = 'PR Alert'
                email_msg['From'] = smtp_user
                email_msg['To'] = to_email
                server.send_message(email_msg)
                server.quit()
                sent = True
            except:
                pass
    
    if not sent:
        print(f"Alert: {msg}")
        
