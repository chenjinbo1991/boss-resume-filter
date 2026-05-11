"""
BOSS 直聘候选人智能提取工具 v3.0
支持 Excel 导出
"""
import time
import json
import re
from datetime import datetime
from DrissionPage import ChromiumPage
import os

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("警告：pandas 未安装，Excel 导出功能将不可用")
    print("安装命令：pip install pandas openpyxl")

try:
    from openpyxl.styles import PatternFill
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


def load_job_config():
    """从外部配置文件加载职位要求（支持多岗位）
    返回：(job_requirements, default_rule)
        - job_requirements: 各岗位的配置（不包含 default）
        - default_rule: 默认过滤规则
    """
    config_file = "job_config.json"
    default_rule = None

    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

                # 支持新旧两种格式
                if "jobs" in config:
                    job_requirements = config["jobs"]
                else:
                    job_requirements = config.get("job_requirements", {})

                # 提取 default 作为默认规则（如果存在）
                if "default" in job_requirements:
                    default_rule = job_requirements.pop("default")

                # 处理岗位名称去空格 + keywords 去重
                new_job_requirements = {}
                for job_name, rule in job_requirements.items():
                    # 岗位名称去除空格
                    clean_job_name = job_name.replace(" ", "")

                    if isinstance(rule, dict) and rule.get('keywords'):
                        seen = set()
                        unique_keywords = []
                        for kw in rule['keywords']:
                            # 支持两种格式：字符串 或 {"name": xxx, "weight": xxx}
                            if isinstance(kw, dict):
                                kw_lower = kw.get('name', '').lower()
                            else:
                                kw_lower = kw.lower()
                            if kw_lower not in seen:
                                seen.add(kw_lower)
                                unique_keywords.append(kw)
                        rule['keywords'] = unique_keywords

                    new_job_requirements[clean_job_name] = rule

                job_requirements = new_job_requirements

                return job_requirements, default_rule
        except Exception as e:
            print(f"读取配置文件出错：{e}")

    print("未找到配置文件，使用默认配置...")
    return {
        "default": {
            "min_exp": 0,
            "edu": "不限",
            "keywords": []
        }
    }, None


JOB_RULES = load_job_config()


def extract_summary_info(text):
    """从候选人摘要中提取结构化信息"""
    info = {
        'salary': '',
        'age': '',
        'exp_years': '',
        'education': '',
        'job_status': '',
        'company': '',
        'city': '',
        'skills': ''
    }

    if not text:
        return info

    lines = text.split('\n')

    # 薪资（第一行通常包含薪资）
    salary_match = re.search(r'(\d+-?\d*)[Kk 千]', lines[0] if lines else '')
    if salary_match:
        info['salary'] = salary_match.group(1) + 'K'

    # 年龄
    age_match = re.search(r'(\d+) 岁', text)
    if age_match:
        info['age'] = age_match.group(1)

    # 工作经验年限
    exp_match = re.search(r'(\d+)\s*年', text)
    if exp_match:
        info['exp_years'] = exp_match.group(1)

    # 学历
    edu_keywords = ['博士', '硕士', '本科', '大专', '高中', '中专']
    for edu in edu_keywords:
        if edu in text:
            info['education'] = edu
            break

    # 求职状态和公司
    status_match = re.search(r'(离职 | 在职 | 在校 | 应届) - ([^\n]+)', text)
    if status_match:
        info['job_status'] = status_match.group(1)
        info['company'] = status_match.group(2).strip()

    # 城市
    city_match = re.search(r'(?:意向？|城市 | 地点)[:：\s]*([一 - 龥]{2,4})', text)
    if city_match:
        info['city'] = city_match.group(1)
    else:
        city_patterns = ['南京', '上海', '北京', '深圳', '广州', '杭州', '苏州']
        for city in city_patterns:
            if city in text:
                info['city'] = city
                break

    # 技能关键词
    skill_keywords = ['Java', 'Python', 'MySQL', 'Oracle', 'Redis', 'Kafka',
                      'Spring', 'MyBatis', 'Dubbo', 'Vue', 'React', 'Linux',
                      'Docker', 'K8s', 'Kubernetes', 'AWS', 'Azure', 'Git']
    found_skills = [s for s in skill_keywords if s in text]
    info['skills'] = ', '.join(found_skills)

    return info


