import pytest
import os
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch, MagicMock
from initials_agent.scheduler import Scheduler
from initials_agent.db.session import get_engine, get_session_factory
from initials_agent.db.models import Base, PipelineRunModel, ApprovalRequestModel
from initials_agent.config import get_settings

@pytest.fixture
def session():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = get_session_factory(engine)
    s = Session()
    yield s
    s.close()

@pytest.fixture
def scheduler(session):
    pipeline = MagicMock()
    from unittest.mock import AsyncMock
    pipeline.run = AsyncMock()
    
    pub_srv = MagicMock()
    app_repo = MagicMock()
    
    sched = Scheduler(pipeline, pub_srv, app_repo, session)
    return sched

@pytest.mark.asyncio
async def test_scheduler_timezone_handling(scheduler, monkeypatch):
    # Set to run at 09:00 in Asia/Kolkata
    scheduler.tz = ZoneInfo("Asia/Kolkata")
    scheduler.schedule_hour = 9
    scheduler.schedule_minute = 0
    
    # Mock time to 08:00 Asia/Kolkata (too early)
    mock_now_early = datetime(2026, 9, 6, 8, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    
    with patch("initials_agent.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now_early
        await scheduler._check_schedule()
        
    # Verify no pipeline run created
    runs = scheduler.session.query(PipelineRunModel).all()
    assert len(runs) == 0
    
    # Mock time to 09:05 Asia/Kolkata (time to run)
    mock_now_time = datetime(2026, 9, 6, 9, 5, tzinfo=ZoneInfo("Asia/Kolkata"))
    with patch("initials_agent.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now_time
        await scheduler._check_schedule()
        
    # Verify pipeline run created
    runs = scheduler.session.query(PipelineRunModel).all()
    assert len(runs) == 1
    assert runs[0].run_date == "2026-09-06"
    assert runs[0].status == "success"
    
@pytest.mark.asyncio
async def test_scheduler_duplicate_prevention(scheduler, monkeypatch):
    scheduler.tz = ZoneInfo("Asia/Kolkata")
    scheduler.schedule_hour = 9
    scheduler.schedule_minute = 0
    
    mock_now = datetime(2026, 9, 6, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    
    with patch("initials_agent.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = mock_now
        
        # Call first time
        await scheduler._check_schedule()
        
        # Verify run created
        runs = scheduler.session.query(PipelineRunModel).all()
        assert len(runs) == 1
        assert runs[0].run_date == "2026-09-06"
        
        # Call second time
        await scheduler._check_schedule()
        
        # Verify no duplicate created
        runs = scheduler.session.query(PipelineRunModel).all()
        assert len(runs) == 1 # Still 1
