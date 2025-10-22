1. pip install uv
2. to create virtual environment -> uv venv
   Activate with: .venv\Scripts\activate
3. uv add -r requirements.txt
4. for initialising alembic -> alembic init alembic
5. to create a table in the database -> alembic revision --autogenerate -m "Initial migration" -> alembic upgrade head
6. in alembic.ini -> sqlalchemy.url =eg: postgresql://postgres:Database%%40123@localhost:5432/Accumen
7. in alembic folder :
from app.db.base import Base
from app.models.user import Project
target_metadata = Base.metadata
