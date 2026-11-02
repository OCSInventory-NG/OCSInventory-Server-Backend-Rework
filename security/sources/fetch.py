"""
Downloads of the source files: streamed to a temporary file, asked again only
when the server says the file changed (ETag, Last-Modified).
"""

import os
import tempfile

import requests

TIMEOUT = 900
CHUNK = 1 << 20


class Unchanged(Exception):
    """The server answered 304: the file is the one already loaded."""


def http_get(url, headers):
    response = requests.get(url, headers=headers, stream=True, timeout=TIMEOUT)
    if response.status_code != 304:
        response.raise_for_status()
    return response


def conditional_headers(fingerprint):
    headers = {}
    if fingerprint.get("etag"):
        headers["If-None-Match"] = fingerprint["etag"]
    if fingerprint.get("last_modified"):
        headers["If-Modified-Since"] = fingerprint["last_modified"]
    return headers


def download(url, fingerprint=None, get=http_get):
    """
    (path of a temporary file, new fingerprint). Raises Unchanged when the
    file did not change since the fingerprint. The caller deletes the file.
    """
    response = get(url, conditional_headers(fingerprint or {}))
    if response.status_code == 304:
        raise Unchanged(url)
    handle, path = tempfile.mkstemp(prefix="ocs-security-")
    try:
        with os.fdopen(handle, "wb") as output:
            for chunk in response.iter_content(CHUNK):
                output.write(chunk)
    except BaseException:
        os.unlink(path)
        raise
    headers = response.headers or {}
    return path, {
        "etag": headers.get("ETag", ""),
        "last_modified": headers.get("Last-Modified", ""),
    }


def read_text(url, get=http_get):
    """A small file (NVD .meta), read at once."""
    response = get(url, {})
    return b"".join(response.iter_content(CHUNK)).decode()
