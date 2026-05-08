"""
BOSS 直聘简历爬取模块
"""
import asyncio
from typing import AsyncGenerator
from dataclasses import dataclass
from .browser import BossBrowser


@dataclass
class CandidateInfo:
    """候选人基本信息"""

    candidate_id: str
    name: str
    position: str  # 当前职位
    company: str  # 当前公司
    experience: str  # 工作年限
    education: str  # 学历
    skills: list[str]  # 技能标签
    expect_city: str  # 期望城市
    expect_salary: str  # 期望薪资
    status: str  # 求职状态（如"在职看机会"）


class BossScraper:
    """BOSS 直聘简历爬取器"""

    def __init__(self, browser: BossBrowser):
        self.browser = browser

    async def get_candidate_list(
        self,
        keywords: str,
        max_pages: int = 5,
    ) -> AsyncGenerator[CandidateInfo, None]:
        """
        获取候选人列表（生成器，逐个返回）

        Args:
            keywords: 搜索关键词
            max_pages: 最大翻页数
        """
        page = self.browser.page
        if not page:
            return

        # 执行搜索
        await self.browser.search_candidates(keywords)
        await asyncio.sleep(2)

        for page_num in range(max_pages):
            if not page:
                break

            # 提取当前页候选人列表
            candidates = await self._extract_candidate_cards(page)

            for candidate in candidates:
                yield candidate

            # 翻到下一页
            if page_num < max_pages - 1:
                next_btn = await page.query_selector(
                    '.next-btn, a:has-text("下一页"), .pagination-next'
                )
                if next_btn:
                    await next_btn.click()
                    await asyncio.sleep(2)
                else:
                    print("已到最后页")
                    break

    async def _extract_candidate_cards(self, page) -> list[CandidateInfo]:
        """
        提取当前页的候选人卡片信息
        """
        candidates = []

        # 查找候选人卡片容器（选择器需根据实际页面调整）
        cards = await page.query_selector_all(
            '.job-card, .candidate-card, [class*="job-card"]'
        )

        for idx, card in enumerate(cards):
            try:
                # 提取候选人 ID（从链接中）
                link = await card.query_selector("a[href*='/job/']")
                if not link:
                    continue

                href = await link.get_attribute("href")
                candidate_id = self._extract_id_from_href(href)

                # 提取职位名称
                position_el = await card.query_selector(".position-name, h3, .job-title")
                position = await position_el.inner_text() if position_el else ""

                # 提取公司信息
                company_el = await card.query_selector(".company-name, .company")
                company = await company_el.inner_text() if company_el else ""

                # 提取经验要求
                exp_el = await card.query_selector(".experience, [class*='experience']")
                experience = await exp_el.inner_text() if exp_el else ""

                # 提取学历要求
                edu_el = await card.query_selector(".education, [class*='education']")
                education = await edu_el.inner_text() if edu_el else ""

                # 提取技能标签
                skill_els = await card.query_selector_all(".skill-tag, .tag")
                skills = []
                for skill_el in skill_els:
                    skill_text = await skill_el.inner_text()
                    if skill_text:
                        skills.append(skill_text)

                # 提取求职状态
                status_el = await card.query_selector(".status, .job-status")
                status = await status_el.inner_text() if status_el else ""

                candidates.append(
                    CandidateInfo(
                        candidate_id=candidate_id,
                        name=f"候选人{idx + 1}",  # BOSS 上通常不显示真实姓名
                        position=position,
                        company=company,
                        experience=experience,
                        education=education,
                        skills=skills,
                        expect_city="",
                        expect_salary="",
                        status=status,
                    )
                )
            except Exception as e:
                print(f"提取候选人信息失败：{e}")
                continue

        return candidates

    def _extract_id_from_href(self, href: str) -> str:
        """从 URL 中提取候选人 ID"""
        # 示例：/job/detail/12345678 -> 12345678
        if not href:
            return ""

        # 提取 ID 部分
        parts = href.rstrip("/").split("/")
        return parts[-1] if parts else ""

    async def download_all_resumes(
        self,
        candidates: list[CandidateInfo],
        delay: float = 2.0,
    ) -> list[tuple[CandidateInfo, str | None]]:
        """
        批量下载简历

        Args:
            candidates: 候选人列表
            delay: 下载间隔（秒），避免触发反爬

        Returns:
            [(候选人信息，简历路径), ...]
        """
        results = []

        for idx, candidate in enumerate(candidates):
            print(f"[{idx + 1}/{len(candidates)}] 下载 {candidate.position} - {candidate.company}")

            resume_path = await self.browser.download_resume(
                candidate.candidate_id,
                candidate.name or f"candidate_{candidate.candidate_id}",
            )

            results.append((candidate, resume_path))

            if idx < len(candidates) - 1:
                await asyncio.sleep(delay)

        return results
