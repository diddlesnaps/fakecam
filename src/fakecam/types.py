from typing import Optional
from typing_extensions import TypedDict


class CommandQueueDict(TypedDict):
    background: Optional[str]
    hologram: bool
    mirror: bool
