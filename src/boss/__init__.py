# BOSS 直聘模块
from .browser import BossBrowser
from .scraper import BossScraper, CandidateInfo
from .candidate_scraper import BossCandidateScraper, CandidateSummary, CandidateEval
from .rough_screening import RoughScreeningEngine, RoughEval
from .job_manager import BossJobManager, JobInfo

__all__ = [
    "BossBrowser",
    "BossScraper",
    "CandidateInfo",
    "BossCandidateScraper",
    "CandidateSummary",
    "CandidateEval",
    "RoughScreeningEngine",
    "RoughEval",
    "BossJobManager",
    "JobInfo",
]
