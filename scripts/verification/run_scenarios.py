"""Read already observed scenario results from the running Heimdal SaaS."""

import argparse
import json
from pathlib import Path
import ssl

import httpx

NAMES = (
    "Local secret handling", "Outage buffering", "Failed-login detection", "Network degradation",
    "Sustained anomaly", "Alert correlation", "Duplicate and late delivery", "Demo remediation",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=Path(".heimdal/dev"))
    parser.add_argument("--tenant", choices=("alpha", "beta"), default="alpha")
    parser.add_argument("--scenario", type=int, choices=range(1, 9))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        operator = json.loads((args.runtime / f"operator-{args.tenant}.json").read_bytes())
        collector = json.loads((args.runtime / f"collector-{args.tenant}.json").read_bytes())
        tls = ssl.create_default_context(cafile=str(args.runtime / "ca.pem"))
        with httpx.Client(base_url=collector["saas_url"], verify=tls, trust_env=False) as client:
            response = client.get("/api/v1/scenario-results", headers={
                "Authorization": f"Bearer {operator['token']}", "X-Tenant-ID": operator["tenant_id"],
            })
            response.raise_for_status()
            observed = {result["scenario_id"]: result for result in response.json()}
    except (OSError, ValueError, KeyError, httpx.HTTPError):
        parser.exit(2, "BLOCKED: Cannot read live SaaS results with this runtime.\n")

    numbers = [args.scenario] if args.scenario else range(1, 9)
    report = {
        "organizer_input": "unverified",
        "results": [observed.get(number, {"scenario_id": number, "status": "blocked",
                                        "reason_code": "no_observed_run"}) for number in numbers],
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for row in report["results"]:
            number = row["scenario_id"]
            print(f"{number}. {NAMES[number - 1]}: {row['status']}")
        print("V00: BLOCKED until the official organizer stream is verified.")
    statuses = {row["status"] for row in report["results"]}
    return 1 if "failed" in statuses else 0 if statuses == {"passed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
