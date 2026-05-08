"""
BOSS 直聘职位管理模块
负责获取已发布职位列表和职位详情
"""
import asyncio
from dataclasses import dataclass
from typing import AsyncGenerator
from .browser import BossBrowser


@dataclass
class JobInfo:
    """职位信息"""
    job_id: str
    job_name: str
    department: str  # 所属部门
    category: str  # 职位类别
    city: str  # 工作城市
    salary: str  # 薪资范围
    experience: str  # 经验要求
    education: str  # 学历要求
    description: str  # 职位描述
    requirements: str  # 职位要求
    status: str  # 发布状态（招聘中/已关闭等）
    apply_count: int  # 投递人数
    view_count: int  # 查看人数

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "job_name": self.job_name,
            "department": self.department,
            "category": self.category,
            "city": self.city,
            "salary": self.salary,
            "experience": self.experience,
            "education": self.education,
            "description": self.description,
            "requirements": self.requirements,
            "status": self.status,
            "apply_count": self.apply_count,
            "view_count": self.view_count,
        }


class BossJobManager:
    """BOSS 直聘职位管理器"""

    def __init__(self, browser: BossBrowser):
        self.browser = browser

    async def get_published_jobs(self) -> AsyncGenerator[JobInfo, None]:
        """
        获取已发布的职位列表
        从"职位管理"栏获取所有正在招聘的职位
        """
        page = self.browser.page
        if not page:
            return

        # 进入职位管理页面（BOSS 直聘的实际 URL）
        #  url 可能是 /web/geek/job 或 /job/manager
        jobs_url = "https://www.zhipin.com/web/geek/job/"
        await self.browser.goto(jobs_url)
        await asyncio.sleep(5)

        # 提取职位列表
        jobs = await self._extract_job_list(page)
        for job in jobs:
            yield job

    async def _extract_job_list(self, page) -> list[JobInfo]:
        """
        提取职位列表信息
        """
        jobs = []

        # 查找职位列表项（选择器需根据实际页面结构调整）
        # BOSS 直聘职位管理页面的常见结构
        job_items = await page.query_selector_all(
            '.job-item, [class*="job-card"], [class*="position-item"], .position-list > div'
        )

        # 如果没有找到，尝试更宽泛的选择器
        if not job_items:
            job_items = await page.query_selector_all('div[class*="job"], div[class*="position"]')

        for idx, item in enumerate(job_items):
            try:
                # 提取职位 ID
                link = await item.query_selector('a[href*="/job/"]')
                href = await link.get_attribute("href") if link else ""
                job_id = self._extract_id_from_href(href) if href else f"unknown_{idx}"

                # 提取职位名称
                name_el = await item.query_selector('.job-name, .position-name, h3, a[href*="/job/"]')
                job_name = await name_el.inner_text() if name_el else ""

                # 提取所属部门
                dept_el = await item.query_selector('.department, .dept-name')
                department = await dept_el.inner_text() if dept_el else ""

                # 提取职位类别
                category_el = await item.query_selector('.category, .job-type')
                category = await category_el.inner_text() if category_el else ""

                # 提取城市
                city_el = await item.query_selector('.city, .work-city')
                city = await city_el.inner_text() if city_el else ""

                # 提取薪资
                salary_el = await item.query_selector('.salary, .pay')
                salary = await salary_el.inner_text() if salary_el else ""

                # 提取经验要求
                exp_el = await item.query_selector('.experience, .exp')
                experience = await exp_el.inner_text() if exp_el else ""

                # 提取学历要求
                edu_el = await item.query_selector('.education, .edu')
                education = await edu_el.inner_text() if edu_el else ""

                # 提取状态
                status_el = await item.query_selector('.status, .job-status')
                status = await status_el.inner_text() if status_el else "招聘中"

                # 提取投递人数
                apply_el = await item.query_selector('.deliver-count, [class*="deliver"]')
                apply_count = int(await apply_el.inner_text()) if apply_el else 0

                # 提取查看人数
                view_el = await item.query_selector('.view-count, [class*="view"]')
                view_count = int(await view_el.inner_text()) if view_el else 0

                jobs.append(
                    JobInfo(
                        job_id=job_id,
                        job_name=job_name,
                        department=department,
                        category=category,
                        city=city,
                        salary=salary,
                        experience=experience,
                        education=education,
                        description="",  # 需要进入详情页获取
                        requirements="",  # 需要进入详情页获取
                        status=status,
                        apply_count=apply_count,
                        view_count=view_count,
                    )
                )
            except Exception as e:
                print(f"提取职位信息失败 (idx={idx}): {e}")
                continue

        return jobs

    async def get_job_detail(self, job_id: str) -> JobInfo | None:
        """
        获取职位详细信息（包括职位描述和要求）
        """
        page = self.browser.page
        if not page:
            return None

        try:
            # 进入职位详情页
            detail_url = f"https://www.zhipin.com/job/{job_id}.html"
            await self.browser.goto(detail_url)
            await asyncio.sleep(2)

            # 提取职位详情
            job = await self._extract_job_detail(page, job_id)
            return job
        except Exception as e:
            print(f"获取职位详情失败：{e}")
            return None

    async def _extract_job_detail(self, page, job_id: str) -> JobInfo:
        """
        提取职位详情信息
        """
        # 提取基本信息
        name_el = await page.query_selector('.job-name, h1')
        job_name = await name_el.inner_text() if name_el else ""

        # 提取部门
        dept_el = await page.query_selector('.department')
        department = await dept_el.inner_text() if dept_el else ""

        # 提取城市
        city_el = await page.query_selector('.city')
        city = await city_el.inner_text() if city_el else ""

        # 提取薪资
        salary_el = await page.query_selector('.salary')
        salary = await salary_el.inner_text() if salary_el else ""

        # 提取经验要求
        exp_el = await page.query_selector('.experience')
        experience = await exp_el.inner_text() if exp_el else ""

        # 提取学历要求
        edu_el = await page.query_selector('.education')
        education = await edu_el.inner_text() if edu_el else ""

        # 提取职位描述（关键部分）
        description = await self._extract_job_description(page)

        # 提取职位要求
        requirements = await self._extract_job_requirements(page)

        # 提取状态
        status_el = await page.query_selector('.status')
        status = await status_el.inner_text() if status_el else "招聘中"

        return JobInfo(
            job_id=job_id,
            job_name=job_name,
            department=department,
            category="",
            city=city,
            salary=salary,
            experience=experience,
            education=education,
            description=description,
            requirements=requirements,
            status=status,
            apply_count=0,
            view_count=0,
        )

    async def _extract_job_description(self, page) -> str:
        """提取职位描述"""
        # 常见的职位描述容器
        desc_selectors = [
            '.job-description',
            '.description',
            '[class*="job-detail"]',
            '.job-content',
            '.position-detail',
        ]

        for selector in desc_selectors:
            el = await page.query_selector(selector)
            if el:
                text = await el.inner_text()
                if text:
                    return text

        # 如果没有找到，尝试提取整个详情区域
        detail_el = await page.query_selector('.detail-content, .job-section')
        if detail_el:
            return await detail_el.inner_text()

        return ""

    async def _extract_job_requirements(self, page) -> str:
        """提取职位要求"""
        # 查找要求部分
        req_selectors = [
            '.job-requirements',
            '.requirements',
            '[class*="requirement"]',
            '.job-req',
        ]

        for selector in req_selectors:
            el = await page.query_selector(selector)
            if el:
                text = await el.inner_text()
                if text:
                    return text

        return ""

    def _extract_id_from_href(self, href: str) -> str:
        """从 URL 中提取职位 ID"""
        if not href:
            return ""

        import re
        # 可能的 URL 格式:
        # /job/12345678.html
        # /job/detail/12345678
        # ?job_id=12345678

        match = re.search(r'(\d+)', href)
        return match.group(1) if match else ""

    async def select_job_for_recommendations(self, job_id: str) -> None:
        """
        选择特定职位，进入该职位的推荐牛人页面
        """
        page = self.browser.page
        if not page:
            return

        # 进入该职位的推荐牛人页面
        # BOSS 直聘的 URL 格式可能需要调整
        recommend_url = f"https://www.zhipin.com/web/geek/recommend?job_id={job_id}"
        await self.browser.goto(recommend_url)
        await asyncio.sleep(3)
