from typing import Optional
from .fqn import NSPart, FQN


def tokenize(s: str) -> list[str]:
    tokens = []
    token = ""
    depth = 0
    i = 0
    while i < len(s):
        char = s[i]
        if char.isspace():
            i += 1
            continue
        if char in "[]," and depth == 0:
            if token:
                tokens.append(token)
                token = ""
            tokens.append(char)
        elif char == "[":
            if token:
                tokens.append(token)
                token = ""
            tokens.append(char)
            depth += 1
        elif char == "]":
            if token:
                tokens.append(token)
                token = ""
            tokens.append(char)
            depth -= 1
        elif char == ":" and i + 1 < len(s) and s[i + 1] == ":" and depth == 0:
            if token:
                tokens.append(token)
                token = ""
            tokens.append("::")
            i += 1  # Skip the next ':'
        elif char == "#" and depth == 0:
            if token:
                tokens.append(token)
                token = ""
            tokens.append("#")
        else:
            token += char
        i += 1
    if token:
        tokens.append(token)
    return tokens


class FQNParser:
    def __init__(self, s: str) -> None:
        self.tokens = tokenize(s)
        self.i = 0
        self.level = 0

    def peek(self) -> Optional[str]:
        while self.i < len(self.tokens) and self.tokens[self.i].isspace():
            self.i += 1
        if self.i >= len(self.tokens):
            return None
        return self.tokens[self.i]

    def parse(self) -> "FQN":
        fqn = self.parse_fqn()
        if self.i < len(self.tokens):
            tok = self.tokens[self.i]
            raise ValueError(f"Unexpected token: {tok}")
        return fqn

    def parse_fqn(self) -> "FQN":
        parts = []
        while True:
            parts.append(self.parse_part())
            if self.peek() == "::":
                self.expect("::")
            else:
                break

        if self.peek() == "#":
            self.expect("#")
            suffix = self.parse_suffix()
            # Create a new NSPart with the suffix for the last part
            last_part = parts[-1]
            parts[-1] = NSPart(last_part.name, last_part.qualifiers, suffix)

        return FQN(parts)

    def parse_part(self) -> NSPart:
        name = self.parse_name()
        if self.peek() == "[":
            self.expect("[")
            qualifiers = self.parse_qualifiers()
            self.expect("]")
            return NSPart(name, qualifiers)
        else:
            return NSPart(name, ())

    def parse_qualifiers(self) -> tuple["FQN", ...]:
        qualifiers = []
        while True:
            qualifiers.append(self.parse_fqn())
            if self.peek() is None:
                raise ValueError("Unclosed bracket")
            elif self.peek() == ",":
                self.expect(",")
            elif self.peek() == "]":
                break
        return tuple(qualifiers)

    def parse_name(self) -> str:
        name = self.peek()
        self.i += 1
        assert name is not None
        return name

    def parse_suffix(self) -> str:
        suffix = self.peek()
        self.i += 1
        assert suffix is not None
        return suffix

    def expect(self, token: str) -> None:
        if self.peek() != token:
            raise ValueError(f"Expected {token}, got {self.peek()}")
        self.i += 1
