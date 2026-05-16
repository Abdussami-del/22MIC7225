import os
import requests

SERVICE_BASE = "http://4.224.186.213/evaluation-service"
TOKEN = os.environ.get("API_TOKEN", "")


def _headers():
    if TOKEN:
        return {"Authorization": f"Bearer {TOKEN}"}
    return {}


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


def display_results(depot_info, optimal_val, chosen_jobs):
    label = depot_info.get("DepotName", depot_info.get("Name", "Unknown"))
    budget = depot_info.get("MechanicHours", 0)
    print("=" * 65)
    print(f"  Depot : {label}")
    print(f"  Available Mechanic Hours : {budget}")
    print(f"  Maximum Impact Achieved  : {optimal_val}")
    print("-" * 65)
    print(f"  {'TaskID':<12} {'Duration (hrs)':<18} {'Impact':<10}")
    print("-" * 65)
    consumed = 0
    for entry in chosen_jobs:
        tid = str(entry.get("TaskID", "N/A"))
        print(f"  {tid:<12} {entry['Duration']:<18} {entry['Impact']:<10}")
        consumed += entry["Duration"]
    print("-" * 65)
    print(f"  Total tasks selected : {len(chosen_jobs)}")
    print(f"  Total hours consumed : {consumed}")
    print("=" * 65)
    print()


def execute():
    print("\n[*] Fetching depot data ...")
    all_depots = pull_depots()
    print(f"[*] Found {len(all_depots)} depot(s).\n")

    print("[*] Fetching vehicle task data ...")
    all_tasks = pull_vehicles()
    print(f"[*] Found {len(all_tasks)} task(s).\n")

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
        display_results(depot, best, selection)


if __name__ == "__main__":
    execute()
