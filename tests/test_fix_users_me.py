import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.routers.users import read_users_me

client = TestClient(app)

# Mock dependencies
@pytest.fixture
def mock_supabase():
    mock_client = MagicMock()
    return mock_client

def test_read_users_me_creates_user_if_missing(mock_supabase):
    # Test data
    user_id = "test-user-id"
    email = "test@example.com"
    user_metadata = {
        "first_name": "Test",
        "last_name": "User",
        "avatar_url": "http://example.com/avatar.jpg"
    }
    
    # Mock current_user
    mock_user_token = {
        "sub": user_id,
        "email": email,
        "user_metadata": user_metadata
    }

    # Setup mock behavior
    # 1. Select fails (simulating missing user)
    # The actual code calls: db.from_("users").select("*").eq("id", user_id).single().execute()
    # We need to make .execute() raise an exception on the first call
    
    query_builder = MagicMock()
    mock_supabase.from_.return_value = query_builder
    query_builder.select.return_value = query_builder
    query_builder.eq.return_value = query_builder
    query_builder.single.return_value = query_builder
    
    # Define side effect for execute: First time raise Exception, Second time (insert) return data
    
    def side_effect(*args, **kwargs):
        # We need to distinguish between select and insert calls if possible
        # Or just rely on the order of calls in the code
        pass

    # Easier approach: Mock the keys specifically
    # The code does:
    # response = db.from_("users").select("*").eq("id", user_id).single().execute() -> raising Exception
    
    # Then:
    # create_response = db.from_("users").insert(new_user).execute() -> returning data
    
    # Define side effect for execute: First time raise Exception (Select)
    
    mock_builder = MagicMock()
    mock_supabase.from_.return_value = mock_builder
    
    # Mock Select
    mock_select = MagicMock()
    mock_builder.select.return_value = mock_select
    mock_select.eq.return_value = mock_select
    mock_select.single.return_value = mock_select
    mock_select.execute.side_effect = Exception("Row not found") # Simulate 404/PGRST116
    
    # Mock Insert (Should NOT be called, but we mock just in case to verify it's NOT called)
    mock_insert = MagicMock()
    mock_builder.insert.return_value = mock_insert


    # Override dependencies
    app.dependency_overrides["app.auth.get_current_user"] = lambda: mock_user_token
    app.dependency_overrides["app.dependencies.get_supabase"] = lambda: mock_supabase

    response = client.get("/users/me")
    
    # Reset overrides
    app.dependency_overrides = {}

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["email"] == email
    assert data["first_name"] == "Test"
    
    # Verify insert was NOT called
    mock_builder.insert.assert_not_called()
    
    # Use render_diffs to show what changed

