"""
简历解析模块
支持 PDF/Word 格式，提取候选人关键信息
"""
import re
from pathlib import Path
from dataclasses import dataclass, field

import pdfplumber
from docx import Document


@dataclass
class ResumeInfo:
    """简历信息"""

    # 基本信息
    name: str = ""  # 姓名
    phone: str = ""  # 电话
    email: str = ""  # 邮箱
    current_city: str = ""  # 当前城市
    years_of_experience: int | None = None  # 工作年限
    education: str = ""  # 最高学历
    graduation_school: str = ""  # 毕业院校
    major: str = ""  # 专业

    # 工作经历
    current_company: str = ""  # 当前公司
    current_position: str = ""  # 当前职位
    industry: str = ""  # 行业背景
    work_history: list[dict] = field(default_factory=list)  # 工作经历列表

    # 技能
    skills: list[str] = field(default_factory=list)  # 技能列表
    programming_languages: list[str] = field(default_factory=list)  # 编程语言
    frameworks: list[str] = field(default_factory=list)  # 框架
    tools: list[str] = field(default_factory=list)  # 工具/平台

    # 项目经验
    projects: list[dict] = field(default_factory=list)  # 项目列表
    project_types: list[str] = field(default_factory=list)  # 项目类型标签

    # 证书/其他
    certifications: list[str] = field(default_factory=list)  # 证书
    self_summary: str = ""  # 自我评价

    # 原始文件路径
    file_path: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "current_city": self.current_city,
            "years_of_experience": self.years_of_experience,
            "education": self.education,
            "graduation_school": self.graduation_school,
            "major": self.major,
            "current_company": self.current_company,
            "current_position": self.current_position,
            "industry": self.industry,
            "skills": self.skills,
            "programming_languages": self.programming_languages,
            "frameworks": self.frameworks,
            "tools": self.tools,
            "project_types": self.project_types,
            "certifications": self.certifications,
            "self_summary": self.self_summary,
        }


