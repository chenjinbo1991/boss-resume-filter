"""
候选人粗筛引擎
基于概要信息进行筛选（无完整简历）
"""
from dataclasses import dataclass, field
from typing import Literal
import os
from dotenv import load_dotenv

from ..parser import JobRequirement
from .candidate_scraper import CandidateSummary, CandidateEval

load_dotenv()


@dataclass
class RoughEval:
    """粗筛评估结果"""

    summary: CandidateSummary
    hard_match: bool = True
    hard_details: dict = field(default_factory=dict)
    soft_score: float = 0.0
    soft_details: dict = field(default_factory=dict)
    total_score: float = 0.0
    match_level: str = ""
    comment: str = ""
    recommend_action: str = ""  # "立即沟通" / "进一步评估" / "暂不考虑"


class RoughScreeningEngine:
    """粗筛引擎"""

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

    # 权重配置（粗筛更看重核心条件）
    WEIGHTS = {
        "position_match": 0.30,  # 职位匹配度
        "experience": 0.25,  # 工作年限
        "education": 0.15,  # 学历
        "company": 0.15,  # 公司背景
        "skills": 0.15,  # 技能匹配
    }

    def __init__(self):
        pass

    def evaluate(
        self,
        requirement: JobRequirement,
        summary: CandidateSummary,
        use_llm: bool = False,
        llm=None,
    ) -> RoughEval:
        """
        执行粗筛评估

        Args:
            requirement: 职位需求
            summary: 候选人概要信息
            use_llm: 是否使用 LLM 生成评语
            llm: LLM 实例

        Returns:
            粗筛评估结果
        """
        result = RoughEval(summary=summary)

        # 1. 硬条件过滤
        result.hard_match, result.hard_details = self._check_hard_requirements(
            requirement, summary
        )

        # 2. 软条件打分
        result.soft_score, result.soft_details = self._score_soft_requirements(
            requirement, summary
        )

        # 3. 计算综合得分
        if result.hard_match:
            result.total_score = result.soft_score
        else:
            # 硬条件不满足，直接给低分
            result.total_score = result.soft_score * 0.3

        # 4. 确定匹配等级
        result.match_level = self._get_match_level(result.total_score)

        # 5. 生成建议操作
        result.recommend_action = self._get_recommend_action(result)

        # 6. 生成评语
        if use_llm and llm:
            result.comment = self._generate_comment(requirement, summary, result, llm)
        else:
            result.comment = self._simple_comment(requirement, summary, result)

        return result

    def _check_hard_requirements(
        self, req: JobRequirement, summary: CandidateSummary
    ) -> tuple[bool, dict]:
        """
        检查硬条件（基于概要信息）
        """
        details = {}
        all_pass = True

        # 1. 必须技能（从概要的技能标签判断）
        if req.required_skills:
            # 技能标签通常是简称，需要模糊匹配
            matched_skills = []
            for skill in req.required_skills:
                for tag in summary.skills:
                    if skill.lower() in tag.lower() or skill in tag:
                        matched_skills.append(skill)
                        break

            passed = len(matched_skills) >= len(req.required_skills) * 0.5  # 概要信息下，匹配 50% 就算过
            details["required_skills"] = {
                "required": req.required_skills,
                "matched": matched_skills,
                "missing": [s for s in req.required_skills if s not in matched_skills],
                "passed": passed,
            }
            # 粗筛阶段技能不作为硬过滤
            # if not passed:
            #     all_pass = False

        # 2. 最低工作年限
        if req.min_years is not None:
            years = self._parse_years(summary.experience)
            passed = years is not None and years >= req.min_years
            details["min_years"] = {
                "required": req.min_years,
                "actual": years,
                "parsed_from": summary.experience,
                "passed": passed,
            }
            if not passed:
                all_pass = False

        # 3. 学历要求
        if req.required_education:
            resume_edu_level = self.EDUCATION_LEVELS.get(summary.education, 0)
            required_max_level = max(
                self.EDUCATION_LEVELS.get(e, 0) for e in req.required_education
            )
            passed = resume_edu_level >= required_max_level

            # 学信网可查要求（如明确要求）
            education_check_pass = True
            if req.education_check:
                # 概要信息中无法判断学信网，标记为"待验证"
                education_check_pass = None  # None 表示待验证

            details["education"] = {
                "required": req.required_education,
                "actual": summary.education,
                "level": resume_edu_level,
                "required_level": required_max_level,
                "education_check_required": req.education_check,
                "education_check_status": education_check_pass,
                "passed": passed,
            }
            if not passed:
                all_pass = False

        # 4. 行业背景（如有明确要求，粗筛阶段可放宽）
        if req.required_industry:
            passed = summary.industry in req.required_industry
            details["industry"] = {
                "required": req.required_industry,
                "actual": summary.industry,
                "passed": passed,
            }
            # 粗筛阶段行业不作为硬过滤

        return all_pass, details

    def _score_soft_requirements(
        self, req: JobRequirement, summary: CandidateSummary
    ) -> tuple[float, dict]:
        """
        软条件打分 (0-100)
        """
        details = {}
        total_score = 0.0

        # 1. 职位匹配分 (30 分)
        position_score = self._score_position_match(req, summary)
        details["position_match"] = position_score
        total_score += position_score * self.WEIGHTS["position_match"]

        # 2. 工作经验分 (25 分)
        exp_score = self._score_experience(req, summary)
        details["experience"] = exp_score
        total_score += exp_score * self.WEIGHTS["experience"]

        # 3. 学历分 (15 分)
        edu_score = self._score_education(req, summary)
        details["education"] = edu_score
        total_score += edu_score * self.WEIGHTS["education"]

        # 4. 公司背景分 (15 分)
        company_score = self._score_company(req, summary)
        details["company"] = company_score
        total_score += company_score * self.WEIGHTS["company"]

        # 5. 技能匹配分 (15 分)
        skill_score = self._score_skills(req, summary)
        details["skills"] = skill_score
        total_score += skill_score * self.WEIGHTS["skills"]

        return total_score, details

    def _score_position_match(
        self, req: JobRequirement, summary: CandidateSummary
    ) -> float:
        """职位匹配分 (0-100)"""
        if not req.position_name:
            return 80.0

        # 职位名称匹配
        req_keywords = self._extract_keywords(req.position_name)
        candidate_keywords = self._extract_keywords(summary.position)

        matched = sum(1 for kw in req_keywords if kw in candidate_keywords)
        total = len(req_keywords)

        if total == 0:
            return 80.0

        return (matched / total) * 100

    def _score_experience(
        self, req: JobRequirement, summary: CandidateSummary
    ) -> float:
        """工作经验分 (0-100)"""
        years = self._parse_years(summary.experience)

        if years is None:
            return 60.0  # 未知年限，给中间分

        # 理想区间：min_years 到 max_years 之间
        if req.min_years and req.max_years:
            if req.min_years <= years <= req.max_years:
                return 100.0
            elif years < req.min_years:
                diff = req.min_years - years
                return max(0, 100 - diff * 20)
            else:
                diff = years - req.max_years
                return max(0, 100 - diff * 10)
        elif req.min_years:
            if years >= req.min_years:
                return 100.0
            else:
                diff = req.min_years - years
                return max(0, 100 - diff * 20)

        return 80.0

    def _score_education(
        self, req: JobRequirement, summary: CandidateSummary
    ) -> float:
        """学历分 (0-100)"""
        resume_level = self.EDUCATION_LEVELS.get(summary.education, 0)

        # 有明确要求
        if req.required_education:
            required_level = max(
                self.EDUCATION_LEVELS.get(e, 0) for e in req.required_education
            )
            if resume_level >= required_level:
                # 名校加分
                if summary.school and any(
                    kw in summary.school for kw in ["大学", "学院"]
                ):
                    return 100.0
                return 90.0
            else:
                return 50.0

        # 没有明确要求，根据学历层级给分
        if resume_level >= 5:  # 硕士及以上
            return 100.0
        elif resume_level == 4:  # 本科
            return 85.0
        elif resume_level == 3:  # 大专
            return 70.0
        else:
            return 50.0

    def _score_company(
        self, req: JobRequirement, summary: CandidateSummary
    ) -> float:
        """公司背景分 (0-100)"""
        if not summary.company:
            return 50.0

        # 知名公司加分
        company_keywords = [
            "大厂", "阿里", "腾讯", "字节", "百度", "京东", "美团", "华为", "小米",
            "互联网", "科技", "世界 500 强", "上市", "知名"
        ]

        for kw in company_keywords:
            if kw in summary.company:
                return 95.0

        # 根据行业判断
        if req.preferred_industry:
            if summary.industry in req.preferred_industry:
                return 90.0

        return 70.0

    def _score_skills(
        self, req: JobRequirement, summary: CandidateSummary
    ) -> float:
        """技能匹配分 (0-100)"""
        if not req.preferred_skills and not req.required_skills:
            return 80.0

        all_skills = req.required_skills + req.preferred_skills
        if not all_skills:
            return 80.0

        matched = 0
        for skill in all_skills:
            for tag in summary.skills:
                if skill.lower() in tag.lower() or skill in tag:
                    matched += 1
                    break

        return (matched / len(all_skills)) * 100

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

    def _get_recommend_action(self, result: RoughEval) -> str:
        """生成建议操作"""
        if result.match_level == "S":
            return "🔥 立即沟通"
        elif result.match_level == "A":
            return "✅ 进一步评估"
        elif result.match_level == "B":
            return "⚠️ 备选考察"
        else:
            return "❌ 暂不考虑"

    def _parse_years(self, experience_text: str) -> int | None:
        """从经验文本中解析工作年限"""
        if not experience_text:
            return None

        import re

        # 匹配 "3 年"、"3-5 年"、"三年以上" 等
        match = re.search(r'(\d+)[\-至～到]?(\d+)?年', experience_text)
        if match:
            return int(match.group(1))

        # 匹配 "3+" 等
        match = re.search(r'(\d+)\+', experience_text)
        if match:
            return int(match.group(1))

        return None

    def _extract_keywords(self, text: str) -> list[str]:
        """提取关键词"""
        if not text:
            return []

        # 简单分词（中文按字符，英文按空格）
        keywords = []

        # 提取英文单词
        import re
        en_words = re.findall(r'[A-Za-z]+', text)
        keywords.extend([w.lower() for w in en_words])

        # 提取中文关键词（简化处理）
        zh_chars = re.findall(r'[一-龥]+', text)
        keywords.extend(zh_chars)

        return keywords

    def _generate_comment(
        self, req: JobRequirement, summary: CandidateSummary, result: RoughEval, llm
    ) -> str:
        """生成 LLM 评语"""
        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一位资深 HR，擅长简历筛选。请根据以下职位需求和候选人概要信息，生成简短的评语（30 字以内）。"),
            ("user", """职位：{position}
要求：{min_years}年以上，{education}

候选人：{name}
当前：{position}@{company}
经验：{experience}
学历：{education}@{school}
技能：{skills}

硬条件：{hard_match}
得分：{score}"""),
        ])

        chain = prompt | llm

        try:
            response = chain.invoke({
                "position": req.position_name,
                "min_years": req.min_years or "?",
                "education": ",".join(req.required_education) or "?",
                "name": summary.name,
                "company": summary.company or "未知",
                "position": summary.position or "未知",
                "experience": summary.experience or "未知",
                "education": summary.education or "未知",
                "school": summary.school or "未知",
                "skills": ",".join(summary.skills[:3]) or "无",
                "hard_match": "是" if result.hard_match else "否",
                "score": f"{result.total_score:.1f}",
            })

            if hasattr(response, "content"):
                return response.content.strip()[:50]
            return str(response).strip()[:50]
        except Exception as e:
            return self._simple_comment(req, summary, result)

    def _simple_comment(
        self, req: JobRequirement, summary: CandidateSummary, result: RoughEval
    ) -> str:
        """简单评语（LLM 不可用时）"""
        parts = []

        if result.hard_match:
            parts.append(f"硬条件满足")
        else:
            parts.append(f"硬条件不满足")

        parts.append(f"得分{result.total_score:.1f}")

        if summary.experience:
            parts.append(f"{summary.experience}")

        if summary.education:
            parts.append(summary.education)

        return " | ".join(parts)
