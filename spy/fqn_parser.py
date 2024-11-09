from typing import Optional
import re
from dataclasses import dataclass
from .fqn import NSPart, QN


def tokenize(s: str) -> list[str]:
    tokens = []
    token = ''
    depth = 0
    i = 0
    while i < len(s):
        char = s[i]
        if char.isspace():
            i += 1
            continue
        if char in '[],' and depth == 0:
            if token:
                tokens.append(token)
                token = ''
            tokens.append(char)
        elif char == '[':
            if token:
                tokens.append(token)
                token = ''
            tokens.append(char)
            depth += 1
        elif char == ']':
            if token:
                tokens.append(token)
                token = ''
            tokens.append(char)
            depth -= 1
        elif char == ':' and i + 1 < len(s) and s[i + 1] == ':' and depth == 0:
            if token:
                tokens.append(token)
                token = ''
            tokens.append('::')
            i += 1  # Skip the next ':'
        else:
            token += char
        i += 1
    if token:
        tokens.append(token)
    return tokens


class QNParser:
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

    def parse(self) -> 'QN':
        qn = self.parse_qn()
        if self.i < len(self.tokens):
            tok = self.tokens[self.i]
            raise ValueError(f'Unexpected token: {tok}')
        return qn

    def parse_qn(self) -> 'QN':
        parts = []
        while True:
            parts.append(self.parse_part())
            if self.peek() == '::':
                self.expect('::')
            else:
                break
        return QN(parts)

    def parse_part(self) -> NSPart:
        name = self.parse_name()
        if self.peek() == '[':
            self.expect('[')
            qualifiers = self.parse_qualifiers()
            self.expect(']')
            return NSPart(name, qualifiers)
        else:
            return NSPart(name, [])

    def parse_qualifiers(self) -> list['QN']:
        qualifiers = []
        while True:
            qualifiers.append(self.parse_qn())
            if self.peek() is None:
                raise ValueError('Unclosed bracket')
            elif self.peek() == ',':
                self.expect(',')
            elif self.peek() == ']':
                break
        return qualifiers

    def parse_name(self) -> str:
        name = self.peek()
        self.i += 1
        assert name is not None
        return name

    def expect(self, token: str) -> None:
        if self.peek() != token:
            raise ValueError(f"Expected {token}, got {self.peek()}")
        self.i += 1
