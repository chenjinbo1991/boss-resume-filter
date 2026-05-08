"""
BOSS 直聘候选人筛选模块
支持两阶段筛选：
1. 粗筛：基于候选人概要信息（无简历）
2. 细筛：基于完整简历
"""
import asyncio
from typing import AsyncGenerator
from dataclasses import dataclass, field
from .browser import BossBrowser


@dataclass
class CandidateSummary:
    """候选人概要信息（粗筛用）"""

    candidate_id: str
    name: str  # 通常被隐藏，显示"某先生/女士"
    position: str  # 当前职位/期望职位
    company: str  # 当前公司
    industry: str  # 当前行业
    experience: str  # 工作年限
    education: str  # 学历
    school: str  # 毕业院校
    skills: list[str]  # 技能标签
    expect_city: str  # 期望城市
    expect_salary: str  # 期望薪资
    status: str  # 求职状态
    active_time: str  # 最近活跃时间
    match_tags: list[str]  # BOSS 匹配标签（如"3 年经验"、"本科"等）

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "name": self.name,
            "position": self.position,
            "company": self.company,
            "industry": self.industry,
            "experience": self.experience,
            "education": self.education,
            "school": self.school,
            "skills": self.skills,
            "expect_city": self.expect_city,
            "expect_salary": self.expect_salary,
            "status": self.status,
            "active_time": self.active_time,
        }


@dataclass
class CandidateEval:
    """候选人评估结果"""

    summary: CandidateSummary
    hard_match: bool = True  # 硬条件是否满足
    hard_details: dict = field(default_factory=dict)  # 硬条件详情
    soft_score: float = 0.0  # 软条件得分 (0-100)
    total_score: float = 0.0  # 综合得分
    match_level: str = ""  # S/A/B/C/D
    comment: str = ""  # 评估评语
    recommend_action: str = ""  # 建议操作（"立即沟通"/"进一步评估"/"暂不考虑"）

    def to_dict(self) -> dict:
        return {
            **self.summary.to_dict(),
            "hard_match": self.hard_match,
            "soft_score": round(self.soft_score, 2),
            "total_score": round(self.total_score, 2),
            "match_level": self.match_level,
            "comment": self.comment,
            "recommend_action": self.recommend_action,
        }


