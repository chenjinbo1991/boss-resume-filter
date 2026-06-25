"""Generate presentation screenshots from the current GUI with synthetic data.

The script never reads real candidate records. It redirects the GUI to a
synthetic dataset before opening any result or statistics page.
"""

from __future__ import annotations

import json
import copy
import re
import sys
import time
from pathlib import Path

import tkinter as tk
from PIL import Image, ImageDraw, ImageFont, ImageGrab


ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = Path(__file__).resolve().parent
DEMO_DATA_PATH = OUT_DIR / "demo-candidates.json"
sys.path.insert(0, str(ROOT))

import gui_main


DEMO_JOB = "证券IT开发工程师（演示岗位）"
DEMO_JOB_RULE = {
    "min_exp": 4,
    "edu": "本科",
    "max_age": 38,
    "work_location": "南京",
    "salary_min": 18,
    "salary_max": 25,
    "keywords": [
        {"name": "Java", "weight": 2},
        {"name": "Spring Cloud", "weight": 2},
        {"name": "MySQL", "weight": 1},
        {"name": "Redis", "weight": 1},
        {"name": "金融系统", "weight": 2},
        {"name": "微服务", "weight": 2},
    ],
    "preferred_keywords": [
        {"name": "证券行业", "weight": 2},
        {"name": "高并发", "weight": 1},
    ],
    "required_conditions": ["统招本科", "4年以上Java开发经验"],
    "original_requirement": (
        "岗位：证券IT开发工程师（演示岗位）\n"
        "负责证券业务系统的设计、开发与优化；熟悉 Java、Spring Cloud、"
        "MySQL、Redis 和微服务架构；具备 4 年以上开发经验，统招本科；"
        "有证券行业、高并发系统经验者优先。"
    ),
}


def _candidate(
    index: int,
    score: int,
    *,
    job: str = DEMO_JOB,
    llm_adjustment: int = 0,
    resume_adjustment: int | None = None,
    greeted: bool = False,
    followup: str = "未沟通",
    feedback: str = "",
) -> dict:
    """Build one fully synthetic candidate record."""
    level = "强烈推荐" if score >= 75 else ("推荐" if score >= 65 else "待定")
    rule_score = score - llm_adjustment - (resume_adjustment or 0)
    name = f"候选人{chr(64 + index)}"
    company = f"某金融科技公司{index}"
    school = f"某重点大学{index}"
    summary = (
        f"{name}  {28 + index}岁  {4 + index % 5}年经验  本科  南京  期望薪资20-25K\n"
        f"教育经历：{school} 软件工程 本科 2014.09 2018.06\n"
        f"工作经历：{company} Java开发工程师 2020.03 至今\n"
        "工作职责：负责交易周边系统和客户服务平台建设，参与微服务拆分、"
        "接口性能优化和生产问题分析。\n"
        "技能标签：Java、Spring Cloud、MySQL、Redis、微服务、金融系统"
    )
    record = {
        "geek_id": f"DEMO-{index:03d}",
        "name": name,
        "job_name": job,
        "batch_timestamp": f"202606{20 + index % 3:02d}_100000",
        "summary": summary,
        "structured": {
            "age": 28 + index,
            "exp_years": 4 + index % 5,
            "salary": "20-25K",
            "education": "本科",
            "city": "南京",
            "job_status": "在职-考虑机会",
        },
        "_api_profile": {
            "educations": [
                {
                    "school": school,
                    "major": "软件工程",
                    "degree": "本科",
                    "start": "2014.09",
                    "end": "2018.06",
                }
            ],
            "works": [
                {
                    "company": company,
                    "position": "Java开发工程师",
                    "category": "金融科技",
                    "start": "2020.03",
                    "end": "至今",
                    "responsibility": "负责证券业务系统开发、微服务改造与性能优化。",
                    "skills": ["Java", "Spring Cloud", "MySQL", "Redis"],
                }
            ],
            "personal_summary": "具备金融系统研发经验，能够独立分析和处理复杂问题。",
        },
        "rule_score": rule_score,
        "match_score": score,
        "recommend_level": level,
        "skill_match_ratio": "6/6",
        "skill_matches": [
            {"name": "Java", "weight": 2},
            {"name": "Spring Cloud", "weight": 2},
            {"name": "MySQL", "weight": 1},
            {"name": "Redis", "weight": 1},
            {"name": "金融系统", "weight": 2},
            {"name": "微服务", "weight": 2},
        ],
        "keyword_evidence": [
            {
                "name": "Spring Cloud",
                "weight": 2,
                "type": "skill",
                "evidence": "参与核心系统微服务拆分和服务治理。",
            },
            {
                "name": "金融系统",
                "weight": 2,
                "type": "skill",
                "evidence": "持续参与交易周边和客户服务平台建设。",
            },
            {
                "name": "证券行业",
                "weight": 2,
                "type": "preferred",
                "evidence": "具备证券业务系统研发经历。",
            },
        ],
        "score_breakdown": {
            "base": 25,
            "skill": 38,
            "experience": 8,
            "education": 5,
            "preferred": 2,
            "ai_adjustment": llm_adjustment,
            "resume_adjustment": resume_adjustment or 0,
        },
        "score_explanation": [
            "学历和工作年限满足岗位要求。",
            "核心技术栈覆盖完整，具备金融系统开发经验。",
            "项目经历与岗位职责具有较高相关性。",
        ],
        "llm_evaluated": True,
        "llm_adjustment": llm_adjustment,
        "llm_model": "演示模型",
        "llm_reason": (
            "候选人的微服务研发和金融系统经历与岗位高度相关；"
            "能够提供性能优化和生产问题处理的具体经历。"
        ),
        "qualification_status": "qualified",
        "qualification_reasons": [],
        "qualification_evidence": ["学历、经验和核心技能均有明确材料支持。"],
        "manual_review_required": False,
        "greet_sent": greeted,
        "followup_status": followup,
        "feedback_status": feedback,
        "feedback_updated_at": "20260622_100000" if feedback else "",
        "resume_file": "候选人A_脱敏简历.pdf" if resume_adjustment is not None else "",
        "resume_imported_at": "20260622_093000" if resume_adjustment is not None else "",
        "resume_eval_adjustment": resume_adjustment,
        "resume_eval_reason": (
            "完整简历补充证明候选人曾负责核心模块设计，并主导接口性能优化；"
            "项目深度高于平台摘要所呈现的信息。"
            if resume_adjustment is not None
            else ""
        ),
        "resume_eval_model": "演示模型" if resume_adjustment is not None else "",
        "resume_eval_at": "20260622_094000" if resume_adjustment is not None else "",
        "risk_flags": [],
    }
    return record


