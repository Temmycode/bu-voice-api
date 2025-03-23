import logging
from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from .. import database, models, oauth2, schemas, utils
from ..schemas import ResponseModel
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/complaint", tags=["complaints"])


def create_complaint(
    title: str,
    description: str,
    category_id: int,
    priority_id: int,
    student: schemas.Student,
    db: Session,
    file: UploadFile | None = None,
):
    # * 1 - Hall, 2 - Course, 3 - Bursary
    try:

        if file:
            upload_result = utils.upload_file(
                file=file,
                type="image",
                public_id=file.filename,
                folder="complaints",
            )
            print(upload_result)

            complaint = models.Complaint(
                student_id=student.id,
                category_id=category_id,
                priority_id=priority_id,
                title=title,
                description=description,
                file_url=upload_result["secure_url"],
                status="pending",
            )
        else:
            complaint = models.Complaint(
                student_id=student.id,
                category_id=category_id,
                priority_id=priority_id,
                title=title,
                description=description,
                status="pending",
            )

        db.add(complaint)
        db.commit()
        db.refresh(complaint)

        complaint = (
            db.query(models.Complaint)
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
                models.Priorities, models.Complaint.priority_id == models.Priorities.id
            )
            .filter(models.Complaint.student_id == student.id)
            .filter(models.Complaint.id == complaint.id)
            .first()
        )

        # * Assign a staff to the complaint
        result = least_work_load_complaint_assigner(db, student, complaint)
        complaint = result["complaint"]
        assignment = result["assignment"]
        print(assignment)

        validated_complaint = schemas.Complaints(
            id=complaint.id,
            student_id=complaint.student_id,
            category=schemas.ComplaintCategory(
                id=complaint.category.id, name=complaint.category.name
            ),
            priority_id=complaint.priority_id,
            title=complaint.title,
            description=complaint.description,
            file_url=complaint.file_url,
            status=complaint.status,
            complaint_assignment=assignment,
            created_at=complaint.created_at,
        )

        return {
            "complaint": validated_complaint,
            # "assignment": schemas.ComplaintAssignment.model_validate(assignment),
        }
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occured {err}",
        )


def least_work_load_complaint_assigner(
    db: Session, student: schemas.Student, complaint: models.Complaint
):
    try:
        staff_role_id = utils.get_staff_role_id_from_complaint(complaint)
        logger.info(f"Staff role id is {staff_role_id}")

        staff = (
            db.query(models.Staff)
            .filter(models.Staff.hall_name == "Nelson Mandela")
            .first()
        )
        print(f"Staff {student.hallname}")

        if complaint.category_id == 1:
            # Hall-specific complaints
            result = (
                db.query(
                    models.Staff,
                    func.count(models.ComplaintAssignment.id).label("complaint_count"),
                )
                .outerjoin(models.ComplaintAssignment)
                .join(models.Student, models.Student.id == complaint.student_id)
                .filter(models.Staff.role_id == staff_role_id)
                .filter(models.Staff.hall_name == student.hallname)
                .group_by(models.Staff.id)
                .order_by(func.count(models.ComplaintAssignment.id).asc())
                .first()
            )

            staff_member = result[0] if result else None

            if not staff_member:
                logger.info("No staff found in the same hall, using fallback.")
                print("No staff found in the same hall, using fallback.")
                fallback_result = (
                    db.query(
                        models.Staff,
                        func.count(models.ComplaintAssignment.id).label(
                            "complaint_count"
                        ),
                    )
                    .outerjoin(models.ComplaintAssignment)
                    .filter(models.Staff.role_id == staff_role_id)
                    .group_by(models.Staff.id)
                    .order_by(func.count(models.ComplaintAssignment.id).asc())
                    .first()
                )
                staff_member = fallback_result[0] if fallback_result else None

        elif complaint.category_id == 2:
            # Department-specific complaints
            result = (
                db.query(
                    models.Staff,
                    func.count(models.ComplaintAssignment.id).label("complaint_count"),
                )
                .outerjoin(models.ComplaintAssignment)
                .join(models.Student, models.Student.id == complaint.student_id)
                .filter(models.Staff.role_id == staff_role_id)
                .filter(models.Staff.department == student.department)
                # .group_by(models.Staff.id)
                .order_by(func.count(models.ComplaintAssignment.id).asc())
                .first()
            )

            staff_member = result[0] if result else None

            if not staff_member:
                logger.info("No staff found in the same department, using fallback.")
                print("No staff found in the same department, using fallback.")
                fallback_result = (
                    db.query(
                        models.Staff,
                        func.count(models.ComplaintAssignment.id).label(
                            "complaint_count"
                        ),
                    )
                    .outerjoin(models.ComplaintAssignment)
                    .filter(models.Staff.role_id == staff_role_id)
                    .group_by(models.Staff.id)
                    .order_by(func.count(models.ComplaintAssignment.id).asc())
                    .first()
                )
                staff_member = fallback_result[0] if fallback_result else None

        else:
            # General case: Assign to any staff with the least workload
            result = (
                db.query(
                    models.Staff,
                    func.count(models.ComplaintAssignment.id).label("complaint_count"),
                )
                .outerjoin(models.ComplaintAssignment)
                .filter(models.Staff.role_id == staff_role_id)
                .group_by(models.Staff.id)
                .order_by(func.count(models.ComplaintAssignment.id).asc())
                .first()
            )
            staff_member = result[0] if result else None

        logger.info(f"Selected staff member: {staff_member}")

        if not staff_member:
            logger.warning("No suitable staff member found for assignment")
            return None

        # Update complaint status
        complaint.status = "assigned"

        # Assign complaint
        assignment = models.ComplaintAssignment(
            complaint_id=complaint.id,
            staff_id=staff_member.id,
            status="assigned",
        )

        db.add(complaint)
        db.add(assignment)
        db.commit()
        db.refresh(complaint)
        db.refresh(assignment)

        try:
            # Implement notification logic here
            pass
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")

        return {"assignment": assignment, "complaint": complaint}

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during complaint assignment: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error assigning complaint: {str(e)}")
        raise


