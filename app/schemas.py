from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

# User Schemas
class UserBase(BaseModel):
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Optional[str] = None
    mobile: Optional[str] = None
    country: Optional[str] = None

class User(UserBase):
    id: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    mobile: Optional[str] = None
    country: Optional[str] = None
    avatar_url: Optional[str] = None

# Course Schemas
class Teacher(BaseModel):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True

class EnrollmentData(BaseModel):
    id: str
    enrolled_at: datetime
    progress_percentage: int = 0
    completed_at: Optional[datetime] = None

class CourseBase(BaseModel):
    title: str
    description: str
    price: float
    duration_hours: float
    category: str
    level: str
    thumbnail_url: Optional[str] = None
    is_published: bool = False

class CourseCreate(CourseBase):
    pass

class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    duration_hours: Optional[float] = None
    category: Optional[str] = None
    level: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_published: Optional[bool] = None

class Course(CourseBase):
    id: str
    teacher_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    teacher: Optional[Teacher] = None
    rating: float = 0.0
    reviewCount: int = 0
    enrollment: Optional[EnrollmentData] = None

    class Config:
        from_attributes = True

class Enrollment(EnrollmentData):
    student_id: str
    course_id: str
    course: Optional[Course] = None

    class Config:
        from_attributes = True

# Post and Comment Schemas
class CommentBase(BaseModel):
    content: str
    post_id: str

class CommentCreate(BaseModel):
    content: str

class Comment(CommentBase):
    id: str
    user_id: str
    created_at: datetime
    users: Optional[User] = None
    like_count: int = 0
    liked_by_me: bool = False

    class Config:
        from_attributes = True

class PostBase(BaseModel):
    content: Optional[str] = None
    attachments: Optional[List[Any]] = None
    attachment_count: int = 0

class PostCreate(PostBase):
    pass

class Post(PostBase):
    id: str
    user_id: str
    created_at: datetime
    users: Optional[User] = None
    like_count: int = 0
    liked_by_me: bool = False
    comments: List[Comment] = []

    class Config:
        from_attributes = True

