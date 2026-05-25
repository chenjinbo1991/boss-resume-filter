# -*- coding: utf-8 -*-
"""
招聘需求文档解析器
支持解析：
1. 必要条件（硬性约束）- 必须全部满足（技术关键词只需满足其一）
2. 职位要求（软性要求）- 用于评分，匹配越多得分越高
"""
import json
import re
import os
from typing import Dict, List
from constants import MAJOR_CITIES


_major_cities_set = set(MAJOR_CITIES)


def _resolve_city(raw: str) -> str:
    """从原始地点字符串中提取城市名，如 '南京市雨花区凯润大厦' → '南京'"""
    if not raw:
        return ""
    # 先从带"市"后缀的格式提取：南京市→南京，上海市→上海
    m = re.search(r'([一-龥]{2,3})市', raw)
    if m:
        candidate = m.group(1)
        if candidate in _major_cities_set:
            return candidate
    # 直接匹配城市名（按长度降序，防止"吉林"误匹配"吉林市"）
    for city in MAJOR_CITIES:
        if city in raw:
            return city
    return ""


def _extract_work_location(text: str) -> str:
    """从招聘需求中提取工作地点（城市名）"""
    if not text:
        return ""
    # 模式1: "工作地点：南京市雨花区凯润大厦"
    m = re.search(r'工作地点\s*[：:]\s*([^\n]{2,20})', text)
    if m:
        city = _resolve_city(m.group(1))
        if city:
            return city
    # 模式2: "base：上海浦东" / "base地：深圳南山"
    m = re.search(r'base\s*(?:地)?\s*[：:]\s*([^\n]{2,20})', text, re.IGNORECASE)
    if m:
        city = _resolve_city(m.group(1))
        if city:
            return city
    # 模式3: "坐标：成都高新区"
    m = re.search(r'坐标\s*[：:]\s*([^\n]{2,20})', text)
    if m:
        city = _resolve_city(m.group(1))
        if city:
            return city
    # 兜底：全文扫描城市名
    for city in MAJOR_CITIES:
        if city in text:
            return city
    return ""


