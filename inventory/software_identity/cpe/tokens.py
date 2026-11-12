import re

# Version-like words ("154.0.1", "v2", "8.9.6.4") never identify a product
VERSION_TOKEN = re.compile(r"^v?\d+([._]\d+)*[a-z]?\d*$", re.IGNORECASE)
TITLE_VERSION_TOKEN = re.compile(r"^v?\d+([.\-_]\d+)*[a-z]?\d*$", re.IGNORECASE)
NOISE = {
    "x64",
    "x86",
    "64-bit",
    "32-bit",
    "bit",
    "amd64",
    "arm64",
    "fr",
    "en",
    "de",
    "us",
    "for",
    "the",
    "and",
    "of",
    "pour",
    "from",
    "with",
    "version",
    "release",
    "edition",
    "windows",
    "win",
    "macos",
    "mac",
    "os",
    "linux",
    "iphone",
    "ipad",
    "android",
    "x",
}


def tokens(text):
    """Words that identify a product, shared by software names and CPE titles."""
    text = re.sub(r"\([^)]*\)", " ", (text or "").lower())
    out = []
    for raw in re.split(r"[\s_/,;:]+", text):
        raw = raw.strip(" .-")
        if not raw or VERSION_TOKEN.match(raw):
            continue
        for part in raw.split("-"):
            part = part.strip(".")
            if part and part not in NOISE and not (part.isdigit() and len(part) > 2):
                out.append(part)
    return out


def base_title(title, version):
    """CPE title without its version ("Mozilla Firefox 154.0.1": "mozilla firefox")."""
    text = (title or "").lower()
    if version and version not in ("*", "-"):
        text = text.replace(version.lower(), " ")
    text = re.sub(r"\([^)]*\)", " ", text)
    words = [word.strip(" ,;:-") for word in re.split(r"[\s/,]+", text)]
    return " ".join(
        word for word in words if word and not TITLE_VERSION_TOKEN.match(word)
    )


def title_entries(vendor, product, titles):
    """
    Word sets of a product's titles, and the vendor words a name may omit.
    Vendor words that are also the product's own name stay required
    (git-scm:git keeps "git"). A title reduced to vendor words ("Microsoft
    Windows 7" gives "microsoft") falls back on the product name of the key.
    """
    product_tokens = set(tokens(product.replace("_", " ")))
    vendor_tokens = set(tokens(vendor.replace("_", " "))) - product_tokens
    entries = []
    for title in titles:
        words = frozenset(tokens(title))
        if not words - vendor_tokens:
            words = frozenset(words | product_tokens)
        if words and words not in entries:
            entries.append(words)
    return vendor_tokens, entries
