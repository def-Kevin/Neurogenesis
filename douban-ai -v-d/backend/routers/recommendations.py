from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import models, schemas, dependencies

router = APIRouter()


@router.get("", response_model=list[schemas.RecommendationOut])
def list_recommendations(
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.Recommendation)
        .filter(models.Recommendation.user_id == current_user.id)
        .order_by(models.Recommendation.created_at.desc())
        .all()
    )


@router.post("/{recommendation_id}/feedback")
def feedback(
    recommendation_id: int,
    feedback: str,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db),
):
    rec = db.query(models.Recommendation).filter(
        models.Recommendation.id == recommendation_id,
        models.Recommendation.user_id == current_user.id,
    ).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    rec.user_feedback = feedback
    db.commit()
    return {"success": True}
