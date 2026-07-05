# 🎙️ PodFlow

> A production-inspired podcast ingestion pipeline built with Apache Airflow.

PodFlow is a hands-on data engineering project that automates the process of discovering, downloading, and managing podcast episodes using Apache Airflow.

The project is being built as a learning journey into modern data engineering practices while following professional software engineering principles.

---

# 🚀 Project Goals

- Learn Apache Airflow from the ground up
- Build production-inspired ETL pipelines
- Practice Python for data engineering
- Work with SQLite databases
- Automate podcast ingestion
- Learn project organization and software architecture
- Develop industry-standard engineering practices

---

# 📚 Learning Objectives

This repository documents the complete journey of building a data pipeline from scratch.

Topics include:

- Linux (WSL2)
- Bash
- Virtual Environments
- Apache Airflow
- DAGs
- Operators
- SQLite
- SQLAlchemy
- ETL Design
- Python
- Logging
- Scheduling
- Error Handling
- Testing
- Git & GitHub

---

# 🏗 Project Structure

```text
airflow-learning/
│
├── airflow_home/
│   ├── dags/
│   ├── logs/
│   ├── plugins/
│   ├── airflow.cfg
│   └── airflow.db
│
├── src/
│
├── scripts/
│
├── data/
│
├── downloads/
│
├── tests/
│
├── .venv/
│
├── requirements.txt
├── README.md
└── .gitignore
```

---

# ⚙️ Tech Stack

- Python 3.12
- Apache Airflow 3.2
- SQLite
- VS Code
- Ubuntu 24.04 (WSL2)
- Git

---

# 📈 Planned Pipeline

```text
Podcast Website
        │
        ▼
Extract Episode Metadata
        │
        ▼
Transform & Validate
        │
        ▼
Store Metadata (SQLite)
        │
        ▼
Download Audio Files
        │
        ▼
Update Database
        │
        ▼
Schedule with Airflow
```

---

# 🛣 Roadmap

## Phase 1 — Development Environment ✅

- [x] WSL2
- [x] Ubuntu 24.04
- [x] VS Code
- [x] Python Virtual Environment
- [x] Apache Airflow
- [x] Project Structure

---

## Phase 2 — Project Foundation

- [ ] Database Design
- [ ] SQLite Setup
- [ ] SQLAlchemy Integration

---

## Phase 3 — Data Extraction

- [ ] Scrape Podcast Metadata
- [ ] Parse RSS Feed
- [ ] Validate Data

---

## Phase 4 — Data Storage

- [ ] Store Episode Metadata
- [ ] Prevent Duplicate Downloads
- [ ] Update Episode Status

---

## Phase 5 — Download Engine

- [ ] Download Audio Files
- [ ] Retry Failed Downloads
- [ ] Logging

---

## Phase 6 — Airflow

- [ ] Build DAG
- [ ] Schedule Pipeline
- [ ] Monitoring
- [ ] Alerts

---

## Phase 7 — Production Improvements

- [ ] Docker
- [ ] PostgreSQL
- [ ] Unit Testing
- [ ] CI/CD
- [ ] Cloud Deployment

---

# 📖 Why this project?

Rather than simply following tutorials, this project focuses on understanding how real-world data engineering systems are designed and implemented.

Every phase emphasizes not only *how* to build the solution but also *why* each architectural decision is made.

---

# 📜 License

MIT License