def escalate_complaint(db: Session, department: str, complaint_id: int):
    # Find the admin in the specified department with the least number of complaint assignments
    admin = (
        db.query(models.Staff)
        .filter(models.Staff.role_id == 1)  # Ensure role is admin
        .join(models.ComplaintAssignment)
        .group_by(models.Staff.id)
        .filter(models.Staff.department == department)  # Fix filter for department
        .order_by(func.count(models.ComplaintAssignment.id))
        .first()
    )

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Admin available for this department",
        )

    # Create an assignment for the escalation
    assignment = models.ComplaintAssignment(
        complaint_id=complaint_id,
        staff_id=admin.id,
        assigned_at=datetime.now(),
        status="escalated",
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)  # Ensure the new assignment is refreshed

    return {
        "message": "Complaint has been successfully escalated",
        "assignment": assignment,
    }


def respond_to_complaint(
    complaint_id: int, complaint_response: schemas.ComplaintResponse, db: Session
):
    db.query(models.Complaint).filter(models.Complaint.id == complaint_id).update(
        {"status": complaint_response.status}
    )
    db.query(models.ComplaintAssignment).filter(
        models.ComplaintAssignment.complaint_id == complaint_id
    ).update({"response": complaint_response.response})
    db.commit()

    complaint = (
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
        .join(
            models.Priorities,
            models.Complaint.priority_id == models.Priorities.id,
        )
        .filter(models.Complaint.id == complaint_id)
        .first()
    )

    data = schemas.Complaints(
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
            None
            if not complaint.assignment
            else schemas.ComplaintAssignment(
                id=complaint.assignment.id,
                staff=(
                    schemas.Staff.model_validate(complaint.assignment.staff)
                    if complaint.assignment and complaint.assignment.staff
                    else None
                ),
                complaint_id=complaint.assignment.complaint_id,
                status=complaint.assignment.status,
                response=complaint.assignment.response,
                internal_notes=complaint.assignment.internal_notes,
                assigned_at=complaint.assignment.assigned_at,
                updated_at=complaint.assignment.updated_at,
                resolved_at=complaint.assignment.resolved_at,
            )
        ),
        created_at=complaint.created_at,
    )

    return ResponseModel(
        metadata=schemas.Metadata(status_code=200, success=True),
        data=data,
    )


