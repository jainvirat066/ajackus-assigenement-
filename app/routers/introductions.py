from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_member
from app.db import get_db
from app.models import Member, MemberAttribute

router = APIRouter(prefix="/introductions", tags=["introductions"])


@router.get("/{member_a_id}/{member_b_id}")
def generate_reason(
    member_a_id: int,
    member_b_id: int,
    reason: str,
    db: Session = Depends(get_db),
    member: Member = Depends(get_current_member),
):
    min_confidence_score = 0.6
    if member_a_id != member.id and member_b_id != member.id:
        raise HTTPException(status_code=403, detail="not a member of this club")
    
    member_a = db.query(Member).filter(Member.id == member_a_id).first()
    member_b = db.query(Member).filter(Member.id == member_b_id).first()
    if member_a.club_id != member.club_id or member_b.club_id != member.club_id:
        raise HTTPException(status_code=403, detail="not a member of this club")


    attrs_a = db.query(MemberAttribute).filter(MemberAttribute.member_id == member_a_id, MemberAttribute.club_id == member.club_id, MemberAttribute.restricted == False).all()
    attrs_b = db.query(MemberAttribute).filter(MemberAttribute.member_id == member_b_id, MemberAttribute.club_id == member.club_id, MemberAttribute.restricted == False).all()

    # Every attribute is stated as fact regardless of its confidence score.

    for attr_a in attrs_a:
        for attr_b in attrs_b:
            if attr_a.text == attr_b.text:
                confidence_score = attr_a.confidence_score * attr_b.confidence_score
                if confidence_score < min_confidence_score:
                    continue
                return {"reason_text": f"Because {attr_a.text} and {attr_b.text} — a good {reason} match."}

    a_text = "; ".join(a.text for a in attrs_a)
    b_text = "; ".join(b.text for b in attrs_b)
    return {"reason_text": f"Because {a_text} and {b_text} — a good {reason} match."}
