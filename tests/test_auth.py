import os
import pytest
from jose import jwt
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_me_unauthenticated():
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as ac:
        r = await ac.get("/me")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated():
    # Arrange: sign a token with the test secret
    secret = "testsecret"
    os.environ["SUPABASE_JWT_SECRET"] = secret
    payload = {"sub": "user-123", "email": "test@example.com", "role": "student"}
    token = jwt.encode(payload, secret, algorithm="HS256")

    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as ac:
        r = await ac.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.json()
        assert data["user"]["id"] == "user-123"
        assert data["user"]["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_instructor_forbidden():
    secret = "testsecret"
    os.environ["SUPABASE_JWT_SECRET"] = secret
    payload = {"sub": "user-123", "email": "test@example.com", "role": "student"}
    token = jwt.encode(payload, secret, algorithm="HS256")

    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as ac:
        r = await ac.get("/instructor-area", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_instructor_allowed():
    secret = "testsecret"
    os.environ["SUPABASE_JWT_SECRET"] = secret
    payload = {"sub": "instr-1", "email": "inst@example.com", "role": "instructor"}
    token = jwt.encode(payload, secret, algorithm="HS256")

    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as ac:
        r = await ac.get("/instructor-area", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["message"] == "Welcome instructor"
