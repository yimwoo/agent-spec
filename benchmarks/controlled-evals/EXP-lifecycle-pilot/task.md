# Task: normalize identifiers without dependencies

The repository's `slugify` helper drops accented Latin letters instead of
normalizing them. Update the implementation so ordinary accented Latin input
produces the corresponding ASCII identifier while preserving current ASCII,
separator-collapsing, trimming, and fallback behavior.

Constraints:

- Use only the Python standard library.
- Keep the public `slugify(value: str, fallback: str = "item") -> str` API.
- Do not change files outside `src/identifier.py` and `tests/`.
- Add or update public regression tests.
- Run `python -m unittest discover -s tests -v` before finishing.
