"""add source_code_projects table

Revision ID: 73746db10459
Revises:
Create Date: 2026-03-19 17:58:20.670313

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '73746db10459'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create source_code_projects table
    op.execute('''
        CREATE TABLE source_code_projects (
            id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            name VARCHAR(200) NOT NULL,
            source_path VARCHAR(500) NOT NULL,
            language VARCHAR(50),
            status VARCHAR(9),
            error_message TEXT,
            endpoints_count INTEGER,
            created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
            parsed_at DATETIME,
            PRIMARY KEY (id),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )
    ''')
    op.execute('CREATE INDEX ix_source_code_projects_id ON source_code_projects(id)')

    # Recreate api_endpoints table with:
    # 1. api_doc_id as nullable
    # 2. source_code_project_id column added
    op.execute('''
        CREATE TABLE api_endpoints_new (
            id INTEGER NOT NULL,
            api_doc_id INTEGER,
            source_code_project_id INTEGER,
            path VARCHAR(500) NOT NULL,
            method VARCHAR(7) NOT NULL,
            summary VARCHAR(500),
            description TEXT,
            operation_id VARCHAR(100),
            request_body JSON,
            request_headers JSON,
            request_params JSON,
            responses JSON,
            is_active BOOLEAN,
            created_at DATETIME,
            updated_at DATETIME,
            PRIMARY KEY (id)
        )
    ''')

    # Copy data from old table to new (without source_code_project_id)
    op.execute('''
        INSERT INTO api_endpoints_new
        (id, api_doc_id, path, method, summary, description,
         operation_id, request_body, request_headers, request_params, responses,
         is_active, created_at, updated_at)
        SELECT id, api_doc_id, path, method, summary, description,
               operation_id, request_body, request_headers, request_params, responses,
               is_active, created_at, updated_at
        FROM api_endpoints
    ''')

    # Drop old table and rename new one
    op.execute('DROP TABLE api_endpoints')
    op.execute('ALTER TABLE api_endpoints_new RENAME TO api_endpoints')

    # Recreate indexes
    op.execute('CREATE INDEX ix_api_endpoints_id ON api_endpoints(id)')
    op.execute('CREATE INDEX ix_api_endpoints_path ON api_endpoints(path)')
    op.execute('CREATE INDEX ix_api_endpoints_source_code_project_id ON api_endpoints(source_code_project_id)')


def downgrade() -> None:
    # Recreate table with original schema (api_doc_id NOT NULL, no source_code_project_id)
    op.execute('''
        CREATE TABLE api_endpoints_old (
            id INTEGER NOT NULL,
            api_doc_id INTEGER NOT NULL,
            path VARCHAR(500) NOT NULL,
            method VARCHAR(7) NOT NULL,
            summary VARCHAR(500),
            description TEXT,
            operation_id VARCHAR(100),
            request_body JSON,
            request_headers JSON,
            request_params JSON,
            responses JSON,
            is_active BOOLEAN,
            created_at DATETIME,
            updated_at DATETIME,
            PRIMARY KEY (id)
        )
    ''')

    op.execute('''
        INSERT INTO api_endpoints_old
        (id, api_doc_id, path, method, summary, description,
         operation_id, request_body, request_headers, request_params, responses,
         is_active, created_at, updated_at)
        SELECT id, api_doc_id, path, method, summary, description,
               operation_id, request_body, request_headers, request_params, responses,
               is_active, created_at, updated_at
        FROM api_endpoints
    ''')

    op.execute('DROP TABLE api_endpoints')
    op.execute('ALTER TABLE api_endpoints_old RENAME TO api_endpoints')

    op.execute('CREATE INDEX ix_api_endpoints_id ON api_endpoints(id)')
    op.execute('CREATE INDEX ix_api_endpoints_path ON api_endpoints(path)')

    # Drop source_code_projects
    op.execute('DROP INDEX IF EXISTS ix_api_endpoints_source_code_project_id')
    op.execute('DROP TABLE source_code_projects')
