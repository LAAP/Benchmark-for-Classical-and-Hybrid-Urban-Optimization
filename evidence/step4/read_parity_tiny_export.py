import json
from pathlib import Path

base = Path("evidence/step4")
json_path = base / "parity_tiny_export.json"
csv_path = base / "parity_tiny_export.csv"

data = json.loads(json_path.read_text())
stats = data["stats"]
exp = data["experiment"]

print("=== FAIRNESS CLASSIFICATION ===")
print(exp["config"]["fairness_classification"])

print("\n=== FAIRNESS REPORT ===")
print(json.dumps(stats["fairness_report"], indent=2))

print("\n=== BACKEND TYPE ===")
hybrid_backend = next(t["backend_type"] for t in exp["trials"] if t["solver_kind"] == "hybrid")
print(hybrid_backend)

print("\n=== RUNTIME SUMMARY ===")
print(json.dumps({"classical": stats["classical"]["runtime"], "hybrid": stats["hybrid"]["runtime"]}, indent=2))

print("\n=== OBJECTIVE SUMMARY ===")
print(json.dumps({"classical": stats["classical"]["objective"], "hybrid": stats["hybrid"]["objective"]}, indent=2))

print("\n=== FEASIBILITY RATE ===")
print(json.dumps({"classical": stats["classical"]["feasibility_rate"], "hybrid": stats["hybrid"]["feasibility_rate"]}, indent=2))

print("\n=== VIOLATION BREAKDOWN ===")
print(json.dumps({"classical": stats["classical"]["violation_breakdown_mean"], "hybrid": stats["hybrid"]["violation_breakdown_mean"]}, indent=2))

print("\n=== JSON REPRESENTATIVE (first 1600 chars) ===")
print(json_path.read_text()[:1600])

print("\n=== CSV REPRESENTATIVE (full file) ===")
print(csv_path.read_text())
