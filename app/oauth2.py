from datetime import timedelta, datetime, timezone
from typing import Optional, Annotated
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from .database import get_db
from . import models, schemas
from .config import settings

student_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="student-login")
staff_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="staff-login")


def get_student(email: str, db: Session = Depends(get_db)) -> Optional[schemas.Student]:
    try:
        user = db.query(models.Student).filter(models.Student.email == email).first()
        # * convert SQLALchemy model to Pydantic model
        return schemas.Student.model_validate(user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


def get_staff(email: str, db: Session = Depends(get_db)) -> Optional[schemas.Staff]:
    try:
        user = db.query(models.Staff).filter(models.Staff.email == email).first()
        # * convert SQLALchemy model to Pydantic model
        return schemas.Staff.model_validate(user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e,
        )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )
    return encoded_jwt


async def get_current_student(
    token: Annotated[str, Depends(student_oauth2_scheme)], db: Session = Depends(get_db)
) -> schemas.Student:
    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credential_exception
        token_data: schemas.TokenData = schemas.TokenData(email=email)
    except InvalidTokenError:
        raise credential_exception
    user: Optional[schemas.Student] = get_student(email=token_data.email, db=db)
    if user is None:
        raise credential_exception
    return user


async def get_current_staff(
    token: Annotated[str, Depends(staff_oauth2_scheme)], db: Session = Depends(get_db)
) -> schemas.Staff:
    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credential_exception
        token_data: schemas.TokenData = schemas.TokenData(email=email)

    except InvalidTokenError:
        raise credential_exception
    user: Optional[schemas.Staff] = get_staff(email=token_data.email, db=db)
    if user is None:
        raise credential_exception
    return user
