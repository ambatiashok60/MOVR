"""Conversation CRUD."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.conversation import Conversation
from app.models.enums import AgentMode
from app.persistence.database import get_database
from app.persistence.repositories import ConversationRepository, MessageRepository

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _repos() -> tuple[ConversationRepository, MessageRepository]:
    db = get_database()
    return ConversationRepository(db), MessageRepository(db)


class CreateConversationRequest(BaseModel):
    workspace_path: str
    mode: AgentMode = AgentMode.AGENT
    title: str = "New Chat"


@router.post("", response_model=Conversation)
def create_conversation(body: CreateConversationRequest) -> Conversation:
    conversations, _ = _repos()
    return conversations.create(body.workspace_path, body.mode, body.title)


@router.get("", response_model=list[Conversation])
def list_conversations(limit: int = 20) -> list[Conversation]:
    conversations, _ = _repos()
    return conversations.list(limit=limit)


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str) -> dict:
    conversations, messages = _repos()
    conversation = conversations.get(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "conversation": conversation.model_dump(),
        "messages": [m.model_dump() for m in messages.list_for_conversation(conversation_id)],
    }


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict:
    conversations, _ = _repos()
    conversations.delete(conversation_id)
    return {"deleted": conversation_id}