def build_demo_candidates() -> list[dict]:
    """Create a varied dataset for result and statistics screenshots."""
    rows = [
        _candidate(1, 86, llm_adjustment=4, resume_adjustment=3, greeted=True, followup="已回复", feedback="合适"),
        _candidate(2, 79, llm_adjustment=3, greeted=True, followup="待约面", feedback="合适"),
        _candidate(3, 76, llm_adjustment=2, greeted=True, followup="已约面", feedback="合适"),
        _candidate(4, 72, llm_adjustment=2, greeted=True, followup="已回复"),
        _candidate(5, 69, llm_adjustment=1, greeted=False),
        _candidate(6, 66, llm_adjustment=1, greeted=True, followup="已打招呼", feedback="误推"),
        _candidate(7, 63, llm_adjustment=0, greeted=False),
        _candidate(8, 59, llm_adjustment=-1, greeted=False),
        _candidate(9, 82, job="数据分析工程师（演示岗位）", llm_adjustment=4, greeted=True, followup="已回复", feedback="合适"),
        _candidate(10, 73, job="数据分析工程师（演示岗位）", llm_adjustment=2, greeted=True, followup="已约面", feedback="合适"),
        _candidate(11, 67, job="数据分析工程师（演示岗位）", llm_adjustment=1, greeted=False),
        _candidate(12, 58, job="数据分析工程师（演示岗位）", llm_adjustment=-1, greeted=False),
    ]
    return rows


def _badge_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_path = Path(r"C:\Windows\Fonts\msyh.ttc")
    if font_path.exists():
        return ImageFont.truetype(str(font_path), size)
    return ImageFont.load_default()


