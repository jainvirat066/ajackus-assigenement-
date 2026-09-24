"""Interface for Part 3's extraction pipeline.

Nothing in this file calls a real API. You implement a real client against
the LLM provider of your choice (OpenAI, Anthropic, or equivalent) for the
actual pipeline. FakeLLMClient below is provided only so your own unit tests
don't need a real API key or network access.
"""

from typing import Protocol, TypedDict
import mistralai
import openai

from app.retry import with_retry

VALID_KINDS = ["need", "offer", "context", "interest"]

SYSTEM_PROMPT = """
You extract structured attributes from one WhatsApp message a member sent to their private members' club concierge. These attributes are stored on the member and later used to introduce members of the same club to each other. Extract only what this message states. Do not invent people, facts, or intent that are not in the text.

Return a JSON array and nothing else. Each object has exactly these fields:
- kind: one of "need", "offer", "context", "interest"
- text: one short third-person phrase, with no "I" or "you", written so two members can be compared
- confidence: a number from 0 to 1
- restricted: true or false

kind:
- need — the member wants something from other members: an introduction, a service, a partner, advice. "I'm trying to raise a Series A, would love intros to VCs" → "raising a Series A, looking for intros to VCs".
- offer — the member can give something others could use, or has done the work they are offering to help with. "I've led fundraising for three Series A rounds, happy to help" → "has led fundraising for three Series A rounds and is happy to help".
- context — background about who they are that helps a match, and is not itself a request or an offer. "I used to run a hospitality business, now I consult" → "former hospitality business owner, now a consultant".
- interest — a social or recreational activity they want to share with other members. "Does anyone want a weekly running club on Tuesday mornings?" → "looking for a weekly running group on Tuesday mornings".

restricted:
Set restricted to true when the attribute is sensitive and must not be said in an introduction. That includes health, mental health, therapy, diagnoses, disability, family crisis, financial hardship, and anything the member marks as private ("between us", "just so you understand", "don't share this"). Professional history, hobbies, and ordinary asks or offers are restricted false.

confidence:
Use 0.85 to 1.0 when the statement is clear and current. Use 0.4 to 0.7 when they hedge ("might", "not sure", "thinking about", "maybe next year"). Use below 0.4 when the remark is vague or hypothetical.

A message may produce zero, one, or several attributes. Split distinct facts into separate objects. Ignore greetings, booking logistics, and club-policy questions that do not describe the member. If nothing is extractable, return [].
"""

EXTRACT_TOOL = {
    "name": "extract_attributes",
    "description": "Extract structured attributes from one WhatsApp message a member sent to their private members' club concierge.",
    "parameters": {
        "type": "object",
        "properties": {
            "message_text": {"type": "string", "description": "The message text to extract attributes from"},
        }
    }
}

def normalize_attributes(attributes: list[ExtractedAttribute]) -> list[ExtractedAttribute]:
    """Never trust model output: drop malformed item."""
    out: list[ExtractedAttribute] = []
    for item in attributes:
        if item["kind"] not in VALID_KINDS:
            continue
        if item["text"] == "":
            continue
        if item["confidence"] < 0.4:
            continue
        try:
            confidence = max(0.4, min(1.0, float(item["confidence"])))
        except ValueError:
            continue
        out.append(ExtractedAttribute(
            kind=item["kind"],
            text=item["text"],
            confidence=confidence,
            restricted=item["restricted"]
        ))
        out.append(item)
    return out



class MistralLLMClient:
    def __init__(self, api_key: str):
        self.client = mistralai.Client(api_key=api_key)

    def _call(self, message_text: str) -> list[ExtractedAttribute]:
        response = self.client.chat.completions.create(
            model="mistral-large-24b",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message_text}
            ],
        )
        return normalize_attributes(response.choices[0].message.content)

    def extract_attributes(self, message_text: str) -> list[ExtractedAttribute]:
        response = with_retry(self._call, message_text)
        for item in response:
           for content in response.content:
                return normalize_attributes(content.input.get("attributes",[]))
        return []

class ExtractedAttribute(TypedDict):
    kind: str  # need | offer | context | interest
    text: str
    confidence: float
    restricted: bool


class LLMClient(Protocol):
    def extract_attributes(self, message_text: str) -> list[ExtractedAttribute]:
        """Extract structured attributes from one raw member message."""
        ...


class FakeLLMClient:
    """Trivial test double — does not call any real API."""

    def __init__(self, canned_response: list[ExtractedAttribute] | None = None) -> None:
        self.canned_response = canned_response or []
        self.calls: list[str] = []

    def extract_attributes(self, message_text: str) -> list[ExtractedAttribute]:
        self.calls.append(message_text)
        return self.canned_response
