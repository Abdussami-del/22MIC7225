import heapq
from datetime import datetime


PRIORITY_MAP = {"Placement": 3, "Result": 2, "Event": 1}
AMPLIFIER = 1_000_000_000


class Alert:
    def __init__(self, uid, category, body, time_str):
        self.uid = uid
        self.category = category
        self.body = body
        self.epoch = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").timestamp()
        self.rank = self._compute_rank()

    def _compute_rank(self):
        tier = PRIORITY_MAP.get(self.category, 0)
        return (tier * AMPLIFIER) + self.epoch

    def __lt__(self, other):
        return self.rank < other.rank


def extract_top(raw_entries, count=10):
    heap = []
    for entry in raw_entries:
        obj = Alert(entry["ID"], entry["Type"], entry["Message"], entry["Timestamp"])
        if len(heap) < count:
            heapq.heappush(heap, obj)
        elif obj.rank > heap[0].rank:
            heapq.heappushpop(heap, obj)
    return sorted(heap, key=lambda a: a.rank, reverse=True)


sample_feed = [
    {"ID": "1",  "Type": "Result",    "Message": "Mid-Sem Grades Published",      "Timestamp": "2026-04-22 17:51:30"},
    {"ID": "2",  "Type": "Placement", "Message": "CSX Corp Hiring - SDE1",        "Timestamp": "2026-04-22 17:51:18"},
    {"ID": "3",  "Type": "Event",     "Message": "Farewell Ceremony - 2026",      "Timestamp": "2026-04-22 17:51:06"},
    {"ID": "4",  "Type": "Placement", "Message": "Google On-Campus Drive",        "Timestamp": "2026-04-21 10:00:00"},
    {"ID": "5",  "Type": "Result",    "Message": "End-Sem Results Declared",      "Timestamp": "2026-04-20 09:30:00"},
    {"ID": "6",  "Type": "Event",     "Message": "Hackathon 2026 Registrations",  "Timestamp": "2026-04-19 14:00:00"},
    {"ID": "7",  "Type": "Placement", "Message": "Amazon SDE Intern Shortlist",   "Timestamp": "2026-04-18 08:45:00"},
    {"ID": "8",  "Type": "Result",    "Message": "Lab Exam Marks Updated",        "Timestamp": "2026-04-17 16:20:00"},
    {"ID": "9",  "Type": "Event",     "Message": "Annual Sports Day - Register",  "Timestamp": "2026-04-16 11:00:00"},
    {"ID": "10", "Type": "Placement", "Message": "Microsoft PPO Offers",          "Timestamp": "2026-04-15 13:30:00"},
    {"ID": "11", "Type": "Event",     "Message": "Cultural Fest Volunteer Signup", "Timestamp": "2026-04-14 17:00:00"},
    {"ID": "12", "Type": "Result",    "Message": "Assignment 3 Grades Released",  "Timestamp": "2026-04-13 12:00:00"},
    {"ID": "13", "Type": "Placement", "Message": "Flipkart SDE2 Walk-In Drive",  "Timestamp": "2026-04-12 09:15:00"},
    {"ID": "14", "Type": "Event",     "Message": "Guest Lecture: AI by Dr. Kumar","Timestamp": "2026-04-11 15:00:00"},
    {"ID": "15", "Type": "Result",    "Message": "Project Review Scores Updated", "Timestamp": "2026-04-10 10:45:00"},
]


if __name__ == "__main__":
    results = extract_top(sample_feed, count=10)

    print()
    print("=" * 72)
    print("  PRIORITY INBOX - TOP 10 NOTIFICATIONS")
    print("=" * 72)
    print(f"  {'Rank':<6} {'Type':<14} {'Message':<38} {'Score'}")
    print("-" * 72)

    for pos, item in enumerate(results, 1):
        print(f"  {pos:<6} [{item.category:<10}] {item.body:<38} {item.rank:,.2f}")

    print("-" * 72)
    print(f"  Heap size: K=10 | Total processed: {len(sample_feed)}")
    print("=" * 72)
    print()
