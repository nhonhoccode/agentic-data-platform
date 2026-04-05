from __future__ import annotations

import psycopg
from psycopg import sql

from app.config import get_settings

GRANT_SCHEMAS = ("marts", "serving")


def ensure_readonly_role() -> None:
    settings = get_settings()
    if not settings.db_enforce_readonly_role:
        print("[SECURITY] Skipping read-only role provisioning (DB_ENFORCE_READONLY_ROLE=false).")
        return

    role = settings.postgres_readonly_user.strip()
    password = settings.postgres_readonly_password

    if not role:
        raise ValueError("POSTGRES_READONLY_USER must not be empty when DB_ENFORCE_READONLY_ROLE=true.")

    with psycopg.connect(settings.postgres_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {role_name}) THEN
                            CREATE ROLE {role_ident} LOGIN PASSWORD {role_password};
                        ELSE
                            ALTER ROLE {role_ident} WITH LOGIN PASSWORD {role_password};
                        END IF;
                    END
                    $$;
                    """
                ).format(
                    role_name=sql.Literal(role),
                    role_ident=sql.Identifier(role),
                    role_password=sql.Literal(password),
                )
            )

            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {};").format(
                    sql.Identifier(settings.postgres_db),
                    sql.Identifier(role),
                )
            )

            for schema in GRANT_SCHEMAS:
                cur.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA {} TO {};").format(
                        sql.Identifier(schema),
                        sql.Identifier(role),
                    )
                )
                cur.execute(
                    sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {};").format(
                        sql.Identifier(schema),
                        sql.Identifier(role),
                    )
                )
                cur.execute(
                    sql.SQL(
                        "ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT SELECT ON TABLES TO {};"
                    ).format(
                        sql.Identifier(schema),
                        sql.Identifier(role),
                    )
                )

    print(f"[SECURITY] Read-only role '{role}' is provisioned and granted to schemas: {GRANT_SCHEMAS}")


def main() -> None:
    ensure_readonly_role()


if __name__ == "__main__":
    main()
