"""
匹配度评分引擎
硬条件过滤 + 软条件打分 + 综合排序
"""
import os
from dataclasses import dataclass, field
from typing import Literal

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate

# 尝试导入 Claude
try:
    from langchain_anthropic import ChatAnthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

# 尝试导入 OpenAI 兼容接口（用于本地 Qwen 等）
try:
    from langchain_openai import ChatOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# 尝试导入 Ollama
try:
    from langchain_community.llms import Ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False

from ..parser import JobRequirement, ResumeInfo

load_dotenv()


@dataclass
class MatchResult:
    """匹配结果"""

    resume: ResumeInfo
    requirement: JobRequirement

    # 硬条件匹配
    hard_match: bool = True  # 是否满足所有硬条件
    hard_details: dict = field(default_factory=dict)  # 硬条件匹配详情

    # 软条件打分
    soft_score: float = 0.0  # 软条件得分 (0-100)
    soft_details: dict = field(default_factory=dict)  # 软条件打分详情

    # 综合得分
    total_score: float = 0.0  # 综合得分 (0-100)
    match_level: str = ""  # 匹配等级 (S/A/B/C/D)

    # LLM 评语
    llm_comment: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.resume.name,
            "phone": self.resume.phone,
            "email": self.resume.email,
            "current_company": self.resume.current_company,
            "current_position": self.resume.current_position,
            "education": self.resume.education,
            "years_of_experience": self.resume.years_of_experience,
            "skills": ", ".join(self.resume.skills),
            "hard_match": self.hard_match,
            "hard_details": self.hard_details,
            "soft_score": round(self.soft_score, 2),
            "soft_details": self.soft_details,
            "total_score": round(self.total_score, 2),
            "match_level": self.match_level,
            "llm_comment": self.llm_comment,
            "file_path": self.resume.file_path,
        }