def add_privacy_badge(image: Image.Image) -> Image.Image:
    """Add a visible presentation badge to every final screenshot."""
    output = image.convert("RGB")
    draw = ImageDraw.Draw(output)
    text = "真实系统 · 信息已脱敏"
    font = _badge_font(max(18, output.width // 70))
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pad_x, pad_y = 16, 9
    x2 = output.width - 18
    x1 = x2 - text_w - pad_x * 2
    y1 = 18
    y2 = y1 + text_h + pad_y * 2
    draw.rounded_rectangle((x1, y1, x2, y2), radius=10, fill="#163A5F")
    draw.text((x1 + pad_x, y1 + pad_y - 2), text, font=font, fill="white")
    return output


def capture_widget(widget: tk.Widget, filename: str, *, privacy_badge: bool = True) -> None:
    """Capture one Tk window or page, optionally adding the privacy badge."""
    widget.update_idletasks()
    widget.update()
    time.sleep(0.45)
    x = widget.winfo_rootx()
    y = widget.winfo_rooty()
    width = widget.winfo_width()
    height = widget.winfo_height()
    image = ImageGrab.grab(bbox=(x, y, x + width, y + height))
    final_image = add_privacy_badge(image) if privacy_badge else image
    final_image.save(OUT_DIR / filename)


def find_toplevel(root: tk.Tk, title: str) -> tk.Toplevel:
    """Find a visible child dialog by title."""
    root.update_idletasks()
    root.update()
    for child in root.winfo_children():
        if isinstance(child, tk.Toplevel) and child.winfo_exists() and child.title() == title:
            return child
    raise RuntimeError(f"Dialog not found: {title}")


def find_text_widget(parent: tk.Widget) -> tk.Text:
    """Find the largest Text widget in a dialog."""
    found: list[tk.Text] = []

    def walk(widget: tk.Widget) -> None:
        for child in widget.winfo_children():
            if isinstance(child, tk.Text):
                found.append(child)
            walk(child)

    walk(parent)
    if not found:
        raise RuntimeError("No Text widget found")
    return max(found, key=lambda item: item.winfo_width() * item.winfo_height())


def select_real_job(app: gui_main.BossFilterGUI) -> str:
    """Select a real configured job without changing the project configuration."""
    jobs = list(app.job_rules)
    if not jobs:
        raise RuntimeError("No real job configuration found")
    selected = next((name for name in jobs if "AI" in name), jobs[0])
    app.config_job_combo["values"] = jobs
    app.config_job_combo.set(selected)
    app.on_job_selected(None)
    # Show the real structured fields and keywords.
    app.root.update_idletasks()
    app.root.update()
    app.config_canvas.configure(scrollregion=app.config_canvas.bbox("all"))
    app.config_canvas.yview_moveto(0.28)
    app.root.update_idletasks()
    app.root.update()
    return selected


def _mask_text(text: object, replacements: dict[str, str]) -> object:
    """Mask common personal identifiers while retaining technical content."""
    if not isinstance(text, str):
        return text
    masked = text
    for source, target in replacements.items():
        if source:
            masked = masked.replace(source, target)
    masked = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "138****0000", masked)
    masked = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "masked@example.com",
        masked,
    )
    masked = re.sub(r"[\u4e00-\u9fffA-Za-z0-9（）()·]{2,30}(?:有限公司|公司)", "某科技公司", masked)
    masked = re.sub(r"[\u4e00-\u9fffA-Za-z0-9（）()·]{2,24}(?:大学|学院)", "某高校", masked)
    masked = re.sub(r"候选人\d{2}(?=\d+年经验)", "该候选人具备", masked)
    return masked


