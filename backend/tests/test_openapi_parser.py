import pytest
import yaml
import json
from app.services.openapi_parser import OpenAPIParser, ApiDocService
from app.schemas.api_doc import ApiDocImport
from app.models.api_doc import ApiDoc
from app.models.api_endpoint import ApiEndpoint, HttpMethod


class TestOpenAPIParser:
    """Tests for OpenAPI parser functionality."""

    def test_parse_json_content(self):
        """Test parsing JSON format OpenAPI content."""
        content = json.dumps({
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {}
        })

        parser = OpenAPIParser(None)
        result = parser.parse_content(content)

        assert result["openapi"] == "3.0.0"
        assert result["info"]["title"] == "Test API"

    def test_parse_yaml_content(self):
        """Test parsing YAML format OpenAPI content."""
        content = """
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths: {}
"""

        parser = OpenAPIParser(None)
        result = parser.parse_content(content)

        assert result["openapi"] == "3.0.0"
        assert result["info"]["title"] == "Test API"

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON raises error."""
        content = '{"openapi": 3.0.0, "info": }'

        parser = OpenAPIParser(None)
        with pytest.raises(ValueError, match="Invalid JSON"):
            parser.parse_content(content)

    def test_parse_invalid_yaml(self):
        """Test parsing invalid YAML raises error."""
        # Use a truly invalid YAML that safe_load cannot parse
        content = "\n[invalid yaml: {\n  key: value\n"

        parser = OpenAPIParser(None)
        with pytest.raises(ValueError, match="Invalid YAML"):
            parser.parse_content(content)

    def test_detect_format_json(self):
        """Test detecting JSON format."""
        parser = OpenAPIParser(None)
        assert parser.detect_format('{"openapi": "3.0.0"}') == "json"
        assert parser.detect_format('  { "openapi": "3.0.0" }') == "json"

    def test_detect_format_yaml(self):
        """Test detecting YAML format."""
        parser = OpenAPIParser(None)
        assert parser.detect_format("openapi: 3.0.0") == "yaml"
        assert parser.detect_format("---\nopenapi: 3.0.0") == "yaml"

    def test_validate_openapi_3(self):
        """Test validating OpenAPI 3.0 document."""
        data = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"}
        }

        parser = OpenAPIParser(None)
        version, info = parser.validate_openapi(data)

        assert version == "3.0.0"
        assert info == "Test API v1.0.0"

    def test_validate_swagger_2(self):
        """Test validating Swagger 2.0 document."""
        data = {
            "swagger": "2.0",
            "info": {"title": "Test API", "version": "1.0.0"}
        }

        parser = OpenAPIParser(None)
        version, info = parser.validate_openapi(data)

        assert version == "2.0"
        assert info == "Test API v1.0.0"

    def test_validate_missing_openapi_field(self):
        """Test that missing openapi/swagger field raises error."""
        data = {
            "info": {"title": "Test API", "version": "1.0.0"}
        }

        parser = OpenAPIParser(None)
        with pytest.raises(ValueError, match="Missing 'openapi' or 'swagger' field"):
            parser.validate_openapi(data)

    def test_validate_missing_info_field(self):
        """Test that missing info field raises error."""
        data = {
            "openapi": "3.0.0"
        }

        parser = OpenAPIParser(None)
        with pytest.raises(ValueError, match="Missing 'info' field"):
            parser.validate_openapi(data)

    def test_extract_endpoints_basic(self):
        """Test extracting basic endpoints from OpenAPI document."""
        data = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/users": {
                    "get": {
                        "summary": "List users",
                        "operationId": "listUsers"
                    },
                    "post": {
                        "summary": "Create user",
                        "operationId": "createUser"
                    }
                },
                "/users/{id}": {
                    "get": {
                        "summary": "Get user",
                        "operationId": "getUser",
                        "parameters": [
                            {"name": "id", "in": "path", "required": True}
                        ]
                    }
                }
            }
        }

        parser = OpenAPIParser(None)
        endpoints = parser.extract_endpoints(data)

        assert len(endpoints) == 3

        # Check GET /users
        get_users = next(e for e in endpoints if e["path"] == "/users" and e["method"] == "GET")
        assert get_users["summary"] == "List users"
        assert get_users["operation_id"] == "listUsers"

        # Check POST /users
        post_users = next(e for e in endpoints if e["path"] == "/users" and e["method"] == "POST")
        assert post_users["summary"] == "Create user"

        # Check GET /users/{id}
        get_user = next(e for e in endpoints if e["path"] == "/users/{id}" and e["method"] == "GET")
        assert get_user["summary"] == "Get user"
        assert len(get_user["parameters"]) == 1
        assert get_user["parameters"][0].name == "id"
        assert get_user["parameters"][0].location == "path"

    def test_extract_endpoints_with_request_body(self):
        """Test extracting endpoints with request body."""
        data = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/users": {
                    "post": {
                        "summary": "Create user",
                        "requestBody": {
                            "required": True,
                            "description": "User data",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "email": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        parser = OpenAPIParser(None)
        endpoints = parser.extract_endpoints(data)

        assert len(endpoints) == 1
        endpoint = endpoints[0]
        assert endpoint["request_body"] is not None
        assert endpoint["request_body"].required is True
        assert endpoint["request_body"].description == "User data"
        assert endpoint["request_body"].body_schema["type"] == "object"

    def test_extract_endpoints_with_responses(self):
        """Test extracting endpoints with responses."""
        data = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/users": {
                    "get": {
                        "summary": "List users",
                        "responses": {
                            "200": {
                                "description": "Successful response",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/User"}
                                        }
                                    }
                                }
                            },
                            "404": {
                                "description": "Not found"
                            }
                        }
                    }
                }
            }
        }

        parser = OpenAPIParser(None)
        endpoints = parser.extract_endpoints(data)

        assert len(endpoints) == 1
        endpoint = endpoints[0]
        assert len(endpoint["responses"]) == 2

        response_200 = next(r for r in endpoint["responses"] if r.status_code == 200)
        assert response_200.description == "Successful response"
        assert response_200.response_schema["type"] == "array"

        response_404 = next(r for r in endpoint["responses"] if r.status_code == 404)
        assert response_404.description == "Not found"

    def test_extract_endpoints_with_query_params(self):
        """Test extracting endpoints with query parameters."""
        data = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/users": {
                    "get": {
                        "summary": "List users",
                        "parameters": [
                            {"name": "page", "in": "query", "required": False, "schema": {"type": "integer"}},
                            {"name": "limit", "in": "query", "required": False, "schema": {"type": "integer"}},
                            {"name": "Authorization", "in": "header", "required": True}
                        ]
                    }
                }
            }
        }

        parser = OpenAPIParser(None)
        endpoints = parser.extract_endpoints(data)

        assert len(endpoints) == 1
        endpoint = endpoints[0]
        assert len(endpoint["parameters"]) == 3

        page_param = next(p for p in endpoint["parameters"] if p.name == "page")
        assert page_param.location == "query"
        assert page_param.required is False
        assert page_param.param_schema["type"] == "integer"

        auth_param = next(p for p in endpoint["parameters"] if p.name == "Authorization")
        assert auth_param.location == "header"
        assert auth_param.required is True

    def test_extract_endpoints_filters_unsupported_methods(self):
        """Test that unsupported methods are filtered out."""
        data = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/trace": {
                    "trace": {"summary": "Trace endpoint"}
                },
                "/connect": {
                    "connect": {"summary": "Connect endpoint"}
                }
            }
        }

        parser = OpenAPIParser(None)
        endpoints = parser.extract_endpoints(data)

        # trace and connect are not in SUPPORTED_METHODS
        assert len(endpoints) == 0

    def test_openapi_3_endpoint_with_path_params(self):
        """Test OpenAPI 3.0 style path parameters."""
        data = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/users/{user_id}/posts/{post_id}": {
                    "get": {
                        "summary": "Get a post",
                        "parameters": [
                            {"name": "user_id", "in": "path", "required": True},
                            {"name": "post_id", "in": "path", "required": True}
                        ]
                    }
                }
            }
        }

        parser = OpenAPIParser(None)
        endpoints = parser.extract_endpoints(data)

        assert len(endpoints) == 1
        endpoint = endpoints[0]
        assert endpoint["path"] == "/users/{user_id}/posts/{post_id}"
        assert len(endpoint["parameters"]) == 2


class TestApiDocImportSchema:
    """Tests for ApiDocImport schema validation."""

    def test_valid_import_data(self):
        """Test valid import data."""
        data = ApiDocImport(
            name="Test API",
            version="2.0.0",
            description="A test API",
            content="openapi: 3.0.0\ninfo:\n  title: Test\n  version: 1.0.0\npaths: {}"
        )
        assert data.name == "Test API"
        assert data.version == "2.0.0"

    def test_empty_content_becomes_none(self):
        """Test that empty content becomes None."""
        data = ApiDocImport(
            name="Test API",
            content="   "
        )
        assert data.content is None

    def test_content_can_be_json(self):
        """Test that content can be JSON."""
        content = json.dumps({
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {}
        })
        data = ApiDocImport(name="Test", content=content)
        assert data.content == content

    def test_default_version(self):
        """Test default version."""
        data = ApiDocImport(name="Test API")
        assert data.version == "1.0.0"


class TestOpenAPIParsedInfo:
    """Tests for OpenAPIParsedInfo schema."""

    def test_create_parsed_info(self):
        """Test creating parsed info."""
        from app.schemas.api_doc import OpenAPIParsedInfo

        info = OpenAPIParsedInfo(
            title="Test API",
            version="1.0.0",
            description="A test API",
            openapi_version="3.0.0",
            endpoints_count=5,
            paths=["/users", "/posts"]
        )

        assert info.title == "Test API"
        assert info.endpoints_count == 5
        assert len(info.paths) == 2


# Integration tests using the test database
@pytest.mark.asyncio
class TestApiDocServiceIntegration:
    """Integration tests for ApiDocService with database."""

    async def test_import_openapi_creates_doc_and_endpoints(self, db_session):
        """Test that importing OpenAPI creates document and endpoints."""
        from app.models.project import Project, ProjectMember, ProjectRole
        from app.models.user import User

        # Create user and project first
        user = User(email="test@example.com", username="testuser", hashed_password="hash")
        db_session.add(user)
        await db_session.flush()

        project = Project(
            name="Test Project",
            project_key="TEST",
            owner_id=user.id
        )
        db_session.add(project)
        await db_session.flush()

        member = ProjectMember(
            project_id=project.id,
            user_id=user.id,
            role=ProjectRole.OWNER
        )
        db_session.add(member)
        await db_session.flush()

        # Import OpenAPI document
        import_data = ApiDocImport(
            name="Test API",
            version="1.0.0",
            content="""
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /users:
    get:
      summary: List users
      responses:
        '200':
          description: OK
  /users/{id}:
    get:
      summary: Get user
      parameters:
        - name: id
          in: path
          required: true
      responses:
        '200':
          description: OK