def export_to_excel(candidates, filename):
    """将候选人数据导出为 Excel - 增强版

    功能：
        - 按匹配分从高到低排序
        - 按岗位分工作表
        - 统计摘要工作表
        - 颜色标识推荐指数和打招呼状态
        - 自动筛选和冻结窗格
    """
    if not PANDAS_AVAILABLE:
        return False

    try:
        # 按匹配分从高到低排序
        sorted_candidates = sorted(candidates, key=lambda x: x.get('match_score', 0), reverse=True)

        data = []
        for i, c in enumerate(sorted_candidates):
            score = c.get('match_score', 0)
            # 根据匹配分计算推荐指数
            if score >= 75:
                recommend_level = "强烈推荐"
            elif score >= 60:
                recommend_level = "推荐"
            else:
                recommend_level = "待定"

            summary_info = extract_summary_info(c.get('summary', ''))
            row = {
                '序号': i + 1,
                '岗位': c.get('job_name', ''),  # 新增岗位字段
                '姓名': c.get('name', '未知'),
                '匹配分': score,
                '推荐指数': recommend_level,
                '是否打招呼': '是' if c.get('greet_sent', False) else '否',
                '技能匹配': c.get('skill_match_ratio', ''),
                '薪资': summary_info['salary'],
                '年龄': summary_info['age'],
                '工作年限': summary_info['exp_years'],
                '学历': summary_info['education'],
                '求职状态': summary_info['job_status'],
                '公司': summary_info['company'],
                '城市': summary_info['city'],
                '技能': summary_info['skills'],
                'geek_id': c.get('geek_id', ''),
                '批次': c.get('batch_timestamp', ''),  # 新增批次字段
                '详细信息': c.get('summary', '')[:200]
            }
            data.append(row)

        df = pd.DataFrame(data)

        # 列顺序调整：岗位提前
        columns = ['序号', '岗位', '姓名', '匹配分', '推荐指数', '是否打招呼', '技能匹配', '薪资', '年龄',
                   '工作年限', '学历', '求职状态', '公司', '城市', '技能', 'geek_id', '批次', '详细信息']
        df = df[[col for col in columns if col in df.columns]]

        # 使用 ExcelWriter 创建多工作表
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # 主工作表：所有候选人
            df.to_excel(writer, index=False, sheet_name='全部候选人')

            # 按岗位分工作表
            if '岗位' in df.columns:
                for job_name in df['岗位'].drop_duplicates():
                    job_df = df[df['岗位'] == job_name].copy()
                    # 重新编号
                    job_df['序号'] = range(1, len(job_df) + 1)
                    # Excel 工作表名不允许: \ / * ? [ ] :
                    sheet_name = job_name.translate(str.maketrans({
                        '\\': '-', '/': '-', '*': '-', '?': '-',
                        '[': '(', ']': ')', ':': '-'
                    }))[:31]
                    job_df.to_excel(writer, index=False, sheet_name=sheet_name)

            # 统计摘要工作表
            summary_data = []
            if '岗位' in df.columns:
                for job_name in df['岗位'].drop_duplicates():
                    job_df = df[df['岗位'] == job_name]
                    total = len(job_df)
                    strong_recommend = len(job_df[job_df['推荐指数'] == '强烈推荐'])
                    recommend = len(job_df[job_df['推荐指数'] == '推荐'])
                    pending = len(job_df[job_df['推荐指数'] == '待定'])
                    greeted = len(job_df[job_df['是否打招呼'] == '是'])
                    avg_score = job_df['匹配分'].mean() if '匹配分' in job_df.columns else 0

                    summary_data.append({
                        '岗位': job_name,
                        '总人数': total,
                        '强烈推荐': strong_recommend,
                        '推荐': recommend,
                        '待定': pending,
                        '已打招呼': greeted,
                        '平均分': f"{avg_score:.1f}"
                    })

            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, index=False, sheet_name='统计摘要')

        # 格式化所有工作表
        from openpyxl import load_workbook
        wb = load_workbook(filename)

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]

            # 设置列宽
            column_widths = {
                'A': 6, 'B': 20, 'C': 10, 'D': 10, 'E': 10, 'F': 12, 'G': 12,
                'H': 10, 'I': 6, 'J': 10, 'K': 10, 'L': 12, 'M': 20, 'N': 10,
                'O': 30, 'P': 15, 'Q': 10, 'R': 80
            }
            for col, width in column_widths.items():
                if col in ws.column_dimensions:
                    ws.column_dimensions[col].width = width

            # 冻结首行（标题行）
            ws.freeze_panes = 'A2'

            # 启用自动筛选
            ws.auto_filter.ref = ws.dimensions

            # 为推荐指数列添加颜色标识（E 列）
            if OPENPYXL_AVAILABLE:
                for row_idx, cell in enumerate(ws['E'], start=2):
                    if cell.value == "强烈推荐":
                        cell.fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")
                    elif cell.value == "推荐":
                        cell.fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
                    elif cell.value == "待定":
                        cell.fill = PatternFill(start_color="FFB6C1", end_color="FFB6C1", fill_type="solid")

                # 为"是否打招呼"列添加颜色标识（F 列）
                for row_idx, cell in enumerate(ws['F'], start=2):
                    if cell.value == "是":
                        cell.fill = PatternFill(start_color="90EE90", end_color="90EE90", fill_type="solid")

        wb.save(filename)
        return True
    except Exception as e:
        print(f"Excel 导出失败：{e}")
        return False


def parse_experience_years(text):
    """
    从文本中解析工作年限，支持中文数字
    支持格式：3 年、三年、3 年经验、三年以上、10 年以上、十二年
    返回：int 或 None
    """
    # 中文数字映射
    chinese_numerals = {
        '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
    }

    # 清理文本中的空格
    text = text.replace(' ', '')

    # 尝试匹配阿拉伯数字格式：(\d+)\s*年
    arabic_match = re.search(r'(\d+)\s*年', text)
    if arabic_match:
        return int(arabic_match.group(1))

    # 尝试匹配中文数字格式
    # 支持：十二年、十年以上、三年以上、近两年等
    chinese_match = re.search(r'([零一二三四五六七八九十两]+(?:十[一二三四五六七八九两]?)?)\s*年', text)
    if chinese_match:
        chinese_num = chinese_match.group(1)

        # 处理特殊格式
        if chinese_num == '十':
            return 10
        elif chinese_num.startswith('十') and len(chinese_num) > 1:
            # 十二、十三等
            return 10 + chinese_numerals.get(chinese_num[1], 0)
        elif chinese_num.endswith('十') and len(chinese_num) > 1:
            # 二十、三十等
            return chinese_numerals.get(chinese_num[0], 0) * 10
        elif len(chinese_num) == 2:
            # 十二、二十三等简式
            first = chinese_numerals.get(chinese_num[0], 0)
            second = chinese_numerals.get(chinese_num[1], 0)
            if first >= 2 and first <= 9:
                return first * 10 + second
            else:
                return first + second
        elif chinese_num in chinese_numerals:
            return chinese_numerals[chinese_num]

        # 逐字转换（备用）
        result = 0
        for char in chinese_num:
            if char in chinese_numerals:
                result += chinese_numerals[char]
        if result > 0:
            return result

    return None


def _keyword_found(text, keyword):
    """检查关键词是否在文本中作为独立词出现，避免子串误匹配（如 AI 匹配 email）"""
    # 中文关键词用子串匹配（中文不存在子串误匹配问题）
    if any('一' <= c <= '鿿' for c in keyword):
        return keyword.lower() in text.lower()
    # 英文/数字关键词用单词边界匹配
    try:
        return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE))
    except re.error:
        return keyword.lower() in text.lower()


def _calc_edu_bonus(text):
    """计算学历加分（0~15）"""
    bonus = 0
    has_985211 = any(mark in text for mark in ['985', '211', '双一流'])
    is_doctor = '博士' in text
    is_master = '硕士' in text
    is_bachelor = '本科' in text

    if is_doctor:
        bonus = 15
    elif is_master:
        bonus = 13 if has_985211 else 10
    elif is_bachelor:
        bonus = 8 if has_985211 else 5

    return bonus


