from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from .. import schemas
from ..auth import get_current_user, require_role
from ..dependencies import get_supabase, get_supabase_admin
from supabase import Client

router = APIRouter(
    prefix="/courses",
    tags=["courses"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=List[schemas.Course])
async def list_courses(
    search: Optional[str] = None,
    category: Optional[str] = "All",
    level: Optional[str] = "All",
    min_price: float = 0,
    max_price: float = 10000,
    min_rating: int = 0,
    db: Client = Depends(get_supabase)
):
    query = db.from_("courses").select("*").eq("is_published", True)

    if search:
        query = query.ilike("title", f"%{search}%")
    
    if category and category != "All":
        query = query.eq("category", category)
    
    if level and level != "All":
        query = query.eq("level", level)
        
    query = query.gte("price", min_price).lte("price", max_price)
    
    # Execute course query first
    response = query.order("created_at", desc=True).execute()
    courses = response.data
    
    if not courses:
        return []

    # Populate teacher info and ratings manually purely in python to avoid complex joins in Supabase-py if not configured
    # Or we can do what the frontend did: fetch teachers and ratings separately
    
    teacher_ids = list(set([c["teacher_id"] for c in courses]))
    course_ids = [c["id"] for c in courses]
    
    teachers_map = {}
    if teacher_ids:
        t_res = db.from_("users").select("id, first_name, last_name, avatar_url").in_("id", teacher_ids).execute()
        if t_res.data:
            teachers_map = {t["id"]: t for t in t_res.data}
            
    ratings_map = {}
    if course_ids:
         r_res = db.from_("course_reviews").select("course_id, rating").in_("course_id", course_ids).execute()
         if r_res.data:
             for r in r_res.data:
                 cid = r["course_id"]
                 if cid not in ratings_map:
                     ratings_map[cid] = {"total": 0, "count": 0}
                 ratings_map[cid]["total"] += r["rating"]
                 ratings_map[cid]["count"] += 1

    enriched_courses = []
    for c in courses:
        teacher = teachers_map.get(c["teacher_id"])
        
        rating_info = ratings_map.get(c["id"], {"total": 0, "count": 0})
        avg_rating = rating_info["total"] / rating_info["count"] if rating_info["count"] > 0 else 0
        
        # Filter by rating if requested
        if avg_rating < min_rating:
            continue
            
        c["teacher"] = teacher
        c["rating"] = avg_rating
        c["reviewCount"] = rating_info["count"]
        enriched_courses.append(c)
        
    return enriched_courses

@router.get("/my/teacher", response_model=List[schemas.Course])
async def list_teacher_courses(
    current_user: Dict[str, Any] = Depends(require_role("teacher")),
    db: Client = Depends(get_supabase),
    db_admin: Client = Depends(get_supabase_admin)
):
    user_id = current_user.get("sub")
    
    try:
        response = db.from_("courses").select("*").eq("teacher_id", user_id).order("created_at", desc=True).execute()
        courses = response.data or []
        
        # Teachers often want to see student counts and basic stats. 
        # For now ensuring schema compliance (we need teacher object even if it's me)
        
        # Optimization: Just use the current user info for teacher
        # Use admin client to bypass RLS
        try:
            user_res = db_admin.from_("users").select("id, first_name, last_name, avatar_url").eq("id", user_id).single().execute()
            teacher_info = user_res.data
        except Exception as e:
            print(f"Warning: Could not fetch teacher info: {e}")
            # Provide minimal teacher info if query fails
            teacher_info = {
                "id": user_id,
                "first_name": None,
                "last_name": None,
                "avatar_url": None
            }
        
        for c in courses:
            c["teacher"] = teacher_info
            # TODO: Add enrollment counts if needed in schema
            
        return courses
    except Exception as e:
        print(f"Error in list_teacher_courses: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching teacher courses: {str(e)}")

@router.get("/my/student", response_model=List[schemas.Course])
async def list_student_courses(
    current_user: Dict[str, Any] = Depends(require_role("student")),
    db: Client = Depends(get_supabase)
):
    user_id = current_user.get("sub")
    
    # Get enrollments
    enrollments_res = db.from_("enrollments").select("*, courses(*)").eq("student_id", user_id).execute()
    
    if not enrollments_res.data:
        return []
        
    # Process to match Course schema
    # The current schema expects a list of Courses, but we might want to return Enrollments which contain course info
    # The current frontend task implies returning courses.
    # However, for "My Courses" student view, we usually want progress data.
    
    # Let's see schemas.py: Enrollment has 'course'.
    # If we change return type to List[schemas.Course], we lose progress info.
    # But the frontend `my-courses` page needs progress.
    # So we probably should return List[schemas.Enrollment] for this endpoint?
    # Or List[Course] with extra fields?
    # Looking at `schemas.py`: Course doesn't have progress.
    # Changing return type to List[Any] or List[schemas.Course] with extra fields attached (not validated)
    # Ideally should return `List[schemas.Course]` where we've added progress? No, schemas are strict.
    
    # Let's fetch the teachers for these courses
    courses = []
    
    for item in enrollments_res.data:
        course = item.get("courses")
        if not course: continue
        
        # Helper to get teacher
        t_res = db.from_("users").select("id, first_name, last_name, avatar_url").eq("id", course["teacher_id"]).single().execute()
        course["teacher"] = t_res.data
        
        # Attach enrollment data
        course["enrollment"] = {
            "id": item["id"],
            "enrolled_at": item["enrolled_at"],
            "progress_percentage": item["progress_percentage"],
            "completed_at": item["completed_at"]
        }
        
        courses.append(course)
        
    return courses

@router.get("/{course_id}", response_model=schemas.Course)
async def get_course(
    course_id: str,
    db: Client = Depends(get_supabase)
):
    response = db.from_("courses").select("*").eq("id", course_id).single().execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Course not found")
    
    course = response.data
    
    # Get teacher
    t_res = db.from_("users").select("id, first_name, last_name, avatar_url").eq("id", course["teacher_id"]).single().execute()
    course["teacher"] = t_res.data
    
    # Get stats
    r_res = db.from_("course_reviews").select("rating").eq("course_id", course_id).execute()
    ratings = [r["rating"] for r in r_res.data]
    course["rating"] = sum(ratings) / len(ratings) if ratings else 0
    course["reviewCount"] = len(ratings)
    
    return course

@router.post("/", response_model=schemas.Course)
async def create_course(
    course: schemas.CourseCreate,
    current_user: Dict[str, Any] = Depends(require_role("teacher")),
    db: Client = Depends(get_supabase)
):
    user_id = current_user.get("sub")
    
    new_course = course.dict()
    new_course["teacher_id"] = user_id
    
    response = db.from_("courses").insert(new_course).execute()
    
    if not response.data:
        raise HTTPException(status_code=400, detail="Could not create course")
        
    created_course = response.data[0]
    
    # Attach teacher info (current user)
    user_res = db.from_("users").select("id, first_name, last_name, avatar_url").eq("id", user_id).single().execute()
    created_course["teacher"] = user_res.data
    
    return created_course

@router.put("/{course_id}", response_model=schemas.Course)
async def update_course(
    course_id: str,
    course_update: schemas.CourseUpdate,
    current_user: Dict[str, Any] = Depends(require_role("teacher")),
    db: Client = Depends(get_supabase)
):
    user_id = current_user.get("sub")
    
    # Verify ownership
    existing = db.from_("courses").select("teacher_id").eq("id", course_id).single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Course not found")
        
    if existing.data["teacher_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this course")

    update_data = {k: v for k, v in course_update.dict().items() if v is not None}
    
    if not update_data:
         raise HTTPException(status_code=400, detail="No data to update")

    response = db.from_("courses").update(update_data).eq("id", course_id).execute()
    
    updated_course = response.data[0]
    
    # Attach teacher info
    user_res = db.from_("users").select("id, first_name, last_name, avatar_url").eq("id", user_id).single().execute()
    updated_course["teacher"] = user_res.data
    
    return updated_course
