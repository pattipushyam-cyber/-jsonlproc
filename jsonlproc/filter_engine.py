"""Expression parser and evaluator for record filtering."""
from __future__ import annotations

import re
from typing import Any

from .exceptions import ParseError

# ---------------------------------------------------------------------------
# Token types
# ---------------------------------------------------------------------------
TOK_EOF = "EOF"
TOK_LPAREN = "LPAREN"
TOK_RPAREN = "RPAREN"
TOK_AND = "AND"
TOK_OR = "OR"
TOK_NOT = "NOT"
TOK_IN = "IN"
TOK_CONTAINS = "CONTAINS"
TOK_EXISTS = "EXISTS"
TOK_EQ = "EQ"
TOK_NEQ = "NEQ"
TOK_LT = "LT"
TOK_LTE = "LTE"
TOK_GT = "GT"
TOK_GTE = "GTE"
TOK_COMMA = "COMMA"
TOK_LBRACKET = "LBRACKET"
TOK_RBRACKET = "RBRACKET"
TOK_IDENT = "IDENT"
TOK_STRING = "STRING"
TOK_NUMBER = "NUMBER"
TOK_BOOL = "BOOL"
TOK_NULL = "NULL"

KEYWORDS = {
    "and": TOK_AND,
    "or": TOK_OR,
    "not": TOK_NOT,
    "in": TOK_IN,
    "contains": TOK_CONTAINS,
    "exists": TOK_EXISTS,
    "true": TOK_BOOL,
    "false": TOK_BOOL,
    "null": TOK_NULL,
}


class Token:
    """Lexer token."""

    __slots__ = ("type", "value", "pos")

    def __init__(self, type_: str, value: Any, pos: int) -> None:
        self.type = type_
        self.value = value
        self.pos = pos

    def __repr__(self) -> str:
        return f"Token({self.type}, {self.value!r}, pos={self.pos})"


class Lexer:
    """Tokenizes a filter expression string.

    Args:
        text: The filter expression to tokenize.
    """

    TOKEN_PATTERNS = [
        (r"<=", TOK_LTE),
        (r">=", TOK_GTE),
        (r"!=", TOK_NEQ),
        (r"==", TOK_EQ),
        (r"<", TOK_LT),
        (r">", TOK_GT),
        (r"\(", TOK_LPAREN),
        (r"\)", TOK_RPAREN),
        (r"\[", TOK_LBRACKET),
        (r"\]", TOK_RBRACKET),
        (r",", TOK_COMMA),
        (r"'[^']*'", TOK_STRING),
        (r'"[^"]*"', TOK_STRING),
        (r"-?\d+\.\d+", TOK_NUMBER),
        (r"-?\d+", TOK_NUMBER),
        (r"[A-Za-z_][A-Za-z0-9_.]*", TOK_IDENT),
    ]
    MASTER_RE = re.compile("|".join(f"({p})" for p, _ in TOKEN_PATTERNS), re.IGNORECASE)

    def __init__(self, text: str) -> None:
        self._text = text
        self._pos = 0

    def tokenize(self) -> list[Token]:
        """Return all tokens from the expression.

        Returns:
            Ordered list of Token objects.

        Raises:
            ParseError: If an unexpected character is found.
        """
        tokens: list[Token] = []
        pos = 0
        text = self._text
        while pos < len(text):
            if text[pos].isspace():
                pos += 1
                continue
            m = self.MASTER_RE.match(text, pos)
            if not m:
                raise ParseError(f"Unexpected character '{text[pos]}'", text, pos)
            raw = m.group(0)
            tok_type = self.TOKEN_PATTERNS[m.lastindex - 1][1]
            if tok_type == TOK_IDENT:
                lower = raw.lower()
                tok_type = KEYWORDS.get(lower, TOK_IDENT)
                if tok_type == TOK_BOOL:
                    tokens.append(Token(TOK_BOOL, lower == "true", pos))
                elif tok_type == TOK_NULL:
                    tokens.append(Token(TOK_NULL, None, pos))
                else:
                    tokens.append(Token(tok_type, raw, pos))
            elif tok_type == TOK_STRING:
                tokens.append(Token(TOK_STRING, raw[1:-1], pos))
            elif tok_type == TOK_NUMBER:
                val: int | float = float(raw) if "." in raw else int(raw)
                tokens.append(Token(TOK_NUMBER, val, pos))
            else:
                tokens.append(Token(tok_type, raw, pos))
            pos = m.end()
        tokens.append(Token(TOK_EOF, None, pos))
        return tokens


# ---------------------------------------------------------------------------
# AST node types (plain dicts for simplicity)
# ---------------------------------------------------------------------------
def _cmp_node(op: str, left: Any, right: Any) -> dict:
    return {"type": "cmp", "op": op, "left": left, "right": right}