def filter_candidate(candidate_text, rule):
    """
    候选人筛选逻辑 - 返回评分结果
    返回：(passed, score, details)
        - passed: 是否通过硬性条件
        - score: 匹配得分（0-100）
        - details: 详细信息

    筛选规则说明：
    - 四维评分模型: 基础30 + 技能(0~35) + 经验超额(0~20) + 学历档次(0~15)
    - 推荐等级: >=75强烈推荐, >=60推荐, >=45待定
    - min_exp: 最低工作年限要求（门限），超额部分每年+4分，20分封顶
    - edu: 最低学历要求（门限），985/211/硕士额外加分
    - keywords: 技能关键词，按权重加权计分，英文词用\b边界避免子串误匹配
    - required_conditions: 必要条件列表，支持 OR/AND 组合规则
    """
    try:
        # 四维评分模型: 基础分30 + 技能分(0~35) + 经验加分(0~20) + 学历加分(0~15)
        SKILL_MAX = 35
        EXP_MAX = 20

        details = {
            'exp_matched': True,
            'edu_matched': True,
            'required_conditions_matched': True,
            'tech_matched': True,
            'skill_matches': [],
            'skill_total': 0,
            'skill_matched_count': 0,
            'exp_bonus': 0,
            'edu_bonus': 0
        }

        # === 硬性条件检查 ===

        # 1. 工作经验（门限 + 超额加分）
        min_exp = rule.get("min_exp", 0)
        exp_years = None
        if min_exp > 0:
            exp_years = parse_experience_years(candidate_text)
            if exp_years is not None:
                if min_exp > exp_years:
                    return False, 0, {"reason": f"经验不足：要求{min_exp}年，实际{exp_years}年"}
                # 超额加分：超出部分每年+4，20分封顶
                details['exp_bonus'] = min((exp_years - min_exp) * 4, EXP_MAX)
            # 找不到经验不再淘汰，仅不加分

        # 2. 学历（门限 + 额外加分）
        edu_bonus = 0
        if rule.get("edu", "不限") != "不限":
            edu_keywords = {"博士": 6, "硕士": 5, "本科": 4, "大专": 3, "高中": 2, "中专": 1}
            candidate_edu_level = max([edu_keywords.get(word, 0) for word in edu_keywords if word in candidate_text])
            required_edu = edu_keywords.get(rule.get("edu", "不限"), 0)

            if rule.get("edu") == "本科":
                non_regular = ["自考", "成教", "函授", "夜大", "网络教育", "继续教育", "非统招"]
                if candidate_edu_level >= 5:
                    pass  # 硕士及以上直接通过
                elif candidate_edu_level == 4:
                    is_non_regular = any(ne in candidate_text for ne in non_regular)
                    if is_non_regular:
                        if "985" in candidate_text or "211" in candidate_text or "统招" in candidate_text:
                            pass
                        else:
                            return False, 0, {"reason": "学历不符：要求统招本科"}
                else:
                    return False, 0, {"reason": "学历不足：要求本科"}
            elif required_edu > 0 and candidate_edu_level < required_edu:
                return False, 0, {"reason": f"学历不足：要求{rule.get('edu')}，实际未达要求"}

            edu_bonus = _calc_edu_bonus(candidate_text)
        details['edu_bonus'] = edu_bonus

        # 3. 必要条件
        required_conditions = rule.get("required_conditions", [])
        for condition in required_conditions:
            cond_result = check_required_condition(candidate_text, condition)
            if not cond_result['passed']:
                return False, 0, {"reason": cond_result['reason']}
        details['required_conditions_matched'] = True

        # 4. 技术关键词（旧格式兼容）
        tech_keywords_or = rule.get("tech_conditions", [])
        if tech_keywords_or:
            tech_found = any(tech.lower() in candidate_text.lower() for tech in tech_keywords_or)
            if not tech_found:
                return False, 0, {"reason": f"技术不匹配：需要{tech_keywords_or}中至少一项"}
        details['tech_matched'] = True

        # === 技能评分（用 word-boundary 匹配避免子串误匹配）===
        keywords = rule.get("keywords", [])
        skill_score = 0
        total_possible_weight = 0
        matched_skills = []

        if keywords:
            for keyword in keywords:
                if isinstance(keyword, dict):
                    kw_name = keyword.get("name", "")
                    kw_weight = keyword.get("weight", 1)
                else:
                    kw_name = keyword
                    kw_weight = 1

                total_possible_weight += kw_weight
                if _keyword_found(candidate_text, kw_name):
                    matched_skills.append(kw_name)
                    skill_score += kw_weight

            details['skill_matched_count'] = len(matched_skills)
            details['skill_matches'] = matched_skills
            details['skill_total'] = total_possible_weight

        # === 四维总分 ===
        if total_possible_weight > 0:
            skill_score_normalized = int((skill_score / total_possible_weight) * SKILL_MAX)
        else:
            skill_score_normalized = SKILL_MAX

        score = 30 + skill_score_normalized + details['exp_bonus'] + details['edu_bonus']
        return True, score, details

    except Exception as e:
        return False, 0, {"reason": f"筛选异常: {str(e)[:50]}"}


def check_required_condition(candidate_text, condition):
    """
    检查单个必要条件

    Args:
        candidate_text: 候选人摘要文本
        condition: 条件，支持三种格式：
            - 字符串："统招本科" -> 直接匹配（985/211 视为统招）
            - dict with type="or": {"type": "or", "items": ["activiti", "camunda"]} -> 至少满足一项
            - dict with type="and": {"type": "and", "items": ["Java", "Spring"]} -> 全部满足

    Returns:
        dict: {"passed": bool, "reason": str}
    """
    if isinstance(condition, str):
        # 字符串形式的必要条件
        # 特殊处理：统招本科 - 985/211 视为统招
        if condition == "统招本科":
            # 硕士/博士自动满足（已具备本科学历）
            if "硕士" in candidate_text or "博士" in candidate_text:
                return {"passed": True, "reason": ""}
            has_regular = "统招" in candidate_text or "985" in candidate_text or "211" in candidate_text
            has_bachelor = "本科" in candidate_text
            if has_regular and has_bachelor:
                return {"passed": True, "reason": ""}
            # 检查是否明确是非统招
            non_regular = ["自考", "成教", "函授", "夜大", "网络教育", "继续教育", "非统招"]
            if any(ne in candidate_text for ne in non_regular):
                return {"passed": False, "reason": f"必要条件不满足：{condition}（非统招）"}
            # 如果没有统招标记但有本科，也视为通过（宽松匹配）
            if has_bachelor:
                return {"passed": True, "reason": ""}
            return {"passed": False, "reason": f"必要条件不满足：{condition}"}

        if condition not in candidate_text:
            return {"passed": False, "reason": f"必要条件不满足：{condition}"}
        return {"passed": True, "reason": ""}

    elif isinstance(condition, dict):
        cond_type = condition.get("type", "or")
        items = condition.get("items", [])

        if not items:
            return {"passed": True, "reason": ""}

        if cond_type == "or":
            # OR 匹配：至少满足一项
            matched = any(item.lower() in candidate_text.lower() for item in items)
            if not matched:
                return {"passed": False, "reason": f"必要条件不满足：需要{items}中至少一项"}
            return {"passed": True, "reason": ""}

        elif cond_type == "and":
            # AND 匹配：全部满足
            for item in items:
                if item.lower() not in candidate_text.lower():
                    return {"passed": False, "reason": f"必要条件不满足：缺少{item}"}
            return {"passed": True, "reason": ""}

    return {"passed": True, "reason": ""}


