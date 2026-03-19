import pytest
from httpx import AsyncClient

from app.models.project import ProjectRole


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient):
    """Test creating a new project."""
    # Register and login first
    await client.post(
        "/auth/register",
        json={
            "email": "owner@example.com",
            "username": "owneruser",
            "password": "password123"
        }
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": "owner@example.com",
            "password": "password123"
        }
    )
    token = login_response.json()["access_token"]

    response = await client.post(
        "/projects",
        json={
            "name": "Test Project",
            "description": "A test project",
            "project_key": "TEST"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Project"
    assert data["description"] == "A test project"
    assert data["project_key"] == "TEST"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_project_duplicate_key(client: AsyncClient):
    """Test creating a project with duplicate key fails."""
    await client.post(
        "/auth/register",
        json={
            "email": "owner2@example.com",
            "username": "owneruser2",
            "password": "password123"
        }
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": "owner2@example.com",
            "password": "password123"
        }
    )
    token = login_response.json()["access_token"]

    # Create first project
    await client.post(
        "/projects",
        json={
            "name": "Project 1",
            "description": "First project",
            "project_key": "DUPKEY"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    # Try to create second project with same key
    response = await client.post(
        "/projects",
        json={
            "name": "Project 2",
            "description": "Second project",
            "project_key": "dupkey"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_project_invalid_key(client: AsyncClient):
    """Test creating a project with invalid key format fails."""
    await client.post(
        "/auth/register",
        json={
            "email": "owner3@example.com",
            "username": "owneruser3",
            "password": "password123"
        }
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": "owner3@example.com",
            "password": "password123"
        }
    )
    token = login_response.json()["access_token"]

    response = await client.post(
        "/projects",
        json={
            "name": "Test Project",
            "project_key": "invalid-key!"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_project(client: AsyncClient):
    """Test getting a project by ID."""
    await client.post(
        "/auth/register",
        json={
            "email": "getproj@example.com",
            "username": "getprojuser",
            "password": "password123"
        }
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": "getproj@example.com",
            "password": "password123"
        }
    )
    token = login_response.json()["access_token"]

    # Create project
    create_response = await client.post(
        "/projects",
        json={
            "name": "Get Project",
            "description": "Get test",
            "project_key": "GETPROJ"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    project_id = create_response.json()["id"]

    # Get project
    response = await client.get(
        f"/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Get Project"
    assert "members" in data


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient):
    """Test getting non-existent project fails."""
    await client.post(
        "/auth/register",
        json={
            "email": "notfound@example.com",
            "username": "notfounduser",
            "password": "password123"
        }
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": "notfound@example.com",
            "password": "password123"
        }
    )
    token = login_response.json()["access_token"]

    response = await client.get(
        "/projects/99999",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient):
    """Test listing projects for current user."""
    await client.post(
        "/auth/register",
        json={
            "email": "listproj@example.com",
            "username": "listprojuser",
            "password": "password123"
        }
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": "listproj@example.com",
            "password": "password123"
        }
    )
    token = login_response.json()["access_token"]

    # Create projects
    for i in range(3):
        await client.post(
            "/projects",
            json={
                "name": f"Project {i}",
                "description": f"Description {i}",
                "project_key": f"PROJ{i}"
            },
            headers={"Authorization": f"Bearer {token}"}
        )

    # List projects
    response = await client.get(
        "/projects",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient):
    """Test updating a project."""
    await client.post(
        "/auth/register",
        json={
            "email": "updateproj@example.com",
            "username": "updateprojuser",
            "password": "password123"
        }
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": "updateproj@example.com",
            "password": "password123"
        }
    )
    token = login_response.json()["access_token"]

    # Create project
    create_response = await client.post(
        "/projects",
        json={
            "name": "Original Name",
            "description": "Original description",
            "project_key": "UPDPROJ"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    project_id = create_response.json()["id"]

    # Update project
    response = await client.put(
        f"/projects/{project_id}",
        json={
            "name": "Updated Name",
            "description": "Updated description"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["description"] == "Updated description"


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient):
    """Test deleting a project."""
    await client.post(
        "/auth/register",
        json={
            "email": "deleteproj@example.com",
            "username": "deleteprojuser",
            "password": "password123"
        }
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": "deleteproj@example.com",
            "password": "password123"
        }
    )
    token = login_response.json()["access_token"]

    # Create project
    create_response = await client.post(
        "/projects",
        json={
            "name": "Delete Me",
            "project_key": "DELPROJ"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    project_id = create_response.json()["id"]

    # Delete project
    response = await client.delete(
        f"/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 204

    # Verify project is gone
    get_response = await client.get(
        f"/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_add_member(client: AsyncClient):
    """Test adding a member to a project."""
    # Register owner
    await client.post(
        "/auth/register",
        json={
            "email": "memberowner@example.com",
            "username": "memberowner",
            "password": "password123"
        }
    )

    # Register new member
    await client.post(
        "/auth/register",
        json={
            "email": "newmember@example.com",
            "username": "newmember",
            "password": "password123"
        }
    )

    # Login as owner
    login_response = await client.post(
        "/auth/login",
        json={
            "email": "memberowner@example.com",
            "password": "password123"
        }
    )
    token = login_response.json()["access_token"]

    # Get new member's ID
    member_login = await client.post(
        "/auth/login",
        json={
            "email": "newmember@example.com",
            "password": "password123"
        }
    )
    member_token = member_login.json()["access_token"]
    member_response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    member_id = member_response.json()["id"]

    # Create project
    create_response = await client.post(
        "/projects",
        json={
            "name": "Member Test Project",
            "project_key": "MEMBER"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    project_id = create_response.json()["id"]

    # Add member
    response = await client.post(
        f"/projects/{project_id}/members?user_id={member_id}&role=developer",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == member_id
    assert data["role"] == "developer"


@pytest.mark.asyncio
async def test_add_duplicate_member(client: AsyncClient):
    """Test adding duplicate member fails."""
    await client.post(
        "/auth/register",
        json={
            "email": "dupmember@example.com",
            "username": "dupmember",
            "password": "password123"
        }
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": "dupmember@example.com",
            "password": "password123"
        }
    )
    token = login_response.json()["access_token"]

    # Get user ID
    me_response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    user_id = me_response.json()["id"]

    # Create project
    create_response = await client.post(
        "/projects",
        json={
            "name": "Duplicate Member Test",
            "project_key": "DUPMEM"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    project_id = create_response.json()["id"]

    # Try to add same user twice
    response = await client.post(
        f"/projects/{project_id}/members?user_id={user_id}&role=viewer",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 400
    assert "already a member" in response.json()["detail"]


@pytest.mark.asyncio
async def test_remove_member(client: AsyncClient):
    """Test removing a member from a project."""
    # Register owner
    await client.post(
        "/auth/register",
        json={
            "email": "removemember@example.com",
            "username": "removemember",
            "password": "password123"
        }
    )

    # Register member to remove
    await client.post(
        "/auth/register",
        json={
            "email": "to_remove@example.com",
            "username": "to_remove",
            "password": "password123"
        }
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": "removemember@example.com",
            "password": "password123"
        }
    )
    token = login_response.json()["access_token"]

    # Get member ID
    member_login = await client.post(
        "/auth/login",
        json={
            "email": "to_remove@example.com",
            "password": "password123"
        }
    )
    member_token = member_login.json()["access_token"]
    member_response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    member_id = member_response.json()["id"]

    # Create project
    create_response = await client.post(
        "/projects",
        json={
            "name": "Remove Member Test",
            "project_key": "REMOVEM"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    project_id = create_response.json()["id"]

    # Add member
    await client.post(
        f"/projects/{project_id}/members?user_id={member_id}&role=viewer",
        headers={"Authorization": f"Bearer {token}"}
    )

    # Remove member
    response = await client.delete(
        f"/projects/{project_id}/members/{member_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_project_unauthorized(client: AsyncClient):
    """Test accessing project without authentication fails."""
    response = await client.get("/projects")
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_project_key_normalized_to_uppercase(client: AsyncClient):
    """Test that project_key is normalized to uppercase."""
    await client.post(
        "/auth/register",
        json={
            "email": "keycase@example.com",
            "username": "keycaseuser",
            "password": "password123"
        }
    )

    login_response = await client.post(
        "/auth/login",
        json={
            "email": "keycase@example.com",
            "password": "password123"
        }
    )
    token = login_response.json()["access_token"]

    response = await client.post(
        "/projects",
        json={
            "name": "Key Case Test",
            "project_key": "lowercase"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 201
    assert response.json()["project_key"] == "LOWERCASE"