def close_complaint(complaint_id: str, staff: schemas.Staff, db: Session):
    complaint_assignment = (
        db.query(models.ComplaintAssignment)
        .filter(models.ComplaintAssignment.complaint_id == complaint_id)
        .first()
    )

    if not complaint_assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint with id {complaint_id} doesn't exist",
        )

    # # Ensure only assigned staff can close the complaint
    # if complaint_assignment.staff_id != staff.id or complaint_assignment.staff:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="You are not authorized to close this complaint",
    #     )

    # Fetch the complaint
    complaint = (
        db.query(models.Complaint).filter(models.Complaint.id == complaint_id).first()
    )

    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found",
        )

    # Update complaint status to 'resolved' and set the closed_by field
    complaint.status = "resolved"
    complaint.closed_by = staff.id

    # Update the assignment status and resolved_at timestamp
    complaint_assignment.status = "resolved"
    complaint_assignment.resolved_at = datetime.utcnow()

    db.commit()
    db.refresh(complaint)
    db.refresh(complaint_assignment)

    data = schemas.Complaints(
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
            None
            if not complaint.assignment
            else schemas.ComplaintAssignment(
                id=complaint.assignment.id,
                staff=(
                    schemas.Staff.model_validate(complaint.assignment.staff)
                    if complaint.assignment and complaint.assignment.staff
                    else None
                ),
                complaint_id=complaint.assignment.complaint_id,
                status=complaint.assignment.status,
                response=complaint.assignment.response,
                internal_notes=complaint.assignment.internal_notes,
                assigned_at=complaint.assignment.assigned_at,
                updated_at=complaint.assignment.updated_at,
                resolved_at=complaint.assignment.resolved_at,
            )
        ),
        created_at=complaint.created_at,
    )

    return ResponseModel(
        metadata=schemas.Metadata(status_code=200, success=True),
        data=data,
    )


@router.get("/")
def get_all_complaints(
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
        .join(models.Student, models.Student.id == models.Complaint.student_id)
        .order_by(models.Complaint.created_at.desc())
    )

    if staff.department == "Hall":
        complaints = base_query.filter(models.Student.hallname == staff.hall_name).all()
    else:
        complaints = base_query.filter(
            models.Student.department == staff.department
        ).all()

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


@router.get(
    "/students",
    status_code=status.HTTP_200_OK,
    response_model=ResponseModel[list[schemas.Complaints]],
)
def get_current_student_complaints(
    search: str | None = None,
    student: schemas.Student = Depends(oauth2.get_current_student),
    db: Session = Depends(database.get_db),
):
    if not search:
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
            .join(
                models.Priorities, models.Complaint.priority_id == models.Priorities.id
            )
            .filter(models.Complaint.student_id == student.id)
            .order_by(models.Complaint.created_at.desc())
            .all()
        )
    else:
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
            .join(
                models.Priorities, models.Complaint.priority_id == models.Priorities.id
            )
            .filter(models.Complaint.student_id == student.id)
            .filter(models.Complaint.title.ilike(f"%{search}%"))
            .order_by(models.Complaint.created_at.desc())
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
                None
                if not complaint.assignment
                else schemas.ComplaintAssignment(
                    id=complaint.assignment.id,
                    staff=(
                        schemas.Staff.model_validate(complaint.assignment.staff)
                        if complaint.assignment and complaint.assignment.staff
                        else None
                    ),
                    complaint_id=complaint.assignment.complaint_id,
                    status=complaint.assignment.status,
                    response=complaint.assignment.response,
                    internal_notes=complaint.assignment.internal_notes,
                    assigned_at=complaint.assignment.assigned_at,
                    updated_at=complaint.assignment.updated_at,
                    resolved_at=complaint.assignment.resolved_at,
                )
            ),
            created_at=complaint.created_at,
        )
        for complaint in complaints
    ]

    return ResponseModel(
        metadata=schemas.Metadata(status_code=200, success=True),
        data=data,
    )