def evaluate_candidate(candidate_text, rule):
    """候选人筛选逻辑（兼容旧版本，返回 True/False）"""
    passed, score, details = filter_candidate(candidate_text, rule)
    return passed


def get_iframe(page):
    """获取包含推荐列表的 iframe"""
    try:
        frames = page.eles('tag:iframe')
        for frame in frames:
            src = frame.attr('src') or ''
            if 'recommend' in src.lower():
                return frame
        if frames:
            return frames[0]
    except Exception as e:
        print(f"获取 iframe 失败：{e}")
    return None


def extract_name_from_card(card_element):
    """从候选人卡片中提取姓名"""
    try:
        # 方法 1: 查找 class=name 的独立元素
        name_elements = card_element.eles('xpath:.//*[contains(@class, "name") and not(contains(@class, "wrap"))]')
        if name_elements:
            for ne in name_elements:
                text = ne.text.strip() if ne.text else ""
                # 验证是否是有效的中文姓名（2-4 个汉字）
                if text and len(text) >= 2 and len(text) <= 4:
                    # 检查是否都是汉字
                    if all('一' <= c <= '鿿' for c in text):
                        return text

        # 方法 2: 从 col-2 元素的第一行提取（姓名通常在开头）
        col2_elements = card_element.eles('xpath:.//*[contains(@class, "col-2")]')
        if col2_elements:
            col2_text = col2_elements[0].text.strip() if col2_elements[0].text else ""
            if col2_text:
                # 第一行可能包含姓名和职位
                first_line = col2_text.split('\n')[0].strip()
                # 提取开头 2-4 个汉字
                if len(first_line) >= 2:
                    potential_name = ""
                    for c in first_line:
                        if '一' <= c <= '鿿':
                            potential_name += c
                            if len(potential_name) > 4:
                                break
                        else:
                            break

                    if 2 <= len(potential_name) <= 4:
                        invalid_names = ['推荐', '位置', '面议', '优势', '推荐牛人', '编组',
                                       '备份', '立即', '沟通', '聊天', '联系', '在线',
                                       '今日', '最近', '邀请', '投递', '刷新', '收藏',
                                       '点赞', '分享', '高级', '资深', '初级', '中级',
                                       '离职', '在职', '看看', '沟通', '职位']
                        if potential_name not in invalid_names:
                            return potential_name

    except Exception as e:
        pass

    return "未知"


def scroll_in_frame(frame, scroll_amount=800):
    """在 iframe 内部滚动"""
    try:
        frame.run_js(f'window.scrollBy(0, {scroll_amount})')
        return True
    except Exception as e:
        print(f"iframe 滚动失败：{e}")
        return False


def get_frame_scroll_info(frame):
    """获取 iframe 内部的滚动信息"""
    try:
        scroll_top = frame.run_js('return document.documentElement.scrollTop || document.body.scrollTop || 0')
        scroll_height = frame.run_js('return document.documentElement.scrollHeight || document.body.scrollHeight || 0')
        client_height = frame.run_js('return window.innerHeight || document.documentElement.clientHeight || 0')
        return {
            'scrollTop': scroll_top,
            'scrollHeight': scroll_height,
            'clientHeight': client_height,
            'atBottom': scroll_top + client_height >= scroll_height - 50
        }
    except Exception as e:
        print(f"获取滚动信息失败：{e}")
        return None


def load_candidates_all():
    """加载 candidates_all.json 中的已有候选人"""
    all_file = "candidates_all.json"
    if os.path.exists(all_file):
        try:
            with open(all_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"加载候选人数据失败：{e}")
    return []


def get_greeted_geek_ids(candidates_all):
    """从 candidates_all 中提取已打招呼的 geek_id 集合"""
    return set(c['geek_id'] for c in candidates_all if c.get('greet_sent') is True)




def save_candidates_all(candidates_all):
    """保存 candidates_all.json（覆盖旧文件）- 支持去重和中断恢复

    去重规则：
        - 基于 geek_id 去重
        - 保留分数高的记录
        - 合并打招呼状态
        - 清理 greeting_in_progress 标记（如果已保存成功）
    """
    all_file = "candidates_all.json"

    # 去重：基于 geek_id，保留最新记录（分数高的）- O(n) 优化
    seen_geek_ids = {}

    for c in candidates_all:
        geek_id = c.get('geek_id')
        if geek_id:
            if geek_id not in seen_geek_ids:
                seen_geek_ids[geek_id] = c
            else:
                # 如果新记录分数更高或打过招呼，更新
                old_c = seen_geek_ids[geek_id]
                if c.get('match_score', 0) > old_c.get('match_score', 0) or c.get('greet_sent', False):
                    # 合并数据：保留打招呼状态
                    if old_c.get('greet_sent', False) and not c.get('greet_sent', False):
                        c['greet_sent'] = True
                    # 保留 greeting_in_progress 标记
                    if old_c.get('greeting_in_progress', False):
                        c['greeting_in_progress'] = True
                    seen_geek_ids[geek_id] = c

    # 直接从字典生成列表（避免 O(n²) 的列表查找）
    unique_candidates = list(seen_geek_ids.values())

    # 清理 completed 的 greeting_in_progress 标记（已打过招呼的不再需要标记）
    for c in unique_candidates:
        if c.get('greeting_in_progress') and c.get('greet_sent'):
            del c['greeting_in_progress']

    with open(all_file, 'w', encoding='utf-8') as f:
        json.dump(unique_candidates, f, ensure_ascii=False, indent=2)
    print(f"已更新 {all_file} (共 {len(unique_candidates)} 个唯一候选人)")


def is_already_greeted(candidates_all, geek_id):
    """检查是否已打过招呼"""
    for c in candidates_all:
        if c.get('geek_id') == geek_id and c.get('greet_sent') is True:
            return True
    return False


