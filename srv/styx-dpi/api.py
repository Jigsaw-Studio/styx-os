from fastapi import FastAPI, Query
from typing import Optional
import sqlite3
from pydantic import BaseModel
from datetime import datetime, timezone

class TrafficAPI:
    def __init__(self, database_path: str):
        self.app = FastAPI()
        self.database_path = database_path
        self.setup_routes()

    class TrafficSummary(BaseModel):
        domain_or_ip: str
        total_sent: int = 0  # Default to 0
        total_received: int = 0  # Default to 0

    def query_database(self, query: str, params: tuple):
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchall()
        conn.close()
        return result

    @staticmethod
    def construct_timestamp(date_part: Optional[str], time_part: Optional[str], is_start: bool):
        utc_now = datetime.now(timezone.utc)

        if date_part and time_part:
            return f"{date_part} {time_part}"
        elif date_part:
            if is_start:
                return f"{date_part} 00:00:00"
            else:
                return f"{date_part} 23:59:59"
        elif time_part:
            today = utc_now.date().strftime("%Y-%m-%d")
            return f"{today} {time_part}"
        else:
            return None

    def setup_routes(self):
        @self.app.get("/v1/domains", response_model=list[self.TrafficSummary])
        def get_domain_summary(
                start_date: Optional[str] = Query(None),
                start_time: Optional[str] = Query(None),
                end_date: Optional[str] = Query(None),
                end_time: Optional[str] = Query(None)
        ):
            query = '''
                SELECT domain_name, SUM(bytes_sent) as total_sent, SUM(bytes_received) as total_received
                FROM traffic
                WHERE domain_name IS NOT NULL
            '''
            params = []

            start_timestamp = self.construct_timestamp(start_date, start_time, is_start=True)
            end_timestamp = self.construct_timestamp(end_date, end_time, is_start=False)

            if start_timestamp:
                query += " AND timestamp >= ?"
                params.append(start_timestamp)

            if end_timestamp:
                query += " AND timestamp <= ?"
                params.append(end_timestamp)

            query += " GROUP BY domain_name"

            results = self.query_database(query, tuple(params))

            return [self.TrafficSummary(domain_or_ip=row[0], total_sent=row[1] or 0, total_received=row[2] or 0) for row in results]

        @self.app.get("/v1/addresses", response_model=list[self.TrafficSummary])
        def get_ip_summary(
                start_date: Optional[str] = Query(None),
                start_time: Optional[str] = Query(None),
                end_date: Optional[str] = Query(None),
                end_time: Optional[str] = Query(None)
        ):
            query = '''
                SELECT remote_ip, SUM(bytes_sent) as total_sent, SUM(bytes_received) as total_received
                FROM traffic
            '''
            params = []

            start_timestamp = self.construct_timestamp(start_date, start_time, is_start=True)
            end_timestamp = self.construct_timestamp(end_date, end_time, is_start=False)

            if start_timestamp:
                query += " WHERE timestamp >= ?"
                params.append(start_timestamp)

            if end_timestamp:
                query += " AND timestamp <= ?" if start_timestamp else " WHERE timestamp <= ?"
                params.append(end_timestamp)

            query += " GROUP BY remote_ip"

            results = self.query_database(query, tuple(params))

            return [self.TrafficSummary(domain_or_ip=row[0], total_sent=row[1] or 0, total_received=row[2] or 0) for row in results]

        @self.app.get("/v1/interface", response_model=self.TrafficSummary)
        def get_interface_summary(
                start_date: Optional[str] = Query(None),
                start_time: Optional[str] = Query(None),
                end_date: Optional[str] = Query(None),
                end_time: Optional[str] = Query(None)
        ):
            query = '''
                SELECT SUM(bytes_sent) as total_sent, SUM(bytes_received) as total_received
                FROM traffic
            '''
            params = []

            start_timestamp = self.construct_timestamp(start_date, start_time, is_start=True)
            end_timestamp = self.construct_timestamp(end_date, end_time, is_start=False)

            if start_timestamp:
                query += " WHERE timestamp >= ?"
                params.append(start_timestamp)

            if end_timestamp:
                query += " AND timestamp <= ?" if start_timestamp else " WHERE timestamp <= ?"
                params.append(end_timestamp)

            results = self.query_database(query, tuple(params))

            if results and results[0][0] is not None and results[0][1] is not None:
                return self.TrafficSummary(domain_or_ip="interface", total_sent=results[0][0] or 0, total_received=results[0][1] or 0)
            else:
                return self.TrafficSummary(domain_or_ip="interface", total_sent=0, total_received=0)

if __name__ == "__main__":
    import uvicorn
    api = TrafficAPI(database_path="data/styx-dpi.db")
    uvicorn.run(api.app, host="0.0.0.0", port=8192)