@router.get(
    "/students/{id}",
    status_code=status.HTTP_200_OK,
    response_model=ResponseModel[schemas.Complaints],
)
def get_students_complaint_by_id(
    id: int,
    student: schemas.Student = Depends(oauth2.get_current_student),
    db: Session = Depends(database.get_db),
):
    complaint = (
        db.query(models.Complaint)
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
        .join(models.Priorities, models.Complaint.priority_id == models.Priorities.id)
        .filter(models.Complaint.student_id == student.id)
        .filter(models.Complaint.id == id)
        .first()
    )

    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint with id {id} not found",
        )

    print(complaint)

    validated_complaint = schemas.Complaints(
        id=complaint.id,
        student_id=complaint.student_id,
        category=schemas.ComplaintCategory(
            id=complaint.category.id, name=complaint.category.name
        ),
        priority_id=complaint.priority_id,
        title=complaint.title,
        description=complaint.description,
        file_url=complaint.file_url,
        status=complaint.status,
        created_at=complaint.created_at,
    )

    return ResponseModel(
        metadata=schemas.Metadata(status_code=200, success=True),
        data={},
    )


# * When the complaint has been resolved the status should be changed to "resolved"
@router.post("/", status_code=status.HTTP_201_CREATED)
def submit_complaint(
    title: Annotated[str, Form(...)],
    description: Annotated[str, Form(...)],
    category_id: Annotated[int, Form(...)],
    priority_id: Annotated[int, Form(...)],
    file: UploadFile | None = None,
    student: schemas.Student = Depends(oauth2.get_current_student),
    db: Session = Depends(database.get_db),
):
    category = utils.categorize_complaint(title, description, category_id)
    print(category)

    data = create_complaint(
        title, description, category.get("category_id"), priority_id, student, db, file
    )

    return ResponseModel(
        metadata=schemas.Metadata(status_code=201, success=True),
        data=data,
    )


@router.post("/course-upload", status_code=status.HTTP_201_CREATED)
async def submit_course_upload(
    upload_details: schemas.CreateCourseUpload,
    student: schemas.Student = Depends(oauth2.get_current_student),
    db: Session = Depends(database.get_db),
):
    try:
        # Start transaction
        db.begin_nested()

        # Check if course already exists
        existing_course = (
            db.query(models.Course)
            .filter(models.Course.code == upload_details.course_code)
            .first()
        )

        if not existing_course:
            course = models.Course(
                title=upload_details.course_title, code=upload_details.course_code
            )
            db.add(course)
            db.flush()
        else:
            course = existing_course

        upload = models.CourseUploadIssue(
            level=upload_details.level,
            student_id=student.id,
            course_id=course.id,
            reason=upload_details.reason,
            total_units=upload_details.total_units_for_the_semester,
        )

        db.add(upload)
        db.flush()

        # Create associated complaint with specific course upload details
        complaint_title = f"Course Upload Issue: {upload_details.course_code}"
        complaint_description = (
            f"Course: {upload_details.course_title}\n"
            f"Level: {upload_details.level}\n"
            f"Reason: {upload_details.reason}"
        )

        complaint = create_complaint(
            title=complaint_title,
            description=complaint_description,
            category_id=2,  # Course category
            priority_id=2,  # Medium priority
            student=student,
            db=db,
        )

        db.commit()
        data = schemas.CourseUpload.model_validate(upload, from_attributes=True)

        return ResponseModel(
            metadata=schemas.Metadata(
                status_code=status.HTTP_201_CREATED, success=True
            ),
            data={"course_upload": data, "complaint": complaint["complaint"]},
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating course upload: {str(e)}",
        )


@router.post("/escalate")
def staff_escalate_complaint(
    complaint_id: int,
    staff: schemas.Staff = Depends(oauth2.get_current_staff),
    db: Session = Depends(database.get_db),
):
    complaint_assignment = (
        db.query(models.ComplaintAssignment)
        .filter(models.ComplaintAssignment.complaint_id == complaint_id)
        .first()
    )
    escalate_complaint(db, staff.role.department, complaint_id)

    return ResponseModel(
        metadata=schemas.Metadata(status_code=200, success=True),
        data={"message": "complaint escalated"},
    )


