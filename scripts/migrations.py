"""Database migration scripts for FitTrack.

Run all migrations in order to set up the schema.
"""

from __future__ import annotations

import logging

import oracledb

logger = logging.getLogger(__name__)


MIGRATION_001_TABLES = """
-- ============================================================
-- Migration 001: Core tables
-- ============================================================

-- Users
CREATE TABLE users (
    user_id             RAW(16) DEFAULT SYS_GUID() PRIMARY KEY,
    email               VARCHAR2(255) NOT NULL UNIQUE,
    password_hash       VARCHAR2(255) NOT NULL,
    email_verified      NUMBER(1) DEFAULT 0,
    email_verified_at   TIMESTAMP,
    status              VARCHAR2(20) DEFAULT 'active'
                        CHECK (status IN ('pending','active','suspended','banned')),
    role                VARCHAR2(20) DEFAULT 'user'
                        CHECK (role IN ('user','premium','admin')),
    premium_expires_at  TIMESTAMP,
    point_balance       NUMBER(10) DEFAULT 0,
    points_earned_total NUMBER(10) DEFAULT 0,
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    updated_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    last_login_at       TIMESTAMP,
    CONSTRAINT chk_point_balance CHECK (point_balance >= 0)
)
"""

MIGRATION_001_SPONSORS = """
CREATE TABLE sponsors (
    sponsor_id          RAW(16) DEFAULT SYS_GUID() PRIMARY KEY,
    name                VARCHAR2(255) NOT NULL,
    contact_name        VARCHAR2(255),
    contact_email       VARCHAR2(255),
    contact_phone       VARCHAR2(20),
    website_url         VARCHAR2(500),
    logo_url            VARCHAR2(500),
    status              VARCHAR2(20) DEFAULT 'active'
                        CHECK (status IN ('active','inactive')),
    notes               CLOB,
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    updated_at          TIMESTAMP DEFAULT SYSTIMESTAMP
)
"""

MIGRATION_001_PROFILES = """
CREATE TABLE profiles (
    profile_id          RAW(16) DEFAULT SYS_GUID() PRIMARY KEY,
    user_id             RAW(16) NOT NULL REFERENCES users(user_id),
    display_name        VARCHAR2(50) NOT NULL,
    date_of_birth       DATE NOT NULL,
    state_of_residence  VARCHAR2(2) NOT NULL,
    biological_sex      VARCHAR2(10) CHECK (biological_sex IN ('male','female')),
    age_bracket         VARCHAR2(10) CHECK (age_bracket IN ('18-29','30-39','40-49','50-59','60+')),
    fitness_level       VARCHAR2(20) CHECK (fitness_level IN ('beginner','intermediate','advanced')),
    tier_code           VARCHAR2(20),
    height_inches       NUMBER(3),
    weight_pounds       NUMBER(4),
    goals               CLOB,
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    updated_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT uk_profiles_user UNIQUE (user_id)
)
"""

MIGRATION_001_CONNECTIONS = """
CREATE TABLE tracker_connections (
    connection_id       RAW(16) DEFAULT SYS_GUID() PRIMARY KEY,
    user_id             RAW(16) NOT NULL REFERENCES users(user_id),
    provider            VARCHAR2(20) NOT NULL
                        CHECK (provider IN ('apple_health','google_fit','fitbit')),
    is_primary          NUMBER(1) DEFAULT 0,
    access_token        VARCHAR2(2000),
    refresh_token       VARCHAR2(2000),
    token_expires_at    TIMESTAMP,
    last_sync_at        TIMESTAMP,
    sync_status         VARCHAR2(20) DEFAULT 'pending'
                        CHECK (sync_status IN ('pending','syncing','success','error')),
    error_message       VARCHAR2(500),
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    updated_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT uk_connection_user_provider UNIQUE (user_id, provider)
)
"""

MIGRATION_001_ACTIVITIES = """
CREATE TABLE activities (
    activity_id         RAW(16) DEFAULT SYS_GUID() PRIMARY KEY,
    user_id             RAW(16) NOT NULL REFERENCES users(user_id),
    connection_id       RAW(16) REFERENCES tracker_connections(connection_id),
    external_id         VARCHAR2(255),
    activity_type       VARCHAR2(30) NOT NULL
                        CHECK (activity_type IN ('steps','workout','active_minutes')),
    start_time          TIMESTAMP NOT NULL,
    end_time            TIMESTAMP,
    duration_minutes    NUMBER(5),
    intensity           VARCHAR2(20) CHECK (intensity IN ('light','moderate','vigorous')),
    metrics             CLOB,
    points_earned       NUMBER(5) DEFAULT 0,
    processed           NUMBER(1) DEFAULT 0,
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT uk_activity_external UNIQUE (user_id, connection_id, external_id)
)
"""

