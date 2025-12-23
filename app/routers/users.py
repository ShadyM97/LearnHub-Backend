from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
from .. import schemas
from ..auth import get_current_user
from ..dependencies import get_supabase, get_supabase_admin
from supabase import Client

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}},
)

@router.get("/me", response_model=schemas.User)
async def read_users_me(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Client = Depends(get_supabase_admin)
):
    user_id = str(current_user.get("sub"))
    # print(f"DEBUG: User ID: {user_id}")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user token")
    
    try:
        response = db.from_("users").select("*").eq("id", user_id).execute()
        if not response.data:
            # print(f"DEBUG: User profile not found in DB for {user_id}")
            raise HTTPException(status_code=404, detail="User profile not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        # print(f"DEBUG: Error in read_users_me: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

@router.put("/me", response_model=schemas.User)
async def update_user_me(
    user_update: schemas.UserUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Client = Depends(get_supabase_admin)
):
    user_id = current_user.get("sub")
    # Filter out None values
    update_data = {k: v for k, v in user_update.dict().items() if v is not None}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No data to update")

    response = db.from_("users").update(update_data).eq("id", user_id).execute()
    
    if not response.data:
         raise HTTPException(status_code=404, detail="User not found")
         
    return response.data[0]
