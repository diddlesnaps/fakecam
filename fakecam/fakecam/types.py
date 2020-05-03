from typing import Optional
from typing_extensions import TypedDict


class QueueDict(TypedDict):
    background: Optional[str]
    hologram: bool
    mirror: bool