MIGRATION_001_TRANSACTIONS = """
CREATE TABLE point_transactions (
    transaction_id      RAW(16) DEFAULT SYS_GUID() PRIMARY KEY,
    user_id             RAW(16) NOT NULL REFERENCES users(user_id),
    transaction_type    VARCHAR2(20) NOT NULL
                        CHECK (transaction_type IN ('earn','spend','adjust')),
    amount              NUMBER(10) NOT NULL,
    balance_after       NUMBER(10) NOT NULL,
    reference_type      VARCHAR2(30),
    reference_id        RAW(16),
    description         VARCHAR2(255),
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP
)
"""

MIGRATION_001_DRAWINGS = """
CREATE TABLE drawings (
    drawing_id          RAW(16) DEFAULT SYS_GUID() PRIMARY KEY,
    drawing_type        VARCHAR2(20) NOT NULL
                        CHECK (drawing_type IN ('daily','weekly','monthly','annual')),
    name                VARCHAR2(255) NOT NULL,
    description         CLOB,
    ticket_cost_points  NUMBER(6) NOT NULL,
    drawing_time        TIMESTAMP NOT NULL,
    ticket_sales_close  TIMESTAMP NOT NULL,
    eligibility         CLOB,
    status              VARCHAR2(20) DEFAULT 'draft'
                        CHECK (status IN ('draft','scheduled','open','closed','completed','cancelled')),
    total_tickets       NUMBER(10) DEFAULT 0,
    random_seed         VARCHAR2(255),
    created_by          RAW(16) REFERENCES users(user_id),
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    updated_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    completed_at        TIMESTAMP
)
"""

MIGRATION_001_PRIZES = """
CREATE TABLE prizes (
    prize_id            RAW(16) DEFAULT SYS_GUID() PRIMARY KEY,
    drawing_id          RAW(16) NOT NULL REFERENCES drawings(drawing_id),
    sponsor_id          RAW(16) REFERENCES sponsors(sponsor_id),
    rank                NUMBER(3) NOT NULL,
    name                VARCHAR2(255) NOT NULL,
    description         CLOB,
    value_usd           NUMBER(10,2),
    quantity            NUMBER(3) DEFAULT 1,
    fulfillment_type    VARCHAR2(20) CHECK (fulfillment_type IN ('digital','physical')),
    image_url           VARCHAR2(500),
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP
)
"""

MIGRATION_001_TICKETS = """
CREATE TABLE tickets (
    ticket_id           RAW(16) DEFAULT SYS_GUID() PRIMARY KEY,
    drawing_id          RAW(16) NOT NULL REFERENCES drawings(drawing_id),
    user_id             RAW(16) NOT NULL REFERENCES users(user_id),
    ticket_number       NUMBER(10),
    purchase_transaction_id RAW(16) REFERENCES point_transactions(transaction_id),
    is_winner           NUMBER(1) DEFAULT 0,
    prize_id            RAW(16),
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP
)
"""

MIGRATION_001_FULFILLMENTS = """
CREATE TABLE prize_fulfillments (
    fulfillment_id      RAW(16) DEFAULT SYS_GUID() PRIMARY KEY,
    ticket_id           RAW(16) NOT NULL REFERENCES tickets(ticket_id),
    prize_id            RAW(16) NOT NULL REFERENCES prizes(prize_id),
    user_id             RAW(16) NOT NULL REFERENCES users(user_id),
    status              VARCHAR2(30) DEFAULT 'pending'
                        CHECK (status IN ('pending','winner_notified','address_confirmed',
                                         'address_invalid','shipped','delivered','forfeited')),
    shipping_address    CLOB,
    tracking_number     VARCHAR2(100),
    carrier             VARCHAR2(50),
    notes               CLOB,
    notified_at         TIMESTAMP,
    address_confirmed_at TIMESTAMP,
    shipped_at          TIMESTAMP,
    delivered_at        TIMESTAMP,
    forfeit_at          TIMESTAMP,
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    updated_at          TIMESTAMP DEFAULT SYSTIMESTAMP
)
"""

