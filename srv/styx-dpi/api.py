import argparse
import datetime
import dateutil.relativedelta
import os
import pytz
import sqlite3
import uvicorn
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import Optional

class TrafficAPI:
    def __init__(self, database_path: str):
        self.app = FastAPI()
        self.database_path = database_path
        self.setup_routes()

    class TrafficSummary(BaseModel):
        domain_or_ip: str
        total_sent: int = 0
        total_received: int = 0

    def query_database(self, query: str, params: tuple):
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchall()
        conn.close()
        return result

    @staticmethod
    def construct_timestamp(
            date_part: Optional[str],
            time_part: Optional[str],
            is_start: bool,
            relative: Optional[str] = None,
            timezone: Optional[str] = None
    ):
        utc_now = datetime.datetime.now(datetime.timezone.utc)

        if timezone:
            try:
                tz = pytz.timezone(timezone)
                utc_now = utc_now.astimezone(tz)
            except pytz.UnknownTimeZoneError:
                raise HTTPException(status_code=400, detail="Invalid timezone")

        if relative:
            time_amount = int(relative[:-1])
            unit = relative[-1]

            if unit == 's':
                delta = datetime.timedelta(seconds=time_amount)
            elif unit == 'm':
                delta = datetime.timedelta(minutes=time_amount)
            elif unit == 'h':
                delta = datetime.timedelta(hours=time_amount)
            elif unit == 'd':
                delta = datetime.timedelta(days=time_amount)
            elif unit == 'y':
                delta = dateutil.relativedelta.relativedelta(years=time_amount)
            else:
                raise HTTPException(status_code=400, detail="Invalid relative time unit")

            if is_start:
                return (utc_now - delta).strftime("%Y-%m-%d %H:%M:%S")
            else:
                return utc_now.strftime("%Y-%m-%d %H:%M:%S")

        if date_part and time_part:
            return f"{date_part} {time_part}"
        elif date_part:
            return f"{date_part} 00:00:00" if is_start else f"{date_part} 23:59:59"
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
                end_time: Optional[str] = Query(None),
                relative: Optional[str] = Query(None),
                timezone: Optional[str] = Query(None)
        ):
            if relative and (start_date or start_time or end_date or end_time or timezone):
                raise HTTPException(status_code=400, detail="Cannot specify both relative time and absolute time parameters")

            query = '''
                SELECT domain_name, SUM(bytes_sent) as total_sent, SUM(bytes_received) as total_received
                FROM traffic
                WHERE domain_name IS NOT NULL
            '''
            params = []

            start_timestamp = self.construct_timestamp(
                start_date, start_time, is_start=True, relative=relative, timezone=timezone
            )
            end_timestamp = self.construct_timestamp(
                end_date, end_time, is_start=False, relative=None, timezone=timezone
            )

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
                end_time: Optional[str] = Query(None),
                relative: Optional[str] = Query(None),
                timezone: Optional[str] = Query(None)
        ):
            if relative and (start_date or start_time or end_date or end_time or timezone):
                raise HTTPException(status_code=400, detail="Cannot specify both relative time and absolute time parameters")

            query = '''
                SELECT remote_ip, SUM(bytes_sent) as total_sent, SUM(bytes_received) as total_received
                FROM traffic
            '''
            (query, params) = self.process_query_parameters(query, start_date, start_time, end_date, end_time, timezone, relative)

            query += " GROUP BY remote_ip"

            results = self.query_database(query, tuple(params))

            return [self.TrafficSummary(domain_or_ip=row[0], total_sent=row[1] or 0, total_received=row[2] or 0) for row in results]

        @self.app.get("/v1/interface", response_model=self.TrafficSummary)
        def get_interface_summary(
                start_date: Optional[str] = Query(None),
                start_time: Optional[str] = Query(None),
                end_date: Optional[str] = Query(None),
                end_time: Optional[str] = Query(None),
                relative: Optional[str] = Query(None),
                timezone: Optional[str] = Query(None)
        ):
            if relative and (start_date or start_time or end_date or end_time or timezone):
                raise HTTPException(status_code=400, detail="Cannot specify both relative time and absolute time parameters")

            query = '''
                SELECT SUM(bytes_sent) as total_sent, SUM(bytes_received) as total_received
                FROM traffic
            '''
            (query, params) = self.process_query_parameters(query, start_date, start_time, end_date, end_time, timezone, relative)

            results = self.query_database(query, tuple(params))

            if results and results[0][0] is not None and results[0][1] is not None:
                return self.TrafficSummary(domain_or_ip="interface", total_sent=results[0][0] or 0, total_received=results[0][1] or 0)
            else:
                return self.TrafficSummary(domain_or_ip="interface", total_sent=0, total_received=0)

    def process_query_parameters(self, query, start_date, start_time, end_date, end_time, timezone, relative):
        params = []

        start_timestamp = self.construct_timestamp(
            start_date, start_time, is_start=True, relative=relative, timezone=timezone
        )
        end_timestamp = self.construct_timestamp(
            end_date, end_time, is_start=False, relative=None, timezone=timezone
        )

        if start_timestamp:
            query += " WHERE timestamp >= ?"
            params.append(start_timestamp)

        if end_timestamp:
            query += " AND timestamp <= ?" if start_timestamp else " WHERE timestamp <= ?"
            params.append(end_timestamp)

        return query, params

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Report network traffic.")
    parser.add_argument('--db_path', default=os.getenv('DB_PATH', 'data/styx-dpi.db'), help='Path to SQLite3 database (default: data/styx-dpi.db)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--host', default=os.getenv('HOST', '0.0.0.0'), help='Address to listen for connections')
    parser.add_argument('--port', default=int(os.getenv('PORT', '8192')), help='Port to listen for connections')
    args = parser.parse_args()

    api = TrafficAPI(database_path=args.db_path)
    uvicorn.run(api.app, host=args.host, port=args.port)
