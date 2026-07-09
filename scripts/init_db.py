"""Utility script for validating bootstrap database connectivity."""

from core.db import test_database_connection


def main() -> None:
    ready = test_database_connection()
    print(f"Database ready: {ready}")


if __name__ == "__main__":
    main()
