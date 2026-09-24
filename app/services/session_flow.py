from sqlalchemy.orm import Session as DbSession
from fastapi import HTTPException
from app.models import Booking, ConversationSession, PaymentAttempt
from app.services.payment_mock import payment_mock_client


class SimulatedCrash(Exception):
    """Lets a caller reproduce a process crash between the charge succeeding
    and the session/booking being persisted — the same ambiguous-outcome
    scenario as a real payment-provider timeout, but deterministic to trigger."""


def advance_turn(session: ConversationSession, intent: str, payload: dict, db: DbSession) -> dict:
    if intent == "refund_dispute":
        session.status = "escalated"
        db.commit()
        return {"status": "escalated"}

    if intent == "book":
        party_size = payload.get("party_size")
        if party_size is not None:
            session.party_size = party_size
        if session.party_size is not None:
            session.awaiting_confirmation = True
        db.commit()
        return {
            "status": "awaiting_confirmation" if session.awaiting_confirmation else "need_party_size",
            "party_size": session.party_size,
        }

    if intent == "affirm" and session.awaiting_confirmation:
        booking = db.query(Booking).filter(Booking.id == session.booking_id).first()
        if amount_cents != booking.amount_cents:
            raise HTTPException(status_code=400, detail="amount does not match the booking")
        amount_cents = payload.get("amount_cents", 0)
        #TODO: Check if the amount is valid amount for the booking
        # No check here for a prior successful charge on this session, and
        # nothing is persisted before the charge happens.

        if booking.status == "succeeded":
            raise HTTPException(status_code=400, detail="booking already succeeded")

        result = payment_mock_client.charge(amount_cents)

        if result.status == "succeeded":
            booking = Booking(
                member_id=session.member_id,
                club_id=session.club_id,
                description="Session-confirmed booking",
                amount_cents=amount_cents,
                status="confirmed" if result.status == "succeeded" else "pending",
            )
            db.add(booking)
            db.add(PaymentAttempt(booking_id=booking.id, amount_cents=amount_cents, status=result.status))
            session.booking_id = booking.id
            session.status = "confirmed"
            session.awaiting_confirmation = False
            db.commit()

        if result.status != "succeeded":
            raise HTTPException(status_code=400, detail="charge failed")
        
        if payload.get("simulate_crash"):
            raise SimulatedCrash("process died after the charge, before the session/booking were saved")

        booking = Booking(
            member_id=session.member_id,
            club_id=session.club_id,
            description="Session-confirmed booking",
            amount_cents=amount_cents,
            status="confirmed" if result.status == "succeeded" else "pending",
        )
        db.add(booking)
        db.flush()
        db.add(PaymentAttempt(booking_id=booking.id, amount_cents=amount_cents, status=result.status))
        session.booking_id = booking.id
        session.status = "confirmed"
        session.awaiting_confirmation = False
        db.commit()
        return {"status": "confirmed", "booking_id": booking.id}

    return {"status": session.status}