MIGRATION_002_INDEXES = [
    "CREATE INDEX idx_users_email ON users(email)",
    "CREATE INDEX idx_users_status ON users(status)",
    "CREATE INDEX idx_profiles_tier ON profiles(tier_code)",
    "CREATE INDEX idx_activities_user_date ON activities(user_id, start_time)",
    "CREATE INDEX idx_transactions_user ON point_transactions(user_id, created_at)",
    "CREATE INDEX idx_drawings_status ON drawings(status, drawing_time)",
    "CREATE INDEX idx_tickets_drawing ON tickets(drawing_id)",
    "CREATE INDEX idx_tickets_user ON tickets(user_id, drawing_id)",
]

# Migration 003: JSON Duality View — provides document-style access over
# the users + profiles join.  Requires Oracle 23ai.
MIGRATION_003_DUALITY_VIEW = """
CREATE OR REPLACE JSON RELATIONAL DUALITY VIEW user_profile_dv AS
SELECT JSON {
    '_id'             : u.user_id,
    'email'           : u.email,
    'status'          : u.status,
    'role'            : u.role,
    'pointBalance'    : u.point_balance,
    'pointsEarnedTotal': u.points_earned_total,
    'createdAt'       : u.created_at,
    'profile'         : (
        SELECT JSON {
            'profileId'        : p.profile_id,
            'displayName'      : p.display_name,
            'dateOfBirth'      : p.date_of_birth,
            'stateOfResidence' : p.state_of_residence,
            'biologicalSex'    : p.biological_sex,
            'ageBracket'       : p.age_bracket,
            'fitnessLevel'     : p.fitness_level,
            'tierCode'         : p.tier_code,
            'heightInches'     : p.height_inches,
            'weightPounds'     : p.weight_pounds,
            'goals'            : p.goals
        }
        FROM profiles p WITH UPDATE
        WHERE p.user_id = u.user_id
    )
}
FROM users u WITH UPDATE
"""

# Order matters: must create parent tables before children
ALL_TABLE_DDLS = [
    ("users", MIGRATION_001_TABLES),
    ("sponsors", MIGRATION_001_SPONSORS),
    ("profiles", MIGRATION_001_PROFILES),
    ("tracker_connections", MIGRATION_001_CONNECTIONS),
    ("activities", MIGRATION_001_ACTIVITIES),
    ("point_transactions", MIGRATION_001_TRANSACTIONS),
    ("drawings", MIGRATION_001_DRAWINGS),
    ("prizes", MIGRATION_001_PRIZES),
    ("tickets", MIGRATION_001_TICKETS),
    ("prize_fulfillments", MIGRATION_001_FULFILLMENTS),
]

# ── Migration 004: OAuth accounts table ─────────────────────────────

MIGRATION_004_OAUTH_ACCOUNTS = """
CREATE TABLE oauth_accounts (
    oauth_account_id    RAW(16) DEFAULT SYS_GUID() PRIMARY KEY,
    user_id             RAW(16) NOT NULL
                        REFERENCES users(user_id),
    provider            VARCHAR2(20) NOT NULL
                        CHECK (provider IN ('google','apple')),
    provider_user_id    VARCHAR2(255) NOT NULL,
    email               VARCHAR2(255),
    display_name        VARCHAR2(255),
    access_token        VARCHAR2(2000),
    refresh_token       VARCHAR2(2000),
    token_expires_at    TIMESTAMP,
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    updated_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT uq_oauth_provider_user UNIQUE (provider, provider_user_id)
)
"""

# ── Migration 005: Sessions table ───────────────────────────────────

MIGRATION_005_SESSIONS = """
CREATE TABLE sessions (
    session_id          RAW(16) DEFAULT SYS_GUID() PRIMARY KEY,
    user_id             RAW(16) NOT NULL
                        REFERENCES users(user_id),
    refresh_token_jti   VARCHAR2(64) NOT NULL,
    device_info         VARCHAR2(500),
    ip_address          VARCHAR2(45),
    revoked             NUMBER(1) DEFAULT 0,
    revoked_at          TIMESTAMP,
    expires_at          TIMESTAMP,
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP
)
"""

# ── Migration 006: Auth columns on users table ──────────────────────

MIGRATION_006_USER_AUTH_COLUMNS = [
    "ALTER TABLE users ADD (failed_login_attempts NUMBER(5) DEFAULT 0)",
    "ALTER TABLE users ADD (locked_until TIMESTAMP)",
    "ALTER TABLE users ADD (date_of_birth DATE)",
    "ALTER TABLE users ADD (state VARCHAR2(2))",
]

# ── Migration 007: Daily points log + point balance version ────────

