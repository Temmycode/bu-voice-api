import httpx
from app import config


NOVU_API_KEY = config.settings.novu_secret_key
NOVU_API_URL = "https://api.novu.co/v1"


async def send_email(recipient_email: str, subject: str, content: str):
    """
    Sends an email via NovuHQ
    """
    headers = {
        "Authorization": f"ApiKey {NOVU_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "to": [{"subscriberId": recipient_email, "email": recipient_email}],
        "payload": {
            "subject": subject,
            "message": content
        },
        "templateIdentifier": "welcome-email"  # Replace with your actual template ID
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{NOVU_API_URL}/events/trigger", json=payload, headers=headers)

    if response.status_code == 201:
        return {"success": True, "message": "Email sent successfully!"}
    else:
        return {"success": False, "error": response.json()}