@router.patch("/staff-response/{complaint_id}")
def staff_complaint_response(
    complaint_id: str,
    complaint_response: schemas.ComplaintResponse,
    staff: schemas.Staff = Depends(oauth2.get_current_staff),
    db: Session = Depends(database.get_db),
):
    try:
        if complaint_response.status == "resolved":
            db.query(models.ComplaintAssignment).filter(
                models.ComplaintAssignment.complaint_id == complaint_id
            ).update({"response": complaint_response.response})
            close_complaint(complaint_id, staff, db)
        else:
            respond_to_complaint(complaint_id, complaint_response, db)
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Internal server error {err}")


@router.patch("/student-follow-up/{id}")
def complaint_follow_up(id: str, response: str, db: Session = Depends(database.get_db)):
    print(id)
    try:
        complaint = db.query(models.Complaint).filter(models.Complaint.id == id).all()
        print(complaint)
        db.query(models.ComplaintAssignment).filter(
            models.ComplaintAssignment.complaint_id == id
        ).update({"internal_notes": response})
        db.commit()

        return ResponseModel(
            metadata=schemas.Metadata(status_code=200, success=True),
            data={"data": "Response sent"},
        )

    except Exception as err:
        raise HTTPException(status_code=status.HTTP_102_PROCESSING, detail=f"{err}")


@router.get("/get-department-staff")
def get_department_staff(
    staff: schemas.Staff = Depends(oauth2.get_current_staff),
    db: Session = Depends(database.get_db),
):
    if staff.department == "Hall":
        staffs = (
            db.query(models.Staff)
            .filter(models.Staff.hall_name == staff.hall_name)
            .filter(models.Staff.id != staff.id)
            .all()
        )
    else:
        staffs = (
            db.query(models.Staff)
            .filter(models.Staff.department == staff.department)
            .filter(models.Staff.id != staff.id)
            .all()
        )

    data = [
        schemas.Staff(
            id=staff.id,
            email=staff.email,
            fullname=staff.fullname,
            department=staff.department,
            hall_name=staff.hall_name,
            profile_image=staff.profile_image,
            role=schemas.Role.model_validate(staff.role),
            created_at=staff.created_at,
        )
        for staff in staffs
    ]
    return ResponseModel(
        metadata=schemas.Metadata(status_code=status.HTTP_200_OK, success=True),
        data=data,
    )


@router.patch("/reassign-complaint/{complaint_id}")
def reassign_complaint(
    complaint_id: str,
    staff_id: int = Query(...),
    staff: schemas.Staff = Depends(oauth2.get_current_staff),
    db: Session = Depends(database.get_db),
):
    try:
        complaint = (
            db.query(models.Complaint)
            .filter(models.Complaint.id == complaint_id)
            .first()
        )

        if not complaint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Complaint with id {complaint_id} not found",
            )

        db.query(models.ComplaintAssignment).filter(
            models.ComplaintAssignment.complaint_id == complaint_id
        ).update({"staff_id": staff_id})

        db.commit()

        complaint = (
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
            .join(
                models.Priorities, models.Complaint.priority_id == models.Priorities.id
            )
            .filter(models.Complaint.id == complaint_id)
            .first()
        )

        data = schemas.Complaints(
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
                None
                if not complaint.assignment
                else schemas.ComplaintAssignment(
                    id=complaint.assignment.id,
                    staff=(
                        schemas.Staff.model_validate(complaint.assignment.staff)
                        if complaint.assignment and complaint.assignment.staff
                        else None
                    ),
                    complaint_id=complaint.assignment.complaint_id,
                    status=complaint.assignment.status,
                    response=complaint.assignment.response,
                    internal_notes=complaint.assignment.internal_notes,
                    assigned_at=complaint.assignment.assigned_at,
                    updated_at=complaint.assignment.updated_at,
                    resolved_at=complaint.assignment.resolved_at,
                )
            ),
            created_at=complaint.created_at,
        )

        return ResponseModel(
            metadata=schemas.Metadata(status_code=200, success=True), data=data
        )
    except Exception as err:
        print(f"Reassign Complaint Error: {err}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {err}")
