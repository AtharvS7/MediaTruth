"""Offline C2PA inspection. Signed provenance is separate from pixel inference."""
import json


def inspect_provenance(path: str) -> dict:
    result = {"status": "not_checked", "network_access": False,
              "trust_policy": "SDK built-in trust anchors; offline revocation checks",
              "actions": [], "watermark_status": "not_checked"}
    try:
        from c2pa import Context, Reader, C2paError
    except (ImportError, OSError):
        return result
    try:
        with Context.from_dict({
            "verify": {"verify_after_reading": True, "verify_trust": True,
                       "verify_timestamp_trust": True, "remote_manifest_fetch": False,
                       "ocsp_fetch": False},
            "core": {"allowed_network_hosts": [], "backing_store_memory_threshold_in_mb": 16},
        }) as context:
            with Reader(path, context=context) as reader:
                data = json.loads(reader.json())
        active = data.get("active_manifest")
        if not active:
            result["status"] = "absent"
            return result
        state = str(data.get("validation_state", "")).lower()
        result["status"] = {"trusted": "trusted", "valid": "valid_untrusted",
                            "invalid": "invalid"}.get(state, "unverified")
        manifest = data.get("manifests", {}).get(active, {})
        for assertion in manifest.get("assertions", [])[:100]:
            if str(assertion.get("label", "")).startswith("c2pa.actions"):
                for action in assertion.get("data", {}).get("actions", [])[:50]:
                    result["actions"].append({
                        "action": str(action.get("action", ""))[:200],
                        "digital_source_type": str(action.get("digitalSourceType", ""))[:300],
                    })
        result["actions"] = result["actions"][:50]
    except C2paError.ManifestNotFound:
        result["status"] = "absent"
    except C2paError.RemoteManifest:
        result["status"] = "remote_not_checked"
    except C2paError.NotSupported:
        result["status"] = "unsupported"
    except (C2paError, ValueError, TypeError, AttributeError):
        result["status"] = "unreadable"
    return result
