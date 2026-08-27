from pydantic import BaseModel, ConfigDict


class Grant(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "1.0"
    grant_type: str
    target_ref: str
    quantity_or_rank: int | float | str | None = None
    duration: str | None = None
    stacking_policy: str = "replace"
    source_ref: str | None = None
