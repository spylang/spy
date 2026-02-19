from typing import Any, ClassVar


class IRTag:
    """
    Additional info attached to e.g. builtin functions, to make the life
    of the backend easier.
    """

    Empty: ClassVar["IRTag"]
    tag: str
    data: dict[str, Any]

    def __init__(self, tag: str, **kwargs: Any) -> None:
        self.tag = tag
        self.data = kwargs

    def __repr__(self) -> str:
        if self.tag == "":
            return "<IRTag (empty)>"
        else:
            return f"<IRTag {self.tag}: {self.data}>"


IRTag.Empty = IRTag("")
