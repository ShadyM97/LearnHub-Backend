from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from typing import Dict, Any, List
import json
from .. import schemas
from ..auth import get_current_user, get_current_user_optional
from ..dependencies import get_supabase_admin
from supabase import Client
import httpx
import re

router = APIRouter(
    prefix="/posts",
    tags=["posts"],
    responses={404: {"description": "Not found"}},
)

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Connection might be closed
                continue

manager = ConnectionManager()

@router.get("/", response_model=List[schemas.Post])
async def get_posts(
    current_user: Dict[str, Any] = Depends(get_current_user_optional),
    db: Client = Depends(get_supabase_admin)
):
    try:
        # Fetch raw posts
        res = db.from_("posts").select("*").order("created_at", desc=True).execute()
        posts = res.data or []
        
        if not posts:
            return []

        user_id = current_user.get("sub") if current_user else None
        post_ids = [p["id"] for p in posts]
        author_ids = list(set([p["user_id"] for p in posts]))

        # Fetch authors
        authors_map = {}
        if author_ids:
            a_res = db.from_("users").select("*").in_("id", author_ids).execute()
            authors_map = {a["id"]: a for a in a_res.data} if a_res.data else {}

        # Fetch comments
        comments_map = {}
        all_comment_ids = []
        if post_ids:
            c_res = db.from_("comments").select("*").in_("post_id", post_ids).execute()
            if c_res.data:
                # Fetch comment authors too
                c_author_ids = list(set([c["user_id"] for c in c_res.data]))
                ca_res = db.from_("users").select("*").in_("id", c_author_ids).execute()
                ca_map = {a["id"]: a for a in ca_res.data} if ca_res.data else {}
                
                for c in c_res.data:
                    pid = c["post_id"]
                    if pid not in comments_map:
                        comments_map[pid] = []
                    c["users"] = ca_map.get(c["user_id"])
                    comments_map[pid].append(c)
                    all_comment_ids.append(c["id"])

        # Fetch comment likes
        comment_likes_map = {}
        if all_comment_ids:
            try:
                cl_res = db.from_("comment_likes").select("*").in_("comment_id", all_comment_ids).execute()
                if cl_res.data:
                    for cl in cl_res.data:
                        cid = cl["comment_id"]
                        if cid not in comment_likes_map:
                            comment_likes_map[cid] = []
                        comment_likes_map[cid].append(cl)
            except Exception as e:
                print(f"Warning: comment_likes table might be missing: {e}")

        # Fetch likes for posts
        likes_map = {}
        if post_ids:
            l_res = db.from_("likes").select("*").in_("post_id", post_ids).execute()
            if l_res.data:
                for l in l_res.data:
                    pid = l["post_id"]
                    if pid not in likes_map:
                        likes_map[pid] = []
                    likes_map[pid].append(l)

        processed_posts = []
        for p in posts:
            pid = p["id"]
            p["users"] = authors_map.get(p["user_id"])
            
            # Enrich comments with like info
            p_comments = comments_map.get(pid, [])
            for c in p_comments:
                cid = c["id"]
                c_likes = comment_likes_map.get(cid, [])
                c["like_count"] = len(c_likes)
                c["liked_by_me"] = any(cl["user_id"] == user_id for cl in c_likes) if user_id else False
            
            p["comments"] = sorted(p_comments, key=lambda x: x["created_at"])
            
            likes = likes_map.get(pid, [])
            p["like_count"] = len(likes)
            p["liked_by_me"] = any(l["user_id"] == user_id for l in likes) if user_id else False
            
            processed_posts.append(p)
            
        return processed_posts
    except Exception as e:
        print(f"DEBUG Error fetching posts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=schemas.Post)
async def create_post(
    post: schemas.PostCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Client = Depends(get_supabase_admin)
):
    try:
        user_id = current_user.get("sub")
        new_post = {
            "content": post.content,
            "user_id": user_id,
            "attachments": post.attachments,
            "attachment_count": post.attachment_count
        }
        
        response = db.from_("posts").insert(new_post).execute()
        if not response.data:
            raise HTTPException(status_code=400, detail="Failed to create post")
        
        created_post = response.data[0]
        
        # Manually enrich the created post for broadcasting/returning
        author_res = db.from_("users").select("*").eq("id", user_id).single().execute()
        created_post["users"] = author_res.data
        created_post["comments"] = []
        created_post["like_count"] = 0
        created_post["liked_by_me"] = False

        # Broadcast the new post
        await manager.broadcast({"type": "NEW_POST", "post": created_post})
        
        return created_post
    except Exception as e:
        print(f"DEBUG Error creating post: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{post_id}/like")
async def toggle_like(
    post_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Client = Depends(get_supabase_admin)
):
    try:
        user_id = current_user.get("sub")
        
        # Check if already liked
        res = db.from_("likes").select("*").eq("post_id", post_id).eq("user_id", user_id).execute()
        
        if res.data:
            # Unlike
            db.from_("likes").delete().eq("post_id", post_id).eq("user_id", user_id).execute()
            liked = False
        else:
            # Like
            db.from_("likes").insert({"post_id": post_id, "user_id": user_id}).execute()
            liked = True
            
        # Get updated count
        count_res = db.from_("likes").select("*", count="exact").eq("post_id", post_id).execute()
        
        return {"liked": liked, "like_count": count_res.count or 0}
    except Exception as e:
        print(f"DEBUG Error toggling like: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{post_id}/comments", response_model=schemas.Comment)
async def add_comment(
    post_id: str,
    comment: schemas.CommentCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Client = Depends(get_supabase_admin)
):
    try:
        user_id = current_user.get("sub")
        
        new_comment = {
            "content": comment.content,
            "post_id": post_id,
            "user_id": user_id,
            "parent_id": comment.parent_id
        }
        
        res = db.from_("comments").insert(new_comment).execute()
        if not res.data:
            raise HTTPException(status_code=400, detail="Failed to add comment")
            
        created_comment = res.data[0]
        
        # Enrich with user info
        author_res = db.from_("users").select("*").eq("id", user_id).single().execute()
        created_comment["users"] = author_res.data
        created_comment["like_count"] = 0
        created_comment["liked_by_me"] = False
        
        return created_comment
    except Exception as e:
        print(f"DEBUG Error adding comment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/comments/{comment_id}/like")
async def toggle_comment_like(
    comment_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Client = Depends(get_supabase_admin)
):
    try:
        user_id = current_user.get("sub")
        
        # Check if already liked
        res = db.from_("comment_likes").select("*").eq("comment_id", comment_id).eq("user_id", user_id).execute()
        
        if res.data:
            # Unlike
            db.from_("comment_likes").delete().eq("comment_id", comment_id).eq("user_id", user_id).execute()
            liked = False
        else:
            # Like
            db.from_("comment_likes").insert({"comment_id": comment_id, "user_id": user_id}).execute()
            liked = True
            
        # Get updated count
        count_res = db.from_("comment_likes").select("*", count="exact").eq("comment_id", comment_id).execute()
        
        return {"liked": liked, "like_count": count_res.count or 0}
    except Exception as e:
        print(f"DEBUG Error toggling comment like: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{post_id}", response_model=schemas.Post)
async def update_post(
    post_id: str,
    post_update: schemas.PostUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Client = Depends(get_supabase_admin)
):
    try:
        user_id = current_user.get("sub")
        
        # Check if post exists and belongs to user
        res = db.from_("posts").select("*").eq("id", post_id).single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Post not found")
        
        if res.data["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to edit this post")
            
        update_data = post_update.model_dump(exclude_unset=True)
        resp = db.from_("posts").update(update_data).eq("id", post_id).execute()
        
        if not resp.data:
            raise HTTPException(status_code=400, detail="Failed to update post")
            
        return resp.data[0]
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{post_id}")
async def delete_post(
    post_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Client = Depends(get_supabase_admin)
):
    try:
        user_id = current_user.get("sub")
        
        # Check if post exists and belongs to user
        res = db.from_("posts").select("*").eq("id", post_id).single().execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Post not found")
        
        if res.data["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this post")
            
        db.from_("posts").delete().eq("id", post_id).execute()
        return {"message": "Post deleted successfully"}
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/utils/link-preview", response_model=schemas.LinkPreview)
async def get_link_preview(url: str):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True, timeout=5.0)
            if response.status_code != 200:
                return schemas.LinkPreview(url=url)
            
            html = response.text
            
            title_match = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
            title = title_match.group(1).strip() if title_match else ""
            
            desc_match = re.search(r'<meta.*?name=["\']description["\'].*?content=["\'](.*?)["\']', html, re.I | re.S)
            if not desc_match:
                desc_match = re.search(r'<meta.*?property=["\']og:description["\'].*?content=["\'](.*?)["\']', html, re.I | re.S)
            description = desc_match.group(1).strip() if desc_match else ""
            
            img_match = re.search(r'<meta.*?property=["\']og:image["\'].*?content=["\'](.*?)["\']', html, re.I | re.S)
            if not img_match:
                img_match = re.search(r'<meta.*?name=["\']twitter:image["\'].*?content=["\'](.*?)["\']', html, re.I | re.S)
            image = img_match.group(1).strip() if img_match else ""
            
            return schemas.LinkPreview(
                title=title,
                description=description,
                image=image,
                url=url
            )
    except Exception as e:
        print(f"Error fetching link preview: {e}")
        return schemas.LinkPreview(url=url)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
