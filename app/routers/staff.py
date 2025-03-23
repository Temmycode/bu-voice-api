import cloudinary.uploader
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    BackgroundTasks,
    UploadFile,
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, joinedload
from .. import database, schemas, models, utils, oauth2
from ..schemas import ResponseModel

router = APIRouter(prefix="/staff", tags=["staff"])


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=ResponseModel[schemas.Staff],
)
def create_staff(staff: schemas.CreateStaff, db: Session = Depends(database.get_db)):
    try:

        hashed_password = utils.get_password_hash(staff.password)
        staff.password = hashed_password
        existing_staff = (
            db.query(models.Staff).filter(models.Staff.email == staff.email).first()
        )

        if existing_staff:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        # * get the staff's role id

        staff = models.Staff(
            email=staff.email,
            fullname=staff.fullname,
            department=staff.department,
            hall_name=staff.hall,
            password=staff.password,
            role_id=staff.role,
        )
        db.add(staff)
        db.commit()
        db.refresh(staff)

        # * Send Welcome Email
        # await utils.send_staff_welcome_email(
        #     background_tasks=background_tasks,
        #     email=staff.email,
        #     name=staff.fullname,
        #     role=role,
        # )

        return ResponseModel(
            metadata=schemas.Metadata(status_code=201, success=True),
            data=staff,
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating staff: {str(err)}",
        )


