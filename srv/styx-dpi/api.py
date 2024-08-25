from fastapi import FastAPI, Query
from typing import Optional
import sqlite3
from pydantic import BaseModel

app = FastAPI()

DATABASE_PATH = "data/styx-dpi.db"

class TrafficSummary(BaseModel):
    domain_or_ip: str
    total_sent: int = 0  # Default to 0
    total_received: int = 0  # Default to 0

def query_database(query: str, params: tuple):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute(query, params)
    result = cursor.fetchall()
    conn.close()
    return result

@app.get("/v1/domains", response_model=list[TrafficSummary])
def get_domain_summary(start: Optional[str] = Query(None), end: Optional[str] = Query(None)):
    query = '''
        SELECT domain_name, SUM(bytes_sent) as total_sent, SUM(bytes_received) as total_received
        FROM traffic
        WHERE domain_name IS NOT NULL
    '''
    params = []

    if start:
        query += " AND timestamp >= ?"
        params.append(start)

    if end:
        query += " AND timestamp <= ?"
        params.append(end)

    query += " GROUP BY domain_name"

    results = query_database(query, tuple(params))

    return [TrafficSummary(domain_or_ip=row[0], total_sent=row[1] or 0, total_received=row[2] or 0) for row in results]

@app.get("/v1/addresses", response_model=list[TrafficSummary])
def get_ip_summary(start: Optional[str] = Query(None), end: Optional[str] = Query(None)):
    query = '''
        SELECT dst_ip, SUM(bytes_sent) as total_sent, SUM(bytes_received) as total_received
        FROM traffic
    '''
    params = []

    if start:
        query += " WHERE timestamp >= ?"
        params.append(start)

    if end:
        query += " AND timestamp <= ?" if start else " WHERE timestamp <= ?"
        params.append(end)

    query += " GROUP BY dst_ip"

    results = query_database(query, tuple(params))

    return [TrafficSummary(domain_or_ip=row[0], total_sent=row[1] or 0, total_received=row[2] or 0) for row in results]

@app.get("/v1/interface", response_model=TrafficSummary)
def get_interface_summary(start: Optional[str] = Query(None), end: Optional[str] = Query(None)):
    query = '''
        SELECT SUM(bytes_sent) as total_sent, SUM(bytes_received) as total_received
        FROM traffic
    '''
    params = []

    if start:
        query += " WHERE timestamp >= ?"
        params.append(start)

    if end:
        query += " AND timestamp <= ?" if start else " WHERE timestamp <= ?"
        params.append(end)

    results = query_database(query, tuple(params))

    if results:
        return TrafficSummary(domain_or_ip="interface", total_sent=results[0][0] or 0, total_received=results[0][1] or 0)
    else:
        return TrafficSummary(domain_or_ip="interface", total_sent=0, total_received=0)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8192)
