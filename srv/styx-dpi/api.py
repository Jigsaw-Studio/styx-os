# Copyright (c) 2024 Steve Castellotti
# This file is part of styx-os and is released under the MIT License.
# See LICENSE file in the project root for full license information.

import argparse
import datetime
import dateutil.relativedelta, dateutil.tz
import os
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
        address: str
        sent: int = 0
        received: int = 0

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
                # Handle timezone abbreviations and full names
                tz = dateutil.tz.gettz(timezone)
                if tz is None:
                    raise HTTPException(status_code=400, detail="Invalid timezone")
                utc_now = utc_now.astimezone(tz)
            except Exception as http_e:
                raise HTTPException(status_code=400, detail=f"Timezone error: {str(http_e)}")
        else:
            tz = dateutil.tz.UTC  # Default to UTC if no timezone is provided

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
                utc_time = (utc_now - delta)
            else:
                utc_time = utc_now

            return utc_time.strftime("%Y-%m-%d %H:%M:%S")

        if date_part and time_part:
            local_time = datetime.datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M:%S")
            local_time = local_time.replace(tzinfo=tz)
            utc_time = local_time.astimezone(dateutil.tz.UTC)
            return utc_time.strftime("%Y-%m-%d %H:%M:%S")
        elif date_part:
            time_part = "00:00:00" if is_start else "23:59:59"
            local_time = datetime.datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M:%S")
            local_time = local_time.replace(tzinfo=tz)
            utc_time = local_time.astimezone(dateutil.tz.UTC)
            return utc_time.strftime("%Y-%m-%d %H:%M:%S")
        elif time_part:
            today = utc_now.date().strftime("%Y-%m-%d")
            local_time = datetime.datetime.strptime(f"{today} {time_part}", "%Y-%m-%d %H:%M:%S")
            local_time = local_time.replace(tzinfo=tz)
            utc_time = local_time.astimezone(dateutil.tz.UTC)
            return utc_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return None

    def setup_routes(self):
        @self.app.get("/v1/domain", response_model=list[self.TrafficSummary])
        def get_domain_summary(
                start_date: Optional[str] = Query(None),
                start_time: Optional[str] = Query(None),
                end_date: Optional[str] = Query(None),
                end_time: Optional[str] = Query(None),
                relative: Optional[str] = Query(None),
                timezone: Optional[str] = Query(None),
                client: Optional[str] = Query(None)
        ):
            if relative and (start_date or start_time or end_date or end_time or timezone):
                raise HTTPException(status_code=400, detail="Cannot specify both relative time and absolute time parameters")

            query = '''
                SELECT domain, SUM(sent) as sent, SUM(received) as received
                FROM traffic
                WHERE domain IS NOT NULL
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

            if client:
                query += " AND local = ?"
                params.append(client)

            query += " GROUP BY domain"

            results = self.query_database(query, tuple(params))

            return [self.TrafficSummary(address=row[0], sent=row[1] or 0, received=row[2] or 0) for row in results]

        @self.app.get("/v1/ip", response_model=list[self.TrafficSummary])
        def get_ip_summary(
                start_date: Optional[str] = Query(None),
                start_time: Optional[str] = Query(None),
                end_date: Optional[str] = Query(None),
                end_time: Optional[str] = Query(None),
                relative: Optional[str] = Query(None),
                timezone: Optional[str] = Query(None),
                client: Optional[str] = Query(None)
        ):
            if relative and (start_date or start_time or end_date or end_time or timezone):
                raise HTTPException(status_code=400, detail="Cannot specify both relative time and absolute time parameters")

            query = '''
                SELECT remote, SUM(sent) as sent, SUM(received) as received
                FROM traffic
            '''
            (query, params) = self.process_query_parameters(query, start_date, start_time, end_date, end_time, timezone, relative, client)

            query += " GROUP BY remote"

            results = self.query_database(query, tuple(params))

            return [self.TrafficSummary(address=row[0], sent=row[1] or 0, received=row[2] or 0) for row in results]

        @self.app.get("/v1/interface", response_model=self.TrafficSummary)
        def get_interface_summary(
                start_date: Optional[str] = Query(None),
                start_time: Optional[str] = Query(None),
                end_date: Optional[str] = Query(None),
                end_time: Optional[str] = Query(None),
                relative: Optional[str] = Query(None),
                timezone: Optional[str] = Query(None),
                client: Optional[str] = Query(None)
        ):
            if relative and (start_date or start_time or end_date or end_time or timezone):
                raise HTTPException(status_code=400, detail="Cannot specify both relative time and absolute time parameters")

            query = '''
                SELECT SUM(sent) as sent, SUM(received) as received
                FROM traffic
            '''
            (query, params) = self.process_query_parameters(query, start_date, start_time, end_date, end_time, timezone, relative, client)

            results = self.query_database(query, tuple(params))

            if results and results[0][0] is not None and results[0][1] is not None:
                return self.TrafficSummary(address="*", sent=results[0][0] or 0, received=results[0][1] or 0)
            else:
                return self.TrafficSummary(address="*", sent=0, received=0)

        @self.app.get("/v1/local", response_model=list[self.TrafficSummary])
        def get_local_summary(
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
                SELECT local, SUM(sent) as sent, SUM(received) as received
                FROM traffic
            '''
            (query, params) = self.process_query_parameters(query, start_date, start_time, end_date, end_time, timezone, relative, None)

            query += " GROUP BY local"

            results = self.query_database(query, tuple(params))

            return [self.TrafficSummary(address=row[0], sent=row[1] or 0, received=row[2] or 0) for row in results]

        @self.app.get("/v1/remote", response_model=list[self.TrafficSummary])
        def get_remote_summary(
                start_date: Optional[str] = Query(None),
                start_time: Optional[str] = Query(None),
                end_date: Optional[str] = Query(None),
                end_time: Optional[str] = Query(None),
                relative: Optional[str] = Query(None),
                timezone: Optional[str] = Query(None),
                client: Optional[str] = Query(None)
        ):
            if relative and (start_date or start_time or end_date or end_time or timezone):
                raise HTTPException(status_code=400, detail="Cannot specify both relative time and absolute time parameters")

            query = '''
                SELECT 
                    COALESCE(domain, remote) as address, 
                    port, 
                    SUM(sent) as sent, 
                    SUM(received) as received
                FROM traffic
            '''
            (query, params) = self.process_query_parameters(query, start_date, start_time, end_date, end_time, timezone, relative, client)

            query += " GROUP BY address, port"

            results = self.query_database(query, tuple(params))

            return [
                self.TrafficSummary(
                    address=f"{row[0]}:{row[1]}", sent=row[2] or 0, received=row[3] or 0
                ) for row in results
            ]

    def process_query_parameters(self, query, start_date, start_time, end_date, end_time, timezone, relative, client):
        params = []

        start_timestamp = self.construct_timestamp(
            start_date, start_time, is_start=True, relative=relative, timezone=timezone
        )
        end_timestamp = self.construct_timestamp(
            end_date, end_time, is_start=False, relative=None, timezone=timezone
        )

        first_conditional = True

        if start_timestamp:
            first_conditional = False
            query += " WHERE timestamp >= ?"
            params.append(start_timestamp)

        if end_timestamp:
            if first_conditional:
                query += " WHERE"
            else:
                query += " AND"
                first_conditional = False
            query += " timestamp <= ?"
            params.append(end_timestamp)

        if client:
            if first_conditional:
                query += " WHERE"
            else:
                query += " AND"
            query += " local = ?"
            params.append(client)

        return query, params

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Report network traffic.")
    parser.add_argument('--db_path', default=os.getenv('DB_PATH', 'data/styx-dpi.db'), help='Path to SQLite3 database (default: data/styx-dpi.db)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--host', default=os.getenv('HOST', '0.0.0.0'), help='Address to listen for connections')
    parser.add_argument('--port', default=int(os.getenv('PORT', '8192')), help='Port to listen for connections')
    args = parser.parse_args()

    if args.debug:
        try:
            import pydevd_pycharm
            pydevd_pycharm.settrace('127.0.0.1', port=12345, stdoutToServer=True, stderrToServer=True, suspend=False)
        except ModuleNotFoundError as e:
            print("IntelliJ debugger not available")

    api = TrafficAPI(database_path=args.db_path)
    uvicorn.run(api.app, host=args.host, port=args.port)
