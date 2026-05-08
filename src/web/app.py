"""
BOSS 简历筛选器 - Web 界面
使用 Streamlit 构建
"""
import os
import sys
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 尝试导入 security 模块（用于从 keyring 读取 API Key）
try:
    from security import get_api_key
    HAS_SECURITY = True
except (ImportError, Exception):
    HAS_SECURITY = False

from src.parser import RequirementParser, ResumeParser
from src.matcher import MatchEngine

load_dotenv()

# 页面配置
st.set_page_config(
    page_title="BOSS 简历筛选器",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _get_api_key_from_keyring(provider: str) -> str | None:
    """从系统钥匙串读取 API Key（按服务商管理）"""
    if not HAS_SECURITY:
        return None
    try:
        return get_api_key(provider)
    except Exception:
        return None

# 自定义 CSS
st.markdown(
    """
<style>
    .match-s { background-color: #d4edda !important; }
    .match-a { background-color: #d1ecf1 !important; }
    .match-b { background-color: #fff3cd !important; }
    .match-c { background-color: #f8d7da !important; }
    .match-d { background-color: #f5c6cb !important; }
    .stDataFrame [data-baseweb="table"] {
        font-size: 13px;
    }
</style>
""",
    unsafe_allow_html=True,
)


def main():
    st.title("📋 BOSS 简历筛选器")
    st.markdown("---")

    # 侧边栏
    with st.sidebar:
        st.header("⚙️ 配置")

        # 文件上传
        st.subheader("1. 上传用人需求文档")
        req_file = st.file_uploader(
            "支持 Word/PDF/Markdown",
            type=["docx", "doc", "pdf", "md", "txt"],
        )

        st.subheader("2. 上传简历文件")
        resume_files = st.file_uploader(
            "支持批量上传",
            type=["pdf", "docx", "doc", "txt"],
            accept_multiple_files=True,
        )

        # 匹配选项
        st.subheader("3. 匹配选项")

        # LLM 选择
        llm_option = st.radio(
            "选择 LLM",
            ["本地 Qwen", "Claude API", "Ollama"],
            index=0,
        )

        # 根据选择显示不同配置
        use_claude = False

        if llm_option == "Claude API":
            # 尝试从 keyring 读取 API Key
            claude_key = _get_api_key_from_keyring("anthropic")
            if claude_key:
                st.success("✓ API Key 已配置（加密存储）")
            else:
                st.warning("需在 GUI 中配置 API Key")
            use_claude = st.checkbox("启用 Claude API", value=bool(claude_key))
        elif llm_option == "本地 Qwen":
            st.success("使用本地 Qwen 模型（通过 OpenAI 兼容接口）")
            st.text_input("API 基础地址", value=os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:8000/v1"), disabled=True)
            model_name = os.getenv("LOCAL_LLM_MODEL", "qwen-plus")
            st.text_input("模型名称", value=model_name, disabled=True)
            # 检查 API Key 是否已配置
            qwen_key = _get_api_key_from_keyring("qwen")
            if qwen_key:
                st.success("✓ API Key 已配置（加密存储）")
            else:
                st.warning("需在 GUI 中配置 API Key")
        elif llm_option == "Ollama":
            st.info("使用 Ollama 本地运行（无需 API Key）")
            st.text_input("Ollama 地址", value="http://localhost:11434", disabled=True)
            st.text_input("模型名称", value="qwen2.5:7b", disabled=True)

        # 开始按钮
        start_btn = st.button("🚀 开始筛选", type="primary", disabled=not req_file)

    # 主内容区
    if start_btn and req_file and resume_files:
        # 根据选择确定 use_claude 参数
        use_claude = (llm_option == "Claude API")
        run_screening(req_file, resume_files, use_claude)
    elif start_btn:
        st.warning("请上传用人需求文档和简历文件")
    else:
        show_welcome()


def show_welcome():
    """显示欢迎页面"""
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
### 📌 使用说明

1. **上传用人需求文档**
   - 支持 Word/PDF/Markdown 格式
   - 文档应包含职位名称、技能要求、工作年限、学历等信息

2. **上传简历文件**
   - 支持批量上传
   - 支持 PDF/Word/TXT 格式

3. **查看筛选结果**
   - 按匹配度排序
   - 支持导出 Excel

### 📊 匹配规则

- **硬条件**：必须技能、工作年限、学历等
- **软条件**：加分技能、行业背景、项目经验等
- **综合得分**：硬条件过滤后，软条件加权计算
"""
        )

    with col2:
        st.markdown(
            """
### 🎯 匹配等级

| 等级 | 分数 | 说明 |
|------|------|------|
| S | 90-100 | 非常匹配 |
| A | 80-89 | 匹配 |
| B | 70-79 | 基本匹配 |
| C | 60-69 | 勉强匹配 |
| D | <60 | 不匹配 |
"""
        )


def run_screening(req_file, resume_files, use_claude):
    """执行筛选流程"""

    # 保存临时文件
    temp_dir = Path("./temp")
    temp_dir.mkdir(exist_ok=True)

    # 保存需求文档
    req_path = temp_dir / f"req_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    req_path.write_bytes(req_file.getvalue())

    # 解析需求
    with st.spinner("📄 解析用人需求文档..."):
        try:
            req_parser = RequirementParser(req_path)
            requirement = req_parser.parse()
            show_requirement_summary(requirement)
        except Exception as e:
            st.error(f"解析需求文档失败：{e}")
            return

    # 解析简历并匹配
    results = []
    progress_bar = st.progress(0)

    for idx, resume_file in enumerate(resume_files):
        resume_path = temp_dir / f"resume_{resume_file.name}"
        resume_path.write_bytes(resume_file.getvalue())

        try:
            # 解析简历
            resume_parser = ResumeParser(resume_path)
            resume_info = resume_parser.parse()

            # 执行匹配
            engine = MatchEngine(use_claude=use_claude)
            result = engine.match(requirement, resume_info)
            results.append(result)
        except Exception as e:
            st.warning(f"解析简历失败 {resume_file.name}: {e}")

        progress_bar.progress((idx + 1) / len(resume_files))

    # 排序结果
    results.sort(key=lambda x: x.total_score, reverse=True)

    # 显示结果
    show_results(results, requirement)

    # 清理临时文件
    for f in temp_dir.glob("*"):
        f.unlink()


def show_requirement_summary(req):
    """显示需求摘要"""
    st.success("✅ 需求文档解析成功")

    with st.expander("📋 职位需求详情", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"**职位**: {req.position_name or '未指定'}")
            st.markdown(f"**部门**: {req.department or '未指定'}")
            st.markdown(f"**地点**: {req.location or '未指定'}")
            st.markdown(f"**薪资**: {req.salary_range or '未指定'}")

        with col2:
            st.markdown(f"**最低学历**: {', '.join(req.required_education) or '未指定'}")
            st.markdown(f"**工作年限**: {req.min_years or '未指定'}-{req.max_years or '未指定'}年")

        st.divider()

        col3, col4 = st.columns(2)

        with col3:
            st.markdown("**必须技能**:")
            for skill in req.required_skills:
                st.write(f"• {skill}")

        with col4:
            st.markdown("**加分技能**:")
            for skill in req.preferred_skills:
                st.write(f"• {skill}")


def show_results(results, requirement):
    """显示筛选结果"""
    st.divider()
    st.subheader("📊 筛选结果")

    if not results:
        st.warning("没有匹配的简历")
        return

    # 统计信息
    s_count = sum(1 for r in results if r.match_level == "S")
    a_count = sum(1 for r in results if r.match_level == "A")
    b_count = sum(1 for r in results if r.match_level == "B")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总简历数", len(results))
    col2.metric("S/A 级", f"{s_count + a_count}")
    col3.metric("B 级", b_count)
    col4.metric("硬条件满足", sum(1 for r in results if r.hard_match))

    st.divider()

    # 结果表格
    df_data = []
    for r in results:
        df_data.append(
            {
                "匹配度": f"{r.total_score:.1f}",
                "等级": r.match_level,
                "姓名": r.resume.name,
                "当前职位": r.resume.current_position,
                "当前公司": r.resume.current_company,
                "学历": r.resume.education,
                "年限": r.resume.years_of_experience,
                "硬条件": "✅" if r.hard_match else "❌",
                "手机号": r.resume.phone,
                "邮箱": r.resume.email,
                "技能": ", ".join(r.resume.skills[:5]),
                "评语": r.llm_comment[:50] + "..." if len(r.llm_comment) > 50 else r.llm_comment,
            }
        )

    df = pd.DataFrame(df_data)

    # 应用样式
    def style_match_level(val):
        if val == "S":
            return "background-color: #d4edda"
        elif val == "A":
            return "background-color: #d1ecf1"
        elif val == "B":
            return "background-color: #fff3cd"
        elif val == "C":
            return "background-color: #f8d7da"
        return ""

    styled_df = df.style.applymap(
        style_match_level, subset=["等级"]
    ).format()

    st.dataframe(
        styled_df,
        use_container_width=True,
        height=400,
    )

    # 详细信息
    st.divider()
    st.subheader("📄 详细点评")

    for r in results:
        with st.expander(
            f"{r.match_level}级 - {r.resume.name or '未知'} - {r.total_score:.1f}分",
            expanded=False,
        ):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**基本信息**")
                st.write(f"姓名：{r.resume.name or '未知'}")
                st.write(f"电话：{r.resume.phone or '未知'}")
                st.write(f"邮箱：{r.resume.email or '未知'}")
                st.write(f"当前：{r.resume.current_position}@{r.resume.current_company}")
                st.write(f"学历：{r.resume.education}")
                st.write(f"经验：{r.resume.years_of_experience}年")

            with col2:
                st.markdown("**技能**")
                st.write(f"编程语言：{', '.join(r.resume.programming_languages) or '无'}")
                st.write(f"框架：{', '.join(r.resume.frameworks) or '无'}")
                st.write(f"工具：{', '.join(r.resume.tools) or '无'}")

            st.divider()

            st.markdown("**匹配详情**")
            st.write(f"硬条件满足：{'✅' if r.hard_match else '❌'}")
            st.write(f"软条件得分：{r.soft_score:.1f}")
            st.write(f"综合得分：{r.total_score:.1f}")

            st.divider()

            st.markdown("**HR 评语**")
            st.info(r.llm_comment)

    # 导出按钮
    st.divider()
    export_button(results)


def export_button(results):
    """导出功能"""
    # 准备数据
    data = []
    for r in results:
        data.append(
            {
                "匹配等级": r.match_level,
                "综合得分": f"{r.total_score:.2f}",
                "软条件得分": f"{r.soft_score:.2f}",
                "硬条件满足": "是" if r.hard_match else "否",
                "姓名": r.resume.name,
                "电话": r.resume.phone,
                "邮箱": r.resume.email,
                "当前公司": r.resume.current_company,
                "当前职位": r.resume.current_position,
                "学历": r.resume.education,
                "工作年限": r.resume.years_of_experience,
                "技能": ", ".join(r.resume.skills),
                "项目类型": ", ".join(r.resume.project_types),
                "证书": ", ".join(r.resume.certifications),
                "HR 评语": r.llm_comment,
                "简历文件": r.resume.file_path,
            }
        )

    df = pd.DataFrame(data)

    # 生成 Excel
    output_dir = Path("./output")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"筛选结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    df.to_excel(output_file, index=False)

    # 下载按钮
    with open(output_file, "rb") as f:
        st.download_button(
            label="📥 导出 Excel",
            data=f.read(),
            file_name=output_file.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


if __name__ == "__main__":
    main()