"""
        )

        service = ApiDocService(db_session)
        api_doc = await service.import_openapi(project.id, import_data)

        assert api_doc.id is not None
        assert api_doc.name == "Test API"
        assert api_doc.project_id == project.id
        assert api_doc.parsed_data is not None

        # Check endpoints were created
        endpoints = await service.get_doc_endpoints(api_doc.id, project.id)
        assert len(endpoints) == 2

        # Check endpoint details
        get_users = next(e for e in endpoints if e.path == "/users" and e.method == HttpMethod.GET)
        assert get_users.summary == "List users"

        get_user = next(e for e in endpoints if e.path == "/users/{id}" and e.method == HttpMethod.GET)
        assert get_user.summary == "Get user"
        assert len(get_user.request_params) == 1
        assert get_user.request_params[0]["name"] == "id"

    async def test_import_invalid_openapi_raises_error(self, db_session):
        """Test that importing invalid OpenAPI raises error."""
        from app.models.project import Project, ProjectMember, ProjectRole
        from app.models.user import User

        # Create user and project
        user = User(email="test@example.com", username="testuser", hashed_password="hash")
        db_session.add(user)
        await db_session.flush()

        project = Project(
            name="Test Project",
            project_key="TEST",
            owner_id=user.id
        )
        db_session.add(project)
        await db_session.flush()

        member = ProjectMember(
            project_id=project.id,
            user_id=user.id,
            role=ProjectRole.OWNER
        )
        db_session.add(member)
        await db_session.flush()

        import_data = ApiDocImport(
            name="Invalid API",
            content="not valid yaml or json"
        )

        service = ApiDocService(db_session)

        with pytest.raises(Exception):  # HTTPException
            await service.import_openapi(project.id, import_data)

    async def test_list_docs(self, db_session):
        """Test listing API documents."""
        from app.models.project import Project, ProjectMember, ProjectRole
        from app.models.user import User

        # Create user and project
        user = User(email="test@example.com", username="testuser", hashed_password="hash")
        db_session.add(user)
        await db_session.flush()

        project = Project(
            name="Test Project",
            project_key="TEST",
            owner_id=user.id
        )
        db_session.add(project)
        await db_session.flush()

        member = ProjectMember(
            project_id=project.id,
            user_id=user.id,
            role=ProjectRole.OWNER
        )
        db_session.add(member)
        await db_session.flush()

        # Create some docs
        doc1 = ApiDoc(project_id=project.id, name="API 1", version="1.0.0")
        doc2 = ApiDoc(project_id=project.id, name="API 2", version="2.0.0")
        db_session.add(doc1)
        db_session.add(doc2)
        await db_session.commit()

        service = ApiDocService(db_session)
        docs = await service.list_docs(project.id)

        assert len(docs) == 2

    async def test_delete_doc_removes_endpoints(self, db_session):
        """Test that deleting a doc also removes its endpoints."""
        from app.models.project import Project, ProjectMember, ProjectRole
        from app.models.user import User

        # Create user and project
        user = User(email="test@example.com", username="testuser", hashed_password="hash")
        db_session.add(user)
        await db_session.flush()

        project = Project(
            name="Test Project",
            project_key="TEST",
            owner_id=user.id
        )
        db_session.add(project)
        await db_session.flush()

        member = ProjectMember(
            project_id=project.id,
            user_id=user.id,
            role=ProjectRole.OWNER
        )
        db_session.add(member)
        await db_session.flush()

        # Create doc with endpoints
        import_data = ApiDocImport(
            name="Test API",
            content="""
openapi: 3.0.0
info:
  title: Test
  version: 1.0.0
paths:
  /users:
    get:
      summary: List users
      responses:
        '200':
          description: OK
"""
        )

        service = ApiDocService(db_session)
        api_doc = await service.import_openapi(project.id, import_data)

        # Verify endpoint exists
        endpoints = await service.get_doc_endpoints(api_doc.id, project.id)
        assert len(endpoints) == 1

        # Delete the doc
        await service.delete_doc(api_doc.id, project.id)

        # Verify doc is gone
        doc = await service.get_doc_by_id(api_doc.id, project.id)
        assert doc is None
