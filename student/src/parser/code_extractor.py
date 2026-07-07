from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass


@dataclass
class ExtractionResult:
    code: str
    matched_format: str
    malformed: bool = False


_PYTHON_BLOCK_RE = re.compile(
    r"```(?:python)?\s*\n([\s\S]*?)\n?```", re.IGNORECASE
)

_XML_INVOKE_RE = re.compile(
    r'<invoke\s+name=["\']([\w\.]+)["\']\s*>([\s\S]*?)</invoke>',
    re.IGNORECASE,
)
_XML_PARAM_RE = re.compile(
    r'<parameter\s+name=["\']([\w\.]+)["\']\s*>([\s\S]*?)</parameter>',
    re.IGNORECASE,
)

_JSON_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*([\s\S]*?)\s*</tool_call>", re.IGNORECASE
)

_REACT_RE = re.compile(
    r"Action:\s*([\w\.]+)\s*\n\s*Action Input:\s*(\{[\s\S]*?\}|\S.*)",
    re.IGNORECASE,
)


def _py_literal(value: str) -> str:
    stripped = value.strip()
    try:
        return repr(json.loads(stripped))
    except (json.JSONDecodeError, ValueError):
        return repr(stripped)


def _call_from_name_and_args(name: str, args: dict) -> str:
    parts = []
    for k, v in args.items():
        if isinstance(v, (int, float, bool, list, dict)):
            parts.append(f"{k}={v!r}")
        else:
            parts.append(f"{k}={_py_literal(str(v))}")
    kwargs = ", ".join(parts)
    return f"result = {name}({kwargs})\nprint(result)"


def _extract_xml(text: str) -> ExtractionResult | None:
    match = _XML_INVOKE_RE.search(text)
    if not match:
        return None

    name, body = match.group(1), match.group(2)
    params = _XML_PARAM_RE.findall(body)
    args = {}
    for pname, pvalue in params:
        args[pname] = pvalue.strip()

    if not params and body.strip():
        return ExtractionResult(
            code=f"result = {name}()\nprint(result)",
            matched_format="xml",
            malformed=True,
        )

    return ExtractionResult(
        code=_call_from_name_and_args(name, args),
        matched_format="xml",
    )


def _extract_json_tool_call(text: str) -> ExtractionResult | None:
    match = _JSON_TOOL_CALL_RE.search(text)
    if not match:
        return None

    raw = match.group(1).strip()
    try:
        payload = json.loads(raw)
        name = payload.get("name") or payload.get("tool")
        args = payload.get(
            "arguments", payload.get("parameters", {})
        ) or {}
        if not name:
            raise ValueError("missing tool name")
        return ExtractionResult(
            code=_call_from_name_and_args(name, args),
            matched_format="json",
        )
    except (json.JSONDecodeError, ValueError, AttributeError):
        return ExtractionResult(
            code=f"# {raw}",
            matched_format="json",
            malformed=True,
        )


def _extract_react(text: str) -> ExtractionResult | None:
    match = _REACT_RE.search(text)
    if not match:
        return None

    name, raw_input = match.group(1), match.group(2).strip()
    try:
        args = json.loads(raw_input)
        if not isinstance(args, dict):
            args = {"value": args}
    except json.JSONDecodeError:
        args = {"value": raw_input}

    return ExtractionResult(
        code=_call_from_name_and_args(name, args),
        matched_format="react",
    )


def extract_code(text: str) -> ExtractionResult:
    if not text or not text.strip():
        return ExtractionResult(
            code="", matched_format="none", malformed=True
        )

    python_blocks = _PYTHON_BLOCK_RE.findall(text)
    if python_blocks:
        code = "\n".join(b.strip() for b in python_blocks).strip()
        try:
            ast.parse(code)
            return ExtractionResult(code=code, matched_format="python")
        except SyntaxError:
            return ExtractionResult(
                code=code, matched_format="python", malformed=True
            )

    for extractor in (_extract_xml, _extract_json_tool_call, _extract_react):
        result = extractor(text)
        if result is not None:
            return result

    return ExtractionResult(
        code=text.strip(), matched_format="none", malformed=True
    )
