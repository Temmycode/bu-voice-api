from enum import Enum
import google.generativeai as genai
import logging
import cloudinary.uploader
import httpx
from passlib.context import CryptContext
from fastapi import UploadFile
from . import models, config

MAILGUN_DOMAIN = "sandbox35d2e69a8a264e7da82233d5568f1a2d.mailgun.org"


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def upload_file(file, type: str, public_id: str, folder: str) -> dict:
    upload_result = cloudinary.uploader.upload(
        file,
        folder=folder,
        public_id=public_id,
        overwrite=True,
        resource_type=type,
    )

    return upload_result


def get_staff_role_id_from_complaint(complaint: models.Complaint) -> int:
    if complaint.category_id == 1:
        return 4
    elif complaint.category_id == 2:
        return 5
    else:
        return 6


# * Function to send Welcom Mail
# async def send_staff_welcome_email(
#     background_tasks: BackgroundTasks, email: str, name: str, role: str
# ):
#     template = Path("app/templates/staff-welcome.html").read_text()
#     template = template.replace("{{name}}", name).replace("{{role}}", role)

#     message = MessageSchema(
#         subject="Welcome to BU-Voice",
#         recipients=[email],
#         body=template,
#         subtype="html",
#     )

#     background_tasks.add_task(fm.send_message, message)


class StaffRole(Enum):
    HADMIN = "hadmin"
    HOD = "hod"
    BURSAR = "bursar"
    HPORTER = "hporter"
    SECRETARY = "secretary"
    BSTAFF = "bstaff"


# def get_staff_role_id(role: str) -> int:
#     if role == "porter":
#         return 4
#     elif role == "secretary":
#         return 5
#     else:
#         return 6


async def send_email(to_email: str, subject: str, template: str, variables: dict):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
                auth=("api", config.settings.mailgun_api_key),
                data={
                    "from": f"Your App <mailgun@{MAILGUN_DOMAIN}>",
                    "to": to_email,
                    "subject": subject,
                    "template": template,
                    "h:X-Mailgun-Variables": str(variables),  # Pass JSON Variables
                },
            )

            response.raise_for_status()  # Raise an error if request fails
            logging.info(f"Email sent to {to_email}: {response.json()}")
    except httpx.HTTPStatusError as e:
        logging.error(f"Error sending email: {e.response.text}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")


def setup_gemini():
    genai.configure(api_key=config.settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
    return model


def categorize_complaint(title: str, description: str, category_id: int) -> dict:
    # """
    # Categorizes complaints using Gemini AI into hall, course, or bursary categories.
    # Returns category_id and confidence score.
    # """
    # model = setup_gemini()

    # prompt = f"""
    # Analyze this complaint and categorize it into one of these categories:
    # 1. Hall (issues related to student accommodation, facilities, or hall management)
    # 2. Course (academic issues, registration, course materials, or lectures)
    # 3. Bursary (financial matters, fees, or payments)

    # Complaint Title: {title}
    # Complaint Description: {description}

    # Respond in this JSON format only:
    # {{
    #     "category_id": (1 for Hall, 2 for Course, 3 for Bursary),
    #     "confidence": (confidence score between 0 and 1),
    #     "reasoning": "brief explanation of the categorization"
    # }}
    # """

    # try:
    #     response = model.generate_content(prompt)
    #     result = eval(response.text)  # Convert string response to dict
    #     return result
    # except Exception as e:
    # Fallback to default category (Course) if AI categorization fails
    return {
        "category_id": category_id,
        "confidence": 0.5,
        "reasoning": "Fallback categorization due to AI processing error",
    }
