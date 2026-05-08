"""
BOSS 简历筛选器 - 命令行入口
"""
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.parser import RequirementParser, ResumeParser
from src.matcher import MatchEngine


def main():
    """命令行模式入口"""
    import argparse

    parser = argparse.ArgumentParser(description="BOSS 简历筛选器")
    parser.add_argument(
        "--requirement",
        "-r",
        type=str,
        required=True,
        help="用人需求文档路径",
    )
    parser.add_argument(
        "--resumes",
        "-s",
        type=str,
        nargs="+",
        required=True,
        help="简历文件路径列表",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="./output",
        help="输出目录",
    )
    parser.add_argument(
        "--no-claude",
        action="store_true",
        help="不使用 Claude API，使用本地 LLM",
    )

    args = parser.parse_args()

    # 解析需求
    print(f"📄 解析需求文档：{args.requirement}")
    req_parser = RequirementParser(args.requirement)
    requirement = req_parser.parse()

    print(f"   职位：{requirement.position_name}")
    print(f"   必须技能：{', '.join(requirement.required_skills) or '无'}")
    print(f"   工作年限：{requirement.min_years or '?'}-{requirement.max_years or '?'}年")
    print(f"   学历：{', '.join(requirement.required_education) or '未指定'}")

    # 解析简历并匹配
    results = []
    for resume_path in args.resumes:
        print(f"\n📄 解析简历：{resume_path}")
        resume_parser = ResumeParser(resume_path)
        resume_info = resume_parser.parse()

        print(f"   姓名：{resume_info.name or '未知'}")
        print(f"   当前：{resume_info.current_position}@{resume_info.current_company}")
        print(f"   技能：{', '.join(resume_info.skills[:5]) or '无'}")

        # 匹配
        engine = MatchEngine(use_claude=not args.no_claude)
        result = engine.match(requirement, resume_info)

        print(f"   匹配度：{result.total_score:.1f} ({result.match_level}级)")
        print(f"   硬条件：{'✅' if result.hard_match else '❌'}")
        print(f"   评语：{result.llm_comment}")

        results.append(result)

    # 排序
    results.sort(key=lambda x: x.total_score, reverse=True)

    # 输出摘要
    print("\n" + "=" * 50)
    print("📊 筛选结果摘要（按匹配度排序）")
    print("=" * 50)

    for idx, r in enumerate(results, 1):
        print(
            f"{idx}. {r.resume.name or '未知'} - {r.total_score:.1f}分 "
            f"({r.match_level}级) - {r.resume.current_position}"
        )

    print("\n✅ 完成")


if __name__ == "__main__":
    main()
