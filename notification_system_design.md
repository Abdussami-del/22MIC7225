# Campus Notification System – Architectural Design Document

---

## Stage 1: API Design & Contract

### 1.1 Core REST APIs

#### Fetch Unread Notifications

```
GET /api/v1/notifications?status=unread&limit=20
Authorization: Bearer <token>
```

**Response — 200 OK**

```json
{
  "status": "success",
  "count": 3,
  "data": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "student_id": 1042,
      "notification_type": "Placement",
      "message": "Google On-Campus Drive scheduled for May 10, 2026.",
      "is_read": false,
      "created_at": "2026-04-22T17:51:18Z"
    }
  ]
}
```

#### Mark a Single Notification as Read

```
PATCH /api/v1/notifications/{notification_id}
Content-Type: application/json
Authorization: Bearer <token>
```

**Request Body**

```json
{
  "isRead": true
}
```

**Response — 200 OK**

```json
{
  "status": "success",
  "message": "Notification marked as read.",
  "data": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "is_read": true
  }
}
```

#### Mark All Notifications as Read

```
POST /api/v1/notifications/mark-all-read
Authorization: Bearer <token>
```

**Response — 200 OK**

```json
{
  "status": "success",
  "message": "All notifications marked as read.",
  "updated_count": 14
}
```

### 1.2 Real-Time Delivery Mechanism

**Recommendation: Server-Sent Events (SSE)**

| Criteria | SSE | WebSockets |
|---|---|---|
| Direction | Server → Client (unidirectional) | Bidirectional |
| Protocol | Standard HTTP/1.1 | Upgrade to `ws://` |
| Reconnection | Built-in auto-reconnect | Must implement manually |
| Complexity | Low | Higher |
| Best for | Notification feeds, live dashboards | Chat, gaming, collaborative editing |

**Why SSE?** A campus notification system is fundamentally **server-push**: the server generates notifications and pushes them to connected students. Students never "send" notifications back. SSE operates over standard HTTP, supports automatic reconnection, and is simpler to deploy behind load balancers and proxies.

**SSE Endpoint:**

```
GET /api/v1/notifications/stream
Authorization: Bearer <token>
Accept: text/event-stream
```

**Event Format:**

```
event: new-notification
data: {"id":"...","type":"Placement","message":"Google hiring!","created_at":"2026-04-22T17:51:18Z"}
```

---

## Stage 2: Database Choice & Schema

### 2.1 Why PostgreSQL?

- **ACID Compliance**: Guarantees that no notification is lost during concurrent writes.
- **Referential Integrity**: Foreign keys enforce valid `student_id` references.
- **Rich Querying**: Supports partitioning, composite indexes, and JSON operators natively.
- **Mature Ecosystem**: Battle-tested at scale with tools like `pg_partman`, `pgBouncer`.

### 2.2 SQL Schema

```sql
-- Users table
CREATE TABLE users (
    student_id  INT PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    email       VARCHAR(255) UNIQUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Notifications table (partitioned by month)
CREATE TABLE notifications (
    id                UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    student_id        INT NOT NULL REFERENCES users(student_id),
    notification_type VARCHAR(20) NOT NULL
                      CHECK (notification_type IN ('Placement', 'Event', 'Result')),
    message           TEXT NOT NULL,
    is_read           BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (created_at);

-- Monthly partitions (example)
CREATE TABLE notifications_2026_04 PARTITION OF notifications
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE TABLE notifications_2026_05 PARTITION OF notifications
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
```

### 2.3 Partitioning Strategy

| Problem | Solution |
|---|---|
| Single table grows to millions of rows | **Range partition** by `created_at` (monthly) |
| Old data slows queries | **Archive** partitions older than 6 months to cold storage |
| Maintenance overhead | Use `pg_partman` extension for automated partition creation |

### 2.4 SQL Queries for Stage 1 APIs

**Fetch unread notifications (GET):**

