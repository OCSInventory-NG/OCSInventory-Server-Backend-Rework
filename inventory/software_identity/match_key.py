import re

_PARENTHESES = re.compile(r"\([^)]*\)")
_DOTTED_VERSION = re.compile(r"v?\d+(\.\d+)+\S*")


def match_key(name):
    """
    Product key of a Windows or macOS software name, shared by all its
    versions: lowercased, without parentheses and dotted version numbers.
    Plain numbers and years stay (Visual Studio 2026 is its own product).
    """
    text = _PARENTHESES.sub(" ", (name or "").lower())
    text = _DOTTED_VERSION.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s*-$", "", text).strip()
