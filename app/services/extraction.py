from typing import Any


import logging

from pytest import Session
from app.llm_client import LLMClient
from app.models import ConversationMessage

log = logging.getLogger(__name__)

class ExtractionService:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def extract_attributes(self, message_text: str) -> list[ExtractedAttribute]:
        return self.llm_client.extract_attributes(message_text)
    
    def extract_for_message(self, message: Message) -> list[ExtractedAttribute]:
        ids = list(dict.fromkeys(message.mentioned_member_ids))
        in_club = {
            mid for (mid,_) in message.mentions
        }
        attrs = []
        touched_member : set[int] = set()  # members that have been touched by this message
        for mid in ids:
            if mid in in_club:
                attrs.extend(self.extract_attributes(message.text))
            try:
                status,created,member_id = _process_one(db,club,mid,llm)
                if created < msg.created:
                    touched_member.add(member_id)

            except Exception as e:
                log.error(f"Error extracting attributes for message {message.id}: {e}")
                continue
        return attrs
    
    def _process_one(self, db: Session,club_id: str,mid: int,llm: LLMClient) -> tuple[str, datetime, int]:
        msg = (db.query(ConversationMessage).filter(ConversationMessage.id == mid,ConversationMessage.club_id == club_id).first())
        if msg is None:
            raise ValueError(f"Message {mid} not found")
        attrs = self.extract_attributes(msg.text)
        return attrs
