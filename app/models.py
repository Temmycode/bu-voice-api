import uuid
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.expression import text
from sqlalchemy.sql.sqltypes import TIMESTAMP
from .database import Base


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
    )
    student_id = Column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    category_id = Column(ForeignKey("complaint_categories.id"), nullable=False)
    priority_id = Column(ForeignKey("priorities.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    file_url = Column(String)
    status = Column(String)  # pending, in-progress, resolved, rejected
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    closed_by = Column(Integer, ForeignKey("staffs.id"))
    is_rated = Column(Boolean, server_default=text("false"))

    category = relationship("ComplaintCategory")
    priority = relationship("Priorities")
    assignment = relationship(
        "ComplaintAssignment", uselist=False, back_populates="complaints"
    )


class ComplaintCategory(Base):
    __tablename__ = "complaint_categories"

    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String, nullable=False)


class ComplaintAssignment(Base):
    __tablename__ = "complaint_assignment"

    id = Column(Integer, primary_key=True, nullable=False)
    complaint_id = Column(
        String,
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
    )
    staff_id = Column(Integer, ForeignKey("staffs.id"), nullable=False)
    status = Column(String)  # unassigned, assigned, resolved, escalated
    response = Column(String)
    internal_notes = Column(String)
    assigned_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    resolved_at = Column(TIMESTAMP(timezone=True))

    complaints = relationship("Complaint", back_populates="assignment")
    staff = relationship("Staff")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, nullable=False)
    matric_no = Column(String, nullable=False, unique=True)
    email = Column(String, unique=True)
    password = Column(String)
    fullname = Column(String)
    department = Column(String, nullable=False)
    school = Column(String, nullable=False)
    hallname = Column(String)
    profile_image = Column(String)
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class Staff(Base):
    __tablename__ = "staffs"
    id = Column(Integer, primary_key=True, nullable=False)
    email = Column(String, unique=True)
    fullname = Column(String, nullable=False)
    department = Column(String, nullable=False)
    hall_name = Column(String)  # only for hall staff
    password = Column(String)
    profile_image = Column(String)
    role_id = Column(
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
    )
    reports_to = Column(
        Integer, ForeignKey("staffs.id")
    )  # ID of the HOD, BURSAR or HALL ADMIN
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    role = relationship("Role")


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String, nullable=False)


class Priorities(Base):
    __tablename__ = "priorities"

    id = Column(Integer, primary_key=True, nullable=False)
    level = Column(String, nullable=False)
    description = Column(String)


class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True, nullable=False)
    complaint_id = Column(
        String, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False
    )
    rating = Column(Integer)
    feedback = Column(String)
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    complaints = relationship("Complaint")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, nullable=False)
    user_id = Column(Integer, nullable=False)
    complaint_id = Column(
        String, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False
    )
    message = Column(String, nullable=False)
    is_read = Column(Boolean, server_default=text("false"))
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, nullable=False)
    title = Column(String, nullable=False)
    code = Column(String, unique=True, nullable=False)


class CourseUploadIssue(Base):
    __tablename__ = "course_upload_issues"

    id = Column(Integer, primary_key=True, nullable=False)
    level = Column(Integer, nullable=False)  # Ensure level is required
    student_id = Column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    course_id = Column(
        Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    reason = Column(String, nullable=False)
    total_units = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # Relationships
    student = relationship("Student")
    course = relationship("Course")


class ComplaintType(Base):
    __tablename__ = "complaint_types"

    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("complaint_categories.id"))
    name = Column(String, nullable=False)
    code = Column(String, nullable=False, unique=True)

    # Example data:
    # id: 1, category_id: 2, name: "Course Upload", code: "COURSE_UPLOAD"
    # id: 2, category_id: 2, name: "Course Registration", code: "COURSE_REG"