def extract_candidates_by_comprehensive_analysis(page, existing_ids=None, max_rounds=30):
    """通过全面分析提取候选人

    Args:
        page: 页面对象
        existing_ids: 已存在的候选人 ID 集合
        max_rounds: 最大滚动轮次（默认 30）
    """
    print("正在提取候选人...")
    time.sleep(1.0)

    iframe = get_iframe(page)

    all_candidates = []
    seen_geek_ids = set()
    target = iframe if iframe else page
    consecutive_empty = 0

    for scroll_round in range(max_rounds):
        # 每轮先检测是否已到底（文本提示）
        if scroll_round > 0:
            bottom_hint = None
            try:
                bottom_hint = target.ele('@text():到底', timeout=0.3)
                if not bottom_hint:
                    bottom_hint = target.ele('@text():没有更多', timeout=0.3)
            except Exception:
                pass
            if bottom_hint:
                print(f"检测到'到底'提示，第 {scroll_round} 轮提前终止（累计 {len(all_candidates)} 个候选人）")
                break

        # 先滚动，再收集数据（除了第一轮）
        if scroll_round > 0:
            if iframe:
                scroll_in_frame(iframe, 600)
                time.sleep(0.4)
                scroll_in_frame(iframe, 200)
                time.sleep(0.2)
            else:
                page.run_js('window.scrollBy(0, 800)')
                time.sleep(0.4)

        # 收集候选人
        candidates_in_round = []
        current_round_ids = set()

        try:
            all_elements = target.eles('xpath://*[@data-geekid]')
            for element in all_elements:
                geek_id = element.attr('data-geekid')
                if not geek_id or geek_id in seen_geek_ids or geek_id in current_round_ids:
                    continue

                current_round_ids.add(geek_id)

                text = element.text.strip() if element.text else ""
                if len(text) < 30:
                    continue

                has_candidate_info = (
                    '经验' in text or '本科' in text or '硕士' in text or
                    'Java' in text or '开发' in text or '工程师' in text or
                    re.search(r'\d+年', text) or re.search(r'\d+岁', text)
                )
                if not has_candidate_info:
                    continue

                name = extract_name_from_card(element)
                candidates_in_round.append({'geek_id': geek_id, 'name': name, 'summary': text})

        except Exception as e:
            print(f"提取候选人元素失败(轮次{scroll_round + 1}): {e}")

        # 更新累计
        for c in candidates_in_round:
            all_candidates.append(c)
            seen_geek_ids.add(c['geek_id'])

        new_count = len(candidates_in_round)
        total_count = len(all_candidates)

        # 连续空轮次检测（兜底策略，不依赖特定文案）
        if new_count == 0:
            consecutive_empty += 1
            if consecutive_empty >= 5:
                print(f"连续 {consecutive_empty} 轮无新候选人，第 {scroll_round + 1} 轮提前终止（累计 {total_count} 个候选人）")
                break
        else:
            consecutive_empty = 0

        # 每 10 轮或最后一轮打印进度
        if (scroll_round + 1) % 10 == 0 or (scroll_round + 1) == max_rounds:
            status = f"+{new_count}" if new_count > 0 else "无新增"
            print(f"轮次 {scroll_round + 1}/{max_rounds}: {status}, 累计 {total_count} 个")

    print(f"\n=== 提取完成 ===")
    print(f"总共找到 {len(all_candidates)} 个候选人")
    return all_candidates


def send_greeting_on_list_page(page, geek_id, retry=0):
    """
    在列表页直接向候选人打招呼（XPath 优化版）
    返回：(是否成功，消息)
    """
    try:
        # 1. 滚动回顶部
        page.run_js('window.scrollTo(0, 0)')
        time.sleep(0.2)

        # 2. 获取 iframe
        iframe = get_iframe(page)
        target = iframe if iframe else page

        # 3. 查找候选人卡片
        card = target.ele('xpath://*[@data-geekid="{}"]'.format(geek_id))
        if not card:
            time.sleep(0.2)
            card = target.ele('xpath://*[@data-geekid="{}"]'.format(geek_id))

        if not card:
            return False, "未找到卡片"

        parent = card.parent()

        # 4. 查找按钮 - 精确匹配优先，模糊匹配备用
        greet_btn = None
        if parent:
            for btn_text in ['继续沟通', '立即沟通', '打招呼']:
                greet_btn = parent.ele('xpath:.//*[text()="{}"]'.format(btn_text))
                if greet_btn:
                    break
            if not greet_btn:
                for btn_text in ['继续沟通', '立即沟通', '打招呼']:
                    greet_btn = parent.ele('xpath:.//*[contains(text(), "{}")]'.format(btn_text))
                    if greet_btn:
                        break

        if not greet_btn:
            return False, "未找到按钮"

        # 5. 点击按钮
        try:
            greet_btn.click()
        except Exception:
            greet_btn.run_js('this.click()')

        # 6. 等待
        time.sleep(0.2)

        return True, "成功"

    except Exception as e:
        return False, f"异常: {str(e)[:50]}"



def verify_greeting_success(page, geek_id, debug=False):
    """
    验证打招呼是否成功（快速版 - 直接检查按钮文本）
    """
    try:
        # 直接查找该候选人的"继续沟通"或"已沟通"标记
        # 使用更精确的 XPath，减少查询范围
        cards = page.eles(f'xpath://*[@data-geekid="{geek_id}"]')
        if not cards:
            return True, "点击已执行"
        
        parent = cards[0].parent()
        if not parent:
            return True, "点击已执行"
        
        # 直接获取父元素下所有文本节点，一次查询
        all_text = parent.text
        
        # 检查是否包含成功标记
        if '已沟通' in all_text or '沟通过' in all_text or '已发送' in all_text:
            return True, "找到成功标记"
        
        if '继续沟通' in all_text:
            return True, "按钮为'继续沟通'"
        
        # 默认成功
        return True, "点击已执行"

    except Exception:
        return True, "点击已执行"

