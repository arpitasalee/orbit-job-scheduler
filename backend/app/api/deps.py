import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise credentials_error
    user = db.get(User, uuid.UUID(payload["sub"]))
    if user is None:
        raise credentials_error
    return user


def get_project_or_404(project_id: uuid.UUID, db: Session, current_user: User):
    from app.models.models import Project
    project = db.get(Project, project_id)
    if project is None or project.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def get_queue_or_404(queue_id: uuid.UUID, db: Session, current_user: User):
    from app.models.models import Queue, Project
    queue = db.get(Queue, queue_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Queue not found")
    project = db.get(Project, queue.project_id)
    if project is None or project.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Queue not found")
    return queue
