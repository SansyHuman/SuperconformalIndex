"""FORM execution and parse helpers."""

import tempfile
import subprocess
from pathlib import Path
import time


def run_form(
    program: str,
    *,
    form_executable: str,
    timeout: float,
) -> str:
    """Run FORM in an isolated temporary directory and return standard output."""
    try:
        with tempfile.TemporaryDirectory(
            prefix="form-"
        ) as directory:
            script = Path(directory) / f"tmp_{time.time_ns()}.frm"
            script.write_text(program, encoding="utf-8")
            result = subprocess.run(
                [form_executable, "-q", str(script)],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"FORM executable {form_executable!r} was not found"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("FORM calculation timed out") from exc

    if result.returncode != 0 or result.stderr.strip():
        raise RuntimeError(
            f"FORM failed with code {result.returncode}: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout


def split_top_level(expression: str, separator: str) -> list[str]:
    """Split on one character outside function arguments and exponent signs."""
    result: list[str] = []
    start = 0
    depth = 0
    for position, character in enumerate(expression):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif (
            character == separator
            and depth == 0
            and not (
                separator in "+-"
                and position > 0
                and expression[position - 1] == "^"
            )
        ):
            result.append(expression[start:position])
            start = position + 1
    result.append(expression[start:])
    return result


def split_signed_terms(expression: str) -> list[str]:
    """Split a flat FORM sum while preserving each monomial's sign."""
    result: list[str] = []
    start = 0
    depth = 0
    for position, character in enumerate(expression):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif (
            position > start
            and depth == 0
            and character in "+-"
            and expression[position - 1] != "^"
        ):
            result.append(expression[start:position])
            start = position
    result.append(expression[start:])
    return [term for term in result if term]
