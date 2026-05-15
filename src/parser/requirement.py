"""
用人需求文档解析模块
支持 Word/PDF/Markdown 格式
"""
import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal

import pdfplumber
from docx import Document


@dataclass
class JobRequirement:
    """职位需求"""

    # 基本信息
    position_name: str = ""  # 职位名称
    department: str = ""  # 部门
    job_type: str = ""  # 职位类型（全职/兼职/实习）

    # 硬性条件（必须满足）
    required_skills: list[str] = field(default_factory=list)  # 必须技能
    min_years: int | None = None  # 最低工作年限
    max_years: int | None = None  # 最高工作年限
    required_education: list[str] = field(default_factory=list)  # 要求学历（本科/硕士等）
    education_check: bool = True  # 是否要求学信网可查
    required_industry: list[str] = field(default_factory=list)  # 要求行业背景
    required_project_type: list[str] = field(default_factory=list)  # 要求项目经验类型

    # 软性条件（有更好，没有也可）
    preferred_skills: list[str] = field(default_factory=list)  # 加分技能
    preferred_industry: list[str] = field(default_factory=list)  # 加分行业
    preferred_project_type: list[str] = field(default_factory=list)  # 加分项目
    preferred_certifications: list[str] = field(default_factory=list)  # 加分证书

    # 其他
    location: str = ""  # 工作地点
    salary_range: str = ""  # 薪资范围
    keywords: list[str] = field(default_factory=list)  # 关键词（用于搜索）

    # 默认硬条件标记
    _uses_defaults: bool = False  # 是否使用了默认值

    def apply_defaults(self) -> None:
        """
        应用默认硬条件
        - 学历默认：本科，学信网可查
        - 工作年限默认：≥1 年
        """
        defaults_applied = []

        # 默认学历：本科
        if not self.required_education:
            self.required_education = ["本科"]
            defaults_applied.append("学历=本科")

        # 默认学信网可查
        if not self.education_check:
            self.education_check = True
            defaults_applied.append("学信网可查=是")

        # 默认工作年限≥1 年
        if self.min_years is None:
            self.min_years = 1
            defaults_applied.append("工作年限≥1 年")

        # 记录是否使用了默认值
        self._uses_defaults = len(defaults_applied) > 0

        if defaults_applied:
            print(f"📌 应用默认硬条件：{', '.join(defaults_applied)}")

    def to_dict(self) -> dict:
        return {
            "position_name": self.position_name,
            "department": self.department,
            "job_type": self.job_type,
            "hard_requirements": {
                "required_skills": self.required_skills,
                "min_years": self.min_years,
                "max_years": self.max_years,
                "required_education": self.required_education,
                "education_check": self.education_check,
                "required_industry": self.required_industry,
                "required_project_type": self.required_project_type,
                "_uses_defaults": self._uses_defaults,
            },
            "soft_requirements": {
                "preferred_skills": self.preferred_skills,
                "preferred_industry": self.preferred_industry,
                "preferred_project_type": self.preferred_project_type,
                "preferred_certifications": self.preferred_certifications,
            },
            "location": self.location,
            "salary_range": self.salary_range,
            "keywords": self.keywords,
        }


