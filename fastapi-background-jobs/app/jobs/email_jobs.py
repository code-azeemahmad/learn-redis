import logging
import time

logger = logging.getLogger(__name__)


def send_welcome_email(email: str):
    """
    Simulates sending a welcome email.
    Takes 5 seconds to simulate external SMTP/network latency.
    Simulates a failure when the email contains 'fail' to demonstrate RQ retry behavior.
    """
    print(f"Preparing welcome email for {email}")

    # Simulate failure for retry testing
    if "fail" in email.lower():
        print(f"Simulated SMTP network error for {email}!")
        raise ConnectionError(f"Temporary SMTP provider outage when sending to {email}")

    # Simulate 5-second email processing delay
    time.sleep(5)
    print(f"Welcome email sent to {email}")
    return {
        "status": "sent",
        "email": email
    }
