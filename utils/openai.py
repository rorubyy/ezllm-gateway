from typing import Optional, List
from pydantic import BaseModel
import json

class CompletionChoice(BaseModel):
    finish_reason: Optional[str]
    index: int
    logprobs: Optional[dict]
    text: Optional[str]

class CompletionUsage(BaseModel):
    completion_tokens: int
    prompt_tokens: int
    total_tokens: int
    completion_tokens_details: Optional[dict]
    prompt_tokens_details: Optional[dict]

class Completion(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: List[CompletionChoice]
    usage: CompletionUsage
    system_fingerprint: Optional[str] = None