@router.patch(
    "/update-profile-picture",
    status_code=status.HTTP_200_OK,
)
def update_profile_picture(
    profile_picture: UploadFile | None,
    staff: schemas.Staff = Depends(oauth2.get_current_staff),
    db: Session = Depends(database.get_db),
):
    if not profile_picture.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image",
        )

    try:
        upload_result = cloudinary.uploader.upload(
            profile_picture.file,
            folder="profile_pictures",
            public_id=f"staff-{staff.id}",
            overwrite=True,
            resource_type="image",
        )

        db.query(models.Staff).filter(models.Staff.id == staff.id).update(
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


@router.get("/complaints")
def get_all_staff_assigned_complaints(
    search: str | None = None,
    staff: schemas.Staff = Depends(oauth2.get_current_staff),
    db: Session = Depends(database.get_db),
):

    base_query = (
        db.query(models.Complaint)
        .options(
            joinedload(models.Complaint.category),
            joinedload(models.Complaint.assignment),
        )
        .join(
            models.ComplaintCategory,
            models.Complaint.category_id == models.ComplaintCategory.id,
            isouter=True,
        )
        .join(
            models.ComplaintType,
            models.Complaint.category_id == models.ComplaintType.category_id,
            isouter=True,
        )
        .join(
            models.ComplaintAssignment,
            models.Complaint.id == models.ComplaintAssignment.complaint_id,
            isouter=True,
        )
        .join(models.Priorities, models.Complaint.priority_id == models.Priorities.id)
        .filter(models.ComplaintAssignment.staff_id == staff.id)
        .order_by(models.Complaint.created_at.desc())
    )

    if search:
        base_query = base_query.filter(models.Complaint.title.ilike(f"%{search}%"))

    complaints: list = base_query.all()

    data = [
        schemas.Complaints(
            id=complaint.id,
            student_id=complaint.student_id,
            category=schemas.ComplaintCategory(
                id=complaint.category.id,
                name=complaint.category.name,
            ),
            priority_id=complaint.priority_id,
            title=complaint.title,
            description=complaint.description,
            file_url=complaint.file_url,
            status=complaint.status,
            complaint_assignment=(
                schemas.ComplaintAssignment(
                    id=complaint.assignment.id,
                    staff=complaint.assignment.staff,
                    complaint_id=complaint.assignment.complaint_id,
                    status=complaint.assignment.status,
                    response=complaint.assignment.response,
                    internal_notes=complaint.assignment.internal_notes,
                    assigned_at=complaint.assignment.assigned_at,
                    updated_at=complaint.assignment.updated_at,
                    resolved_at=complaint.assignment.resolved_at,
                )
                if complaint.assignment is not None
                else None
            ),
            created_at=complaint.created_at,
        )
        for complaint in complaints
    ]

    return ResponseModel(
        metadata=schemas.Metadata(status_code=200, success=True),
        data=data,
    )


@router.get("/resolved-complaints")
def get_all_staff_resolved_complaints(
    staff: schemas.Staff = Depends(oauth2.get_current_staff),
    db: Session = Depends(database.get_db),
):
    complaints: list = (
        db.query(models.Complaint)
        .options(
            joinedload(models.Complaint.category),
            joinedload(models.Complaint.assignment),
        )
        .join(
            models.ComplaintCategory,
            models.Complaint.category_id == models.ComplaintCategory.id,
            isouter=True,
        )
        .join(
            models.ComplaintType,
            models.Complaint.category_id == models.ComplaintType.category_id,
            isouter=True,
        )
        .join(
            models.ComplaintAssignment,
            models.Complaint.id == models.ComplaintAssignment.complaint_id,
            isouter=True,
        )
        .join(models.Priorities, models.Complaint.priority_id == models.Priorities.id)
        .filter(models.Complaint.closed_by == staff.id)
        .all()
    )

    data = [
        schemas.Complaints(
            id=complaint.id,
            student_id=complaint.student_id,
            category=schemas.ComplaintCategory(
                id=complaint.category.id,
                name=complaint.category.name,
            ),
            priority_id=complaint.priority_id,
            title=complaint.title,
            description=complaint.description,
            file_url=complaint.file_url,
            status=complaint.status,
            complaint_assignment=(
                schemas.ComplaintAssignment(
                    id=complaint.assignment.id,
                    staff=complaint.assignment.staff,
                    complaint_id=complaint.assignment.complaint_id,
                    status=complaint.assignment.status,
                    response=complaint.assignment.response,
                    internal_notes=complaint.assignment.internal_notes,
                    assigned_at=complaint.assignment.assigned_at,
                    updated_at=complaint.assignment.updated_at,
                    resolved_at=complaint.assignment.resolved_at,
                )
                if complaint.assignment is not None
                else None
            ),
            created_at=complaint.created_at,
        )
        for complaint in complaints
    ]

    return ResponseModel(
        metadata=schemas.Metadata(status_code=200, success=True), data=data
    )


@router.patch("/update-complaint")
def update_complaint(
    update_complaint: schemas.ComplaintUpdate,
    staff: schemas.Staff = Depends(oauth2.get_current_staff),
    db: Session = Depends(database.get_db),
):
    complaint = (
        db.query(models.Complaint)
        .filter(models.Complaint.id == update_complaint.id)
        .first()
    )

    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint with id {update_complaint.id} doesn't exist",
        )

    complaint.status = update_complaint.status
    complaint.assignment.response = update_complaint.response
    db.add(complaint)
    db.commit()
    db.refresh(complaint)

    complaint = schemas.Complaints(
        id=complaint.id,
        student_id=complaint.student_id,
        category=schemas.ComplaintCategory(
            id=complaint.category.id,
            name=complaint.category.name,
        ),
        priority_id=complaint.priority_id,
        title=complaint.title,
        description=complaint.description,
        file_url=complaint.file_url,
        status=complaint.status,
        complaint_assignment=(
            schemas.ComplaintAssignment(
                id=complaint.assignment.id,
                staff=complaint.assignment.staff,
                complaint_id=complaint.assignment.complaint_id,
                status=complaint.assignment.status,
                response=complaint.assignment.response,
                internal_notes=complaint.assignment.internal_notes,
                assigned_at=complaint.assignment.assigned_at,
                updated_at=complaint.assignment.updated_at,
                resolved_at=complaint.assignment.resolved_at,
            )
            if complaint.assignment is not None
            else None
        ),
        created_at=complaint.created_at,
    )

    return complaint
