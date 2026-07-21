"""Atom: fetch data from a REST API and write to CSV.

This is a generic example. For real APIs, Claude Code generates a custom atom
per API with specific auth, pagination, and parsing logic. This atom handles
the simplest case: single GET request, JSON array response, flat field extraction.
"""

import csv
import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def _resolve_env_vars(d: dict) -> dict:
    """Resolve ${VAR_NAME} patterns in dict values from os.environ.
    Handles both exact match (value is "${VAR}") and inline ("Bearer ${VAR}")."""
    import re
    pattern = re.compile(r"\$\{([^}]+)\}")
    resolved = {}
    for key, value in d.items():
        if isinstance(value, str) and "${" in value:
            def replacer(m):
                return os.environ.get(m.group(1), "")
            resolved[key] = pattern.sub(replacer, value)
            if not resolved[key] and value != resolved[key]:
                resolved[key] = None  # signal missing env var
        else:
            resolved[key] = value
    return resolved


def execute(params_json: str) -> str:
    """
    Params: {
        "endpoint": str,
        "method": "GET" (default),
        "headers": {"Header-Name": "value"},  # optional
        "params": {"key": "value"},            # query params, optional
        "response_format": "json",             # json | csv | xml
        "data_path": "results.items",          # dot-path to array in response, optional
        "field_mapping": {"output_col": "response_field"},  # optional, extracts subset
        "target_path": str
    }

    Auth: atoms read credentials from os.environ (loaded by framework from env_file).
    The config should specify which env vars to use in headers, e.g.:
        "headers": {"Authorization": "Bearer ${API_TOKEN}"}
    The framework does NOT interpolate — the atom must read os.environ directly.

    Returns: {"success": bool, "message": str, "row_count": int}
    """
    try:
        params = json.loads(params_json)
        endpoint = params["endpoint"]
        method = params.get("method", "GET")
        headers = params.get("headers", {})
        query_params = params.get("params", {})
        response_format = params.get("response_format", "json")
        data_path = params.get("data_path")
        field_mapping = params.get("field_mapping")
        target_path = params["target_path"]

        # Resolve env var references (pattern: ${VAR_NAME}) in headers and params
        resolved_headers = _resolve_env_vars(headers)
        query_params = _resolve_env_vars(query_params)

        missing = [k for k, v in {**resolved_headers, **query_params}.items() if v is None]
        if missing:
            return json.dumps({"success": False, "row_count": 0,
                               "message": f"Unresolved env vars for keys: {missing}"})

        # Build URL with query params
        if query_params:
            from urllib.parse import urlencode
            endpoint = f"{endpoint}?{urlencode(query_params)}"

        # Make request
        req = Request(endpoint, method=method, headers=resolved_headers)
        try:
            with urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
        except HTTPError as e:
            return json.dumps({"success": False, "row_count": 0,
                               "message": f"HTTP {e.code}: {e.reason}"})
        except URLError as e:
            return json.dumps({"success": False, "row_count": 0,
                               "message": f"Connection failed: {e.reason}"})

        # Parse response
        if response_format == "json":
            data = json.loads(raw)
            if data_path:
                for key in data_path.split("."):
                    if isinstance(data, dict):
                        data = data[key]
                    elif isinstance(data, list) and key.isdigit():
                        data = data[int(key)]
            if not isinstance(data, list):
                data = [data]
        elif response_format == "csv":
            import io
            reader = csv.DictReader(io.StringIO(raw))
            data = list(reader)
        elif response_format == "xml":
            from xml.etree import ElementTree as ET
            root = ET.fromstring(raw)
            data = []
            for item in root:
                row = {}
                for child in item:
                    row[child.tag] = child.text
                data.append(row)
        else:
            return json.dumps({"success": False, "row_count": 0,
                               "message": f"Unsupported response_format: {response_format}"})

        if not data:
            return json.dumps({"success": False, "row_count": 0,
                               "message": "API returned no data."})

        # Apply field mapping (rename/subset)
        if field_mapping:
            mapped_data = []
            for row in data:
                mapped_row = {}
                for output_col, source_field in field_mapping.items():
                    # Support dot notation for nested fields
                    value = row
                    for part in source_field.split("."):
                        if isinstance(value, dict):
                            value = value.get(part)
                        else:
                            value = None
                            break
                    # Flatten lists to comma-separated for CSV
                    if isinstance(value, list):
                        value = ",".join(str(v) for v in value)
                    mapped_row[output_col] = value
                mapped_data.append(mapped_row)
            data = mapped_data

        # Write CSV
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        fieldnames = list(data[0].keys())
        with open(target_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

        return json.dumps({"success": True, "row_count": len(data),
                           "message": f"Fetched {len(data)} records from API, written to {target_path}."})

    except Exception as e:
        return json.dumps({"success": False, "row_count": 0, "message": str(e)})
