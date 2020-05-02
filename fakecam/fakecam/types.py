from typing import TypedDict, Optional


class QueueDict(TypedDict):
    background: Optional[str]
    hologram: bool
    mirror: bool
