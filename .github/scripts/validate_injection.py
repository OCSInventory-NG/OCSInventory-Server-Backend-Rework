#!/usr/bin/env python3
"""
Post-run gate for .github/workflows/loadtest.yml.

Locust exiting 0 only means no request failed; it says nothing about whether
the run landed anything. This logs in as admin and checks, domain by domain,
that the platform holds what the locustfiles were supposed to create.
"""

import argparse
import ast
import json
import os
import sys

import requests

# Depends on the automation engine firing, not on the injection: reported,
# never fatal.
INFORMATIONAL = {"Automation history"}


class ValidationError(Exception):
    pass


def count_list_literal(path, name):
    """Length of a module-level `NAME = [...]`, read without importing."""
    try:
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
    except (OSError, SyntaxError):
        return None

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if name in targets and isinstance(node.value, (ast.List, ast.Tuple)):
            return len(node.value.elts)
    return None


def load_expectations(loadtest_dir):
    """
    Expected roster sizes, read from the loadtest checkout so they track it
    instead of drifting. Unresolvable values fall back to "at least one".
    """
    expectations = {"users": 1, "roles": 1, "sites": 1}

    if not loadtest_dir:
        return expectations

    users_py = os.path.join(loadtest_dir, "common", "users.py")
    sites_py = os.path.join(loadtest_dir, "common", "sites.py")

    users = count_list_literal(users_py, "USERS")
    roles = count_list_literal(users_py, "ROLES")
    sites = count_list_literal(sites_py, "SITES")

    if users is None or roles is None or sites is None:
        print(
            "::warning::could not read the loadtest rosters from "
            f"{loadtest_dir}; falling back to >0 checks"
        )
        return expectations

    # +1 for the admin superuser created by the initial migration.
    expectations["users"] = users + 1
    expectations["roles"] = roles
    expectations["sites"] = sites
    return expectations


def get_token(base_url, username, password):
    response = requests.post(
        f"{base_url}/api-auth/token",
        headers={"Content-Type": "application/json"},
        data=json.dumps({"username": username, "password": password}),
        timeout=30,
    )
    if response.status_code != 200:
        raise ValidationError(
            f"authentication as '{username}' failed "
            f"(HTTP {response.status_code}): {response.text[:300]}"
        )

    token = response.json().get("token")
    if not token:
        raise ValidationError(f"no token in auth response: {response.text[:300]}")
    return token


def fetch(base_url, headers, path, params=None):
    response = requests.get(
        f"{base_url}{path}", headers=headers, params=params, timeout=120
    )
    if response.status_code != 200:
        raise ValidationError(
            f"GET {path} returned HTTP {response.status_code}: {response.text[:300]}"
        )
    return response


def count(base_url, headers, path):
    """
    Number of objects behind a list endpoint. The API paginates only when
    `limit` is passed, so limit=1 is the cheap way to get an authoritative
    count.
    """
    payload = fetch(base_url, headers, path, params={"limit": 1}).json()

    if isinstance(payload, dict) and "count" in payload:
        return payload["count"]
    if isinstance(payload, list):
        return len(payload)
    raise ValidationError(f"unexpected payload shape for {path}: {type(payload)}")


def sample(base_url, headers, path, limit=50):
    payload = fetch(base_url, headers, path, params={"limit": limit}).json()
    if isinstance(payload, dict):
        return payload.get("results", [])
    return payload if isinstance(payload, list) else []


def build_volume_checks(expectations, min_assets):
    """
    (label, endpoint, minimum) per domain. Fixed rosters get their exact
    expected size; volume and probabilistic domains only have to be non-empty,
    since a tighter bound there would just make the job flaky.
    """
    return [
        ("Assets", "/asset/bases/", min_assets),
        ("Asset logs", "/asset/logs/", 1),
        ("Asset groups", "/asset/groups/", 1),
        ("Asset notes", "/notes/", 1),
        ("Users", "/users/", expectations["users"]),
        ("Roles (auth groups)", "/groups/", expectations["roles"]),
        ("Accountinfo configs", "/accountinfo/config/", 1),
        ("Accountinfo values", "/accountinfo/value/", 1),
        ("Accountinfo data (assigned)", "/accountinfo/data/", 1),
        ("Networks", "/networks/", 1),
        ("Netgroups", "/netgroups/", 1),
        ("Netdevices", "/netdevices/", 1),
        ("SNMP configs", "/snmp/config/", 1),
        ("SNMP scanners", "/snmp/scanner/", 1),
        ("Deployment packages", "/deployment/packages/", 1),
        ("Deployment actions", "/deployment/actions/", 1),
        ("Deployment results", "/deployment/results/", 1),
        ("Automation rules", "/automation/rule/", 1),
        ("Automation schedulers", "/automation/scheduler/", 1),
        ("Automation history", "/automation/history/", 1),
        ("Saved searches", "/search/save/", 1),
    ]


