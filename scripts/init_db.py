"""Day2 数据库初始化脚本。"""

from core.db import create_all_tables, test_database_connection


def main() -> None:
    """创建 Day2 所需的全部数据表，并输出数据库状态。"""
    ready = test_database_connection()
    print(f"Database ready: {ready}")

    create_all_tables()
    print("All Day2 tables have been created successfully.")


if __name__ == "__main__":
    main()
