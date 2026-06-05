import socket
import time
import psycopg2
import redis
import os
from urllib.parse import urlparse

def wait_for_postgres():
    db_url = os.getenv('DATABASE_URL')
    parsed = urlparse(db_url)
    db_params = {
        'database': parsed.path[1:],
        'user': parsed.username,
        'password': parsed.password,
        'host': parsed.hostname,
        'port': parsed.port or 5432
    }
    
    while True:
        try:
            conn = psycopg2.connect(**db_params)
            conn.close()
            print("PostgreSQL is ready!")
            break
        except psycopg2.OperationalError:
            print("Waiting for PostgreSQL...")
            time.sleep(1)

def wait_for_redis():
    redis_url = os.getenv('REDIS_URL')
    parsed = urlparse(redis_url)
    redis_host = parsed.hostname
    redis_port = parsed.port or 6379
    
    while True:
        try:
            r = redis.Redis(host=redis_host, port=redis_port)
            r.ping()
            print("Redis is ready!")
            break
        except (redis.exceptions.ConnectionError, socket.gaierror):
            print("Waiting for Redis...")
            time.sleep(1)

if __name__ == "__main__":
    print("Waiting for services to be ready...")
    wait_for_postgres()
    wait_for_redis()
    print("All services are ready!") 