def _and_node(left: Any, right: Any) -> dict:
    return {"type": "and", "left": left, "right": right}


def _or_node(left: Any, right: Any) -> dict:
    return {"type": "or", "left": left, "right": right}


def _not_node(operand: Any) -> dict:
    return {"type": "not", "operand": operand}


def _in_node(field: Any, values: list) -> dict:
    return {"type": "in", "field": field, "values": values}


def _contains_node(field: Any, value: Any) -> dict:
    return {"type": "contains", "field": field, "value": value}


def _exists_node(field: Any) -> dict:
    return {"type": "exists", "field": field}


def _field_node(path: str) -> dict:
    return {"type": "field", "path": path}


def _lit_node(value: Any) -> dict:
    return {"type": "lit", "value": value}


# ---------------------------------------------------------------------------
# Parser (recursive descent)
# ---------------------------------------------------------------------------
COMP_OPS = {TOK_EQ: "==", TOK_NEQ: "!=", TOK_LT: "<", TOK_LTE: "<=", TOK_GT: ">", TOK_GTE: ">="}


class Parser:
    """Recursive-descent parser for filter expressions.

    Args:
        tokens: List of Token objects from the lexer.
        expression: Original expression string (for error messages).
    """

    def __init__(self, tokens: list[Token], expression: str) -> None:
        self._tokens = tokens
        self._pos = 0
        self._expression = expression

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _consume(self, expected: str | None = None) -> Token:
        tok = self._tokens[self._pos]
        if expected and tok.type != expected:
            raise ParseError(
                f"Expected {expected} but got {tok.type} ({tok.value!r})",
                self._expression,
                tok.pos,
            )
        self._pos += 1
        return tok

    def parse(self) -> dict:
        """Parse the token stream into an AST.

        Returns:
            Root AST node dict.

        Raises:
            ParseError: On syntax errors.
        """
        node = self._parse_or()
        self._consume(TOK_EOF)
        return node

    def _parse_or(self) -> dict:
        left = self._parse_and()
        while self._peek().type == TOK_OR:
            self._consume(TOK_OR)
            right = self._parse_and()
            left = _or_node(left, right)
        return left

    def _parse_and(self) -> dict:
        left = self._parse_not()
        while self._peek().type == TOK_AND:
            self._consume(TOK_AND)
            right = self._parse_not()
            left = _and_node(left, right)
        return left

    def _parse_not(self) -> dict:
        if self._peek().type == TOK_NOT:
            self._consume(TOK_NOT)
            return _not_node(self._parse_not())
        return self._parse_primary()

    def _parse_primary(self) -> dict:
        tok = self._peek()
        if tok.type == TOK_LPAREN:
            self._consume(TOK_LPAREN)
            node = self._parse_or()
            self._consume(TOK_RPAREN)
            return node
        if tok.type == TOK_EXISTS:
            self._consume(TOK_EXISTS)
            field = self._parse_field_path()
            return _exists_node(field)
        return self._parse_comparison()

    def _parse_field_path(self) -> dict:
        """Parse a field path like 'user.name' or 'tags[0]'."""
        tok = self._consume(TOK_IDENT)
        path = tok.value
        # Accumulate dotted segments and bracket indices
        while self._peek().type == TOK_LBRACKET:
            self._consume(TOK_LBRACKET)
            idx = self._consume(TOK_NUMBER)
            self._consume(TOK_RBRACKET)
            path = f"{path}[{int(idx.value)}]"
        return _field_node(path)

    def _parse_value(self) -> dict:
        tok = self._peek()
        if tok.type == TOK_STRING:
            self._consume(TOK_STRING)
            return _lit_node(tok.value)
        if tok.type == TOK_NUMBER:
            self._consume(TOK_NUMBER)
            return _lit_node(tok.value)
        if tok.type == TOK_BOOL:
            self._consume(TOK_BOOL)
            return _lit_node(tok.value)
        if tok.type == TOK_NULL:
            self._consume(TOK_NULL)
            return _lit_node(None)
        # field reference
        return self._parse_field_path()

    def _parse_comparison(self) -> dict:
        left = self._parse_value()
        tok = self._peek()
        if tok.type in COMP_OPS:
            op = COMP_OPS[tok.type]
            self._consume(tok.type)
            right = self._parse_value()
            return _cmp_node(op, left, right)
        if tok.type == TOK_IN:
            self._consume(TOK_IN)
            values = self._parse_value_list()
            return _in_node(left, values)
        if tok.type == TOK_CONTAINS:
            self._consume(TOK_CONTAINS)
            right = self._parse_value()
            return _contains_node(left, right)
        # standalone boolean-like field reference (treated as exists)
        if left["type"] == "field":
            return _exists_node(left)
        return left

    def _parse_value_list(self) -> list:
        """Parse a parenthesised comma-separated value list."""
        self._consume(TOK_LPAREN)
        values = []
        while self._peek().type != TOK_RPAREN:
            v = self._parse_value()
            values.append(v["value"] if v["type"] == "lit" else v)
            if self._peek().type == TOK_COMMA:
                self._consume(TOK_COMMA)
        self._consume(TOK_RPAREN)
        return values


