from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BodyMode(StrEnum):
    NONE = "none"
    JSON = "json"
    TEXT = "text"


class HttpBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: BodyMode = BodyMode.NONE
    content: str = ""


class AuthType(StrEnum):
    NONE = "none"
    BEARER = "bearer"
    BASIC = "basic"
    API_KEY = "api_key"


class ApiKeyIn(StrEnum):
    HEADER = "header"
    QUERY = "query"


class HttpAuth(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: AuthType = AuthType.NONE
    token: str = ""
    username: str = ""
    password: str = ""
    key_name: str = ""
    key_value: str = ""
    key_in: ApiKeyIn = ApiKeyIn.HEADER


class HttpRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = "Untitled request"
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"] = "GET"
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    body: HttpBody = Field(default_factory=HttpBody)
    auth: HttpAuth = Field(default_factory=HttpAuth)


class HttpResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status_code: int
    reason: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    body: str = ""
    elapsed_ms: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.status_code < 300