MIGRATION_007_DAILY_POINTS_LOG = """
CREATE TABLE daily_points_log (
    log_id              RAW(16) DEFAULT SYS_GUID() PRIMARY KEY,
    user_id             RAW(16) NOT NULL
                        REFERENCES users(user_id),
    log_date            DATE NOT NULL,
    total_points        NUMBER(10) DEFAULT 0,
    step_points         NUMBER(10) DEFAULT 0,
    workout_points      NUMBER(10) DEFAULT 0,
    workout_count       NUMBER(5) DEFAULT 0,
    active_minute_points NUMBER(10) DEFAULT 0,
    bonus_points        NUMBER(10) DEFAULT 0,
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    updated_at          TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT uq_user_log_date UNIQUE (user_id, log_date)
)
"""

MIGRATION_007_BALANCE_VERSION = [
    "ALTER TABLE users ADD (point_balance_version NUMBER(10) DEFAULT 0)",
]

# Combined table creation list including new auth tables
ALL_AUTH_TABLE_DDLS = [
    ("oauth_accounts", MIGRATION_004_OAUTH_ACCOUNTS),
    ("sessions", MIGRATION_005_SESSIONS),
]

# Migration 007 tables
ALL_CP4_TABLE_DDLS = [
    ("daily_points_log", MIGRATION_007_DAILY_POINTS_LOG),
]

# ── Migration 008: Notifications table ──────────────────────────────

MIGRATION_008_NOTIFICATIONS = """
CREATE TABLE notifications (
    notification_id     RAW(16) DEFAULT SYS_GUID() PRIMARY KEY,
    user_id             RAW(16) NOT NULL
                        REFERENCES users(user_id),
    notification_type   VARCHAR2(50) NOT NULL
                        CHECK (notification_type IN (
                            'winner_selected','fulfillment_update',
                            'account_status_change','point_adjustment',
                            'verification','password_reset','general'
                        )),
    title               VARCHAR2(500) NOT NULL,
    message             CLOB,
    metadata            VARCHAR2(4000),
    is_read             NUMBER(1) DEFAULT 0,
    read_at             TIMESTAMP,
    email_sent          NUMBER(1) DEFAULT 0,
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP
)
"""

MIGRATION_008_INDEXES = [
    "CREATE INDEX idx_notifications_user ON notifications(user_id)",
    "CREATE INDEX idx_notifications_user_read ON notifications(user_id, is_read)",
    "CREATE INDEX idx_notifications_type ON notifications(notification_type)",
]

# ── Migration 009: Admin actions log table ──────────────────────────

MIGRATION_009_ADMIN_ACTIONS_LOG = """
CREATE TABLE admin_actions_log (
    log_id              RAW(16) DEFAULT SYS_GUID() PRIMARY KEY,
    admin_user_id       RAW(16) NOT NULL
                        REFERENCES users(user_id),
    action_type         VARCHAR2(50) NOT NULL,
    target_user_id      RAW(16)
                        REFERENCES users(user_id),
    details             VARCHAR2(4000),
    created_at          TIMESTAMP DEFAULT SYSTIMESTAMP
)
"""

MIGRATION_009_INDEXES = [
    "CREATE INDEX idx_admin_log_admin ON admin_actions_log(admin_user_id)",
    "CREATE INDEX idx_admin_log_target ON admin_actions_log(target_user_id)",
    "CREATE INDEX idx_admin_log_type ON admin_actions_log(action_type)",
]

# CP7 tables
ALL_CP7_TABLE_DDLS = [
    ("notifications", MIGRATION_008_NOTIFICATIONS),
    ("admin_actions_log", MIGRATION_009_ADMIN_ACTIONS_LOG),
]

# Tables in reverse order for dropping (children first)
DROP_ORDER = [
    "admin_actions_log",
    "notifications",
    "daily_points_log",
    "prize_fulfillments",
    "tickets",
    "prizes",
    "drawings",
    "point_transactions",
    "activities",
    "tracker_connections",
    "profiles",
    "sessions",
    "oauth_accounts",
    "sponsors",
    "users",
]


