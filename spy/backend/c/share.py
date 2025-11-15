from dataclasses import dataclass


@dataclass
class C_Type:
    """
    Just a tiny wrapper around a string, but it helps to make things tidy.
    """

    name: str

    def __repr__(self) -> str:
        return f"<C type '{self.name}'>"

    def __str__(self) -> str:
        return self.name
