#!/usr/bin/env python3
"""Drop existing enum types before migration"""
import os
from sqlalchemy import create_engine, text

url = os.getenv("DATABASE_URL")
if url and url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql://", 1)

engine = create_engine(url)
with engine.connect() as conn:
    conn.execute(text("DROP TYPE IF EXISTS alerttype CASCADE"))
    conn.execute(text("DROP TYPE IF EXISTS backteststatus CASCADE"))
    conn.commit()
print("Enum types dropped successfully")
