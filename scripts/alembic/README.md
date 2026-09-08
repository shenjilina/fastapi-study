# Day2 Alembic 学习脚手架

这个目录用于存放第二天学习数据库迁移时需要的 Alembic 配置文件和版本脚本。

## 目录说明

- `env.py`：迁移运行入口，负责连接项目配置并加载 `Base.metadata`
- `script.py.mako`：生成新迁移文件时使用的模板
- `versions/`：存放具体的迁移版本脚本

## 学习建议

1. 先运行 `uv run python scripts/init_db.py`，观察基于 ORM 直接建表的效果
2. 再阅读 `alembic.ini` 与 `scripts/alembic/env.py`，理解 Alembic 如何接入项目模型
3. 最后阅读 `versions` 里的首个迁移脚本，对照 ORM 模型理解表结构映射关系