class BossCandidateScraper:
    """BOSS 直聘候选人爬取器"""

    def __init__(self, browser: BossBrowser):
        self.browser = browser

    async def get_job_recommendations(
        self,
        job_id: str = None,
        job_name: str = None,
        max_pages: int = 10,
    ) -> AsyncGenerator[CandidateSummary, None]:
        """
        获取推荐牛人列表

        Args:
            job_id: 职位 ID（从职位管理栏获取）
            job_name: 职位名称
            max_pages: 最大翻页数
        """
        page = self.browser.page
        if not page:
            return

        # 进入推荐牛人页面
        if job_id:
            # 特定职位的推荐
            url = f"https://www.zhipin.com/job/apply/{job_id}.html"
        else:
            # 推荐牛人首页
            url = "https://www.zhipin.com/web/geek/recommend"

        await self.browser.goto(url)
        await asyncio.sleep(3)

        for page_num in range(max_pages):
            if not page:
                break

            print(f"正在爬取第 {page_num + 1} 页推荐候选人...")

            # 提取当前页候选人
            candidates = await self._extract_candidate_cards(page)

            for candidate in candidates:
                yield candidate

            # 翻到下一页
            if page_num < max_pages - 1:
                next_btn = await page.query_selector(
                    '.pagination-next, a:contains("下一页"), button:contains("下一页")'
                )
                if next_btn:
                    await next_btn.click()
                    await asyncio.sleep(3)
                else:
                    print("已到最后页")
                    break

    async def _extract_candidate_cards(self, page) -> list[CandidateSummary]:
        """
        提取候选人卡片信息（概要信息）
        """
        candidates = []

        # BOSS 直聘推荐牛人页面的卡片选择器
        # 实际选择器需要根据页面 HTML 结构调整
        cards = await page.query_selector_all(
            '.candidate-card, .recommend-card, [class*="recommend"], [class*="candidate"]'
        )

        # 如果没有找到，尝试更宽泛的选择器
        if not cards:
            cards = await page.query_selector_all('div[class*="card"]')

        for idx, card in enumerate(cards):
            try:
                # 提取候选人 ID
                link = await card.query_selector("a[href*='/job/']")
                if not link:
                    # 尝试其他可能的链接格式
                    link = await card.query_selector("a[href*='/geek/']")

                href = await link.get_attribute("href") if link else ""
                candidate_id = self._extract_id_from_href(href) if href else f"unknown_{idx}"

                # 提取基本信息
                # 姓名（通常被隐藏）
                name_el = await card.query_selector(".name, .candidate-name, h3")
                name = await name_el.inner_text() if name_el else "未知"

                # 职位/期望职位
                position_el = await card.query_selector(".position, .job-title, .expect-position")
                position = await position_el.inner_text() if position_el else ""

                # 公司
                company_el = await card.query_selector(".company, .company-name")
                company = await company_el.inner_text() if company_el else ""

                # 行业
                industry_el = await card.query_selector(".industry")
                industry = await industry_el.inner_text() if industry_el else ""

                # 工作年限
                exp_el = await card.query_selector(".experience, [class*='exp']")
                experience = await exp_el.inner_text() if exp_el else ""

                # 学历
                edu_el = await card.query_selector(".education, [class*='edu']")
                education = await edu_el.inner_text() if edu_el else ""

                # 毕业院校
                school_el = await card.query_selector(".school, .university")
                school = await school_el.inner_text() if school_el else ""

                # 技能标签
                skill_els = await card.query_selector_all(
                    ".skill-tag, .tag, [class*='skill'], [class*='label']"
                )
                skills = []
                for skill_el in skill_els:
                    skill_text = await skill_el.inner_text()
                    if skill_text and len(skill_text) < 20:  # 过滤太长的文本
                        skills.append(skill_text)

                # 期望城市
                city_el = await card.query_selector(".city, .expect-city")
                expect_city = await city_el.inner_text() if city_el else ""

                # 期望薪资
                salary_el = await card.query_selector(".salary, .expect-salary")
                expect_salary = await salary_el.inner_text() if salary_el else ""

                # 求职状态
                status_el = await card.query_selector(".status, .job-status")
                status = await status_el.inner_text() if status_el else "未知"

                # 最近活跃时间
                active_el = await card.query_selector(".active-time, [class*='active']")
                active_time = await active_el.inner_text() if active_el else ""

                # 匹配标签（BOSS 会根据职位要求显示匹配标签）
                tag_els = await card.query_selector_all(".match-tag, [class*='match']")
                match_tags = []
                for tag_el in tag_els:
                    tag_text = await tag_el.inner_text()
                    if tag_text:
                        match_tags.append(tag_text)

                candidates.append(
                    CandidateSummary(
                        candidate_id=candidate_id,
                        name=name,
                        position=position,
                        company=company,
                        industry=industry,
                        experience=experience,
                        education=education,
                        school=school,
                        skills=skills,
                        expect_city=expect_city,
                        expect_salary=expect_salary,
                        status=status,
                        active_time=active_time,
                        match_tags=match_tags,
                    )
                )
            except Exception as e:
                print(f"提取候选人信息失败 (idx={idx}): {e}")
                continue

        return candidates

    def _extract_id_from_href(self, href: str) -> str:
        """从 URL 中提取候选人 ID"""
        if not href:
            return ""

        # 可能的 URL 格式:
        # /job/12345678.html
        # /geek/12345678/
        # ?job_id=12345678

        import re

        # 提取数字 ID
        match = re.search(r'(\d+)', href)
        return match.group(1) if match else ""

    async def get_candidate_count(self) -> int:
        """获取当前页候选人数量"""
        if not self.browser.page:
            return 0

        cards = await self.browser.page.query_selector_all(
            '.candidate-card, .recommend-card'
        )
        return len(cards)