```sql
SELECT id, student_id, notification_type, message, is_read, created_at
FROM notifications
WHERE student_id = :student_id
  AND is_read = FALSE
ORDER BY created_at DESC
LIMIT 20;
```

**Mark single notification as read (PATCH):**

```sql
UPDATE notifications
SET is_read = TRUE
WHERE id = :notification_id
  AND student_id = :student_id;
```

**Mark all as read (POST):**

```sql
UPDATE notifications
SET is_read = TRUE
WHERE student_id = :student_id
  AND is_read = FALSE;
```

---

## Stage 3: Query Optimization

### 3.1 Problem Analysis

**Slow query:**

```sql
SELECT * FROM notifications
WHERE student_id = 1042 AND is_read = FALSE
ORDER BY created_at DESC;
```

**Why is it slow?** Without an index, PostgreSQL performs a **Full Table Scan** — examining all 5,000,000 rows sequentially to find the handful that match student 1042's unread notifications. This is `O(n)` on the entire table.

### 3.2 Solution: Composite Index

```sql
CREATE INDEX idx_student_unread
ON notifications (student_id, is_read, created_at DESC);
```

**Why this column order?**

1. `student_id` — high selectivity, narrows to a single user's rows.
2. `is_read` — further filters to only unread rows.
3. `created_at DESC` — the B-tree is pre-sorted for the `ORDER BY`, eliminating a sort step.

The query now performs an **Index Scan** instead of a full table scan, reducing I/O from millions of rows to a handful.

### 3.3 Why NOT Index Every Column?

| Concern | Impact |
|---|---|
| **Write overhead** | Every `INSERT`, `UPDATE`, and `DELETE` must update **every** index on the table. With N indexes, write operations become N× slower. |
| **Storage bloat** | Each index is a separate B-tree data structure stored on disk. Indexing every column can **double or triple** the storage footprint. |
| **Maintenance cost** | `VACUUM` and `REINDEX` operations take longer. Lock contention increases during high-write workloads. |
| **Diminishing returns** | Low-cardinality columns like `is_read` (only TRUE/FALSE) provide almost no selectivity when indexed alone. |

**Rule of thumb:** Only index columns that appear frequently in `WHERE`, `JOIN`, or `ORDER BY` clauses of performance-critical queries.

### 3.4 Placement Notifications in Last 7 Days

```sql
SELECT DISTINCT student_id
FROM notifications
WHERE notification_type = 'Placement'
  AND created_at >= NOW() - INTERVAL '7 days';
```

**Supporting index:**

```sql
CREATE INDEX idx_type_created
ON notifications (notification_type, created_at DESC);
```

---

## Stage 4: Performance & Caching

### 4.1 Problem

Every time a student opens their notifications page, the application hits the database directly. At peak hours (e.g., placement announcements), thousands of students load the page simultaneously, overwhelming PostgreSQL with identical read queries.

### 4.2 Solution: Redis Caching Layer (Cache-Aside Pattern)

```
┌──────────┐      Cache Hit       ┌───────┐
│  Client  │ ──────────────────► │ Redis │
│ (Browser)│ ◄────────────────── │       │
└──────────┘                     └───────┘
      │                               │
      │  Cache Miss                   │ Populate on miss
      ▼                               ▼
┌──────────┐                     ┌────────────┐
│  App     │ ──────────────────► │ PostgreSQL │
│  Server  │ ◄────────────────── │            │
└──────────┘                     └────────────┘
```

**Redis Key Design:**

```
notifications:unread_count:{student_id}  →  integer
notifications:recent:{student_id}        →  JSON list (top 20)
```

**Cache-Aside Flow:**

```python
def get_unread_notifications(student_id):
    # 1. Try cache first
    cached = redis.get(f"notifications:recent:{student_id}")
    if cached:
        return json.loads(cached)

    # 2. Cache miss — query the DB
    result = db.query("SELECT ... WHERE student_id = %s AND is_read = FALSE ...", student_id)

    # 3. Populate cache with TTL (e.g., 5 minutes)
    redis.setex(f"notifications:recent:{student_id}", 300, json.dumps(result))

    return result
```

