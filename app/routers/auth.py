import time
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests
from .. import models, utils, oauth2, schemas
from ..database import get_db
from ..config import settings
from ..schemas import ResponseModel

router = APIRouter(tags=["Authentication"])


@router.post("/student/login", response_model=ResponseModel[schemas.LoginResponse])
def student_login(
    user_credentials: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user: models.Student = (
        db.query(models.Student)
        .filter(models.Student.email == user_credentials.username)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Credentials"
        )

    if not utils.verify_password(user_credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Credentials"
        )

    # * create access token
    access_token = oauth2.create_access_token(data={"sub": user.email})
    data = schemas.LoginResponse(
        access_token=access_token,
        token_type="bearer",
        student=user,
    )
    return ResponseModel(
        metadata=schemas.Metadata(status_code=200, success=True),
        data=data,
    )


@router.post("/staff/login", response_model=ResponseModel[schemas.StaffLoginResponse])
def staff_login(
    user_credentials: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user: models.Staff = (
        db.query(models.Staff)
        .filter(models.Staff.email == user_credentials.username)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Credentials"
        )

    if not utils.verify_password(user_credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Credentials"
        )

    # * create access token
    access_token = oauth2.create_access_token(data={"sub": user.email})
    data = schemas.StaffLoginResponse(
        access_token=access_token,
        token_type="bearer",
        staff=schemas.Staff.model_validate(user),
    )
    return ResponseModel(
        metadata=schemas.Metadata(status_code=200, success=True),
        data=data,
    )


@router.post("/google/staff-verify")
def verify_staff_google_token(
    token_data: schemas.GoogleToken, db: Session = Depends(get_db)
):
    try:
        idinfo = id_token.verify_oauth2_token(
            token_data.token, requests.Request(), settings.google_client_id
        )
        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Wrong issuer.")

        staff_email = idinfo["email"]
        staff_fullname = idinfo["name"]

        # * Check if user exists
        staff = db.query(models.Staff).filter(models.Staff.email == staff_email).first()

        if not staff:
            # * Create user
            staff: models.Staff = models.Staff(
                email=staff_email, fullname=staff_fullname
            )
            db.add(staff)
            db.commit()
            db.refresh(staff)

            # * generate access token
            access_token = oauth2.create_access_token(data={"sub": staff.email})

            return {"access_token": access_token, "token_type": "bearer"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            details=f"Invalid token {e}",
        )


@router.post("/google/student-login")
def google_student_login(
    token_data: schemas.GoogleToken, db: Session = Depends(get_db)
):
    """Login students using Google OAuth if they already exist."""
    try:
        idinfo = id_token.verify_oauth2_token(
            token_data.token, requests.Request(), settings.google_client_id
        )

        # Validate token
        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Wrong issuer.")

        if idinfo["aud"] != settings.google_client_id:
            raise ValueError("Invalid audience.")

        if idinfo["exp"] < time.time():
            raise ValueError("Token expired.")

        if not idinfo.get("email_verified", False):
            raise ValueError("Email not verified by Google.")
        print(f"idinfo {idinfo}")
        student_email = idinfo["email"]
        print(student_email)

        # Check if user exists
        student = (
            db.query(models.Student)
            .filter(models.Student.email == student_email)
            .first()
        )

        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found. Please sign up first.",
            )

        # Generate access token
        access_token = oauth2.create_access_token(data={"sub": student.email})
        data = schemas.LoginResponse(
            access_token=access_token,
            token_type="bearer",  # Standard OAuth token type
            student=student,
        )

        return ResponseModel(
            metadata=schemas.Metadata(status_code=200, success=True),
            data=data,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}",
        )


@router.post("/google/student-signup")
def google_student_signup(
    token_data: schemas.GoogleToken, db: Session = Depends(get_db)
):
    print(token_data)
    """Sign up students using Google OAuth if they don’t exist."""
    try:
        idinfo = id_token.verify_oauth2_token(
            token_data.token, requests.Request(), settings.google_client_id
        )
        print("Decoded Token: ", idinfo)
        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Wrong issuer.")

        student_email = idinfo["email"]
        student_fullname = idinfo["name"]

        # * Check if student already exists
        existing_student = (
            db.query(models.Student)
            .filter(models.Student.email == student_email)
            .first()
        )
        if existing_student:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Student already exists. Please log in.",
            )

        # * Create new student
        student = models.Student(email=student_email, fullname=student_fullname)
        db.add(student)
        db.commit()
        db.refresh(student)

        # * Generate access token
        access_token = oauth2.create_access_token(data={"sub": student.email})

        return {"access_token": access_token, "token_type": "bearer"}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid token: {e}",
        )