def _mask_nested(value: object, replacements: dict[str, str]) -> object:
    """Recursively mask strings in nested candidate data."""
    if isinstance(value, dict):
        return {key: _mask_nested(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_mask_nested(item, replacements) for item in value]
    if isinstance(value, str):
        return _mask_text(value, replacements)
    return value


def build_sanitized_real_candidates(real_job_name: str) -> list[dict]:
    """Create a privacy-safe copy of the current real candidate dataset."""
    source_path = ROOT / "candidates_all.json"
    rows = json.loads(source_path.read_text(encoding="utf-8"))
    sanitized: list[dict] = []
    global_replacements: dict[str, str] = {}
    for original in rows:
        for field, replacement in (
            ("name", "候选人"),
            ("company", "某科技公司"),
            ("school", "某高校"),
            ("geek_id", "MASKED-ID"),
        ):
            value = str(original.get(field) or "").strip()
            if len(value) >= 2:
                global_replacements[value] = replacement

    for index, original in enumerate(rows, 1):
        candidate = _mask_nested(copy.deepcopy(original), global_replacements)
        alias = f"候选人{index:02d}"
        original_name = str(candidate.get("name") or "")
        original_company = str(candidate.get("company") or "")
        original_school = str(candidate.get("school") or "")
        replacements = dict(global_replacements)
        if len(original_name) >= 2:
            replacements[original_name] = alias
        if len(original_company) >= 2:
            replacements[original_company] = "某科技公司"
        if len(original_school) >= 2:
            replacements[original_school] = "某高校"
        original_geek_id = str(original.get("geek_id") or "")
        if len(original_geek_id) >= 2:
            replacements[original_geek_id] = f"MASKED-{index:03d}"

        candidate["name"] = alias
        candidate["geek_id"] = f"MASKED-{index:03d}"
        if candidate.get("job_id"):
            candidate["job_id"] = f"JOB-MASKED-{index:03d}"
        if "�" in str(candidate.get("job_name") or ""):
            candidate["job_name"] = real_job_name
        if candidate.get("company"):
            candidate["company"] = "某科技公司"
        if candidate.get("school"):
            candidate["school"] = "某高校"
        if candidate.get("resume_file"):
            candidate["resume_file"] = f"{alias}_脱敏简历.pdf"

        for key in (
            "summary",
            "llm_reason",
            "resume_eval_reason",
            "feedback_note",
            "followup_note",
            "blacklist_reason",
        ):
            if key in candidate:
                candidate[key] = _mask_text(candidate.get(key), replacements)

        evidence = candidate.get("keyword_evidence")
        if isinstance(evidence, list):
            for item in evidence:
                if isinstance(item, dict) and "evidence" in item:
                    item["evidence"] = _mask_text(item.get("evidence"), replacements)

        profile = candidate.get("_api_profile")
        if isinstance(profile, dict):
            for edu in profile.get("educations") or []:
                if isinstance(edu, dict) and edu.get("school"):
                    edu["school"] = "某高校"
            for work in profile.get("works") or []:
                if isinstance(work, dict):
                    if work.get("company"):
                        work["company"] = "某科技公司"
                    if work.get("responsibility"):
                        work["responsibility"] = _mask_text(work["responsibility"], replacements)
            if profile.get("personal_summary"):
                profile["personal_summary"] = _mask_text(
                    profile["personal_summary"], replacements
                )

        sanitized.append(candidate)

    return sanitized


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gui_main._enable_high_dpi_awareness()
    monitor_area = gui_main._get_windows_monitor_area()

    root = tk.Tk()
    root.withdraw()
    app = gui_main.BossFilterGUI(root)
    gui_main._show_main_window_centered(root, monitor_area)
    root.lift()
    root.attributes("-topmost", True)
    root.update()
    root.attributes("-topmost", False)

    app.show_page_config()
    selected_job = select_real_job(app)
    capture_widget(root, "01-job-requirement-parsing.png", privacy_badge=False)
    print(f"Captured real job configuration: {selected_job}")

    app.show_page_run()
    app.job_combo["values"] = ["全部岗位", *list(app.job_rules)]
    app.job_combo.set(selected_job)
    app.run_canvas.yview_moveto(0.0)
    root.update_idletasks()
    root.update()
    capture_widget(root, "02-run-control.png", privacy_badge=False)
    app.hide_all_pages()

    # Redirect candidate pages to a sanitized copy of the current real data.
    DEMO_DATA_PATH.write_text(
        json.dumps(
            build_sanitized_real_candidates(selected_job),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    gui_main.CANDIDATES_PATH = DEMO_DATA_PATH
    gui_main.CANDIDATES_XLSX_PATH = OUT_DIR / "sanitized-candidates.xlsx"

    app.show_page_result()
    root.update()
    app.refresh_results()
    root.update()
    capture_widget(root, "03-candidate-screening-results.png")

    first_item = app.result_tree.get_children()[0]
    app.result_tree.selection_set(first_item)
    app.result_tree.focus(first_item)
    app._show_candidate_detail(first_item)
    root.update()
    detail = find_toplevel(root, "候选人详情")
    detail.lift()
    detail_text = find_text_widget(detail)
    ai_section = detail_text.search("【AI 一次评估】", "1.0", stopindex="end")
    if ai_section:
        detail_text.yview(ai_section)
        detail.update_idletasks()
        detail.update()
    capture_widget(detail, "04-ai-evaluation-detail.png")
    detail.grab_release()
    detail.destroy()

    app.show_page_stats()
    root.update()
    app.refresh_stats()
    root.update()
    capture_widget(root, "05-recruitment-data-dashboard.png")

    root.destroy()
    print(f"Generated screenshots in: {OUT_DIR}")


if __name__ == "__main__":
    main()
