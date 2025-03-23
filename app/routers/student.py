import cloudinary.uploader
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    status,
    File,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.novu import send_email
from .. import schemas, utils, models, database, oauth2
from ..schemas import ResponseModel

router = APIRouter(prefix="/student", tags=["students"])


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=ResponseModel[schemas.Student],
)
async def create_student(
    student: schemas.CreateStudent,
    background_task: BackgroundTasks,
    db: Session = Depends(database.get_db),
):
    hashed_password = utils.get_password_hash(student.password)
    student.password = hashed_password
    existing_student = (
        db.query(models.Student).filter(models.Student.email == student.email).first()
    )
    if existing_student:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )
    student = models.Student(**student.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)

    # Send email in the background
    subject = "Welcome to BU Voice 🎉"
    content = f"Hello {student.fullname},\n\nWelcome to BU Voice! We're excited to have you on board."
    await send_email(student.email, subject, content)
    # background_task.add_task(send_email, student.email, subject, content)

    return ResponseModel(
        metadata=schemas.Metadata(status_code=201, success=True),
        data=student,
    )


@router.patch("/update-profile-picture", status_code=status.HTTP_200_OK)
def update_profile_picture(
    profile_picture: UploadFile = File(...),
    student: schemas.Student = Depends(oauth2.get_current_student),
    db: Session = Depends(database.get_db),
):
    if not profile_picture.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image",
        )

    try:
        # Read the file as binary
        file_bytes = profile_picture.file.read()

        # Upload to Cloudinary using a binary stream
        upload_result = utils.upload_file(
            file=file_bytes,  # Pass binary data instead of file object
            type="image",
            public_id=f"student-{student.id}",
            folder="profile_pictures",
        )

        # Update student profile picture in DB
        db.query(models.Student).filter(models.Student.id == student.id).update(
            {"profile_image": upload_result["secure_url"]}
        )
        db.commit()

        data = {
            "message": "Profile picture updated successfully",
            "profile_picture_url": upload_result["secure_url"],
        }
        return ResponseModel(
            metadata=schemas.Metadata(status_code=200, success=True),
            data=data,
        )

    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading file: {str(err)}",
        )
    finally:
        profile_picture.file.close()