def run_volume_checks(base_url, headers, checks):
    failures = []
    counts = {}
    width = max(len(label) for label, _, _ in checks)

    print("\nInjected volume per domain")
    print("-" * (width + 34))

    for label, path, minimum in checks:
        try:
            found = count(base_url, headers, path)
        except ValidationError as exc:
            counts[label] = None
            print(f"  {label.ljust(width)}  {'ERROR':>8}  (min {minimum:>4})  <- {exc}")
            if label not in INFORMATIONAL:
                failures.append(f"{label}: {exc}")
            continue

        counts[label] = found
        if found >= minimum:
            status = "OK"
        elif label in INFORMATIONAL:
            status = "SKIP"
        else:
            status = "FAIL"
            failures.append(
                f"{label}: only {found} object(s) on {path}, "
                f"expected at least {minimum}"
            )

        print(f"  {label.ljust(width)}  {found:>8}  (min {minimum:>4})  {status}")

    print("-" * (width + 34))
    return failures, counts


def run_content_checks(base_url, headers):
    """Rows with the right shape but no usable content still pass a count."""
    failures = []
    print("\nContent spot-checks")
    print("-" * 60)

    def report(label, ok, detail):
        print(f"  {'OK  ' if ok else 'FAIL'}  {label}: {detail}")
        if not ok:
            failures.append(f"{label}: {detail}")

    assets = sample(base_url, headers, "/asset/bases/")
    if not assets:
        report("assets", False, "no asset returned by /asset/bases/?limit=50")
    else:
        named = [a for a in assets if a.get("name")]
        with_os = [a for a in assets if a.get("osname")]
        distinct_os = {a.get("osname") for a in with_os}
        report(
            "assets have a name",
            len(named) == len(assets),
            f"{len(named)}/{len(assets)} sampled assets have a non-empty name",
        )
        report(
            "assets have an OS",
            len(with_os) == len(assets),
            f"{len(with_os)}/{len(assets)} sampled assets have osname set",
        )
        report(
            "OS variety",
            len(distinct_os) > 1,
            f"{len(distinct_os)} distinct osname value(s) in the sample",
        )

    configs = sample(base_url, headers, "/accountinfo/config/", limit=50)
    if configs:
        selects = [c for c in configs if c.get("datatype") == "SELECT"]
        filled = [c for c in selects if c.get("accountinfo_values")]
        report(
            "SELECT admin-data fields have values",
            not selects or len(filled) == len(selects),
            f"{len(filled)}/{len(selects)} SELECT config(s) have at least one value",
        )

    assigned = sample(base_url, headers, "/accountinfo/data/", limit=50)
    if assigned:
        bound = [
            a
            for a in assigned
            if a.get("accountdata") and a.get("object_slug") and a.get("object_id")
        ]
        report(
            "assigned admin data is bound",
            len(bound) == len(assigned),
            f"{len(bound)}/{len(assigned)} sampled rows carry accountdata "
            f"and target an object",
        )

        # Counted per slug, not sampled: rows come back in insertion order, so
        # whichever fleet was populated first can fill the page on its own.
        for label, slug in (
            ("assets", "inventory_base.inventorybase"),
            ("netdevices", "netdevice.netdevice"),
        ):
            try:
                found = count(
                    base_url, headers, f"/accountinfo/data/?object_slug={slug}"
                )
            except ValidationError as exc:
                report(f"admin data on {label}", False, str(exc))
                continue
            report(
                f"admin data on {label}",
                found > 0,
                f"{found} row(s) targeting {slug}",
            )

    netdevices = sample(base_url, headers, "/netdevices/", limit=20)
    if netdevices:
        with_ip = [n for n in netdevices if n.get("ip")]
        report(
            "netdevices have an IP",
            len(with_ip) == len(netdevices),
            f"{len(with_ip)}/{len(netdevices)} sampled netdevices have an ip",
        )

    results = sample(base_url, headers, "/deployment/results/", limit=20)
    if results:
        linked = [
            r
            for r in results
            if r.get("package") and (r.get("asset") or r.get("group"))
        ]
        report(
            "deployment results are linked",
            len(linked) == len(results),
            f"{len(linked)}/{len(results)} sampled results reference a package "
            f"and an asset or group",
        )
        statuses = {r.get("status") for r in results}
        report(
            "deployment statuses vary",
            len(statuses) > 1,
            f"{len(statuses)} distinct status value(s) in the sample",
        )

    print("-" * 60)
    return failures