def smart_scan_candidates(page, job_info, auto_greet=False, max_rounds=30, verbose=False, greet_level='normal', greet_names_list=None, list_candidates=False):
    """
    智能扫描候选人 - 两阶段模式

    阶段 1: 滚动收集所有候选人并筛选（不打招呼）
    阶段 2: 按分数从高到低依次打招呼

    Args:
        page: 浏览器页面对象
        job_info: 岗位信息
        auto_greet: 是否自动打招呼
        max_rounds: 最大滚动轮次
        verbose: 是否输出详细评分信息
        greet_level: 打招呼等级 'strong'=仅强烈推荐，'normal'=强烈推荐 + 推荐
        greet_names_list: 点对点打招呼的姓名列表（如果指定，只给这些候选人打招呼）
        list_candidates: 是否仅列出候选人，不打招呼
    """
    job_name = job_info['job_name']

    # 确定打招呼等级的显示和筛选逻辑
    if greet_level == 'strong':
        greet_levels_allowed = ['强烈推荐']
        greet_level_text = '仅强烈推荐'
    else:
        greet_levels_allowed = ['强烈推荐', '推荐']
        greet_level_text = '强烈推荐 + 推荐'

    # 点对点模式
    point_to_point_mode = bool(greet_names_list)

    if point_to_point_mode:
        print(f"开始智能扫描候选人... (岗位：{job_name}, 点对点打招呼：{greet_names_list}, 轮次：{max_rounds})")
    else:
        print(f"开始智能扫描候选人... (岗位：{job_name}, 自动打招呼：{'是 (' + greet_level_text + ')' if auto_greet else '否'}, 轮次：{max_rounds})")

    # 加载 candidates_all.json，检查已打招呼的候选人
    candidates_all = load_candidates_all()
    greeted_geek_ids = get_greeted_geek_ids(candidates_all)

    # 从 candidates_all 中获取已匹配的 ID（按岗位过滤）
    existing_ids_for_job_and_greeted = set()  # 当前岗位已匹配且打过招呼的 ID（需要过滤）
    all_existing_ids = set()  # 所有岗位已匹配的 ID
    if candidates_all:
        for c in candidates_all:
            all_existing_ids.add(c['geek_id'])
            if c.get('job_name') == job_name and c.get('greet_sent') is True:
                existing_ids_for_job_and_greeted.add(c['geek_id'])

        print(f"已加载 candidates_all.json：累计 {len(all_existing_ids)} 个候选人，{len(greeted_geek_ids)} 人已打招呼")

    # === 阶段 1: 滚动收集所有候选人 ===
    raw_candidates = extract_candidates_by_comprehensive_analysis(page, existing_ids_for_job_and_greeted, max_rounds=max_rounds)
    print(f"原始提取到 {len(raw_candidates)} 个唯一候选人")

    # 过滤当前岗位已匹配且打过招呼的候选人
    if existing_ids_for_job_and_greeted:
        before_count = len(raw_candidates)
        raw_candidates = [c for c in raw_candidates if c['geek_id'] not in existing_ids_for_job_and_greeted]
        print(f"过滤当前岗位已匹配且打过招呼的候选人：{before_count} -> {len(raw_candidates)} (新增 {len(raw_candidates)} 个)")

    # 筛选所有候选人（暂不打招呼）
    print("\n=== 阶段 1: 筛选候选人 ===")
    passed_candidates = []  # 通过筛选的候选人（含分数）
    failed_reasons = {}

    for i, candidate in enumerate(raw_candidates):
        passed, score, details = filter_candidate(candidate['summary'], job_info['rule'])
        if passed:
            # 计算推荐等级
            if score >= 75:
                recommend_level = "强烈推荐"
            elif score >= 60:
                recommend_level = "推荐"
            else:
                recommend_level = "待定"

            candidate_record = {
                "geek_id": candidate['geek_id'],
                "name": candidate['name'],
                "summary": candidate['summary'],
                "job_id": job_info['job_id'],
                "job_name": job_name.replace(" ", ""),  # 去除岗位名称中的空格
                "match_rule": job_info['rule_key'],
                "match_score": score,
                "skill_matches": details.get('skill_matches', []),
                "skill_match_ratio": f"{details.get('skill_matched_count', 0)}/{details.get('skill_total', 0)}",
                "recommend_level": recommend_level,
                "batch_timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "greet_sent": False
            }
            passed_candidates.append(candidate_record)

            if verbose:
                print(f"  [{i+1}/{len(raw_candidates)}] {candidate['name']} - {score}分 ({recommend_level})")
        else:
            reason = details.get('reason', '未知')
            failed_reasons[reason] = failed_reasons.get(reason, 0) + 1

        if (i + 1) % 20 == 0:
            print(f"  已筛选 {i + 1}/{len(raw_candidates)} 个，通过 {len(passed_candidates)} 个")

    # 按分数从高到低排序
    passed_candidates.sort(key=lambda x: x.get('match_score', 0), reverse=True)

    print(f"\n筛选完成：通过 {len(passed_candidates)}/{len(raw_candidates)} 个")
    if failed_reasons:
        print(f"淘汰原因:")
        for reason, count in sorted(failed_reasons.items(), key=lambda x: -x[1])[:5]:
            print(f"  - {reason}: {count} 人")

    # === 仅列出候选人，不打招呼 ===
    if list_candidates and passed_candidates:
        print("\n=== 候选人列表 ===")
        print(f"岗位：{job_name}")
        print(f"总人数：{len(passed_candidates)}")
        print(f"{'序号':<4} {'姓名':<10} {'匹配分':<8} {'推荐指数':<10} {'已打招呼':<8}")
        print("-" * 50)
        for i, c in enumerate(passed_candidates[:50], 1):  # 最多显示前 50 个
            print(f"{i:<4} {c['name']:<10} {c['match_score']:<8} {c['recommend_level']:<10} {'是' if c.get('greet_sent') else '否':<8}")
        if len(passed_candidates) > 50:
            print(f"... 还有 {len(passed_candidates) - 50} 个")
        return passed_candidates

    # === 阶段 2: 按分数从高到低依次打招呼 ===
    if auto_greet and passed_candidates:
        print("\n=== 阶段 2: 按分数排序打招呼 ===")
        print("正在刷新候选人列表...")

        # 先向下滚动再滚回顶部，强制触发懒加载重新加载所有卡片
        iframe = get_iframe(page)
        if iframe:
            # 在 iframe 内滚动
            iframe.run_js('window.scrollTo(0, 3000)')
            time.sleep(0.5)
            iframe.run_js('window.scrollTo(0, 0)')
            time.sleep(1.0)
        else:
            # 直接在页面滚动
            page.run_js('window.scrollTo(0, 800)')
            time.sleep(0.5)
            page.run_js('window.scrollTo(0, 0)')
            time.sleep(1.0)

        # 筛选需要打招呼的候选人
        if point_to_point_mode:
            # 点对点模式：只筛选指定姓名的候选人
            to_greet_list = [c for c in passed_candidates
                            if c.get('name') in greet_names_list]
            print(f"需要打招呼：{len(to_greet_list)} 人 (点对点)")
            if not to_greet_list:
                print(f"  未找到匹配的候选人，姓名列表：{greet_names_list}")
        else:
            # 自动模式：根据推荐等级筛选
            to_greet_list = [c for c in passed_candidates
                            if c.get('recommend_level') in greet_levels_allowed
                            and c.get('geek_id') not in existing_ids_for_job_and_greeted]
            print(f"需要打招呼：{len(to_greet_list)} 人 ({greet_level_text})")

        # 按分数排序
        to_greet_list.sort(key=lambda x: x.get('match_score', 0), reverse=True)

        greet_success_count = 0
        greet_fail_count = 0
        greeted_in_this_run = []
        consecutive_failures = 0  # 连续失败计数
        pending_save_count = 0  # 延迟保存计数

        try:
            for i, candidate in enumerate(to_greet_list):
                action = "补打招呼" if candidate['geek_id'] in all_existing_ids else "打招呼"

                # 检查连续失败，如果连续失败 3 次则停止
                if consecutive_failures >= 3:
                    print(f"\n⚠️  连续 {consecutive_failures} 次失败，停止打招呼")
                    break

                # 每个打招呼间隔 0.5 秒
                if i > 0:
                    time.sleep(0.5)

                print(f"  [{i+1}/{len(to_greet_list)}] {candidate['name']} ({candidate['recommend_level']}, {candidate['match_score']}分) {action}...", end=" ")

                success, msg = send_greeting_on_list_page(page, candidate['geek_id'])

                if success:
                    greet_success_count += 1
                    consecutive_failures = 0  # 重置连续失败计数
                    candidate['greet_sent'] = True
                    candidates_all.append(candidate)
                    greeted_in_this_run.append(candidate['geek_id'])
                    # 成功打招呼立即保存（防止中断丢失）
                    save_candidates_all(candidates_all)
                    print(f"OK")
                else:
                    greet_fail_count += 1
                    consecutive_failures += 1  # 累加连续失败计数
                    candidate['greet_sent'] = False
                    candidates_all.append(candidate)
                    # 失败招呼延迟保存，攒够 5 个再写文件
                    pending_save_count += 1
                    if pending_save_count >= 5:
                        save_candidates_all(candidates_all)
                        pending_save_count = 0
                    print(f"失败：{msg}")

        except KeyboardInterrupt:
            print(f"\n\n⚠️  检测到中断，保存当前进度...")
            # 中断时立即保存所有数据
            save_candidates_all(candidates_all)
            if greeted_in_this_run:
                print(f"  本次运行已打招呼 {len(greeted_in_this_run)} 人")
            print(f"✅ 候选人总数：{len(candidates_all)}")
            raise

        # 循环结束后，保存剩余未写入的数据
        if pending_save_count > 0:
            save_candidates_all(candidates_all)

        print(f"\n打招呼完成：成功 {greet_success_count} 人，失败 {greet_fail_count} 人")

    # 保存所有通过的候选人（包含未打招呼的）
    for c in passed_candidates:
        if not c.get('greet_sent'):
            # 检查是否已存在
            exists = False
            for existing in candidates_all:
                if existing.get('geek_id') == c.get('geek_id'):
                    exists = True
                    break
            if not exists:
                candidates_all.append(c)
    save_candidates_all(candidates_all)

    return passed_candidates


