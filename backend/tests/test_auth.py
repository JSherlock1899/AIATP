import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Test successful user registration."""
    response = await client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpassword123"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"
    assert "id" in data
    assert "created_at" in data
    assert "password" not in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Test registration with duplicate email fails."""
    user_data = {
        "email": "duplicate@example.com",
        "username": "user1",
        "password": "password123"
    }
    response = await client.post("/auth/register", json=user_data)
    assert response.status_code == 201

    response = await client.post("/auth/register", json=user_data)
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    """Test registration with duplicate username fails."""
    response = await client.post(
        "/auth/register",
        json={
            "email": "user1@example.com",
            "username": "duplicateuser",
            "password": "password123"
        }
    )
    assert response.status_code == 201

    response = await client.post(
        "/auth/register",
        json={
            "email": "user2@example.com",
            "username": "duplicateuser",
            "password": "password123"
        }
    )
    assert response.status_code == 400
    assert "Username already taken" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Test successful login."""
    await client.post(
        "/auth/register",
        json={
            "email": "login@example.com",
            "username": "loginuser",
            "password": "password123"
        }
    )

    response = await client.post(
        "/auth/login",
        json={
            "email": "login@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_email(client: AsyncClient):
    """Test login with non-existent email fails."""
    response = await client.post(
        "/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    """Test login with wrong password fails."""
    await client.post(
        "/auth/register",
        json={
            "email": "wrongpass@example.com",
            "username": "wrongpassuser",
            "password": "correctpassword"
        }
    )

    response = await client.post(
        "/auth/login",
        json={
            "email": "wrongpass@example.com",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_invalid_email_format(client: AsyncClient):
    """Test registration with invalid email format fails."""
    response = await client.post(
        "/auth/register",
        json={
            "email": "invalid-email",
            "username": "testuser",
            "password": "password123"
        }
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_me_success(client: AsyncClient):
    """Test getting current user with valid token."""
    # Register a user
    await client.post(
        "/auth/register",
        json={
            "email": "me@example.com",
            "username": "meuser",
            "password": "password123"
        }
    )

    # Login to get token
    login_response = await client.post(
        "/auth/login",
        json={
            "email": "me@example.com",
            "password": "password123"
        }
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # Get current user
    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@example.com"
    assert data["username"] == "meuser"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_me_without_token(client: AsyncClient):
    """Test getting current user without token fails."""
    response = await client.get("/auth/me")
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_get_me_with_invalid_token(client: AsyncClient):
    """Test getting current user with invalid token fails."""
    response = await client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid-token"}
    )
    assert response.status_code == 401