def table_exists(conn: oracledb.Connection, table_name: str) -> bool:
    """Check if a table exists in the current schema."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM user_tables WHERE table_name = :name",
            {"name": table_name.upper()},
        )
        row = cur.fetchone()
        return bool(row and row[0] > 0)


def run_migrations(conn: oracledb.Connection) -> list[str]:
    """Run all pending migrations. Returns list of actions taken."""
    actions: list[str] = []

    # Create core tables (Migration 001)
    for table_name, ddl in ALL_TABLE_DDLS:
        if not table_exists(conn, table_name):
            with conn.cursor() as cur:
                cur.execute(ddl)
            actions.append(f"Created table: {table_name}")
            logger.info("Created table: %s", table_name)

    # Create auth tables (Migration 004-005)
    for table_name, ddl in ALL_AUTH_TABLE_DDLS:
        if not table_exists(conn, table_name):
            with conn.cursor() as cur:
                cur.execute(ddl)
            actions.append(f"Created table: {table_name}")
            logger.info("Created table: %s", table_name)

    # Add auth columns to users table (Migration 006)
    for alter_sql in MIGRATION_006_USER_AUTH_COLUMNS:
        try:
            with conn.cursor() as cur:
                cur.execute(alter_sql)
            col_name = alter_sql.split("(")[1].split(" ")[0] if "(" in alter_sql else "?"
            actions.append(f"Added column: users.{col_name}")
        except oracledb.DatabaseError as e:
            error_obj = e.args[0]
            # ORA-01430: column already exists
            if hasattr(error_obj, "code") and error_obj.code == 1430:
                pass
            else:
                raise

    # Create CP4 tables (Migration 007)
    for table_name, ddl in ALL_CP4_TABLE_DDLS:
        if not table_exists(conn, table_name):
            with conn.cursor() as cur:
                cur.execute(ddl)
            actions.append(f"Created table: {table_name}")
            logger.info("Created table: %s", table_name)

    # Add balance version column (Migration 007)
    for alter_sql in MIGRATION_007_BALANCE_VERSION:
        try:
            with conn.cursor() as cur:
                cur.execute(alter_sql)
            col_name = alter_sql.split("(")[1].split(" ")[0] if "(" in alter_sql else "?"
            actions.append(f"Added column: users.{col_name}")
        except oracledb.DatabaseError as e:
            error_obj = e.args[0]
            if hasattr(error_obj, "code") and error_obj.code == 1430:
                pass
            else:
                raise

    # Create indexes (ignore if already exists)
    for idx_sql in MIGRATION_002_INDEXES:
        try:
            with conn.cursor() as cur:
                cur.execute(idx_sql)
            idx_name = idx_sql.split("INDEX ")[1].split(" ON")[0]
            actions.append(f"Created index: {idx_name}")
        except oracledb.DatabaseError as e:
            error_obj = e.args[0]
            # ORA-00955: name already used; ORA-01408: column list already indexed
            if hasattr(error_obj, 'code') and error_obj.code in (955, 1408):
                pass
            else:
                raise

    # Create CP7 tables (Migration 008-009)
    for table_name, ddl in ALL_CP7_TABLE_DDLS:
        if not table_exists(conn, table_name):
            with conn.cursor() as cur:
                cur.execute(ddl)
            actions.append(f"Created table: {table_name}")
            logger.info("Created table: %s", table_name)

    # Create CP7 indexes
    for idx_sql in MIGRATION_008_INDEXES + MIGRATION_009_INDEXES:
        try:
            with conn.cursor() as cur:
                cur.execute(idx_sql)
            idx_name = idx_sql.split("INDEX ")[1].split(" ON")[0]
            actions.append(f"Created index: {idx_name}")
        except oracledb.DatabaseError as e:
            error_obj = e.args[0]
            if hasattr(error_obj, 'code') and error_obj.code in (955, 1408):
                pass
            else:
                raise

    # Create JSON Duality View (Oracle 23ai only)
    try:
        with conn.cursor() as cur:
            cur.execute(MIGRATION_003_DUALITY_VIEW)
        actions.append("Created duality view: user_profile_dv")
        logger.info("Created duality view: user_profile_dv")
    except oracledb.DatabaseError as e:
        error_obj = e.args[0]
        # ORA-00955: name already used, or ORA-00907/ORA-00922 if Oracle version doesn't support it
        if hasattr(error_obj, 'code') and error_obj.code in (955, 907, 922, 11536):
            logger.warning(
                "Skipping duality view (may already exist or unsupported): %s", e
            )
        else:
            raise

    conn.commit()
    return actions


def drop_all_tables(conn: oracledb.Connection) -> list[str]:
    """Drop all tables (for reset). Returns list of actions taken."""
    actions: list[str] = []
    for table_name in DROP_ORDER:
        if table_exists(conn, table_name):
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE {table_name} CASCADE CONSTRAINTS PURGE")
            actions.append(f"Dropped table: {table_name}")
            logger.info("Dropped table: %s", table_name)
    conn.commit()
    return actions
