"""Use the existing XSAU calendar, with explicit session/open/close boundaries."""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import pandas as pd
from radar import session_calendar

def open_utc(date):
    return datetime.combine(pd.Timestamp(date).date(),datetime.min.time(),ZoneInfo('Asia/Riyadh')).replace(hour=10).astimezone(timezone.utc)

def close_utc(date):
    return datetime.combine(pd.Timestamp(date).date(),datetime.min.time(),ZoneInfo('Asia/Riyadh')).replace(hour=15,minute=20).astimezone(timezone.utc)

def next_session(date,cfg):
    sessions,_=session_calendar(datetime.combine(pd.Timestamp(date).date(),datetime.min.time(),timezone.utc)+timedelta(days=14,hours=15),cfg)
    later=sessions[sessions>pd.Timestamp(date)]
    if not len(later):raise ValueError('Calendar has no next session')
    return str(later[0].date())

def prospective_source(source,now,registration,cfg):
    sessions,expected=session_calendar(now,cfg);date=source['expected_session'];cutoff=datetime.fromisoformat(registration)
    run_time=datetime.fromisoformat(source['run_utc'])
    valid=(source.get('event')=='schedule' and source.get('conclusion')=='success' and source.get('head_branch')=='main' and source.get('workflow_name')=='TASI Radar 3.0'
           and date==expected and pd.Timestamp(date) in sessions and run_time>=cutoff and close_utc(date)<=run_time<=now
           and pd.Timestamp(date).date()>=cutoff.astimezone(ZoneInfo('Asia/Riyadh')).date() and now<open_utc(next_session(date,cfg)))
    return bool(valid),sessions,expected
