from datetime import UTC, datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(UTC)


class RequestRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["request"] = "request"
    name: str
    file: str


class FolderItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["folder"] = "folder"
    name: str
    items: list["CollectionItem"] = Field(default_factory=list)


CollectionItem = Annotated[Union[FolderItem, RequestRef], Field(discriminator="type")]
FolderItem.model_rebuild()


class Collection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[CollectionItem] = Field(default_factory=list)


class Project(BaseModel):
    model_config = ConfigDict(extra="ignore")

    format_version: int = 1
    name: str = "Untitled Project"
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)