class RequirementParser:
    """需求文档解析器"""

    # 学历层级映射（用于比较）
    EDUCATION_LEVELS = {
        "中专": 1,
        "高中": 2,
        "大专": 3,
        "本科": 4,
        "学士": 4,
        "硕士": 5,
        "博士": 6,
        "博士后": 7,
    }

    # 常见技能关键词
    SKILL_KEYWORDS = {
        "Python": ["Python", "python", "PY"],
        "Java": ["Java", "java"],
        "JavaScript": ["JavaScript", "js", "JS", "typescript", "TypeScript", "TS"],
        "Go": ["Go", "golang", "Golang"],
        "C++": ["C++", "cpp", "CPP"],
        "SQL": ["SQL", "sql", "MySQL", "PostgreSQL", "Oracle"],
        "Linux": ["Linux", "linux"],
        "Docker": ["Docker", "docker", "容器化"],
        "Kubernetes": ["Kubernetes", "k8s", "K8s"],
        "AWS": ["AWS", "aws", "Amazon"],
        "Azure": ["Azure", "azure"],
        "机器学习": ["机器学习", "ML", "machine learning"],
        "深度学习": ["深度学习", "DL", "deep learning"],
        "AI": ["AI", "人工智能", "大模型", "LLM"],
    }

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.content = ""

    def parse(self) -> JobRequirement:
        """解析需求文档"""
        # 读取文件内容
        self._read_file()

        # 提取各项信息
        req = JobRequirement()

        req.position_name = self._extract_position_name()
        req.department = self._extract_department()
        req.job_type = self._extract_job_type()

        # 硬性条件
        req.required_skills = self._extract_required_skills()
        req.min_years = self._extract_min_years()
        req.max_years = self._extract_max_years()
        req.required_education = self._extract_required_education()
        req.required_industry = self._extract_required_industry()
        req.required_project_type = self._extract_required_project_type()

        # 提取学信网要求
        req.education_check = self._extract_education_check()

        # 应用默认硬条件（如果文档中未指定）
        req.apply_defaults()

        # 软性条件
        req.preferred_skills = self._extract_preferred_skills()
        req.preferred_industry = self._extract_preferred_industry()
        req.preferred_project_type = self._extract_preferred_project_type()
        req.preferred_certifications = self._extract_preferred_certifications()

        # 其他
        req.location = self._extract_location()
        req.salary_range = self._extract_salary_range()
        req.keywords = self._extract_keywords()

        return req

    def _read_file(self) -> None:
        """读取文件内容"""
        ext = self.file_path.suffix.lower()

        if ext == ".pdf":
            self.content = self._read_pdf()
        elif ext in [".docx", ".doc"]:
            self.content = self._read_docx()
        elif ext in [".md", ".markdown", ".txt"]:
            self.content = self._read_text()
        else:
            raise ValueError(f"不支持的文件格式：{ext}")

    def _read_pdf(self) -> str:
        """读取 PDF 文件"""
        text_parts = []
        with pdfplumber.open(self.file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n".join(text_parts)

    def _read_docx(self) -> str:
        """读取 Word 文件"""
        doc = Document(self.file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)

    def _read_text(self) -> str:
        """读取文本文件"""
        with open(self.file_path, "r", encoding="utf-8") as f:
            return f.read()

    # ========== 提取方法 ==========

    def _extract_position_name(self) -> str:
        """提取职位名称"""
        patterns = [
            r"\*\*职位名称\*\*\s*[：:]\s*(.+?)(?:\n|$)",  # Markdown 粗体格式
            r"职位名称 [：:]\s*(.+?)(?:\n|$)",
            r"岗位 [名称 ]?[：:]\s*(.+?)(?:\n|$)",
            r"招聘 [岗位职位 ]?[：:]\s*(.+?)(?:\n|$)",
            r"^#\s*(.+ 工程师 | 架构师 | 开发 | 产品 | 设计)",  # Markdown 标题
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip()

        return ""

    def _extract_department(self) -> str:
        """提取部门"""
        patterns = [
            r"部门 [名称 ]?[：:]\s*(.+?)(?:\n|$)",
            r"所属部门 [：:]\s*(.+?)(?:\n|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, self.content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_job_type(self) -> str:
        """提取职位类型"""
        patterns = [
            r"职位类型 [：:]\s*(.+?)(?:\n|$)",
            r"工作性质 [：:]\s*(.+?)(?:\n|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, self.content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return "全职"

    def _extract_required_skills(self) -> list[str]:
        """提取必须技能"""
        skills = []

        # 查找"必须/要求"相关的技能描述段落
        patterns = [
            r"(?:必须 | 要求 | 必备) 技能 [：:]?\s*(.+?)(?:\n\n|$)",
            r"(?:岗位要求 | 任职资格 | 任职要求)[：:]?\s*(.+?)(?:\n\n|$)",
            r"硬性条件 [：:]?\s*(.+?)(?:\n\n|$)",
        ]

        skill_text = ""
        for pattern in patterns:
            match = re.search(pattern, self.content, re.IGNORECASE | re.DOTALL)
            if match:
                skill_text = match.group(1)
                break

        if not skill_text:
            return skills

        # 从文本中提取技能关键词
        for skill_name, keywords in self.SKILL_KEYWORDS.items():
            for keyword in keywords:
                if keyword in skill_text:
                    skills.append(skill_name)
                    break

        return list(set(skills))

    def _extract_preferred_skills(self) -> list[str]:
        """提取加分技能"""
        skills = []

        patterns = [
            r"(?:优先 | 加分 | 有。* 经验.* 者 | 熟悉 .* 优先)[：:]?\s*(.+?)(?:\n\n|$)",
            r"(?:其他要求 | 额外要求)[：:]?\s*(.+?)(?:\n\n|$)",
        ]

        skill_text = ""
        for pattern in patterns:
            match = re.search(pattern, self.content, re.IGNORECASE | re.DOTALL)
            if match:
                skill_text = match.group(1)
                break

        if not skill_text:
            return skills

        for skill_name, keywords in self.SKILL_KEYWORDS.items():
            if skill_name in self._extract_required_skills():
                continue  # 已经作为必须技能的不再重复
            for keyword in keywords:
                if keyword in skill_text:
                    skills.append(skill_name)
                    break

        return list(set(skills))

    def _extract_min_years(self) -> int | None:
        """提取最低工作年限"""
        patterns = [
            r"(\d+)[\-至～到]+\d+ 年",  # "3-5 年" -> 3
            r"(\d+) 年以上",
            r"至少 (\d+) 年",
            r"最低 (\d+) 年",
            r"(\d+)[+ 以上] 年",
            r"工作经验 [：:]\s*(\d+)[\-至～]",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content)
            if match:
                return int(match.group(1))

        return None

    def _extract_education_check(self) -> bool:
        """提取学信网可查要求"""
        patterns = [
            r"学信网",
            r"学信可查",
            r"国家承认学历",
            r"统招",
        ]

        for pattern in patterns:
            if re.search(pattern, self.content):
                return True

        return False

    def _extract_max_years(self) -> int | None:
        """提取最高工作年限"""
        patterns = [
            r"\d+[\-至～到](\d+) 年",  # "3-5 年" -> 5
            r"最多 (\d+) 年",
            r"不超过 (\d+) 年",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content)
            if match:
                return int(match.group(1))

        return None

    def _extract_required_education(self) -> list[str]:
        """提取要求学历"""
        education = []

        patterns = [
            r"学历 [要求至]?[：:]\s*(.+?)(?:\n|$)",
            r"最低学历 [：:]\s*(.+?)(?:\n|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content, re.IGNORECASE)
            if match:
                edu_text = match.group(1)
                for edu in self.EDUCATION_LEVELS.keys():
                    if edu in edu_text:
                        education.append(edu)

        # 如果没有明确列出，尝试推断
        if not education:
            if "本科" in self.content:
                education.append("本科")
            elif "大专" in self.content:
                education.append("大专")
            elif "硕士" in self.content:
                education.append("硕士")

        return education

    def _extract_required_industry(self) -> list[str]:
        """提取要求行业背景"""
        industries = []

        patterns = [
            r"(?:必须 | 要求).*(?:行业 | 领域)[：:]?\s*(.+?)(?:\n|$)",
            r"行业背景 [：:]\s*(.+?)(?:\n|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content, re.IGNORECASE)
            if match:
                industry_text = match.group(1)
                # 常见行业关键词
                industry_keywords = [
                    "金融",
                    "银行",
                    "证券",
                    "保险",
                    "互联网",
                    "电商",
                    "游戏",
                    "医疗",
                    "教育",
                    "制造",
                    "汽车",
                    "房地产",
                ]
                for kw in industry_keywords:
                    if kw in industry_text:
                        industries.append(kw)

        return industries

    def _extract_required_project_type(self) -> list[str]:
        """提取要求项目经验类型"""
        projects = []

        patterns = [
            r"(?:必须 | 要求).*(?:项目 | 系统).*(?:经验 | 经历)[：:]?\s*(.+?)(?:\n|$)",
            r"项目经验 [：:]\s*(.+?)(?:\n|$)",
            r"有.*(?:从 0 到 1|架构设计 | 高并发 | 分布式) 经验",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content, re.IGNORECASE)
            if match:
                project_text = match.group(1)
                # 常见项目类型
                project_keywords = [
                    "从 0 到 1",
                    "架构设计",
                    "高并发",
                    "分布式",
                    "微服务",
                    "大数据",
                    "实时",
                    "ToB",
                    "ToC",
                    "SaaS",
                    "平台",
                ]
                for kw in project_keywords:
                    if kw in project_text:
                        projects.append(kw)

        return projects

    def _extract_preferred_industry(self) -> list[str]:
        """提取加分行业背景"""
        # 类似 required_industry，但查找"优先"相关描述
        industries = []

        patterns = [
            r"(?:优先 | 加分).*(?:行业 | 领域)[：:]?\s*(.+?)(?:\n|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content, re.IGNORECASE)
            if match:
                industry_text = match.group(1)
                industry_keywords = [
                    "金融",
                    "银行",
                    "证券",
                    "互联网",
                    "电商",
                    "游戏",
                    "医疗",
                    "教育",
                ]
                for kw in industry_keywords:
                    if kw in industry_text:
                        industries.append(kw)

        return industries

    def _extract_preferred_project_type(self) -> list[str]:
        """提取加分项目经验"""
        projects = []

        patterns = [
            r"(?:优先 | 加分).*(?:项目 | 系统)[：:]?\s*(.+?)(?:\n|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content, re.IGNORECASE)
            if match:
                project_text = match.group(1)
                project_keywords = [
                    "从 0 到 1",
                    "架构设计",
                    "高并发",
                    "分布式",
                    "微服务",
                    "大数据",
                ]
                for kw in project_keywords:
                    if kw in project_text:
                        projects.append(kw)

        return projects

    def _extract_preferred_certifications(self) -> list[str]:
        """提取加分证书"""
        certs = []

        patterns = [
            r"(?:优先 | 加分 | 有).*证书 [：:]?\s*(.+?)(?:\n|$)",
            r"证书 [：:]\s*(.+?)(?:\n|$)",
            r"(?:PMP|PMP| 软考| 架构师 | 云认证).*证书",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content, re.IGNORECASE)
            if match:
                cert_text = match.group(1)
                cert_keywords = ["PMP", "软考", "架构师", "AWS", "Azure", "云认证"]
                for kw in cert_keywords:
                    if kw in cert_text:
                        certs.append(kw)

        return certs

    def _extract_location(self) -> str:
        """提取工作地点"""
        patterns = [
            r"工作地点 [：:]\s*(.+?)(?:\n|$)",
            r"工作城市 [：:]\s*(.+?)(?:\n|$)",
            r"城市 [：:]\s*(.+?)(?:\n|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return ""

    def _extract_salary_range(self) -> str:
        """提取薪资范围"""
        # 边界情况：面议/可谈等非数字薪资描述
        for kw in ['面议', '薪资面议', '待遇面议', '薪资可谈', '薪资Open', '薪资open']:
            if kw in self.content:
                return ""

        patterns = [
            r"薪资 [范围]?[：:]\s*(.+?)(?:\n|$)",
            r"薪酬 [：:]\s*(.+?)(?:\n|$)",
            r"(\d+[kK]-\d+[kK])",
            r"(\d+[万 W]-\d+[万 W])",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content, re.IGNORECASE)
            if match:
                return match.group(1).strip() if match.group(1) else match.group(0).strip()

        return ""

    def _extract_keywords(self) -> list[str]:
        """提取搜索关键词（用于 BOSS 搜索）"""
        keywords = []

        # 优先使用职位名称
        position = self._extract_position_name()
        if position:
            keywords.append(position)

        # 添加核心技能作为关键词
        skills = self._extract_required_skills()
        keywords.extend(skills[:2])  # 最多添加 2 个技能关键词

        return keywords
