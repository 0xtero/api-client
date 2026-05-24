from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KeyValueEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    value: str = ""
    enabled: bool = True


class BodyMode(StrEnum):
    NONE = "none"
    JSON = "json"
    TEXT = "text"
    FORM_URLENCODED = "form-urlencoded"
    MULTIPART = "multipart"
    FILE = "file"


class FormFieldKind(StrEnum):
    TEXT = "text"
    FILE = "file"


class FormFieldEntry(KeyValueEntry):
    kind: FormFieldKind = FormFieldKind.TEXT
    file_path: str = ""


class HttpBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: BodyMode = BodyMode.NONE
    content: str = ""
    form_fields: list[KeyValueEntry] = Field(default_factory=list)
    multipart_fields: list[FormFieldEntry] = Field(default_factory=list)
    file_path: str = ""
    content_type: str = ""


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


class HttpRequestSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    follow_redirects: bool = True
    max_redirects: int = Field(default=5, ge=1, le=50)
    timeout_ms: int = Field(default=30000, ge=1000, le=300000)
    encode_url: bool = True


class HttpRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = "Untitled request"
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"] = "GET"
    url: str = ""
    headers: list[KeyValueEntry] = Field(default_factory=list)
    query_params: list[KeyValueEntry] = Field(default_factory=list)
    path_params: list[KeyValueEntry] = Field(default_factory=list)
    body: HttpBody = Field(default_factory=HttpBody)
    auth: HttpAuth = Field(default_factory=HttpAuth)
    settings: HttpRequestSettings = Field(default_factory=HttpRequestSettings)

    @field_validator("headers", mode="before")
    @classmethod
    def _normalize_headers(cls, value: object) -> list[KeyValueEntry]:
        from apiclient.models.compat import headers_to_entries

        return headers_to_entries(value)


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
