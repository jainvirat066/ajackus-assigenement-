# Design notes

Findings ordered by impact: payment integrity first, then cross-club data leaks, then restricted-attribute handling, then performance.

## P0 — Payment integrity

### 1. Charge amount is taken from the caller

**Area:** Security  
**Where:** `app/routers/bookings.py` (`confirm_payment`)

`payment_mock_client.charge` uses `payload.amount_cents`. A member can send any amount and still confirm the booking. The amount charged should be the booking’s stored `amount_cents`.

### 2. A successful charge is not checked before charging again

**Area:** Security  
**Where:** `app/services/session_flow.py` (`advance_turn`, `affirm`)

Nothing looks for an existing successful charge on this session or booking before calling `payment_mock_client.charge` again. Repeating the confirm step can charge the member twice.

### 3. The charge is not persisted before it is treated as done

**Area:** Security  
**Where:** `app/services/session_flow.py` (`advance_turn`, `affirm`)

The provider is charged first. The booking and `PaymentAttempt` are written only after that returns. A crash in between (see `simulate_crash`) leaves a successful charge with no persisted payment.

**Fix:** In `advance_turn`, when `intent == "affirm"` and `session.awaiting_confirmation`, insert the `Booking` with `status="pending"`, add a `PaymentAttempt` for that `booking.id`, set `session.booking_id`, and `db.commit()` before `payment_mock_client.charge(amount_cents)`. On a later affirm, if `session.booking_id` is already set, load that booking’s `PaymentAttempt` rows and return the existing `booking_id` without calling `charge` again when one has `status == "succeeded"` or is still the in-flight row from that pre-charge commit. Set `session.status = "confirmed"` and `session.awaiting_confirmation = False` only after `result.status == "succeeded"`, so the `simulate_crash` raise no longer drops the only record of the charge.

## P1 — Data isolation

### 4. Knowledge search is not scoped to the club

**Area:** Data isolation  
**Where:** `app/routers/knowledge.py` (`query_knowledge`)

Membership in `club_id` is checked, but the cosine search on `KnowledgeChunk` has no `club_id` filter. Nearest neighbours can come from every club.

### 5. Introductions are not scoped to the caller’s club

**Area:** Data isolation  
**Where:** `app/routers/introductions.py` (`generate_reason`)

Attributes are loaded by `member_id` only. There is no check that both members belong to the caller’s club, so another club’s member text can be returned.

## P2 — Restricted attributes

### 6. Introduction text includes restricted attributes

**Area:** Data integrity  
**Where:** `app/routers/introductions.py` (`generate_reason`)

Both members’ attributes are joined into `reason_text` with no `restricted` filter, so restricted attribute text is stated as part of the introduction.

### 7. The caller’s match profile includes restricted attributes

**Area:** Data integrity  
**Where:** `app/routers/matching.py` → `build_member_profile_text` in `app/services/matching_service.py`

The requesting member’s profile text is built from every attribute they have, including rows with `restricted=True`.

### 8. Candidate attributes ignore the restricted flag

**Area:** Data integrity  
**Where:** `app/services/matching_service.py` (`build_member_profile_text`)

The attribute query filters only on `member_id`. Every attribute is joined into the profile string regardless of `restricted`.

## P3 — Performance

### 9. The caller’s embedding is recomputed on every candidate

**Area:** Performance  
**Where:** `app/services/matching_service.py` (`rank_candidates`)

`embedding_client.embed()` runs inside the candidate loop for the requesting member’s own text. Compute that vector once before the loop and reuse it.