def run_smart_scan(args=None):
    """运行智能扫描（支持多岗位）

    参数：
        args: argparse.Namespace 对象，如果为 None 则从命令行解析
    """
    import argparse

    # 如果没有传入参数，从命令行解析
    if args is None:
        parser = argparse.ArgumentParser(description='BOSS 直聘候选人智能提取工具')
        parser.add_argument('--clear', action='store_true', help='清空 candidates_all.json 后全新跑')
        parser.add_argument('--job', type=str, help='指定岗位名称，只跑该岗位')
        parser.add_argument('--greet', action='store_true', help='自动打招呼：对新匹配的候选人自动发送消息')
        parser.add_argument('--re-greet', action='store_true', help='补打招呼：给已匹配但未打招呼的候选人发送消息')
        parser.add_argument('--greet-level', type=str, choices=['strong', 'normal'], default='normal',
                            help='打招呼等级（仅补打招呼模式有效）：strong=仅强烈推荐，normal=强烈推荐 + 推荐（默认）')
        parser.add_argument('--greet-names', type=str, help='点对点打招呼（仅补打招呼模式有效）：指定候选人姓名，多个用逗号分隔')
        parser.add_argument('--list-candidates', action='store_true', help='仅列出候选人，不打招呼')
        parser.add_argument('--rounds', type=int, default=30, help='最大滚动轮次（默认 30，推荐 20-40）')
        parser.add_argument('--verbose', action='store_true', help='输出详细评分信息（显示技能匹配详情）')
        args = parser.parse_args()

    # 确定运行模式
    re_greet_mode = args.re_greet
    point_to_point_mode = bool(args.greet_names) and re_greet_mode  # 点对点模式仅在补打招呼时生效

    # 初次扫描时的自动打招呼逻辑（--greet）
    auto_greet_scan = args.greet  # 初次扫描时对所有符合条件的打招呼

    # 补打招呼时的打招呼等级
    greet_levels_allowed = ['强烈推荐', '推荐']  # 默认
    greet_level_text = '强烈推荐 + 推荐'
    if re_greet_mode:
        if args.greet_level == 'strong':
            greet_levels_allowed = ['强烈推荐']
            greet_level_text = '仅强烈推荐'

    # 模式显示
    mode_text = "补打招呼模式" if re_greet_mode else ("全新模式" if args.clear else "增量模式")
    if point_to_point_mode:
        mode_text = f"点对点打招呼模式 ({args.greet_names})"
    greet_text = ""
    if auto_greet_scan:
        greet_level_display = "仅强烈推荐" if args.greet_level == 'strong' else "强烈推荐 + 推荐"
        greet_text = f" + 自动打招呼 ({greet_level_display})"
    elif re_greet_mode:
        greet_text = f" + 打招呼等级 ({greet_level_text})"
    print(f">>> BOSS 直聘候选人智能提取工具 v3.0 [{mode_text}{greet_text}]")
    print("="*50)

    # 清空 candidates_all.json（如果指定 --clear）
    if args.clear and os.path.exists("candidates_all.json"):
        os.remove("candidates_all.json")
        print("已清空 candidates_all.json")

    # 补打招呼模式：直接处理，不需要打开浏览器扫描
    if re_greet_mode:
        print(f"\n[补打招呼模式] 读取 candidates_all.json，给未打招呼的候选人发送消息...")
        print("="*50)

        # 读取已有数据
        candidates_all = load_candidates_all()
        if not candidates_all:
            print("candidates_all.json 为空或不存在")
        else:
            # 解析点对点打招呼的姓名列表
            greet_names_list = None
            if args.greet_names:
                greet_names_list = [name.strip() for name in args.greet_names.split(',')]
                print(f"点对点打招呼：{greet_names_list}")

            # 筛选需要打招呼的候选人
            if greet_names_list:
                # 点对点模式：只筛选指定姓名的候选人
                to_greet = [c for c in candidates_all
                           if c.get('name') in greet_names_list
                           and not c.get('greet_sent', False)]
                filter_text = f" (姓名匹配：{greet_names_list})"
            else:
                # 自动模式：根据推荐等级筛选
                to_greet = [c for c in candidates_all
                           if c.get('recommend_level') in greet_levels_allowed
                           and not c.get('greet_sent', False)]
                filter_text = f" ({greet_level_text})"

            if not to_greet:
                print(f"没有需要补打招呼的候选人{filter_text}")
            else:
                print(f"找到 {len(to_greet)} 个需要补打招呼的候选人{filter_text}:")
                for c in to_greet[:10]:
                    print(f"  - {c.get('name')} ({c.get('recommend_level')}, {c.get('match_score')}分)")
                if len(to_greet) > 10:
                    print(f"  ... 还有 {len(to_greet) - 10} 个")

                # 需要打开浏览器进行打招呼
                page = ChromiumPage()
                print("\n浏览器已打开，请手动导航到候选人推荐页面")
                print("等待 10 秒...")
                time.sleep(10)

                # 执行补打招呼
                success_count = 0
                fail_count = 0
                skip_count = 0

                try:
                    for i, c in enumerate(to_greet):
                        geek_id = c.get('geek_id')
                        name = c.get('name', '未知')
                        print(f"[{i+1}/{len(to_greet)}] 正在向 {name} 打招呼...", end=" ")
                        success, msg = send_greeting_on_list_page(page, geek_id)
                        if success:
                            # 检查是否真的成功（不是"可能需手动确认"）
                            if "可能需手动确认" in msg:
                                skip_count += 1
                                print(f"待确认：{msg}")
                            else:
                                success_count += 1
                                c['greet_sent'] = True
                                # 立即保存
                                save_candidates_all(candidates_all)
                                print("OK")
                        else:
                            fail_count += 1
                            print(f"失败：{msg}")

                except KeyboardInterrupt:
                    print(f"\n\n检测到中断，保存当前进度...")
                    save_candidates_all(candidates_all)
                    # 生成 Excel 文件
                    if export_to_excel(candidates_all, "candidates_all.xlsx"):
                        print(f"[SAVE] Excel 文件：candidates_all.xlsx")
                    print(f"已保存 {success_count} 个成功打招呼的候选人状态")
                    raise

                print(f"\n补打招呼完成：成功 {success_count} 人，失败 {fail_count} 人，待确认 {skip_count} 人")
                print(f"已更新 candidates_all.json")

        print("\n--- 浏览器保持打开 ---")
        return  # 补打招呼模式结束，直接返回

    page = None
    all_candidates = []  # 保存所有岗位的候选人

    try:
        print("正在连接到浏览器...")
        page = ChromiumPage()

        print("\n浏览器已打开，请手动导航到候选人推荐页面")
        print("例如：https://www.zhipin.com/web/chat/recommend")
        print("请确保页面完全加载后，等待 10 秒...")
        time.sleep(10)

        job_rules, default_rule = load_job_config()

        # 确定要运行的岗位列表
        jobs_to_run = []
        if args.job:
            if args.job in job_rules:
                jobs_to_run = [args.job]
            else:
                print(f"错误：未找到岗位 '{args.job}'")
                print(f"可用岗位：{', '.join(job_rules.keys())}")
                return
        else:
            jobs_to_run = list(job_rules.keys())

        print(f"\n将要运行 {len(jobs_to_run)} 个岗位：{', '.join(jobs_to_run)}")
        if default_rule:
            print(f"(另有 default 默认规则，不作为岗位运行)")
        print("="*50)

        # 逐个岗位处理
        for idx, job_name in enumerate(jobs_to_run, 1):
            print(f"\n{'='*50}")
            print(f">>> 处理岗位 {idx}/{len(jobs_to_run)}: {job_name}")
            print(f"{'='*50}")

            rule = job_rules[job_name]
            job_info = {
                "job_id": "unknown",
                "job_name": job_name,
                "rule": rule,
                "rule_key": job_name
            }

            print(f"过滤规则：经验≥{rule.get('min_exp', 0)}年，学历≥{rule.get('edu', '不限')}")
            print(f"Keywords: {[k.get('name', k) if isinstance(k, dict) else k for k in rule.get('keywords', [])][:5]}...")

            candidates = smart_scan_candidates(page, job_info, auto_greet=auto_greet_scan,
                                               max_rounds=args.rounds, verbose=args.verbose,
                                               greet_level=args.greet_level, greet_names_list=None,
                                               list_candidates=args.list_candidates)
            all_candidates.extend(candidates)
            # smart_scan_candidates 已经即时保存了，这里不需要重复保存

        # 最后生成 Excel 文件
        existing_all = load_candidates_all()
        excel_file = "candidates_all.xlsx"
        if export_to_excel(existing_all, excel_file):
            print(f"[SAVE] Excel 文件：{excel_file}")
        else:
            print("[WARN] Excel 导出失败")

    except KeyboardInterrupt:
        print(f"\n\n检测到中断，保存当前进度...")
        # 生成 Excel 文件
        existing_all = load_candidates_all()
        excel_file = "candidates_all.xlsx"
        if export_to_excel(existing_all, excel_file):
            print(f"[SAVE] Excel 文件：{excel_file}")
        print(f"已保存 {len(existing_all)} 个候选人的状态")
        raise

    except Exception as e:
        print(f"程序执行出错：{e}")
        import traceback
        print(traceback.format_exc())

    finally:
        if page:
            print("\n--- 浏览器保持打开 ---")


if __name__ == "__main__":
    run_smart_scan()
