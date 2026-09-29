"""Check upstream release advisories for official CPU wheels skipped by pip-audit.

This complements package auditing; it does not scan native binary contents.
"""
from importlib.metadata import version
import requests


def main():
    findings = []
    for name in ("torch", "torchvision"):
        upstream = version(name).split("+", 1)[0]
        response = requests.post("https://api.osv.dev/v1/query", json={
            "package": {"name": name, "ecosystem": "PyPI"}, "version": upstream,
        }, timeout=30)
        response.raise_for_status()
        advisories = [item["id"] for item in response.json().get("vulns", [])]
        print(f"{name} {upstream} upstream advisories: {advisories}")
        findings.extend(advisories)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
