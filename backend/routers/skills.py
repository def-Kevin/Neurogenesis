from fastapi import APIRouter, Header, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.services.tool_dispatcher import dispatch
from backend.database import get_db

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.post("/{tool_name}")
def call_skill(
    tool_name: str,
    body: dict,
    x_avatar_id: int = Header(alias="X-Avatar-Id"),
    db: Session = Depends(get_db),
):
    if not x_avatar_id:
        raise HTTPException(status_code=400, detail="X-Avatar-Id header is required")
    result = dispatch(tool_name, body, x_avatar_id, db)
    return {"result": result}