def read_demo_credentials(loadtest_dir):
    """(username, password) of the first roster entry, read without importing."""
    path = os.path.join(loadtest_dir, "common", "users.py")
    try:
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), filename=path)
    except (OSError, SyntaxError):
        return None

    default_password, first_user = None, None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]

        if "DEFAULT_PASSWORD" in targets and isinstance(node.value, ast.Constant):
            default_password = node.value.value
        elif (
            "USERS" in targets
            and isinstance(node.value, ast.List)
            and node.value.elts
            and isinstance(node.value.elts[0], ast.Dict)
        ):
            first_user = node.value.elts[0]

    if first_user is None:
        return None

    entry = {}
    for key, value in zip(first_user.keys, first_user.values):
        if isinstance(key, ast.Constant) and isinstance(value, ast.Constant):
            entry[key.value] = value.value

    username = entry.get("username")
    password = entry.get("password", default_password)
    if not username or not password:
        return None
    return username, password


def check_demo_user_login(base_url, loadtest_dir):
    """The demo operators must be able to authenticate, not merely exist."""
    if not loadtest_dir:
        return []

    credentials = read_demo_credentials(loadtest_dir)
    if credentials is None:
        print("\n  SKIP  demo user login: no roster credentials found")
        return []

    username, password = credentials
    try:
        get_token(base_url, username, password)
    except ValidationError as exc:
        return [f"demo user login: {exc}"]

    print(f"\n  OK    demo user login: '{username}' authenticated successfully")
    return []


def write_summary(counts, checks, failures):
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    minimums = {label: minimum for label, _, minimum in checks}
    lines = [
        "## Locust data injection",
        "",
        f"**Result:** {'FAILED' if failures else 'PASSED'}",
        "",
        "| Domain | Injected | Minimum | Status |",
        "| --- | ---: | ---: | --- |",
    ]

    for label, _, minimum in checks:
        found = counts.get(label)
        if found is None:
            status = "error"
        elif found >= minimum:
            status = "pass"
        elif label in INFORMATIONAL:
            status = "skipped"
        else:
            status = "fail"
        shown = "-" if found is None else found
        lines.append(f"| {label} | {shown} | {minimums[label]} | {status} |")

    if failures:
        lines += ["", "### Problems", ""]
        lines += [f"- {failure}" for failure in failures]

    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.getenv("OCS_BASE_URL", "http://localhost:8000"),
        help="Backend base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--loadtest-dir",
        default=os.getenv("LOADTEST_DIR"),
        help="Path to the OCSInventory-Loadtest-Rework checkout",
    )
    parser.add_argument(
        "--min-assets",
        type=int,
        default=int(os.getenv("MIN_ASSETS", "20")),
        help="Minimum number of assets the run must have created "
        "(default: %(default)s)",
    )
    parser.add_argument("--username", default=os.getenv("OCS_USERNAME", "admin"))
    parser.add_argument("--password", default=os.getenv("OCS_PASSWORD", "admin"))
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    print(f"Validating data injection on {base_url}")

    expectations = load_expectations(args.loadtest_dir)

    try:
        token = get_token(base_url, args.username, args.password)
    except ValidationError as exc:
        print(f"\n::error::{exc}")
        return 1

    headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}

    checks = build_volume_checks(expectations, args.min_assets)
    failures, counts = run_volume_checks(base_url, headers, checks)
    failures += run_content_checks(base_url, headers)
    failures += check_demo_user_login(base_url, args.loadtest_dir)

    write_summary(counts, checks, failures)

    if failures:
        print(f"\nData injection validation FAILED ({len(failures)} problem(s)):")
        for failure in failures:
            print(f"  - {failure}")
            print(f"::error::{failure}")
        return 1

    total = sum(c for c in counts.values() if c)
    print(
        f"\nData injection validation PASSED - {total} object(s) across "
        f"{len(checks)} domain(s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
