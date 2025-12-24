from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List
from .. import schemas
from ..auth import get_current_user
from ..dependencies import get_supabase_admin
from supabase import Client

router = APIRouter(
    prefix="/spaces",
    tags=["spaces"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=List[schemas.Space])
async def get_spaces(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Client = Depends(get_supabase_admin)
):
    try:
        user_id = current_user.get("sub")
        # Fetch all spaces
        res = db.from_("spaces").select("*").execute()
        spaces = res.data or []

        # Fetch membership info for the current user
        member_res = db.from_("space_members").select("space_id").eq("user_id", user_id).execute()
        joined_space_ids = [m["space_id"] for m in member_res.data] if member_res.data else []

        # Enrich spaces with member counts and membership status
        # In a real app, you might use a more efficient query or a view
        for space in spaces:
            count_res = db.from_("space_members").select("*", count="exact").eq("space_id", space["id"]).execute()
            space["member_count"] = count_res.count or 0
            space["is_member"] = space["id"] in joined_space_ids

        return spaces
    except Exception as e:
        print(f"DEBUG Error fetching spaces: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=schemas.Space)
async def create_space(
    space: schemas.SpaceCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Client = Depends(get_supabase_admin)
):
    try:
        user_id = current_user.get("sub")
        new_space = {
            **space.model_dump(),
            "created_by": user_id
        }
        res = db.from_("spaces").insert(new_space).execute()
        if not res.data:
            raise HTTPException(status_code=400, detail="Failed to create space")
        
        created_space = res.data[0]
        
        # Automatically join the space as admin
        db.from_("space_members").insert({
            "space_id": created_space["id"],
            "user_id": user_id,
            "role": "admin"
        }).execute()
        
        created_space["member_count"] = 1
        created_space["is_member"] = True
        
        return created_space
    except Exception as e:
        print(f"DEBUG Error creating space: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{space_id}/join")
async def join_space(
    space_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Client = Depends(get_supabase_admin)
):
    try:
        user_id = current_user.get("sub")
        # Check if already a member
        res = db.from_("space_members").select("*").eq("space_id", space_id).eq("user_id", user_id).execute()
        if res.data:
            return {"message": "Already a member"}
        
        db.from_("space_members").insert({
            "space_id": space_id,
            "user_id": user_id,
            "role": "member"
        }).execute()
        
        return {"message": "Joined successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{space_id}/threads", response_model=List[schemas.SpaceThread])
async def get_space_threads(
    space_id: str,
    db: Client = Depends(get_supabase_admin)
):
    try:
        res = db.from_("space_threads").select("*").eq("space_id", space_id).order("created_at", desc=True).execute()
        threads = res.data or []
        
        if not threads:
            return []
            
        # Enrich with user info and message count
        author_ids = list(set([t["created_by"] for t in threads]))
        a_res = db.from_("users").select("*").in_("id", author_ids).execute()
        authors_map = {a["id"]: a for a in a_res.data} if a_res.data else {}
        
        for thread in threads:
            thread["users"] = authors_map.get(thread["created_by"])
            m_res = db.from_("space_messages").select("*", count="exact").eq("thread_id", thread["id"]).execute()
            thread["message_count"] = m_res.count or 0
            
        return threads
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{space_id}/threads", response_model=schemas.SpaceThread)
async def create_thread(
    space_id: str,
    thread: schemas.SpaceThreadCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Client = Depends(get_supabase_admin)
):
    try:
        user_id = current_user.get("sub")
        new_thread = {
            "title": thread.title,
            "space_id": space_id,
            "created_by": user_id
        }
        res = db.from_("space_threads").insert(new_thread).execute()
        if not res.data:
            raise HTTPException(status_code=400, detail="Failed to create thread")
            
        created_thread = res.data[0]
        # Enrich for return
        author_res = db.from_("users").select("*").eq("id", user_id).single().execute()
        created_thread["users"] = author_res.data
        created_thread["message_count"] = 0
        
        return created_thread
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/threads/{thread_id}/messages", response_model=List[schemas.SpaceMessage])
async def get_thread_messages(
    thread_id: str,
    db: Client = Depends(get_supabase_admin)
):
    try:
        res = db.from_("space_messages").select("*").eq("thread_id", thread_id).order("created_at", desc=False).execute()
        messages = res.data or []
        
        if not messages:
            return []
            
        # Enrich with user info
        user_ids = list(set([m["user_id"] for m in messages]))
        u_res = db.from_("users").select("*").in_("id", user_ids).execute()
        users_map = {u["id"]: u for u in u_res.data} if u_res.data else {}
        
        for message in messages:
            message["users"] = users_map.get(message["user_id"])
            
        return messages
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/threads/{thread_id}/messages", response_model=schemas.SpaceMessage)
async def create_message(
    thread_id: str,
    message: schemas.SpaceMessageCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Client = Depends(get_supabase_admin)
):
    try:
        user_id = current_user.get("sub")
        new_message = {
            "content": message.content,
            "thread_id": thread_id,
            "user_id": user_id,
            "attachments": message.attachments,
            "attachment_count": message.attachment_count
        }
        res = db.from_("space_messages").insert(new_message).execute()
        if not res.data:
            raise HTTPException(status_code=400, detail="Failed to post message")
            
        created_message = res.data[0]
        # Enrich for return
        author_res = db.from_("users").select("*").eq("id", user_id).single().execute()
        created_message["users"] = author_res.data
        
        return created_message
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