def _extract_salary_range(text: str):
    """从招聘需求中提取薪资范围。返回 (min_k, max_k)，未匹配或面议返回 (None, None)"""
    if not text:
        return None, None

    # 边界情况：面议/薪资open/可谈 等非数字薪资描述，直接跳过
    non_numeric = ['面议', '薪资面议', '待遇面议', '薪资可谈', '薪资Open', '薪资open', '薪资OPEN']
    for kw in non_numeric:
        if kw in text:
            return None, None

    patterns = [
        r'薪资(?:范围)?\s*[：:]\s*(\d+)\s*[kK]\s*[-~～\-]\s*(\d+)\s*[kK]',
        r'月薪\s*[：:]\s*(\d+)\s*[kK]\s*[-~～\-]\s*(\d+)\s*[kK]',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None, None


def parse_job_requirements(text: str) -> Dict:
    """
    从招聘需求文本中解析出关键信息
    """
    # 预定义关键词库
    experience_keywords = {
        '应届生': 0, '应届毕业生': 0,
        '1 年': 1, '一年': 1, '1-3 年': 1, '1-5 年': 1,
        '2 年': 2, '两年': 2, '3-5 年': 3,
        '3 年': 3, '三年': 3, '3-10 年': 3,
        '4 年': 4, '四年': 4, '5-10 年': 5,
        '5 年': 5, '五年': 5, '5 年以上': 5,
        '6 年': 6, '六年': 6,
        '7 年': 7, '七年': 7,
        '8 年': 8, '八年': 8,
        '9 年': 9, '九年': 9,
        '10 年': 10, '十年': 10,
        '不限': 0, '无要求': 0
    }

    education_keywords = {
        '不限': '不限', '无要求': '不限',
        '高中': '高中', '中专': '中专', '大专': '大专',
        '本科': '本科', '学士': '本科',
        '硕士': '硕士', '研究生': '硕士',
        '博士': '博士', '博士后': '博士'
    }

    # === 1. 提取职位名称 ===
    job_title = "Java 工程师"  # 默认值

    # 支持多种格式匹配岗位名称
    title_patterns = [
        # markdown 标题格式：# 高级 Python/Java 开发工程师
        r'#\s*(.*(工程师|开发|架构|专家|经理|总监))',
        # 职位描述【高级 Java/Python 工程师】
        r'职位描述\s*[\[【〔(（]\s*(.*?(?:工程师|开发|架构|专家|经理|总监))\s*[\]】〕)）]',
        # 【高级 Java/Python 工程师】（没有"职位描述"前缀）
        r'^[\[【〔(（]\s*(.*?(?:工程师|开发|架构|专家|经理|总监))\s*[\]】〕)）]',
        # 职位：高级 Java/Python 工程师
        r'职位\s*[：:]\s*(.*?(?:工程师|开发|架构|专家|经理|总监))',
        # 岗位：高级 Java/Python 工程师
        r'岗位\s*[：:]\s*(.*?(?:工程师|开发|架构|专家|经理|总监))',
        # 诚聘：高级 Java/Python 工程师
        r'诚聘\s*[：:]\s*(.*?(?:工程师|开发|架构|专家|经理|总监))',
        # 职位名称：高级 Java 工程师
        r'职位名称\s*[：:]\s*(.*?(?:工程师|开发|架构|专家|经理|总监))',
    ]

    for pattern in title_patterns:
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            matched = match.group(1).strip()
            if matched:
                job_title = matched
                break

    # === 2. 分离不同部分 ===
    required_section = ""
    job_desc_section = ""
    position_req_section = ""

    # 先尝试用 markdown 格式分离
    if re.search(r'^##\s*硬性条件', text, re.MULTILINE):
        # markdown 格式：## 硬性条件
        parts = re.split(r'^##\s*硬性条件', text, flags=re.MULTILINE)
        if len(parts) > 1:
            job_desc_and_position = parts[0]
            required_section = parts[1]
    elif '必要条件' in text:
        parts = text.split('必要条件', 1)
        job_desc_and_position = parts[0]
        required_section = parts[1] if len(parts) > 1 else ""
        # 清理前缀符号
        required_section = re.sub(r'^[\s:：（(]*.*?[）)]?[\s:：,，]*', '', required_section).strip()
    else:
        job_desc_and_position = text

    # 进一步分离职位描述和职位要求
    if '职位描述' in job_desc_and_position and '职位要求' in job_desc_and_position:
        # 先按职位描述分
        pos_parts = job_desc_and_position.split('职位描述', 1)
        if len(pos_parts) > 1:
            remaining = pos_parts[1]
            if '职位要求' in remaining:
                req_parts = remaining.split('职位要求', 1)
                job_desc_section = req_parts[0]
                position_req_section = req_parts[1] if len(req_parts) > 1 else ""
            else:
                job_desc_section = remaining
    elif '职位描述' in job_desc_and_position:
        pos_parts = job_desc_and_position.split('职位描述', 1)
        job_desc_section = pos_parts[1] if len(pos_parts) > 1 else ""
    elif '职位要求' in job_desc_and_position:
        pos_parts = job_desc_and_position.split('职位要求', 1)
        position_req_section = pos_parts[1] if len(pos_parts) > 1 else ""
    else:
        job_desc_section = job_desc_and_position

    # 如果是 markdown 格式，使用章节来分离
    if re.search(r'^#\s*', text, re.MULTILINE):
        # 提取## 硬性条件 和### 工作经验、### 学历要求等章节
        hard_match = re.search(r'^##\s*硬性条件.*?(?=^##|\Z)', text, flags=re.MULTILINE|re.DOTALL)
        work_exp_match = re.search(r'^###\s*工作经验.*?(?=^###|\Z)', text, flags=re.MULTILINE|re.DOTALL)
        edu_match = re.search(r'^###\s*学历要求.*?(?=^###|\Z)', text, flags=re.MULTILINE|re.DOTALL)

        # 合并硬性条件、工作经验、学历要求作为 required_section
        sections = []
        if hard_match:
            sections.append(hard_match.group(0))
        if work_exp_match:
            sections.append(work_exp_match.group(0))
        if edu_match:
            sections.append(edu_match.group(0))
        required_section = '\n'.join(sections)

        # 提取## 软性条件 章节作为 position_req_section
        match = re.search(r'^##\s*软性条件.*?(?=^##|\Z)', text, flags=re.MULTILINE|re.DOTALL)
        if match:
            position_req_section = match.group(0)
        # 其余部分作为 job_desc_section
        job_desc_section = text

    # === 3. 提取经验要求 ===
    exp_value = 0

    # 优先从明确的"工作年限"字段匹配
    work_exp_patterns = [
        r'工作年限\s*[：:]\s*(\d+)\s*[-~～]\s*(\d+)\s*年',  # 5-8 年
        r'工作年限\s*[：:]\s*(\d+)\s*年及以上',
        r'工作年限\s*[：:]\s*(\d+)\s*年以上',
        r'工作年限\s*[：:]\s*(\d+)\s*年',
        # 支持 markdown 粗体格式：**工作年限**：5-8 年
        r'\*\*工作年限\*\*\s*[：:]\s*(\d+)\s*[-~～]\s*(\d+)\s*年',
        r'\*\*工作年限\*\*\s*[：:]\s*(\d+)\s*年及以上',
        r'\*\*工作年限\*\*\s*[：:]\s*(\d+)\s*年以上',
        r'\*\*工作年限\*\*\s*[：:]\s*(\d+)\s*年',
    ]

    # 优先从必要条件部分查找明确的"工作年限"字段
    for pattern in work_exp_patterns:
        match = re.search(pattern, required_section)
        if match:
            if len(match.groups()) == 2:  # 范围匹配，取最小值
                exp_value = int(match.group(1))
            else:
                exp_value = int(match.group(1))
            break

    # 如果没有找到，再用通用模式匹配
    if exp_value == 0:
        # 按优先级排序：越具体的模式越优先
        exp_patterns = [
            (r'(\d+)\s*年以上', lambda m: int(m)),         # X 年以上 - 直接取
            (r'(\d+)\s*年及以上', lambda m: int(m)),       # X 年及以上 - 直接取
            (r'(\d+)\s*年工作经验', lambda m: int(m)),     # X 年工作经验 - 直接取
            (r'(\d+)\s*年经验', lambda m: int(m)),         # X 年经验 - 直接取
            (r'(\d+)\s*[-~～]\s*(\d+)\s*年', lambda m: min(int(m[0]), int(m[1]))),  # X-Y 年 - 取最小值
            (r'(\d+)\s*年', lambda m: int(m)),             # 单独 X 年 - 最后使用
        ]

        # 优先从必要条件部分查找
        for pattern, extractor in exp_patterns:
            match = re.search(pattern, required_section)
            if match:
                if len(match.groups()) == 1:
                    exp_value = extractor(match.group(1))
                else:
                    exp_value = extractor(match.groups())
                break

    # 如果必要条件没有，从职位要求部分查找
    if exp_value == 0:
        for pattern, extractor in exp_patterns:
            match = re.search(pattern, position_req_section)
            if match:
                if len(match.groups()) == 1:
                    exp_value = extractor(match.group(1))
                else:
                    exp_value = extractor(match.groups())
                break

    # 最后从职位描述部分查找
    if exp_value == 0:
        for pattern, extractor in exp_patterns:
            match = re.search(pattern, job_desc_section)
            if match:
                if len(match.groups()) == 1:
                    exp_value = extractor(match.group(1))
                else:
                    exp_value = extractor(match.groups())
                break

    # === 4. 提取学历要求 ===
    edu_value = "不限"

    # 优先从明确的学历字段匹配（如"最低学历：本科"）
    edu_field_patterns = [
        r'最低学历\s*[：:]\s*([^\n]+)',
        r'学历\s*要求\s*[：:]\s*([^\n]+)',
        r'学历要求\s*[：:]\s*([^\n]+)',
        # 支持 markdown 粗体格式：**最低学历**：本科
        r'\*\*最低学历\*\*\s*[：:]\s*([^\n]+)',
        r'\*\*学历\*\*\s*[：:]\s*([^\n]+)',
    ]

    found_edu = None

    # 优先从必要条件部分查找明确的学历字段
    for pattern in edu_field_patterns:
        match = re.search(pattern, required_section)
        if match:
            edu_text = match.group(1).strip()
            # 从匹配结果中提取学历
            if '本科' in edu_text or '学士' in edu_text:
                found_edu = '本科'
                break
            elif '硕士' in edu_text or '研究生' in edu_text:
                found_edu = '硕士'
                break
            elif '博士' in edu_text or '博士后' in edu_text:
                found_edu = '博士'
                break
            elif '大专' in edu_text:
                found_edu = '大专'
                break
            elif '高中' in edu_text or '中专' in edu_text:
                found_edu = '高中'
                break
            elif '不限' in edu_text or '无要求' in edu_text:
                found_edu = '不限'
                break

    # 如果没有找到明确字段，从必要条件部分提取学历关键词
    # 注意：最低学历应从低到高判断，因为"最低"意味着门槛，不应被加分项误导
    if found_edu is None and required_section:
        # 先排除加分语境（如"博士优先"、"硕士优先"等）
        cleaned_section = required_section
        for pattern in [r'博士优先\b', r'博士后优先\b', r'硕士优先\b', r'研究生优先\b', r'博士学历加分\b']:
            cleaned_section = re.sub(pattern, '', cleaned_section)
        # 从低到高判断：大专 → 本科 → 硕士 → 博士
        if '大专' in cleaned_section:
            found_edu = '大专'
        elif '高中' in cleaned_section or '中专' in cleaned_section:
            found_edu = '高中'
        elif '本科' in cleaned_section or '学士' in cleaned_section:
            found_edu = '本科'
        elif '硕士' in cleaned_section or '研究生' in cleaned_section:
            found_edu = '硕士'
        elif '博士' in cleaned_section or '博士后' in cleaned_section:
            found_edu = '博士'

    # 如果没有找到，从职位要求部分查找
    if found_edu is None:
        for pattern in edu_field_patterns:
            match = re.search(pattern, position_req_section)
            if match:
                edu_text = match.group(1).strip()
                if '本科' in edu_text or '学士' in edu_text:
                    found_edu = '本科'
                    break
                elif '硕士' in edu_text or '研究生' in edu_text:
                    found_edu = '硕士'
                    break
                elif '博士' in edu_text or '博士后' in edu_text:
                    found_edu = '博士'
                    break
                elif '大专' in edu_text:
                    found_edu = '大专'
                    break
                elif '高中' in edu_text or '中专' in edu_text:
                    found_edu = '高中'
                    break

    # 最后从职位描述部分查找（优先级最低）
    if found_edu is None:
        # 排除加分语境后再判断，从低到高
        cleaned_desc = job_desc_section
        for pattern in [r'博士优先\b', r'博士后优先\b', r'硕士优先\b', r'研究生优先\b', r'博士学历加分\b',
                        r'博士及以上\b', r'硕士及以上\b', r'有博士\b', r'有硕士\b']:
            cleaned_desc = re.sub(pattern, '', cleaned_desc)
        if '大专' in cleaned_desc:
            found_edu = '大专'
        elif '高中' in cleaned_desc or '中专' in cleaned_desc:
            found_edu = '高中'
        elif '本科' in cleaned_desc or '学士' in cleaned_desc:
            found_edu = '本科'
        elif '硕士' in cleaned_desc or '研究生' in cleaned_desc:
            found_edu = '硕士'
        elif '博士' in cleaned_desc or '博士后' in cleaned_desc:
            found_edu = '博士'

    if found_edu:
        edu_value = found_edu

    # === 5. 提取必要条件（硬性约束）===
    required_conditions = []

    # 学历相关要求
    if '双证齐全' in required_section:
        required_conditions.append('双证齐全')
    if '统招' in required_section:
        if '本科' in required_section:
            required_conditions.append('统招本科')
        else:
            required_conditions.append('统招')
    if '全日制' in required_section:
        required_conditions.append('全日制')
    if '第一学历' in required_section:
        required_conditions.append('第一学历本科')
    if '985' in required_section:
        required_conditions.append('985 院校')
    if '211' in required_section:
        required_conditions.append('211 院校')

    # 年龄限制
    age_match = re.search(r'年龄在?\s*(\d+)\s*岁', required_section)
    max_age = None
    if age_match:
        max_age = int(age_match.group(1))
        required_conditions.append(f'年龄≤{max_age}岁')

    # 从必要条件部分提取技术关键词（硬约束，只需满足其一）
    tech_condition_keywords = []
    tech_keywords = [
        'activiti', 'camunda', 'flowable', '工作流',
        'Java', 'Python', 'JavaScript', 'TypeScript', 'Go', 'C++', 'C#',
        'Spring', 'Spring Boot', 'SpringBoot', 'Spring Cloud', 'SpringCloud', 'Spring AI', 'Dubbo', 'MyBatis', 'MyBatis Plus',
        'MySQL', 'Oracle', 'Redis', 'MongoDB', 'Kafka', 'RabbitMQ',
        'Docker', 'Kubernetes', 'K8s', 'Linux',
        'Vue', 'Vue.js', 'React', 'Angular', 'HTML', 'CSS',
        'AI', '人工智能', '机器学习', '深度学习',
        'LLM', '大模型', 'AI Agent', '智能体', 'Langchain', 'LangChain', '智能问答', '知识库', 'RAG',
        '微服务', '分布式', '消息中间件'
    ]

    if required_section:
        for keyword in tech_keywords:
            keyword_variants = [keyword.lower(), keyword.lower().replace(' ', '')]
            for variant in keyword_variants:
                if variant and variant in required_section.lower():
                    if not any(keyword.lower() in existing.lower() for existing in tech_condition_keywords):
                        tech_condition_keywords.append(keyword)
                    break

    # === 6. 提取技能关键词（从所有部分）- 软性要求，用于评分 ===
    soft_skills = []

    # 合并所有部分作为技能提取源
    # markdown 格式中，技能可能在硬性条件（### 技能要求）或软性条件中
    combined_soft_section = required_section + "\n" + job_desc_section + "\n" + position_req_section

    # 技能列表 - 按长度降序排列，优先匹配长技能名
    tech_skills = [
        # Spring 家族
        'Spring Cloud', 'SpringBoot', 'Spring Boot', 'Spring MVC', 'SpringMvc', 'Spring AI', 'Spring',
        # 数据库
        'MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Oracle', 'SQLServer', 'SQLite', 'Elasticsearch',
        # 语言
        'JavaScript', 'TypeScript', 'Java', 'Python', 'Go', 'Rust', 'C++', 'C#', 'PHP', 'Ruby', 'Swift', 'Kotlin', 'Scala',
        # 前端
        'React', 'Vue.js', 'Vue', 'Angular', 'HTML', 'CSS', 'Sass', 'Less', 'jQuery', 'Bootstrap', 'Webpack', 'Vite', 'Node.js', 'Next.js',
        # 后端框架
        'Django', 'Flask', 'Express', 'FastAPI', 'Gin', 'Laravel', 'Dubbo', 'MyBatis Plus', 'MyBatis',
        # 云/DevOps
        'AWS', 'Azure', '阿里云', '腾讯云', '华为云',
        'Docker', 'Kubernetes', 'K8s', 'Jenkins', 'GitLab', 'CI/CD', 'Terraform', 'Ansible', 'Nginx', 'Apache',
        # 数据/AI
        'TensorFlow', 'PyTorch', 'Pandas', 'NumPy', 'Spark', 'Hadoop',
        'AI', '人工智能', '机器学习', '深度学习', '数据分析',
        'LLM', '大模型', 'AI Agent', '智能体', 'Langchain', 'LangChain', '智能问答', '知识库', 'RAG', '向量数据库',
        # 其他
        'Linux', 'Git', '微服务', '分布式', '大数据', '云计算',
        'MQTT', 'Kafka', 'RabbitMQ', '消息队列', '消息中间件', 'GraphQL', 'RESTful', 'API', 'RPC',
        # 工作流
        'activiti', 'camunda', 'flowable', '工作流'
    ]

    # 对文本进行预处理，统一常见变体
    normalized_text = combined_soft_section
    normalized_text = re.sub(r'Spring\s*Cloud', 'SpringCloud', normalized_text, flags=re.IGNORECASE)
    normalized_text = re.sub(r'Spring\s*Boot', 'SpringBoot', normalized_text, flags=re.IGNORECASE)
    normalized_text = re.sub(r'Spring\s*MVC', 'SpringMvc', normalized_text, flags=re.IGNORECASE)
    normalized_text = re.sub(r'Spring\s*Mvc', 'SpringMvc', normalized_text, flags=re.IGNORECASE)
    normalized_text = re.sub(r'Spring\s*AI', 'SpringAI', normalized_text, flags=re.IGNORECASE)
    normalized_text = re.sub(r'My\s*Batis\s*Plus', 'MyBatisPlus', normalized_text, flags=re.IGNORECASE)
    normalized_text = re.sub(r'My\s*Batis', 'MyBatis', normalized_text, flags=re.IGNORECASE)
    normalized_text = re.sub(r'Node\s*\.\s*js', 'NodeJs', normalized_text, flags=re.IGNORECASE)
    normalized_text = re.sub(r'Vue\s*\.\s*js', 'VueJs', normalized_text, flags=re.IGNORECASE)
    normalized_text = re.sub(r'AI\s*Agent', 'AIAgent', normalized_text, flags=re.IGNORECASE)

    normalized_skill_map = {
        'Spring Cloud': 'SpringCloud',
        'Spring Boot': 'SpringBoot',
        'Spring MVC': 'SpringMvc',
        'Spring AI': 'SpringAI',
        'MyBatis Plus': 'MyBatisPlus',
        'MyBatis': 'MyBatis',
        'Node.js': 'NodeJs',
        'Vue.js': 'VueJs',
        'AI Agent': 'AIAgent',
    }

    # 匹配技能关键词 - 按长度降序，优先匹配长技能名
    for skill in tech_skills:
        normalized_skill = normalized_skill_map.get(skill, re.sub(r'\s+', '', skill))

        # 英文技能：不使用 \b，改用更宽松的模式（适配中文上下文）
        if re.search(re.escape(normalized_skill), normalized_text, re.IGNORECASE):
            if skill not in soft_skills:
                soft_skills.append(skill)
        # 中文技能直接匹配
        elif len(skill) >= 2 and not any(c.isalpha() for c in skill):
            if skill in combined_soft_section and skill not in soft_skills:
                soft_skills.append(skill)

    # 去重（忽略大小写，同时处理空格变体）
    unique_soft_skills = []
    seen_skills = set()
    for skill in soft_skills:
        skill_key = re.sub(r'\s+', '', skill).lower()
        if skill_key not in seen_skills:
            seen_skills.add(skill_key)
            unique_soft_skills.append(skill)

    # 返回解析结果
    salary_min, salary_max = _extract_salary_range(text)
    return {
        "job_title": job_title,
        "min_exp": exp_value,
        "edu": edu_value,
        "work_location": _extract_work_location(text),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "max_age": max_age,
        "soft_skills": unique_soft_skills,  # 职位描述中的技能要求（用于评分）
        "required_conditions": required_conditions,
        "tech_conditions": tech_condition_keywords  # 必要条件中的技术要求（只需满足其一）
    }


def generate_config_from_text(requirements_text: str, merge_existing: bool = True) -> Dict:
    """
    从招聘需求文本生成完整的配置文件（支持权重）
    merge_existing: True=合并到现有配置（岗位覆盖或新增），False=生成新配置
    """
    parsed = parse_job_requirements(requirements_text)

    # 对 soft_skills 去重（忽略大小写）
    skills = parsed["soft_skills"]
    seen = set()
    unique_skills = []
    for skill in skills:
        skill_lower = skill.lower()
        if skill_lower not in seen:
            seen.add(skill_lower)
            unique_skills.append(skill)

    # 为技能分配权重
    weighted_keywords = []

    # 提取职位名称中的技术关键词（Java、Python 等），这些词权重调高
    job_title = parsed.get("job_title", "").lower()
    position_tech_keywords = []

    # 从职位名称中提取技术关键词
    tech_keywords_in_title = [
        'java', 'python', 'javascript', 'typescript', 'go', 'c++', 'c#', 'php', 'ruby', 'swift', 'kotlin', 'scala',
        '前端', '后端', '全栈', '移动端', 'android', 'ios',
        'ai', '算法', '数据', '测试', '运维', '开发'
    ]

    for kw in tech_keywords_in_title:
        if kw in job_title:
            position_tech_keywords.append(kw.lower())

    # 先从需求原文中提取明确提到"优先"的 AI 关键词
    # 如果需求中明确列举了 AI 关键词优先，则以需求为准；否则使用兜底列表
    explicit_ai_keywords = []
    for line in requirements_text.split('\n'):
        if '优先' in line:
            # 提取该行中提到的所有技能关键词
            for skill in unique_skills:
                skill_lower = skill.lower()
                if skill_lower in line.lower():
                    explicit_ai_keywords.append(skill_lower)

    # 兜底的 AI 关键词列表（当需求没有明确说明时使用）
    default_ai_keywords = ['llm', '大模型', 'ai agent', '智能体', 'langchain', '智能问答', '知识库', 'rag', '向量数据库', '生成式 ai', 'aigc', 'spring ai', 'ai']

    for skill in unique_skills:
        weight = 1  # 默认权重
        skill_lower = skill.lower()

        # 检查技能在原文中的上下文，确定权重
        # 权重 3：精通、擅长、深入、核心
        # 权重 2：熟练、熟悉、掌握、有...经验、优先、职位名称相关
        # 权重 1：了解、接触过、基本
        # 注意：中文和英文之间可能有空格，需要用正则匹配

        if re.search(rf'{re.escape(skill_lower)}\s*精通|精通\s*{re.escape(skill_lower)}', requirements_text.lower()):
            weight = 3
        elif re.search(rf'{re.escape(skill_lower)}\s*熟练 | 熟练\s*{re.escape(skill_lower)}|'
                       rf'{re.escape(skill_lower)}\s*熟悉 | 熟悉\s*{re.escape(skill_lower)}|'
                       rf'{re.escape(skill_lower)}\s*优先 | 优先\s*{re.escape(skill_lower)}|'
                       rf'{re.escape(skill_lower)}\s*深入 | 深入\s*{re.escape(skill_lower)}', requirements_text.lower()):
            weight = 2
        # 检查是否在"优先/熟悉/熟练"条件所在的同一行（支持同一行中多个技能共享权重）
        for line in requirements_text.split('\n'):
            line_lower = line.lower()
            if skill_lower in line_lower:
                # 检查该行是否有"优先"、"熟悉"、"熟练"等关键词
                if re.search(r'优先 | 熟悉 | 熟练 | 掌握 | 擅长', line_lower):
                    weight = 2
                    break

        # 如果技能与职位名称相关，权重设为 2
        if weight == 1 and position_tech_keywords:
            for pos_kw in position_tech_keywords:
                if pos_kw in skill_lower or skill_lower in pos_kw:
                    weight = 2
                    break

        # AI 关键词权重处理：
        # 1. 如果需求中明确提到某些 AI 关键词"优先"，则只对这些关键词加权
        # 2. 如果需求中没有明确提到任何 AI 关键词优先，则使用兜底列表对所有 AI 关键词加权
        if explicit_ai_keywords:
            # 需求中有明确说明，只对明确提到的关键词加权
            if skill_lower in explicit_ai_keywords:
                weight = 2
        else:
            # 需求中没有明确说明，使用兜底列表
            if any(ai_kw in skill_lower for ai_kw in default_ai_keywords):
                weight = 2

        weighted_keywords.append({"name": skill, "weight": weight})

    # 合并必要条件和技术条件
    all_required = parsed["required_conditions"].copy()
    for tech_cond in parsed.get("tech_conditions", []):
        if tech_cond not in all_required:
            all_required.append(tech_cond)

    # 生成新岗位配置
    new_job_config = {
        "min_exp": parsed["min_exp"],
        "edu": parsed["edu"],
        "work_location": parsed.get("work_location", ""),
        "salary_min": parsed.get("salary_min"),
        "salary_max": parsed.get("salary_max"),
        "keywords": weighted_keywords,  # 带权重的技能列表
        "required_conditions": all_required,
        "tech_conditions": parsed.get("tech_conditions", [])  # 单独存储，用于 OR 检查
    }

    # 如果合并现有配置，则读取并更新
    if merge_existing:
        config_file = "job_config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    existing_config = json.load(f)
            except Exception:
                existing_config = {"job_requirements": {}}
        else:
            existing_config = {"job_requirements": {}}

        # 确保 job_requirements 键存在
        if "job_requirements" not in existing_config:
            existing_config["job_requirements"] = {}
    else:
        existing_config = {"job_requirements": {}}

    # 更新或新增岗位配置
    job_title = parsed["job_title"]
    if job_title == "default":
        print("警告：'default' 是保留字，不能作为岗位名称")
        job_title = "Java 工程师"  # 使用默认名称

    # 规范化岗位名称：去除多余空格，统一格式
    normalized_job_title = re.sub(r'\s+', ' ', job_title).strip()

    # 检查是否已存在相同（规范化后）的岗位，如果存在则覆盖
    existing_key_to_delete = None
    for key in existing_config["job_requirements"].keys():
        normalized_key = re.sub(r'\s+', ' ', key).strip()
        if normalized_key.lower() == normalized_job_title.lower():
            existing_key_to_delete = key
            break

    if existing_key_to_delete:
        print(f"检测到重复岗位：'{existing_key_to_delete}'，将进行覆盖更新")
        del existing_config["job_requirements"][existing_key_to_delete]

    existing_config["job_requirements"][normalized_job_title] = new_job_config

    return existing_config


def save_config(config: Dict, filename: str = "job_config.json"):
    """保存配置到文件"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    print(f"配置已保存到 {filename}")


def main():
    """主函数"""
    print("招聘需求文档解析器")
    print("=" * 50)
    print("请粘贴您的招聘需求文档内容，结束后输入 'END'：")
    print()

    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == 'END':
                break
            lines.append(line)
        except KeyboardInterrupt:
            print("\n操作已取消")
            return

    requirements_text = '\n'.join(lines)

    if not requirements_text.strip():
        print("未输入任何内容")
        return

    print("\n正在解析招聘需求...")
    try:
        # 检查是否已存在该岗位
        parsed = parse_job_requirements(requirements_text)
        job_title = parsed["job_title"]

        config_file = "job_config.json"
        is_new_job = True
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                    # default 不是岗位，跳过
                    job_keys = [k for k in existing.get("job_requirements", {}).keys() if k != "default"]
                    if job_title in job_keys:
                        is_new_job = False
            except Exception:
                pass

        if is_new_job:
            print(f"\n[新增岗位] {job_title}")
        else:
            print(f"\n[覆盖岗位] {job_title}")

        config = generate_config_from_text(requirements_text)
        job_info = config["job_requirements"][job_title]

        print("\n解析结果：")
        print(f"职位名称：{job_title}")
        print(f"最低经验：{job_info['min_exp']}年")
        print(f"最低学历：{job_info['edu']}")
        print(f"技能要求（软性，用于评分）：{[k.get('name', k) if isinstance(k, dict) else k for k in job_info['keywords']]}")
        print(f"必要条件（硬性）：{job_info.get('required_conditions', [])}")
        print(f"技术条件（OR 检查）：{job_info.get('tech_conditions', [])}")

        save_config(config)

        print("\n提示：配置文件已生成，运行 bossmaster.py 时将自动使用")

    except Exception as e:
        print(f"解析出错：{e}")
        import traceback
        print(traceback.format_exc())


if __name__ == "__main__":
    main()
