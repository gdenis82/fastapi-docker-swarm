from pydantic import BaseModel
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[int] = None
    type: Optional[str] = None
    exp: Optional[int] = None
    jti: Optional[str] = None
