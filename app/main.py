import cloudinary
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from .database import engine
from . import models
from .routers import auth, staff, student, complaints
from .config import settings

# TODO: WORK ON SENDING THE EMAILS TO THE STAFF AND STUDENTS WHEN:
# 1: STUDENTS SUBMITS A COMPLAINT (COMPLAINT ID IS SENT)
# 2: STUDENT REGISTERS INTO THE SYSTEM
# 3: STAFF IS ASSIGNED A TASK
# 4: STAFF REGISTERS ONTO THE SYSTEM

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

origins = ["*"]

cloudinary.config(
    cloud_name=settings.cloudinary_cloud_name,
    api_key=settings.cloudinary_api_key,
    api_secret=settings.cloudinary_secret_key,
    secure=True,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # ✅ Your frontend
        "https://accounts.google.com",  # ✅ Google Auth
    ],
    allow_credentials=True,  # ✅ Allows cookies, session tokens
    allow_methods=["*"],  # ✅ Allows all HTTP methods
    allow_headers=["*"],  # ✅ Allows all headers
)


class COOPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        return response


app.add_middleware(COOPMiddleware)


@app.get("/")
def root():
    return {"data": "Welcome to Student Complaint Management System"}


app.include_router(auth.router)
app.include_router(staff.router)
app.include_router(student.router)
app.include_router(complaints.router)