# ---------------------------------------------------------------------------
# Field accessor
# ---------------------------------------------------------------------------
_BRACKET_RE = re.compile(r"(\w+)\[(\d+)\]")


def _get_field(record: dict, path: str) -> Any:
    """Access a nested field using dot-notation and bracket indexing.

    Args:
        record: The source record dict.
        path: Field path like 'user.name' or 'tags[0]'.

    Returns:
        The field value, or a sentinel _MISSING if not found.
    """
    parts = path.split(".")
    obj: Any = record
    for part in parts:
        m = _BRACKET_RE.fullmatch(part)
        if m:
            key, idx = m.group(1), int(m.group(2))
            if not isinstance(obj, dict) or key not in obj:
                return _MISSING
            obj = obj[key]
            if not isinstance(obj, list) or idx >= len(obj):
                return _MISSING
            obj = obj[idx]
        else:
            if not isinstance(obj, dict) or part not in obj:
                return _MISSING
            obj = obj[part]
    return obj


class _MissingSentinel:
    """Singleton sentinel for missing field values."""
    _instance = None

    def __new__(cls) -> "_MissingSentinel":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "MISSING"


_MISSING = _MissingSentinel()


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------
class _Evaluator:
    """Evaluates an AST node against a record."""

    def evaluate(self, node: dict, record: dict) -> bool:
        """Recursively evaluate a node.

        Args:
            node: AST node dict.
            record: The record being tested.

        Returns:
            Boolean result.
        """
        t = node["type"]
        if t == "and":
            return self.evaluate(node["left"], record) and self.evaluate(node["right"], record)
        if t == "or":
            return self.evaluate(node["left"], record) or self.evaluate(node["right"], record)
        if t == "not":
            return not self.evaluate(node["operand"], record)
        if t == "exists":
            return _get_field(record, node["field"]["path"]) is not _MISSING
        if t == "in":
            val = self._resolve(node["field"], record)
            return val in node["values"]
        if t == "contains":
            val = self._resolve(node["field"], record)
            sub = self._resolve(node["value"], record)
            if isinstance(val, str) and isinstance(sub, str):
                return sub in val
            if isinstance(val, list):
                return sub in val
            return False
        if t == "cmp":
            left = self._resolve(node["left"], record)
            right = self._resolve(node["right"], record)
            return self._compare(left, node["op"], right)
        return False

    def _resolve(self, node: dict, record: dict) -> Any:
        """Resolve a node to its concrete value."""
        if node["type"] == "lit":
            return node["value"]
        if node["type"] == "field":
            v = _get_field(record, node["path"])
            return None if v is _MISSING else v
        return None

    def _compare(self, left: Any, op: str, right: Any) -> bool:
        """Perform a comparison, handling None gracefully."""
        try:
            if op == "==":
                return left == right
            if op == "!=":
                return left != right
            if left is None or right is None:
                return False
            if op == "<":
                return left < right
            if op == "<=":
                return left <= right
            if op == ">":
                return left > right
            if op == ">=":
                return left >= right
        except TypeError:
            return False
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
class FilterEngine:
    """Evaluates filter expressions against record dicts.

    Args:
        expression: Filter expression string.

    Example:
        >>> fe = FilterEngine("age >= 18 AND status == 'active'")
        >>> fe.evaluate({"age": 25, "status": "active"})
        True
    """

    def __init__(self, expression: str) -> None:
        self._expression = expression
        self._ast: dict | None = None
        self._evaluator = _Evaluator()

    def compile(self) -> None:
        """Parse the expression into an AST.

        Raises:
            ParseError: If the expression is syntactically invalid.
        """
        tokens = Lexer(self._expression).tokenize()
        self._ast = Parser(tokens, self._expression).parse()

    def evaluate(self, record: dict) -> bool:
        """Test a record against the compiled expression.

        Args:
            record: The dict record to test.

        Returns:
            True if the record matches the expression.

        Raises:
            ParseError: If compile() has not been called and auto-compilation fails.
        """
        if self._ast is None:
            self.compile()
        return self._evaluator.evaluate(self._ast, record)
