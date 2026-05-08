# 文档解析模块
from .requirement import RequirementParser, JobRequirement
from .resume import ResumeParser, ResumeInfo

__all__ = [
    "RequirementParser",
    "JobRequirement",
    "ResumeParser",
    "ResumeInfo",
]
