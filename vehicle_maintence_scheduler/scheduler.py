import os
import requests

SERVICE_BASE = "http://4.224.186.213/evaluation-service"

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJNYXBDbGFpbXMiOnsiYXVkIjoiaHR0cDovLzIwLjI0NC41Ni4xNDQvZXZhbHVhdGlvbi1zZXJ2aWNlIiwiZW1haWwiOiJuYWJkdXNzYW1pQGdtYWlsLmNvbSIsImV4cCI6MTc3ODkyOTQzOSwiaWF0IjoxNzc4OTI4NTM5LCJpc3MiOiJBZmZvcmQgTWVkaWNhbCBUZWNobm9sb2dpZXMgUHJpdmF0ZSBMaW1pdGVkIiwianRpIjoiNTNlYzM0ZmMtZTFhNi00NzU3LThjYTAtYjY1NWU5MGFlMTNmIiwibG9jYWxlIjoiZW4tSU4iLCJuYW1lIjoibiBhYmR1cyBzYW1pIiwic3ViIjoiYmFmMTQ4NzYtNGM5Yy00YjkzLWIxMGYtMDI5ZDEwZDVjZjJkIn0sImVtYWlsIjoibmFiZHVzc2FtaUBnbWFpbC5jb20iLCJuYW1lIjoibiBhYmR1cyBzYW1pIiwicm9sbE5vIjoiMjJtaWM3MjI1IiwiYWNjZXNzQ29kZSI6IlNmRnVXZyIsImNsaWVudElEIjoiYmFmMTQ4NzYtNGM5Yy00YjkzLWIxMGYtMDI5ZDEwZDVjZjJkIiwiY2xpZW50U2VjcmV0IjoicEd5YkpVclVFbnRqUE5NcCJ9.DVvXnJYc3Hx7eCFpJv0xkZH1ieGpP82MvpkpQusW0QY"


def _headers():
    return {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}


def pull_depots():
    resp = requests.get(f"{SERVICE_BASE}/depots", headers=_headers())
    resp.raise_for_status()
    raw = resp.json()
    if isinstance(raw, list):
        return raw
    return raw.get("depots", raw.get("data", []))


def pull_vehicles():
    resp = requests.get(f"{SERVICE_BASE}/vehicles", headers=_headers())
    resp.raise_for_status()
    raw = resp.json()
    if isinstance(raw, list):
        return raw
    return raw.get("vehicles", raw.get("data", []))


def knapsack_optimize(capacity, job_list):
    total_jobs = len(job_list)
    table = [[0] * (capacity + 1) for _ in range(total_jobs + 1)]

    for row in range(1, total_jobs + 1):
        current = job_list[row - 1]
        hrs = current["Duration"]
        val = current["Impact"]
        for col in range(1, capacity + 1):
            if hrs <= col:
                with_item = val + table[row - 1][col - hrs]
                without_item = table[row - 1][col]
                table[row][col] = max(with_item, without_item)
            else:
                table[row][col] = table[row - 1][col]

    best_val = table[total_jobs][capacity]

    picked = []
    remaining = capacity
    for row in range(total_jobs, 0, -1):
        if table[row][remaining] != table[row - 1][remaining]:
            picked.append(job_list[row - 1])
            remaining -= job_list[row - 1]["Duration"]

    return best_val, picked


def build_schedule():
    all_depots = pull_depots()
    all_tasks = pull_vehicles()

    output = []
    for depot in all_depots:
        budget = depot.get("MechanicHours", 0)
        d_id = depot.get("DepotID", depot.get("Id", None))

        if d_id is not None:
            relevant = [t for t in all_tasks if t.get("DepotID", t.get("depotId")) == d_id]
        else:
            relevant = list(all_tasks)

        if len(relevant) == 0:
            relevant = list(all_tasks)

        best, selection = knapsack_optimize(budget, relevant)

        consumed = sum(t["Duration"] for t in selection)
        task_ids = [t.get("TaskID", t.get("Id", "N/A")) for t in selection]

        output.append({
            "depot": depot.get("DepotName", depot.get("Name", "Unknown")),
            "mechanic_hours": budget,
            "max_impact": best,
            "hours_used": consumed,
            "tasks_selected": len(selection),
            "task_ids": task_ids,
            "details": selection
        })

    return output


if __name__ == "__main__":
    results = build_schedule()
    for r in results:
        print("=" * 65)
        print(f"  Depot : {r['depot']}")
        print(f"  Available Mechanic Hours : {r['mechanic_hours']}")
        print(f"  Maximum Impact Achieved  : {r['max_impact']}")
        print("-" * 65)
        print(f"  {'TaskID':<12} {'Duration (hrs)':<18} {'Impact':<10}")
        print("-" * 65)
        for t in r["details"]:
            tid = str(t.get("TaskID", t.get("Id", "N/A")))
            print(f"  {tid:<12} {t['Duration']:<18} {t['Impact']:<10}")
        print("-" * 65)
        print(f"  Total tasks selected : {r['tasks_selected']}")
        print(f"  Total hours consumed : {r['hours_used']}")
        print("=" * 65)
        print()
