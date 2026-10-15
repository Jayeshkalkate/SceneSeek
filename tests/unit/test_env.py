from pathlib import Path

from app import env


def test_blank_and_placeholder_urls_fall_back_to_sqlite():
    assert env.normalize_database_url("") == env.DEFAULT_DATABASE_URL
    assert env.normalize_database_url("postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require") == env.DEFAULT_DATABASE_URL


def test_postgres_scheme_is_normalised():
    assert env.normalize_database_url("postgres://u:p@db.example.com/x").startswith("postgresql://")


def test_relative_sqlite_path_becomes_absolute():
    url = env.normalize_database_url("sqlite:///./data/x.db")
    assert Path(env.sqlite_path_from_url(url)).is_absolute()


def test_windows_and_posix_absolute_paths_are_kept():
    assert env.normalize_database_url("sqlite:///C:/Projects/x.db") == "sqlite:///C:/Projects/x.db"
    assert env.normalize_database_url("sqlite:////data/x.db") == "sqlite:////data/x.db"
    assert env.sqlite_path_from_url("sqlite:///:memory:") is None