class MatchEngine:
    """匹配度评分引擎"""

    # 学历层级映射
    EDUCATION_LEVELS = {
        "中专": 1,
        "高中": 2,
        "职高": 2,
        "大专": 3,
        "本科": 4,
        "学士": 4,
        "硕士": 5,
        "博士": 6,
        "博士后": 7,
    }

    # 权重配置
    WEIGHTS = {
        "skills": 0.35,  # 技能匹配
        "experience": 0.25,  # 工作经验
        "education": 0.15,  # 学历
        "industry": 0.15,  # 行业背景
        "projects": 0.10,  # 项目经验
    }

    def __init__(self, use_claude: bool = False):
        """
        初始化匹配引擎

        Args:
            use_claude: 是否使用 Claude API，False 则使用本地 LLM
        """
        self.use_claude = use_claude and HAS_ANTHROPIC and os.getenv("ANTHROPIC_API_KEY")

        # 读取本地 LLM 配置
        self.local_llm_type = os.getenv("LOCAL_LLM_TYPE", "openai").lower()  # openai / ollama
        self.local_base_url = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
        self.local_model_name = os.getenv("LOCAL_LLM_MODEL", "qwen2.5:7b")
        self.local_api_key = os.getenv("LOCAL_LLM_API_KEY", "ollama")  # Ollama 默认不需要 key

        if self.use_claude:
            # 使用 Claude API
            self.llm = ChatAnthropic(
                model=os.getenv("MODEL_NAME", "claude-sonnet-4-6"),
                temperature=0.1,
                max_tokens=1024,
            )
        elif self.local_llm_type == "openai" and HAS_OPENAI:
            # 使用 OpenAI 兼容接口（Qwen、DeepSeek 等）
            self.llm = ChatOpenAI(
                model=self.local_model_name,
                base_url=self.local_base_url,
                api_key=self.local_api_key,
                temperature=0.1,
                max_tokens=1024,
            )
        elif self.local_llm_type == "ollama" and HAS_OLLAMA:
            # 使用 Ollama
            self.llm = Ollama(
                model=self.local_model_name,
                base_url=self.local_base_url.replace("/v1", ""),
                temperature=0.1,
            )
        else:
            # 降级到 Ollama 默认配置
            if HAS_OLLAMA:
                self.llm = Ollama(model="qwen2.5:7b", temperature=0.1)
            else:
                self.llm = None
                print("⚠️ 警告：未配置可用的 LLM，评语功能将不可用")

    def match(self, requirement: JobRequirement, resume: ResumeInfo) -> MatchResult:
        """
        执行匹配评分

        Args:
            requirement: 职位需求
            resume: 简历信息

        Returns:
            匹配结果
        """
        result = MatchResult(resume=resume, requirement=requirement)

        # 1. 硬条件过滤
        result.hard_match, result.hard_details = self._check_hard_requirements(
            requirement, resume
        )

        # 2. 软条件打分
        result.soft_score, result.soft_details = self._score_soft_requirements(
            requirement, resume
        )

        # 3. 计算综合得分
        if result.hard_match:
            result.total_score = result.soft_score
        else:
            # 硬条件不满足，直接给低分
            result.total_score = result.soft_score * 0.3

        # 4. 确定匹配等级
        result.match_level = self._get_match_level(result.total_score)

        # 5. 生成 LLM 评语
        result.llm_comment = self._generate_comment(requirement, resume, result)

        return result

    def _check_hard_requirements(
        self, req: JobRequirement, resume: ResumeInfo
    ) -> tuple[bool, dict]:
        """
        检查硬条件

        Returns:
            (是否满足，详情)
        """
        details = {}
        all_pass = True

        # 1. 必须技能
        if req.required_skills:
            matched_skills = [
                s for s in req.required_skills if s in resume.skills
            ]
            passed = len(matched_skills) == len(req.required_skills)
            details["required_skills"] = {
                "required": req.required_skills,
                "matched": matched_skills,
                "missing": [s for s in req.required_skills if s not in resume.skills],
                "passed": passed,
            }
            if not passed:
                all_pass = False

        # 2. 最低工作年限
        if req.min_years is not None:
            passed = (
                resume.years_of_experience is not None
                and resume.years_of_experience >= req.min_years
            )
            details["min_years"] = {
                "required": req.min_years,
                "actual": resume.years_of_experience,
                "passed": passed,
            }
            if not passed:
                all_pass = False

        # 3. 最高工作年限（如有）
        if req.max_years is not None and resume.years_of_experience is not None:
            passed = resume.years_of_experience <= req.max_years
            details["max_years"] = {
                "max": req.max_years,
                "actual": resume.years_of_experience,
                "passed": passed,
            }
            # 最高年限通常不作为硬过滤条件
            # if not passed:
            #     all_pass = False

        # 4. 学历要求
        if req.required_education:
            resume_edu_level = self.EDUCATION_LEVELS.get(resume.education, 0)
            required_max_level = max(
                self.EDUCATION_LEVELS.get(e, 0) for e in req.required_education
            )
            passed = resume_edu_level >= required_max_level
            details["education"] = {
                "required": req.required_education,
                "actual": resume.education,
                "passed": passed,
            }
            if not passed:
                all_pass = False

        # 5. 行业背景（如有明确要求）
        if req.required_industry:
            passed = resume.industry in req.required_industry
            details["industry"] = {
                "required": req.required_industry,
                "actual": resume.industry,
                "passed": passed,
            }
            # 行业背景通常不作为硬过滤
            # if not passed:
            #     all_pass = False

        return all_pass, details

    def _score_soft_requirements(
        self, req: JobRequirement, resume: ResumeInfo
    ) -> tuple[float, dict]:
        """
        软条件打分 (0-100)

        Returns:
            (总分，详情)
        """
        details = {}
        total_score = 0.0

        # 1. 技能匹配分 (35 分)
        skill_score = self._score_skills(req, resume)
        details["skills"] = skill_score
        total_score += skill_score * self.WEIGHTS["skills"]

        # 2. 工作经验分 (25 分)
        exp_score = self._score_experience(req, resume)
        details["experience"] = exp_score
        total_score += exp_score * self.WEIGHTS["experience"]

        # 3. 学历分 (15 分)
        edu_score = self._score_education(req, resume)
        details["education"] = edu_score
        total_score += edu_score * self.WEIGHTS["education"]

        # 4. 行业背景分 (15 分)
        industry_score = self._score_industry(req, resume)
        details["industry"] = industry_score
        total_score += industry_score * self.WEIGHTS["industry"]

        # 5. 项目经验分 (10 分)
        project_score = self._score_projects(req, resume)
        details["projects"] = project_score
        total_score += project_score * self.WEIGHTS["projects"]

        return total_score, details

    def _score_skills(self, req: JobRequirement, resume: ResumeInfo) -> float:
        """技能匹配分 (0-100)"""
        if not req.preferred_skills:
            return 100.0  # 没有加分技能要求，满分

        matched = [s for s in req.preferred_skills if s in resume.skills]
        return (len(matched) / len(req.preferred_skills)) * 100

    def _score_experience(self, req: JobRequirement, resume: ResumeInfo) -> float:
        """工作经验分 (0-100)"""
        if resume.years_of_experience is None:
            return 50.0  # 未知年限，给中间分

        # 理想区间：min_years 到 max_years 之间
        if req.min_years and req.max_years:
            if req.min_years <= resume.years_of_experience <= req.max_years:
                return 100.0
            elif resume.years_of_experience < req.min_years:
                diff = req.min_years - resume.years_of_experience
                return max(0, 100 - diff * 20)
            else:
                diff = resume.years_of_experience - req.max_years
                return max(0, 100 - diff * 10)  # 超出扣分较少
        elif req.min_years:
            if resume.years_of_experience >= req.min_years:
                return 100.0
            else:
                diff = req.min_years - resume.years_of_experience
                return max(0, 100 - diff * 20)

        return 100.0

    def _score_education(self, req: JobRequirement, resume: ResumeInfo) -> float:
        """学历分 (0-100)"""
        resume_level = self.EDUCATION_LEVELS.get(resume.education, 0)

        # 有明确要求
        if req.required_education:
            required_level = max(
                self.EDUCATION_LEVELS.get(e, 0) for e in req.required_education
            )
            if resume_level >= required_level:
                return 100.0
            else:
                return 50.0  # 不满足要求，给一半分

        # 没有明确要求，根据学历层级给分
        if resume_level >= 5:  # 硕士及以上
            return 100.0
        elif resume_level == 4:  # 本科
            return 85.0
        elif resume_level == 3:  # 大专
            return 70.0
        else:
            return 50.0

    def _score_industry(self, req: JobRequirement, resume: ResumeInfo) -> float:
        """行业背景分 (0-100)"""
        # 有要求的行业
        if req.preferred_industry:
            if resume.industry in req.preferred_industry:
                return 100.0
            elif resume.industry:
                return 60.0  # 有其他行业经验
            else:
                return 40.0

        # 没有明确要求，有行业经验就给满分
        return 100.0 if resume.industry else 80.0

    def _score_projects(self, req: JobRequirement, resume: ResumeInfo) -> float:
        """项目经验分 (0-100)"""
        if not req.preferred_project_type:
            return 100.0

        matched = [p for p in req.preferred_project_type if p in resume.project_types]
        return (len(matched) / len(req.preferred_project_type)) * 100

    def _get_match_level(self, score: float) -> str:
        """根据分数确定匹配等级"""
        if score >= 90:
            return "S"
        elif score >= 80:
            return "A"
        elif score >= 70:
            return "B"
        elif score >= 60:
            return "C"
        else:
            return "D"

    def _generate_comment(
        self, req: JobRequirement, resume: ResumeInfo, result: MatchResult
    ) -> str:
        """生成 LLM 评语"""
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一位资深 HR，擅长简历筛选。请根据以下职位需求和简历信息，生成简短的评语（50 字以内）。"
                    "重点说明候选人的优势和不足。",
                ),
                (
                    "user",
                    """职位：{position}
要求技能：{required_skills}
加分技能：{preferred_skills}

候选人：{name}
当前：{position}@{company}
技能：{skills}
经验：{years}年
学历：{education}

硬条件匹配：{hard_match}
软条件得分：{soft_score}
""",
                ),
            ]
        )

        chain = prompt | self.llm

        try:
            response = chain.invoke(
                {
                    "position": req.position_name,
                    "required_skills": ", ".join(req.required_skills) or "无",
                    "preferred_skills": ", ".join(req.preferred_skills) or "无",
                    "name": resume.name or "未知",
                    "company": resume.current_company or "未知",
                    "position": resume.current_position or "未知",
                    "skills": ", ".join(resume.skills[:5]) or "无",
                    "years": resume.years_of_experience or "未知",
                    "education": resume.education or "未知",
                    "hard_match": "是" if result.hard_match else "否",
                    "soft_score": round(result.soft_score, 1),
                }
            )

            # 处理不同类型的响应
            if hasattr(response, "content"):
                return response.content.strip()
            elif hasattr(response, "text"):
                return response.text.strip()
            else:
                return str(response).strip()
        except Exception as e:
            # LLM 调用失败，返回简单评语
            if result.hard_match:
                return f"硬条件满足，软条件得分{result.soft_score:.1f}，建议面试"
            else:
                return f"硬条件不满足，建议慎重"