class ResumeParser:
    """简历解析器"""

    # 学历映射
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

    # 技能关键词分类
    SKILL_CATEGORIES = {
        "languages": [
            "Python",
            "Java",
            "JavaScript",
            "TypeScript",
            "Go",
            "Golang",
            "C++",
            "C#",
            "Ruby",
            "PHP",
            "Swift",
            "Kotlin",
            "Rust",
            "SQL",
            "R",
            "MATLAB",
        ],
        "frameworks": [
            "Django",
            "Flask",
            "FastAPI",
            "Spring",
            "Spring Boot",
            "React",
            "Vue",
            "Angular",
            "TensorFlow",
            "PyTorch",
            ".NET",
            "Express",
        ],
        "tools": [
            "Git",
            "Docker",
            "Kubernetes",
            "Jenkins",
            "Linux",
            "AWS",
            "Azure",
            "GCP",
            "Redis",
            "MongoDB",
            "MySQL",
            "PostgreSQL",
            "Kafka",
            "Elasticsearch",
            "Nginx",
        ],
    }

    # 项目类型关键词
    PROJECT_TYPE_KEYWORDS = {
        "从 0 到 1": ["从 0 到 1", "从零开始", "初创", "搭建", "创立"],
        "架构设计": ["架构设计", "系统架构", "架构师", "重构"],
        "高并发": ["高并发", "高可用", "高性能", "亿级流量"],
        "分布式": ["分布式", "微服务", "服务化"],
        "大数据": ["大数据", "Hadoop", "Spark", "数据仓库"],
        "实时": ["实时", "流式处理", "在线"],
        "ToB": ["ToB", "企业级", "B 端"],
        "ToC": ["ToC", "消费者", "C 端"],
        "SaaS": ["SaaS", "云平台", "多租户"],
        "AI/ML": ["AI", "机器学习", "深度学习", "大模型", "LLM"],
    }

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.content = ""

    def parse(self) -> ResumeInfo:
        """解析简历"""
        self._read_file()

        resume = ResumeInfo()
        resume.file_path = str(self.file_path)

        # 提取各项信息
        resume.name = self._extract_name()
        resume.phone = self._extract_phone()
        resume.email = self._extract_email()
        resume.current_city = self._extract_city()
        resume.years_of_experience = self._extract_years_of_experience()
        resume.education = self._extract_education()
        resume.graduation_school = self._extract_school()
        resume.major = self._extract_major()
        resume.current_company = self._extract_current_company()
        resume.current_position = self._extract_current_position()
        resume.industry = self._extract_industry()
        resume.skills = self._extract_skills()
        resume.programming_languages = self._extract_programming_languages()
        resume.frameworks = self._extract_frameworks()
        resume.tools = self._extract_tools()
        resume.project_types = self._extract_project_types()
        resume.certifications = self._extract_certifications()
        resume.self_summary = self._extract_self_summary()

        return resume

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
        try:
            with pdfplumber.open(self.file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
        except Exception as e:
            print(f"读取 PDF 失败：{e}")
        return "\n".join(text_parts)

    def _read_docx(self) -> str:
        """读取 Word 文件"""
        try:
            doc = Document(self.file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paragraphs)
        except Exception as e:
            print(f"读取 Word 失败：{e}")
            return ""

    def _read_text(self) -> str:
        """读取文本文件"""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"读取文本失败：{e}")
            return ""

    # ========== 提取方法 ==========

    def _extract_name(self) -> str:
        """提取姓名"""
        # 常见姓名位置模式
        patterns = [
            r"^姓名 [：:]\s*(.+?)(?:\n|$)",
            r"^([张王李赵刘陈杨吴周郑孙朱马胡郭何高梁罗宋唐许邓韩冯曹彭曾萧田董袁潘于蒋蔡余杜叶程苏魏吕丁任沈姚卢姜崔钟谭陆汪范金石廖韦邱贾侯邵孟毛秦白尹万段康贺覃])[一-龥]{1,3}(?:\s|$)",
            r"^([一-龥]{2,4})\s*(?:男 | 女|\d{3}[- ]?\d{4}[- ]?\d{4})",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content, re.MULTILINE)
            if match:
                return match.group(1).strip()

        return ""

    def _extract_phone(self) -> str:
        """提取电话"""
        patterns = [
            r"电话 [：:]\s*(\d{3,4}[- ]?\d{3,4}[- ]?\d{4})",
            r"手机 [：:]\s*(\d{3,4}[- ]?\d{3,4}[- ]?\d{4})",
            r"(\d{3}[- ]?\d{4}[- ]?\d{4})",
            r"(\d{3}[- ]?\d{8})",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content)
            if match:
                return match.group(1).replace(" ", "").replace("-", "")

        return ""

    def _extract_email(self) -> str:
        """提取邮箱"""
        pattern = r"[\w\.-]+@[\w\.-]+\.\w+"
        match = re.search(pattern, self.content)
        return match.group(0) if match else ""

    def _extract_city(self) -> str:
        """提取当前城市"""
        patterns = [
            r"现居 [：:]\s*(.+?)(?:\n|$)",
            r"当前城市 [：:]\s*(.+?)(?:\n|$)",
            r"所在城市 [：:]\s*(.+?)(?:\n|$)",
        ]

        city_keywords = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "西安", "南京", "苏州"]

        for pattern in patterns:
            match = re.search(pattern, self.content)
            if match:
                text = match.group(1)
                for city in city_keywords:
                    if city in text:
                        return city
                return text.strip()

        # 从工作经历推断
        for city in city_keywords:
            if city in self.content:
                return city

        return ""

    def _extract_years_of_experience(self) -> int | None:
        """提取工作年限"""
        patterns = [
            r"(\d+) 年 (?:工作 | 开发 | 从业) 经验",
            r"(?:工作 | 从业)[：:]\s*(\d+) 年",
            r"(\d+) 年以上",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content)
            if match:
                return int(match.group(1))

        # 从工作经历时间推断
        year_pattern = r"(\d{4})[.-](\d{4}|\d{2}|至今)"
        matches = re.findall(year_pattern, self.content)

        if matches:
            years = set()
            for start, end in matches:
                try:
                    start_year = int(start)
                    if end in ["至今", "Present"]:
                        end_year = 2026
                    elif len(end) == 2:
                        end_year = int("20" + end)
                    else:
                        end_year = int(end)
                    years.add(end_year - start_year)
                except:
                    continue

            if years:
                return max(years)

        return None

    def _extract_education(self) -> str:
        """提取学历"""
        patterns = [
            r"学历 [：:]\s*(本科 | 硕士 | 博士 | 大专| 高中 | 中专)",
            r"(本科 | 硕士 | 博士 | 大专 | 高中 | 中专) (?:毕业 | 在读)",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content)
            if match:
                return match.group(1)

        # 查找最高学历
        for edu in ["博士", "硕士", "本科", "大专"]:
            if edu in self.content:
                return edu

        return ""

    def _extract_school(self) -> str:
        """提取毕业院校"""
        patterns = [
            r"(?:毕业) 院校 [：:]\s*(.+?)(?:\n|$)",
            r"([清华北大复旦交大浙大南大中科大武大华科中大](?:大学 | 大))",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content)
            if match:
                return match.group(1).strip()

        return ""

    def _extract_major(self) -> str:
        """提取专业"""
        patterns = [
            r"专业 [：:]\s*(.+?)(?:\n|$)",
            r"(计算机 | 软件 | 通信 | 电子 | 自动化 | 数学 | 物理 | 经济 | 管理) 相关",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content)
            if match:
                return match.group(1).strip()

        return ""

    def _extract_current_company(self) -> str:
        """提取当前公司"""
        patterns = [
            r"现任公司 [：:]\s*(.+?)(?:\n|$)",
            r"当前公司 [：:]\s*(.+?)(?:\n|$)",
            r"现就职于 [：:]\s*(.+?)(?:\n|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content)
            if match:
                return match.group(1).strip()

        # 从最近的工作经历提取
        work_pattern = r"(\d{4})[.-](?:\d{4}|至今)\s*(?:在 | 就职于)?(.+?)(?:\n|$)"
        match = re.search(work_pattern, self.content)
        if match:
            return match.group(2).strip()

        return ""

    def _extract_current_position(self) -> str:
        """提取当前职位"""
        patterns = [
            r"现任职位 [：:]\s*(.+?)(?:\n|$)",
            r"当前职位 [：:]\s*(.+?)(?:\n|$)",
            r"(?:高级 | 中级 | 初级)?(工程师 | 开发 | 架构师 | 经理 | 主管| 总监)",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content)
            if match:
                return match.group(0).strip()

        return ""

    def _extract_industry(self) -> str:
        """提取行业背景"""
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
            "通信",
            "软件",
            "硬件",
            "咨询",
        ]

        for industry in industry_keywords:
            if industry in self.content:
                return industry

        return ""

    def _extract_skills(self) -> list[str]:
        """提取技能列表"""
        skills = []

        # 合并所有技能分类的关键词
        all_skills = []
        for category in self.SKILL_CATEGORIES.values():
            all_skills.extend(category)

        # 添加项目类型关键词
        for kw_list in self.PROJECT_TYPE_KEYWORDS.values():
            all_skills.extend(kw_list)

        for skill in all_skills:
            if skill in self.content:
                skills.append(skill)

        return list(set(skills))

    def _extract_programming_languages(self) -> list[str]:
        """提取编程语言"""
        return [lang for lang in self.SKILL_CATEGORIES["languages"] if lang in self.content]

    def _extract_frameworks(self) -> list[str]:
        """提取框架"""
        return [fw for fw in self.SKILL_CATEGORIES["frameworks"] if fw in self.content]

    def _extract_tools(self) -> list[str]:
        """提取工具/平台"""
        return [tool for tool in self.SKILL_CATEGORIES["tools"] if tool in self.content]

    def _extract_project_types(self) -> list[str]:
        """提取项目类型标签"""
        types = []

        for project_type, keywords in self.PROJECT_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw in self.content:
                    types.append(project_type)
                    break

        return types

    def _extract_certifications(self) -> list[str]:
        """提取证书"""
        certs = []
        cert_keywords = ["PMP", "软考", "架构师", "AWS", "Azure", "云认证", "认证"]

        for kw in cert_keywords:
            if kw in self.content:
                certs.append(kw)

        return certs

    def _extract_self_summary(self) -> str:
        """提取自我评价"""
        patterns = [
            r"自我评价 [：:]\s*(.+?)(?:\n\n|\Z)",
            r"个人总结 [：:]\s*(.+?)(?:\n\n|\Z)",
            r"简介 [：:]\s*(.+?)(?:\n\n|\Z)",
        ]

        for pattern in patterns:
            match = re.search(pattern, self.content, re.DOTALL)
            if match:
                return match.group(1).strip()

        return ""
