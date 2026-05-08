"""
BOSS 简历筛选器 - 粗筛 Web 界面（增强版）
支持从 BOSS 职位管理栏获取已发布职位需求
"""
import os
import sys
from pathlib import Path
from datetime import datetime
import asyncio

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.parser import RequirementParser, JobRequirement
from src.boss import BossBrowser, BossCandidateScraper, RoughScreeningEngine, BossJobManager, JobInfo
from src.matcher import MatchEngine

load_dotenv()

# 页面配置
st.set_page_config(
    page_title="BOSS 候选人粗筛",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 自定义 CSS
st.markdown(
    """
<style>
    .match-s { background-color: #d4edda !important; }
    .match-a { background-color: #d1ecf1 !important; }
    .match-b { background-color: #fff3cd !important; }
    .match-c { background-color: #f8d7da !important; }
    .match-d { background-color: #f5c6cb !important; }
    .action-immediate { color: #dc3545; font-weight: bold; }
    .action-further { color: #007bff; }
    .action-backup { color: #ffc107; }
    .action-reject { color: #6c757d; }
</style>
""",
    unsafe_allow_html=True,
)


def main():
    st.title("🎯 BOSS 候选人粗筛器")
    st.markdown("---")

    # 侧边栏
    with st.sidebar:
        st.header("⚙️ 配置")

        # 步骤 1：职位需求
        st.subheader("1. 职位需求来源")
        req_source = st.radio(
            "选择需求来源",
            ["从 BOSS 职位获取", "上传需求文档"],
            index=0,
        )

        requirement = None
        selected_job = None

        if req_source == "从 BOSS 职位获取":
            # 从 BOSS 获取职位列表
            if st.button("📋 从 BOSS 获取职位列表", type="primary"):
                load_jobs_from_boss()
            st.session_state.jobs = st.session_state.get("jobs", [])
            if st.session_state.jobs:
                job_options = {f"{j['job_name']} - {j['department']}": j for j in st.session_state.jobs}
                selected_job_name = st.selectbox("选择职位", list(job_options.keys()))
                if selected_job_name:
                    selected_job = job_options[selected_job_name]
                    requirement = job_info_to_requirement(selected_job)
                    st.success(f"✅ 已选择：{selected_job['job_name']}")
        else:
            req_file = st.file_uploader(
                "上传需求文档",
                type=["docx", "doc", "pdf", "md", "txt"],
            )
            if req_file:
                requirement = parse_requirement_file(req_file)
                selected_job = None

        # 步骤 2：获取候选人
        st.subheader("2. 获取候选人")
        get_candidates = st.checkbox("从 BOSS 获取推荐候选人")
        max_pages = st.slider("最大爬取页数", 1, 20, 5)

        # 步骤 3：筛选选项
        st.subheader("3. 筛选选项")
        use_llm = st.checkbox("使用 LLM 生成评语", value=True)

        # 开始按钮
        start_btn = st.button("🚀 开始筛选", type="primary")

    # 主内容区
    if start_btn:
        if requirement or get_candidates:
            run_rough_screening(requirement, get_candidates, max_pages, use_llm, selected_job)
        else:
            st.warning("请至少选择职位或上传需求文档，或选择从 BOSS 获取候选人")
    else:
        show_welcome()


def job_info_to_requirement(job: dict) -> JobRequirement:
    """将职位信息转换为需求对象"""
    from src.parser.requirement import JobRequirement

    # 解析经验要求
    min_years = None
    max_years = None
    if job.get('experience'):
        import re
        match = re.search(r'(\d+)[\-至～到]?(\d+)?年', job['experience'])
        if match:
            min_years = int(match.group(1))
            max_years = int(match.group(2)) if match.group(2) else None

    # 解析学历要求
    required_education = []
    if job.get('education'):
        edu = job['education']
        if "本科" in edu:
            required_education.append("本科")
        if "硕士" in edu:
            required_education.append("硕士")
        if "大专" in edu:
            required_education.append("大专")
        if "博士" in edu:
            required_education.append("博士")

    # 从职位描述中提取技能和行业
    description_text = job.get('description', '') + ' ' + job.get('requirements', '')
    required_skills = []
    preferred_skills = []

    # 简单提取技能关键词（实际应使用 NLP 或 LLM）
    skill_keywords = ["Python", "Java", "C++", "JavaScript", "Go", "SQL", "MySQL", "Redis",
                      "Docker", "Kubernetes", "AWS", "Azure", "Linux", "React", "Vue", "Spring",
                      "TensorFlow", "PyTorch", "数据分析", "机器学习", "深度学习"]
    for skill in skill_keywords:
        if skill.lower() in description_text.lower():
            required_skills.append(skill)

    return JobRequirement(
        position_name=job.get('job_name', ''),
        department=job.get('department', ''),
        min_years=min_years,
        max_years=max_years,
        required_education=required_education,
        education_check=False,
        required_skills=required_skills[:5],  # 限制数量
        preferred_skills=preferred_skills,
        required_industry=[],
        preferred_industry=[],
        location=job.get('city', ''),
        salary_range=job.get('salary', ''),
        keywords=[],
        _uses_defaults=False,
    )


def load_jobs_from_boss():
    """从 BOSS 获取职位列表（分两步操作）"""
    import subprocess
    import json
    import os

    st.session_state.jobs = []
    st.session_state.job_fetch_status = "loading"

    # 询问用户当前步骤
    step = st.radio("请选择操作步骤", ["第一步：打开浏览器并登录", "第二步：提取职位信息"], key="job_fetch_step")

    if step == "第一步：打开浏览器并登录":
        with st.spinner("正在启动浏览器，请稍候...\n\n操作说明：\n1. 在打开的浏览器中访问 https://www.zhipin.com/\n2. 扫码登录 BOSS 直聘\n3. 登录后点击左侧菜单的'职位管理'\n4. 等待职位列表加载完成\n5. 完成后回来选择'第二步'"):
            try:
                # 运行浏览器打开脚本
                script_path = Path(__file__).parent.parent.parent / "fetch_jobs_sync.py"
                result = subprocess.run(
                    ["python", str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=30,  # 30秒后超时，但仍保持浏览器打开
                )

                st.info("✅ 浏览器已打开，请完成登录操作，然后回来选择'第二步：提取职位信息'\n\n提示：完成登录和导航后，浏览器会保持打开状态。")

            except subprocess.TimeoutExpired:
                st.info("✅ 浏览器已打开，请完成登录操作，然后回来选择'第二步：提取职位信息'\n\n提示：完成登录和导航后，浏览器会保持打开状态。")
            except Exception as e:
                st.error(f"启动失败：{e}")

    else:  # 第二步：提取职位信息
        with st.spinner("正在从浏览器中提取职位信息...\n请确保您已经在职位管理页面"):
            try:
                # 运行提取脚本
                script_path = Path(__file__).parent.parent.parent / "bypass_antispider.py"
                result = subprocess.run(
                    ["python", str(script_path)],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                # 解析输出
                for line in result.stdout.split("\n"):
                    if line.startswith("RESULT:"):
                        data = json.loads(line[7:])
                        if data.get("status") == "success":
                            st.session_state.jobs = data.get("jobs", [])
                            if st.session_state.jobs:
                                st.success(f"✅ 成功获取到 {len(st.session_state.jobs)} 个职位")
                            else:
                                st.warning("⚠️ 未找到职位，请确保已在职位管理页面\n\n如果职位确实存在，请尝试：\n1. 确认页面URL包含'/web/geek/job/'\n2. 刷新职位管理页面\n3. 再次尝试提取")
                        else:
                            st.error(f"❌ 提取失败：{data.get('error', '未知错误')}")
                        break
                else:
                    # 没有找到 RESULT 行，检查错误输出
                    if result.stderr:
                        st.error(f"执行错误：{result.stderr[:500]}")
                    else:
                        st.warning("⚠️ 未获取到职位数据，请确保已在职位管理页面")
                    # 显示 stdout 以便调试
                    with st.expander("📋 详细日志"):
                        st.write("标准输出:")
                        st.code(result.stdout)
                        if result.stderr:
                            st.write("错误输出:")
                            st.code(result.stderr)

            except subprocess.TimeoutExpired:
                st.error("⏰ 提取超时，请重试")
            except Exception as e:
                st.error(f"❌ 提取失败：{e}")

    st.session_state.job_fetch_status = "done"


def parse_requirement_file(req_file):
    """解析需求文档"""
    temp_dir = Path("./temp")
    temp_dir.mkdir(exist_ok=True)

    req_path = temp_dir / f"req_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    req_path.write_bytes(req_file.getvalue())

    try:
        req_parser = RequirementParser(req_path)
        requirement = req_parser.parse()
        st.success(f"✅ 职位：{requirement.position_name}")
        return requirement
    except Exception as e:
        st.error(f"解析需求文档失败：{e}")
        return None


def run_rough_screening(requirement, get_candidates, max_pages, use_llm, selected_job=None):
    """执行粗筛流程"""

    # 初始化浏览器
    browser = BossBrowser()

    # 启动浏览器（需要用户扫码登录）
    st.info("🔐 请在弹出的浏览器窗口中扫码登录 BOSS 直聘")

    async def run():
        # 启动浏览器
        await browser.launch(headless=False)

        # 检查登录状态
        logged_in = await browser.is_logged_in()
        if not logged_in:
            st.warning("请先登录 BOSS 直聘")
            await asyncio.sleep(10)

        # 如果选择了职位，进入该职位的推荐牛人页面
        if selected_job:
            job_manager = BossJobManager(browser)
            await job_manager.select_job_for_recommendations(selected_job['job_id'])
            st.info(f"📍 已定位到职位：{selected_job['job_name']}")

        # 获取候选人
        candidates = []
        if get_candidates:
            scraper = BossCandidateScraper(browser)

            progress_bar = st.progress(0)
            status_text = st.empty()

            async for candidate in scraper.get_job_recommendations(max_pages=max_pages):
                candidates.append(candidate)
                progress_bar.progress(len(candidates) / (max_pages * 10))
                status_text.text(f"已获取 {len(candidates)} 位候选人")

            st.success(f"✅ 共获取 {len(candidates)} 位候选人")

        # 执行筛选
        if candidates and requirement:
            st.subheader("📊 筛选结果")

            engine = RoughScreeningEngine()
            results = []

            for candidate in candidates:
                result = engine.evaluate(requirement, candidate, use_llm=use_llm, llm=None)
                results.append(result)

            # 排序
            results.sort(key=lambda x: x.total_score, reverse=True)

            # 显示结果
            show_results(results)

        await browser.close()

    # 运行异步代码
    try:
        asyncio.run(run())
    except Exception as e:
        st.error(f"执行失败：{e}")


def show_results(results):
    """显示筛选结果"""

    # 统计
    s_count = sum(1 for r in results if r.match_level == "S")
    a_count = sum(1 for r in results if r.match_level == "A")
    b_count = sum(1 for r in results if r.match_level == "B")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总人数", len(results))
    col2.metric("S/A 级", f"{s_count + a_count}")
    col3.metric("B 级", b_count)
    col4.metric("硬条件满足", sum(1 for r in results if r.hard_match))

    st.divider()

    # 结果表格
    df_data = []
    for r in results:
        df_data.append({
            "匹配度": f"{r.total_score:.1f}",
            "等级": r.match_level,
            "姓名": r.summary.name,
            "职位": r.summary.position,
            "公司": r.summary.company,
            "经验": r.summary.experience,
            "学历": r.summary.education,
            "学校": r.summary.school,
            "建议": r.recommend_action,
            "评语": r.comment[:30] + "..." if len(r.comment) > 30 else r.comment,
        })

    df = pd.DataFrame(df_data)

    # 样式
    def style_level(val):
        if val == "S": return "background-color: #d4edda"
        elif val == "A": return "background-color: #d1ecf1"
        elif val == "B": return "background-color: #fff3cd"
        elif val == "C": return "background-color: #f8d7da"
        return ""

    styled_df = df.style.applymap(style_level, subset=["等级"])

    st.dataframe(styled_df, use_container_width=True, height=400)

    # 详细信息
    st.divider()
    st.subheader("📄 详细点评")

    for r in results:
        with st.expander(
            f"{r.match_level}级 - {r.summary.name} - {r.total_score:.1f}分",
            expanded=False,
        ):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**基本信息**")
                st.write(f"姓名：{r.summary.name}")
                st.write(f"职位：{r.summary.position}")
                st.write(f"公司：{r.summary.company}")
                st.write(f"行业：{r.summary.industry}")
                st.write(f"经验：{r.summary.experience}")
                st.write(f"学历：{r.summary.education}")
                st.write(f"学校：{r.summary.school}")

            with col2:
                st.markdown("**其他信息**")
                st.write(f"期望城市：{r.summary.expect_city}")
                st.write(f"期望薪资：{r.summary.expect_salary}")
                st.write(f"状态：{r.summary.status}")
                st.write(f"活跃时间：{r.summary.active_time}")
                st.write(f"技能：{', '.join(r.summary.skills)}")

            st.divider()
            st.markdown("**评估结果**")
            st.write(f"硬条件：{'✅' if r.hard_match else '❌'}")
            st.write(f"得分：{r.total_score:.1f}")
            st.write(f"建议：{r.recommend_action}")
            st.info(f"评语：{r.comment}")

    # 导出
    st.divider()
    export_results(results)


def export_results(results):
    """导出结果"""
    data = []
    for r in results:
        data.append({
            "匹配等级": r.match_level,
            "综合得分": f"{r.total_score:.2f}",
            "硬条件满足": "是" if r.hard_match else "否",
            "姓名": r.summary.name,
            "职位": r.summary.position,
            "公司": r.summary.company,
            "行业": r.summary.industry,
            "经验": r.summary.experience,
            "学历": r.summary.education,
            "学校": r.summary.school,
            "期望城市": r.summary.expect_city,
            "期望薪资": r.summary.expect_salary,
            "状态": r.summary.status,
            "活跃时间": r.summary.active_time,
            "技能": ", ".join(r.summary.skills),
            "建议": r.recommend_action,
            "评语": r.comment,
        })

    df = pd.DataFrame(data)

    output_dir = Path("./output")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"粗筛结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    df.to_excel(output_file, index=False)

    with open(output_file, "rb") as f:
        st.download_button(
            label="📥 导出 Excel",
            data=f.read(),
            file_name=output_file.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def show_welcome():
    """欢迎页面"""
    st.markdown("""
### 📌 使用说明

#### 粗筛流程

1. **选择职位需求**
   - 从 BOSS 职位管理栏获取已发布的职位，或
   - 上传用人需求文档

2. **获取候选人**
   - 系统会从 BOSS 推荐牛人栏自动获取候选人概要信息
   - 无需下载简历，保护候选人隐私

3. **智能筛选**
   - 硬条件过滤：学历、工作年限等
   - 软条件评分：职位匹配、公司背景、技能等
   - LLM 生成评语（可选）

4. **查看结果**
   - 按匹配度排序（S/A/B/C/D）
   - 支持导出 Excel

### 🎯 粗筛 vs 细筛

| 阶段 | 数据源 | 用途 |
|------|--------|------|
| **粗筛** | 候选人概要 | 快速过滤，决定是否沟通 |
| **细筛** | 完整简历 | 深度评估，决定是否面试 |

### 📊 匹配等级

| 等级 | 分数 | 建议 |
|------|------|------|
| S | 90-100 | 🔥 立即沟通 |
| A | 80-89 | ✅ 进一步评估 |
| B | 70-79 | ⚠️ 备选考察 |
| C | 60-69 | ❌ 暂不考虑 |
| D | <60 | ❌ 不匹配 |
""")


if __name__ == "__main__":
    main()
