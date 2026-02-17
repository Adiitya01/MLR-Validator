import os
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from pathlib import Path

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# Load env from root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

def test_send():
    sg_api_key = os.getenv("SENDGRID_API_KEY")
    from_email = os.getenv("FROM_EMAIL")
    test_receiver = "adityapasare158@gmail.com" # Hardcoded for test
    
    print(f"API Key found: {sg_api_key[:10]}...")
    print(f"From Email: {from_email}")
    print(f"To Email: {test_receiver}")
    
    message = Mail(
        from_email=from_email,
        to_emails=test_receiver,
        subject='TEST EMAIL - MLR Validator',
        html_content='<strong>This is a test email to verify SendGrid settings.</strong>'
    )
    
    try:
        sg = SendGridAPIClient(sg_api_key)
        response = sg.send(message)
        print(f"Status Code: {response.status_code}")
        print(f"Body: {response.body}")
        print(f"Headers: {response.headers}")
        print("\n✅ SUCCESS: Email request accepted by SendGrid!")
    except Exception as e:
        print(f"\n❌ FAILED: {str(e)}")
        if hasattr(e, 'body'):
            print(f"Error Details: {e.body}")

if __name__ == "__main__":
    test_send()
