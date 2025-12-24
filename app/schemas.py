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
    parent_id: Optional[str] = None

class CommentCreate(BaseModel):
    content: str
    parent_id: Optional[str] = None

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

class PostUpdate(BaseModel):
    content: Optional[str] = None
    attachments: Optional[List[Any]] = None
    attachment_count: Optional[int] = None

class LinkPreview(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    url: str

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

# Space Schemas
class SpaceBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None

class SpaceCreate(SpaceBase):
    pass

class SpaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None

class Space(SpaceBase):
    id: str
    created_at: datetime
    created_by: str
    member_count: int = 0
    is_member: bool = False

    class Config:
        from_attributes = True

class SpaceThreadBase(BaseModel):
    title: str
    space_id: str

class SpaceThreadCreate(BaseModel):
    title: str

class SpaceThread(SpaceThreadBase):
    id: str
    created_by: str
    created_at: datetime
    users: Optional[User] = None
    message_count: int = 0

    class Config:
        from_attributes = True

class SpaceMessageBase(BaseModel):
    content: str
    thread_id: str
    attachments: Optional[List[Any]] = None
    attachment_count: int = 0

class SpaceMessageCreate(BaseModel):
    content: str
    attachments: Optional[List[Any]] = None
    attachment_count: int = 0

class SpaceMessage(SpaceMessageBase):
    id: str
    user_id: str
    created_at: datetime
    users: Optional[User] = None

    class Config:
        from_attributes = True
