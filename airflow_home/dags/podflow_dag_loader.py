"""
DAG loader — Airflow discovers this file and imports the actual DAG
from :mod:`podflow.airflow.podcast_pipeline`.
"""

from podflow.airflow.podcast_pipeline import podcast_pipeline_dag  # noqa: F401
