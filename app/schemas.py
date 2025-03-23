from datetime import datetime
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, EmailStr

T = TypeVar("T")


class TokenData(BaseModel):
    email: str | None = None


class Student(BaseModel):
    id: int
    matric_no: str
    fullname: str
    email: str
    department: str
    school: str
    hallname: Optional[str] = None
    profile_image: Optional[str] = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class CreateStudent(BaseModel):
    fullname: str
    matric_no: str
    school: str
    email: EmailStr
    password: str
    department: str
    hallname: str


class Role(BaseModel):
    id: int
    name: str

    model_config = {
        "from_attributes": True,
    }


class Staff(BaseModel):
    id: int
    email: str
    fullname: str
    department: str
    hall_name: str | None = None
    profile_image: str | None = None
    role: Role | None = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class CreateStaff(BaseModel):
    email: EmailStr
    fullname: str
    department: str
    hall: str | None = None
    role: int
    password: str


class Metadata(BaseModel):
    timestamp: datetime = datetime.now()
    status_code: int
    success: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    student: Student


class StaffLoginResponse(BaseModel):
    access_token: str
    token_type: str
    staff: Staff


class ResponseModel(BaseModel, Generic[T]):
    metadata: Metadata
    data: Optional[T] = None


class GoogleToken(BaseModel):
    token: str


class ComplaintCategory(BaseModel):
    id: int
    name: str


class ComplaintCreate(BaseModel):
    title: str
    description: str
    category_id: int
    priority_id: int
    file_url: str | None = None


class ComplaintAssignment(BaseModel):
    id: int
    staff: Staff | None = None
    complaint_id: str
    status: str
    response: str | None = None
    internal_notes: str | None = None
    assigned_at: datetime | None = None
    updated_at: datetime | None = None
    resolved_at: datetime | None = None

    model_config = {
        "from_attributes": True,
    }


class Complaints(BaseModel):
    id: str
    student_id: int
    category: ComplaintCategory
    priority_id: int | None = None
    title: str
    description: str
    file_url: str | None = None
    status: str
    complaint_assignment: ComplaintAssignment | None = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class CreateCourseUpload(BaseModel):
    level: int
    academic_year: int
    reason: str
    course_title: str
    course_code: str
    total_units_for_the_semester: int


class ComplaintUpdate(BaseModel):
    id: str
    status: str
    response: str | None = None


class Course(BaseModel):
    id: int
    title: str
    code: str


class CourseUpload(BaseModel):
    id: int
    level: int
    student: Student
    course: Course
    reason: str
    total_units: int

    model_config = {
        "from_attributes": True,
    }


class ComplaintResponse(BaseModel):
    response: str
    status: str