**Cache Invalidation (on new notification):**

```python
def on_new_notification(student_id, notification):
    db.insert(notification)  # Write to DB first
    redis.delete(f"notifications:recent:{student_id}")   # Invalidate cache
    redis.incr(f"notifications:unread_count:{student_id}")
```

### 4.3 Tradeoffs

| Pros | Cons |
|---|---|
| Massive reduction in DB read load | **Cache Invalidation** is notoriously hard — stale data is possible |
| Sub-millisecond response times for cached reads | If server crashes between DB write and Redis update, data is inconsistent |
| Horizontally scalable (Redis Cluster) | Added infrastructure complexity (another service to monitor, deploy, and maintain) |
| Natural TTL-based expiry keeps data reasonably fresh | Memory cost for storing cached data |

---

## Stage 5: Notify-All Architecture

### 5.1 Problem Analysis

**Flawed synchronous pseudocode:**

```python
def notify_all(student_ids, message):
    for student_id in student_ids:       # 50,000 students
        save_to_db(student_id, message)  # Blocking I/O
        send_email(student_id, message)  # Blocking network call
        push_to_app(student_id, message) # Blocking push
```

**Failure modes:**

1. If `send_email()` times out on student #200, the loop halts — the remaining 49,800 students receive **nothing**.
2. DB persistence is tightly coupled to email delivery — a transient email API failure prevents the notification from being saved.
3. A single thread processes 50,000 students sequentially — this could take **hours**.

### 5.2 Solution: Event-Driven Architecture with Message Broker

```
┌──────────┐    publish     ┌─────────────────┐    consume     ┌──────────────┐
│ Producer │ ─────────────► │  Message Broker  │ ─────────────► │   Worker(s)  │
│ (API)    │   (fast, async)│ (RabbitMQ/Kafka) │  (parallel)    │ (Background) │
└──────────┘                └─────────────────┘                └──────────────┘
                                    │                                │
                                    │ failed msgs                    │
                                    ▼                                ▼
                            ┌───────────────┐              ┌────────────────┐
                            │  Retry Queue  │              │   PostgreSQL   │
                            │  / DLQ        │              │   + Redis      │
                            └───────────────┘              └────────────────┘
```

**Should DB saving and emailing happen together? No.** They must be **decoupled**. The database write is critical and fast; the email is external, slow, and failure-prone. Coupling them means an email outage causes data loss.

### 5.3 Redesigned Pseudocode

```python
# ─── Producer Service (Fast – returns immediately to the HR user) ───
def notify_all(student_ids, message):
    """Publish one message per student to the notification queue."""
    for student_id in student_ids:
        message_broker.publish('notification_queue', {
            'student_id': student_id,
            'message': message
        })
    return {"status": "queued", "count": len(student_ids)}


# ─── Worker Service (Runs asynchronously in background) ───
def handle_queue_message(payload):
    """Process a single notification message from the queue."""

    # Step 1: Persist to database (critical, fast)
    save_to_db(payload['student_id'], payload['message'])

    # Step 2: Push to live app via SSE/WebSocket (fast)
    push_to_app(payload['student_id'], payload['message'])

    # Step 3: Send email (slow, failure-prone — isolated)
    try:
        send_email(payload['student_id'], payload['message'])
    except EmailAPIError:
        # Email failed — push to a retry queue with exponential backoff
        # After N retries, move to Dead Letter Queue for manual inspection
        message_broker.publish('email_retry_queue', payload)
```

**Key benefits of this redesign:**

| Aspect | Synchronous (Before) | Event-Driven (After) |
|---|---|---|
| Speed | Sequential, hours for 50K users | Parallel workers, minutes |
| Fault tolerance | One failure stops everything | Individual failures are retried |
| Coupling | DB + Email + Push tightly coupled | Each concern is independent |
| Scalability | Single thread | Add more workers horizontally |
| User experience | HR waits for completion | HR gets instant "queued" response |
