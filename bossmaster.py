"""
BOSS 直聘候选人智能提取工具 v2.9.1
支持 Excel 导出
"""
from __future__ import annotations

import time
import json
import re
import random
import threading
from datetime import datetime
from typing import Any
from DrissionPage import ChromiumPage
import os
from filtering import (
    _calc_edu_bonus,
    _extract_city,
    _keyword_found,
    _parse_candidate_salary_range,
    check_required_condition,
    evaluate_candidate,
    filter_candidate,
    parse_experience_years,
)
from storage import (
    build_greeted_index,
    get_greeted_geek_ids,
    is_already_greeted,
    load_candidates_all,
    save_candidates_all,
)
from constants import (
    SCORE_THRESHOLD_PASS, SCORE_THRESHOLD_RECOMMEND, SCORE_THRESHOLD_STRONG,
    SCROLL_PX, MAX_SCROLL_SEARCH, MAX_ROUNDS_DEFAULT, EMPTY_ROUNDS_LIMIT,
    GREET_FAIL_LIMIT, CAPTCHA_MAX_WAIT, CAPTCHA_CHECK_INTERVAL,
)
from paths import BASE_DIR, SELECTORS_PATH, CONFIG_PATH, CANDIDATES_PATH, CANDIDATES_XLSX_PATH


class StopRequested(Exception):
    """停止请求异常 — 用于立即终止扫描流程"""
    pass


def _human_delay(center: float, spread: float = 0.3) -> float:
    """模拟人类操作延迟，在 center ± spread/2 范围内随机抖动，降低行为指纹风险"""
    return center + random.uniform(-spread / 2, spread / 2)


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


_SELECTORS_CACHE = None


def load_selectors() -> dict[str, Any]:
    """加载 selectors.json 选择器配置（首次调用后缓存）"""
    global _SELECTORS_CACHE
    if _SELECTORS_CACHE is not None:
        return _SELECTORS_CACHE
    try:
        with open(SELECTORS_PATH, "r", encoding="utf-8") as f:
            _SELECTORS_CACHE = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"⚠️  加载 selectors.json 失败：{e}，使用内置默认值")
        _SELECTORS_CACHE = {}
    return _SELECTORS_CACHE


def _sel(group: str, key: str, default: str = "") -> str:
    """从 selectors.json 获取选择器值，找不到则返回 default"""
    s = load_selectors()
    return s.get(group, {}).get(key, default)


def load_job_config() -> tuple[dict[str, Any], dict[str, Any]]:
    """从外部配置文件加载职位要求（支持多岗位）
    返回：(job_requirements, default_rule)
        - job_requirements: 各岗位的配置（不包含 default）
        - default_rule: 默认过滤规则
    """
    default_rule = None

    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
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


def extract_summary_info(text: str) -> dict[str, Any]:
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
    salary_match = re.search(r'(\d+(?:-\d+)?)[Kk千]', lines[0] if lines else '')
    if salary_match:
        info['salary'] = salary_match.group(1) + 'K'
    elif '面议' in (lines[0] if lines else ''):
        info['salary'] = '面议'

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
    status_match = re.search(r'(离职|在职|在校|应届)[-·—]([^\n]+)', text)
    if status_match:
        info['job_status'] = status_match.group(1)
        info['company'] = status_match.group(2).strip()

    # 城市
    info['city'] = _extract_city(text)

    # 技能关键词
    skill_keywords = ['Java', 'Python', 'MySQL', 'Oracle', 'Redis', 'Kafka',
                      'Spring', 'MyBatis', 'Dubbo', 'Vue', 'React', 'Linux',
                      'Docker', 'K8s', 'Kubernetes', 'AWS', 'Azure', 'Git']
    found_skills = [s for s in skill_keywords if s in text]
    info['skills'] = ', '.join(found_skills)

    return info


def export_to_excel(candidates: list[dict[str, Any]], filename: str) -> None:
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
            if score >= SCORE_THRESHOLD_STRONG:
                recommend_level = "强烈推荐"
            elif score >= SCORE_THRESHOLD_RECOMMEND:
                recommend_level = "推荐"
            elif score >= SCORE_THRESHOLD_PASS:
                recommend_level = "待定"
            else:
                continue  # 低于通过分直接过滤，不进入导出

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


def get_iframe(page: ChromiumPage):
    """获取包含推荐列表的 iframe"""
    try:
        frames = page.eles(_sel('iframe', 'selector', 'tag:iframe'))
        for frame in frames:
            src = frame.attr('src') or ''
            if _sel('iframe', 'src_match', 'recommend') in src.lower():
                return frame
        if frames:
            return frames[0]
    except Exception as e:
        print(f"获取 iframe 失败：{e}")
    return None


def extract_name_from_card(card_element: Any) -> str:
    """从候选人卡片中提取姓名"""
    try:
        # 方法 1: 查找 class=name 的独立元素
        name_elements = card_element.eles(_sel('name_extraction', 'name_xpath',
            'xpath:.//*[contains(@class, "name") and not(contains(@class, "wrap"))]'))
        if name_elements:
            for ne in name_elements:
                text = ne.text.strip() if ne.text else ""
                # 验证是否是有效的中文姓名（2-4 个汉字）
                if text and len(text) >= 2 and len(text) <= 4:
                    # 检查是否都是汉字
                    if all('一' <= c <= '鿿' for c in text):
                        return text

        # 方法 2: 从 col-2 元素的第一行提取（姓名通常在开头）
        col2_elements = card_element.eles(_sel('name_extraction', 'col2_xpath',
            'xpath:.//*[contains(@class, "col-2")]'))
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


def scroll_in_frame(frame: Any, scroll_amount: int = SCROLL_PX) -> None:
    """在 iframe 内部滚动"""
    try:
        frame.run_js(f'window.scrollBy(0, {scroll_amount})')
        return True
    except Exception as e:
        print(f"iframe 滚动失败：{e}")
        return False


def get_frame_scroll_info(frame: Any) -> dict[str, Any]:
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


def _extract_cards_batch(target):
    """单次 JS 调用批量提取所有候选人卡片数据（替代逐卡片的 N+1 调用）

    在 JS 端完成：遍历所有 [data-geekid] 卡片，提取 geek_id、innerText、姓名。
    姓名提取逻辑复用 extract_name_from_card() 的两种策略。

    Args:
        target: DrissionPage 的 page 或 iframe 对象

    Returns:
        list[dict]: [{'geek_id': str, 'name': str, 'text': str}, ...]
    """
    script = '''
    return (function(){
        var cards = document.querySelectorAll('[data-geekid]');
        var results = [];
        var invalidNames = '推荐,位置,面议,优势,推荐牛人,编组,备份,立即,沟通,聊天,联系,在线,今日,最近,邀请,投递,刷新,收藏,点赞,分享,高级,资深,初级,中级,离职,在职,看看,职位'.split(',');
        for (var c = 0; c < cards.length; c++) {
            var card = cards[c];
            var geekId = card.getAttribute('data-geekid');
            if (!geekId) continue;
            var rawText = card.innerText || '';
            if (rawText.length < 30) continue;
            var name = '';
            var nameEls = card.querySelectorAll('[class*="name"]:not([class*="wrap"])');
            for (var i = 0; i < nameEls.length; i++) {
                var t = (nameEls[i].innerText || '').trim();
                if (t.length >= 2 && t.length <= 4 && /^[\\u4e00-\\u9fff]+$/.test(t)) {
                    name = t; break;
                }
            }
            if (!name) {
                var col2 = card.querySelectorAll('[class*="col-2"]');
                if (col2.length > 0) {
                    var ct = (col2[0].innerText || '').trim();
                    var fl = ct.split('\\n')[0].trim();
                    var pn = '';
                    for (var j = 0; j < fl.length; j++) {
                        var code = fl.charCodeAt(j);
                        if (code >= 0x4e00 && code <= 0x9fff) {
                            pn += fl[j];
                            if (pn.length > 4) break;
                        } else break;
                    }
                    if (pn.length >= 2 && pn.length <= 4 && invalidNames.indexOf(pn) === -1) {
                        name = pn;
                    }
                }
            }
            results.push({geek_id: geekId, name: name || '未知', text: rawText});
        }
        return results;
    })()
    '''
    try:
        return target.run_js(script) or []
    except Exception as e:
        print(f"批量提取候选人数据失败：{e}")
        return []


def extract_candidates_by_comprehensive_analysis(page, max_rounds=MAX_ROUNDS_DEFAULT, progress_callback=None, stop_event=None, captcha_callback=None):
    """通过全面分析提取候选人

    Args:
        page: 页面对象
        max_rounds: 最大滚动轮次（默认 30）
        progress_callback: 进度回调 callable(percentage, description)，percentage 0-100
        stop_event: threading.Event，设位时立即停止扫描
    """
    print("正在提取候选人...")
    time.sleep(_human_delay(1.0, 0.5))

    iframe = get_iframe(page)

    all_candidates = []
    seen_geek_ids = set()
    target = iframe if iframe else page
    consecutive_empty = 0

    for scroll_round in range(max_rounds):
        # 检查停止信号
        if stop_event and stop_event.is_set():
            raise StopRequested()

        # 验证码检测：每 3 轮一次（降低调用频率，弹窗一旦出现 1.5s 内必然可见）
        if scroll_round % 3 == 0:
            is_captcha, captcha_msg = _detect_captcha(page)
            if is_captcha:
                print(f"\n⚠️  检测到安全验证弹窗 ({captcha_msg})")
                if not _wait_for_captcha_resolution(page, stop_event, captcha_callback=captcha_callback, detail=captcha_msg):
                    break

        # 进度上报
        if progress_callback:
            pct = int((scroll_round + 1) / max_rounds * 100)
            progress_callback(pct, f"正在扫描候选人... 第{scroll_round + 1}/{max_rounds}轮")

        # 先滚动（第一轮跳过）
        if scroll_round > 0:
            if iframe:
                # 同时滚动 window 和可能的滚动容器（BOSS 直聘虚拟列表的实际滚动目标）
                _scroll_sel = _sel('scroll', 'container_js_selectors',
                    '.candidate-list,.geek-list,.recommend-list,[class*=list],[class*=scroll]')
                iframe.run_js(f'''
                    window.scrollBy(0, {SCROLL_PX});
                    var list = document.querySelector("{_scroll_sel}");
                    if(list) list.scrollTop += {SCROLL_PX};
                ''')
                time.sleep(_human_delay(0.8, 0.5))
            else:
                page.run_js(f'window.scrollBy(0, {SCROLL_PX})')
                time.sleep(_human_delay(0.8, 0.5))

            # 到底检测：滚动位置优先（单次 JS 调用，无 DOM 查找）
            scroll_info = get_frame_scroll_info(iframe) if iframe else None
            if scroll_info and scroll_info.get('atBottom'):
                # 兜底：再用文本确认一次
                bottom_hint = None
                try:
                    _bottom_texts = _sel('scroll', 'bottom_texts', ["到底", "没有更多"])
                    bottom_hint = target.ele(f'@text():{_bottom_texts[0]}', timeout=0.3)
                    if not bottom_hint and len(_bottom_texts) > 1:
                        bottom_hint = target.ele(f'@text():{_bottom_texts[1]}', timeout=0.3)
                except Exception:
                    pass
                if bottom_hint:
                    print(f"检测到'到底'提示，第 {scroll_round + 1} 轮提前终止（累计 {len(all_candidates)} 个候选人）")
                    break

        # 收集候选人（单次 JS 批量提取，替代逐卡片的 N+1 调用）
        candidates_in_round = []
        current_round_ids = set()

        try:
            batch = _extract_cards_batch(target)
            for item in batch:
                geek_id = item['geek_id']
                if not geek_id or geek_id in seen_geek_ids or geek_id in current_round_ids:
                    continue

                current_round_ids.add(geek_id)

                text = item['text']
                # 内容过滤（Python 端，零网络开销）
                has_candidate_info = (
                    '经验' in text or '本科' in text or '硕士' in text or
                    'Java' in text or '开发' in text or '工程师' in text or
                    re.search(r'\d+年', text) or re.search(r'\d+岁', text)
                )
                if not has_candidate_info:
                    continue

                candidates_in_round.append({
                    'geek_id': geek_id,
                    'name': item['name'],
                    'summary': text,
                })

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
            if consecutive_empty >= EMPTY_ROUNDS_LIMIT:
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


def _find_card_by_scroll(target, card_css, stop_event=None, max_scrolls=MAX_SCROLL_SEARCH, scroll_px=SCROLL_PX):
    """智能滚动定位候选人卡片

    BOSS 直聘使用虚拟列表，只渲染视口内的卡片。此函数通过系统性滚动搜索
    不在当前视口的候选人，解决补打招呼和右键打招呼找不到卡片的问题。

    策略：
    1. 先检查当前位置（最快路径，刚扫描完的场景）
    2. 滚到顶部建立已知起点
    3. 从顶部向下逐步滚动，每步检查卡片是否渲染

    Args:
        target: DrissionPage 的 page 或 iframe 对象
        card_css: CSS 选择器字符串（含 data-geekid）
        stop_event: threading.Event，设置时立即放弃搜索
        max_scrolls: 最大滚动次数（默认 40，覆盖约 32000px 的列表高度）
        scroll_px: 每次滚动像素（默认 800）

    Returns:
        card element 或 None
    """
    # Phase 1: 当前位置快速检查
    try:
        card = target.ele(card_css, timeout=1)
        if card:
            return card
    except Exception:
        pass

    # Phase 2: 滚到顶部
    try:
        target.run_js('''
            window.scrollTo(0, 0);
            var list = document.querySelector(".candidate-list,.geek-list,.recommend-list,[class*=list],[class*=scroll]");
            if(list) list.scrollTop = 0;
        ''')
    except Exception:
        pass
    time.sleep(_human_delay(0.5, 0.3))

    # 检查顶部位置
    try:
        card = target.ele(card_css, timeout=1)
        if card:
            return card
    except Exception:
        pass

    # Phase 3: 从顶部向下逐步滚动搜索
    prev_scroll = -1
    for _ in range(max_scrolls):
        if stop_event and stop_event.is_set():
            return None

        try:
            target.run_js(f'''
                window.scrollBy(0, {scroll_px});
                var list = document.querySelector(".candidate-list,.geek-list,.recommend-list,[class*=list],[class*=scroll]");
                if(list) list.scrollTop += {scroll_px};
            ''')
        except Exception:
            break
        time.sleep(_human_delay(0.3, 0.2))

        try:
            card = target.ele(card_css, timeout=0.5)
            if card:
                return card
        except Exception:
            pass

        # 检测是否已到底（scrollTop 不再变化）
        try:
            cur_scroll = target.run_js('return document.documentElement.scrollTop || document.body.scrollTop || 0')
            if cur_scroll == prev_scroll:
                break
            prev_scroll = cur_scroll
        except Exception:
            pass

    return None


def send_greeting_on_list_page(page, geek_id, retry=0, stop_event=None, captcha_callback=None):
    """
    在列表页直接向候选人打招呼（极速优化版）

    优化要点：
    - 智能滚动搜索替代单次 300px 滚动，系统性定位不在可视区的卡片
    - CSS 选择器替代 //* 全局 XPath 扫描
    - 合并按钮文本查询为单次 XPath OR 表达式，消灭循环等待叠加
    - 所有 ele() 调用设短超时，不再死等默认 10s
    - 点击后检测升级套餐/次数上限弹窗，防止假成功
    - 检测到安全验证弹窗时暂停等待用户处理，验证完成后自动重试

    返回：(是否成功，消息)
    """
    try:
        iframe = get_iframe(page)
        target = iframe if iframe else page

        # CSS 选择器按 data-geekid 属性定位卡片，比 //* 快几个数量级
        card_css = _sel('candidate_card', 'card_by_id_css',
                        'css:[data-geekid="{geek_id}"]').format(geek_id=geek_id)
        card = target.ele(card_css, timeout=2)

        if not card:
            # 智能滚动搜索：当前位置 → 滚到顶部 → 逐步向下（最多 40 轮 × 800px）
            card = _find_card_by_scroll(target, card_css, stop_event=stop_event)

        if not card:
            return False, "未找到卡片(滚动搜索后仍不在可视区)"

        parent = card.parent()
        if not parent:
            return False, "未找到卡片父容器"

        # 合并 XPath：单次查询匹配三种按钮文本，彻底消灭 for 循环 + 默认超时叠加
        xpath_query = _sel('greet_button', 'button_xpath',
            'xpath:.//*[text()="继续沟通" or text()="立即沟通" or text()="打招呼" '
            'or contains(text(), "继续沟通") or contains(text(), "立即沟通") '
            'or contains(text(), "打招呼")]')
        greet_btn = parent.ele(xpath_query, timeout=2)

        if not greet_btn:
            return False, "未找到按钮"

        # 滚到可见区域再点击，防止被悬浮头部遮挡
        try:
            greet_btn.scroll.to_see(center=True)
            time.sleep(_human_delay(0.1, 0.08))
            greet_btn.click()
        except Exception:
            greet_btn.run_js('this.click()')

        time.sleep(_human_delay(0.3, 0.3))  # 等待按钮点击生效

        # 检测升级套餐/次数上限弹窗（重试一次，弹窗可能有渲染延迟）
        is_limited, limit_msg = _detect_limit_popup(page)
        is_captcha, captcha_msg = _detect_captcha(page)
        if not is_limited and not is_captcha:
            time.sleep(_human_delay(0.3, 0.3))
            is_limited, limit_msg = _detect_limit_popup(page)
            if not is_captcha:
                is_captcha, captcha_msg = _detect_captcha(page)

        if is_limited:
            return False, f"沟通次数已达上限: {limit_msg}"
        if is_captcha:
            print(f"\n   打招呼时检测到安全验证弹窗 ({captcha_msg})")
            if _wait_for_captcha_resolution(page, stop_event, captcha_callback=captcha_callback, detail=captcha_msg):
                # 验证完成后重新检测弹窗状态
                time.sleep(_human_delay(0.5, 0.3))
                is_limited, limit_msg = _detect_limit_popup(page)
                is_captcha, captcha_msg = _detect_captcha(page)
                if is_limited:
                    return False, f"沟通次数已达上限: {limit_msg}"
                if is_captcha:
                    return False, f"验证后仍存在安全弹窗: {captcha_msg}"
                return True, "成功（验证后继续）"
            else:
                return False, f"安全验证未完成: {captcha_msg}"

        return True, "成功"

    except Exception as e:
        return False, f"异常: {str(e)[:50]}"



def _detect_limit_popup(page: ChromiumPage) -> tuple[bool, str]:
    """
    检测是否弹出了 BOSS 直聘沟通次数上限/升级套餐弹窗（极速版）

    单次 JS 调用合并所有关键词检测，<10ms 完成，不影响打招呼速度。

    返回: (is_limited: bool, detail: str)
    """
    # 所有限制弹窗关键词，用 || 合并为一条 JS 表达式
    limit_keywords = _sel('limit_detection', 'keywords', [
        "次数已用完", "沟通次数", "今日上限", "升级套餐",
        "立即升级", "联系次数", "已达上限", "今日剩余",
        "开通套餐", "购买套餐", "次数不足", "免费次数",
        "升级VIP", "VIP无限沟通", "体验VIP", "今日免费",
    ])
    checks = " || ".join(f'body.innerText.includes("{kw}")' for kw in limit_keywords)
    script = f'return (function(){{var body=document.body;return {checks};}})()'

    try:
        # 只搜 iframe（BOSS 弹窗在此渲染），主页面作为兜底
        iframe = get_iframe(page)
        if iframe:
            try:
                if iframe.run_js(script):
                    return True, "iframe检测到限制弹窗"
            except Exception:
                pass

        # 兜底：主页面
        try:
            if page.run_js(script):
                return True, "主页面检测到限制弹窗"
        except Exception:
            pass

        return False, ""

    except Exception:
        return False, ""


def _detect_captcha(page: ChromiumPage) -> tuple[bool, str]:
    """
    检测是否弹出了 BOSS 直聘安全验证弹窗（滑块/图形验证码等）

    BOSS 直聘常见验证形式：
        - 滑块拼图验证（.captcha-slider, .slider-verify 等）
        - 图形验证码（.geetest, .captcha-img 等）
        - 安全提醒弹窗（"检测到异常操作"、"请完成安全验证"）

    检测到验证码时暂停自动化并提示用户处理，避免盲目重试触发风控升级。

    返回: (is_captcha: bool, detail: str)
    """
    captcha_keywords = _sel('captcha_detection', 'keywords', [
        "请完成安全验证", "滑块验证", "请拖动滑块",
        "拖拽拼图", "检测到异常操作", "请先完成验证",
        "行为验证", "请完成验证", "拖动下方滑块", "请按住滑块",
    ])

    # 构建只检查可见文本节点的 JS（排除 display:none / visibility:hidden / 视口外元素）
    # \\n in Python → \n in JS (literal newline inside JS string)
    kw_js = "\\n".join(captcha_keywords)
    script = (
        'return (function(){'
        'var kws=("' + kw_js + '").split("\\n");'
        'function vis(el){'
        'var n=el;'
        'while(n&&n.nodeType===1){'
        'var s=getComputedStyle(n);'
        'if(s.display==="none"||s.visibility==="hidden"||s.opacity==="0")return false;'
        'n=n.parentElement;}'
        'var r=el.getBoundingClientRect();'
        'if(r.width<10||r.height<10)return false;'
        'var vw=window.innerWidth,vh=window.innerHeight;'
        'if(r.bottom<0||r.top>vh||r.right<0||r.left>vw)return false;'
        'return true;}'
        'var tw=document.createTreeWalker(document.body,4,null);'
        'var nd;'
        'while(nd=tw.nextNode()){'
        'if(nd.parentElement&&vis(nd.parentElement)){'
        'for(var i=0;i<kws.length;i++){if(nd.textContent.indexOf(kws[i])!==-1)return kws[i];}}}'
        'return "";})()'
    )

    try:
        iframe = get_iframe(page)
        if iframe:
            try:
                matched_kw = iframe.run_js(script)
                if matched_kw:
                    return True, f"iframe 检测到安全验证弹窗（匹配词：{matched_kw}）"
            except Exception:
                pass

        try:
            matched_kw = page.run_js(script)
            if matched_kw:
                return True, f"主页面检测到安全验证弹窗（匹配词：{matched_kw}）"
        except Exception:
            pass

        # 额外检查常见验证码容器的 DOM 存在性（无文本提示的纯图形验证）
        container_checks = _sel('captcha_detection', 'css_selectors', [
            '.geetest_panel', '.captcha-box', '.slider-captcha',
            '.verify-captcha', '.captcha-container', '#captcha',
            '.yoda-modal',
        ])
        for selector in container_checks:
            try:
                el = page.ele(f'css:{selector}', timeout=0.3)
                if el and el.states.is_displayed:
                    return True, f"检测到验证码容器 ({selector})"
            except Exception:
                continue

        return False, ""

    except Exception:
        return False, ""


def _wait_for_captcha_resolution(page, stop_event=None, max_wait=CAPTCHA_MAX_WAIT, captcha_callback=None, detail=""):
    """
    等待用户手动完成安全验证（验证码/滑块）。

    每隔 3 秒检查验证码是否已消失。用户完成验证后自动恢复。
    支持 stop_event 中断和最大等待时间。

    参数:
        page: DrissionPage 页面对象
        stop_event: threading.Event，设置时立即返回 False
        max_wait: 最大等待秒数（默认 5 分钟），超时返回 False
        captcha_callback: callable(detail) -> bool，检测到验证码时调用，
            用于 GUI 弹窗通知用户。返回 True 继续等待，False 中止。
            若为 None 则仅通过日志通知。

    返回:
        True: 验证已完成，可继续
        False: 用户中止或超时
    """
    print(f"\n⚠️  检测到安全验证弹窗，请在浏览器中手动完成验证。")
    print(f"   程序将自动检测验证状态，完成后继续运行...（最长等待 {max_wait} 秒）")

    # 通知 GUI 弹窗
    if captcha_callback:
        try:
            user_continue = captcha_callback(detail)
            if not user_continue:
                print("   用户选择跳过验证等待。")
                return False
        except Exception:
            pass

    elapsed = 0
    check_interval = CAPTCHA_CHECK_INTERVAL
    while elapsed < max_wait:
        if stop_event and stop_event.is_set():
            print("   用户中止，停止等待验证。")
            return False
        time.sleep(check_interval)
        elapsed += check_interval
        is_still, _ = _detect_captcha(page)
        if not is_still:
            print(f"✅ 验证已完成，继续运行...")
            return True
        if elapsed % 15 == 0:
            remaining = max_wait - elapsed
            print(f"   仍在等待验证...（剩余 {remaining} 秒，可随时在浏览器中完成验证）")

    print(f"⏰ 等待验证超时（{max_wait} 秒），停止当前操作。")
    return False


def verify_greeting_success(page: ChromiumPage, geek_id: str, debug: bool = False) -> tuple[bool, str]:
    """
    验证打招呼是否成功（快速版 - 直接检查按钮文本）
    """
    try:
        # 直接查找该候选人的"继续沟通"或"已沟通"标记
        # 使用更精确的 XPath，减少查询范围
        _geek_attr = _sel('candidate_card', 'geek_id_attr', 'data-geekid')
        cards = page.eles(f'xpath://*[@{_geek_attr}="{geek_id}"]')
        if not cards:
            return True, "点击已执行"
        
        parent = cards[0].parent()
        if not parent:
            return True, "点击已执行"
        
        # 直接获取父元素下所有文本节点，一次查询
        all_text = parent.text
        
        # 检查是否包含成功标记
        _success_marks = _sel('greeting_verify', 'success_marks', ["已沟通", "沟通过", "已发送"])
        _continue_mark = _sel('greeting_verify', 'continue_mark', "继续沟通")

        if any(mark in all_text for mark in _success_marks):
            return True, "找到成功标记"

        if _continue_mark in all_text:
            return True, "按钮为'继续沟通'"
        
        # 默认成功
        return True, "点击已执行"

    except Exception:
        return True, "点击已执行"


def check_selectors_health(page: ChromiumPage) -> list[dict[str, Any]]:
    """选择器健康检查：逐一测试 selectors.json 中的关键选择器，返回诊断报告。

    返回: list[dict]，每项包含:
        - group: 选择器组名
        - name: 选择器名称
        - status: 'ok' | 'warn' | 'fail'
        - detail: 描述信息
    """
    results = []
    sel = load_selectors()

    def _check(name, test_fn, group="", expect_found=True):
        try:
            found = test_fn()
            if expect_found and found:
                results.append({'group': group, 'name': name, 'status': 'ok',
                               'detail': f'找到 {found} 个匹配元素'})
            elif expect_found and not found:
                results.append({'group': group, 'name': name, 'status': 'warn',
                               'detail': '未找到匹配元素（可能页面未加载或选择器已失效）'})
            else:
                results.append({'group': group, 'name': name, 'status': 'ok',
                               'detail': '检查通过'})
        except Exception as e:
            results.append({'group': group, 'name': name, 'status': 'fail',
                           'detail': f'异常：{type(e).__name__}: {str(e)[:80]}'})

    # 1. iframe 检测
    iframe_sel = _sel('iframe', 'selector', 'tag:iframe')
    def _test_iframe():
        frames = page.eles(iframe_sel)
        return len(frames) if frames else 0
    _check('iframe', _test_iframe, group='iframe', expect_found=False)

    # 2. 候选人卡片
    cards_sel = _sel('candidate_card', 'all_cards_xpath', 'xpath://*[@data-geekid]')
    iframe = get_iframe(page)
    target = iframe if iframe else page
    def _test_cards():
        els = target.eles(cards_sel)
        return len(els) if els else 0
    _check('all_cards', _test_cards, group='candidate_card')

    # 3. 验证码容器（不应存在）
    captcha_css = _sel('captcha_detection', 'css_selectors', [])
    captcha_found = []
    for css in captcha_css:
        try:
            el = page.ele(f'css:{css}', timeout=0.3)
            if el and el.states.is_displayed:
                captcha_found.append(css)
        except Exception:
            continue
    if captcha_found:
        results.append({'group': 'captcha_detection', 'name': 'css_containers',
                       'status': 'warn', 'detail': f'检测到验证码容器: {captcha_found}'})
    else:
        results.append({'group': 'captcha_detection', 'name': 'css_containers',
                       'status': 'ok', 'detail': '无验证码弹窗'})

    # 4. 限制弹窗关键词
    limit_kws = _sel('limit_detection', 'keywords', [])
    if limit_kws:
        checks = " || ".join(f'body.innerText.includes("{kw}")' for kw in limit_kws)
        script = f'return (function(){{var body=document.body;return {checks};}})()'
        try:
            triggered = target.run_js(script)
            if triggered:
                results.append({'group': 'limit_detection', 'name': 'keywords',
                               'status': 'warn', 'detail': '检测到限制弹窗关键词'})
            else:
                results.append({'group': 'limit_detection', 'name': 'keywords',
                               'status': 'ok', 'detail': '无限制弹窗'})
        except Exception as e:
            results.append({'group': 'limit_detection', 'name': 'keywords',
                           'status': 'fail', 'detail': f'JS 执行失败：{str(e)[:60]}'})

    # 5. 打招呼按钮（需要至少有卡片才能检测）
    btn_xpath = _sel('greet_button', 'button_xpath', '')
    if btn_xpath and _test_cards() > 0:
        try:
            cards = target.eles(cards_sel)
            if cards:
                parent = cards[0].parent()
                if parent:
                    btn = parent.ele(btn_xpath, timeout=1)
                    results.append({'group': 'greet_button', 'name': 'button_xpath',
                                   'status': 'ok' if btn else 'warn',
                                   'detail': '找到按钮' if btn else '第一张卡片未找到按钮'})
        except Exception as e:
            results.append({'group': 'greet_button', 'name': 'button_xpath',
                           'status': 'fail', 'detail': str(e)[:80]})

    # 6. selectors.json 文件完整性
    expected_groups = ['candidate_card', 'name_extraction', 'greet_button',
                       'iframe', 'scroll', 'captcha_detection', 'limit_detection']
    missing = [g for g in expected_groups if g not in sel]
    if missing:
        results.append({'group': 'config', 'name': 'selectors.json',
                       'status': 'warn', 'detail': f'缺少配置组: {missing}'})
    else:
        results.append({'group': 'config', 'name': 'selectors.json',
                       'status': 'ok', 'detail': f'配置文件完整 ({len(sel)} 组)'})

    return results

def smart_scan_candidates(page, job_info, auto_greet=False, max_rounds=MAX_ROUNDS_DEFAULT, verbose=False, greet_level='normal', greet_names_list=None, list_candidates=False, progress_callback=None, stop_event=None, ai_eval=False, api_config=None, api_key=None, captcha_callback=None):
    """
    智能扫描候选人 - 两阶段模式

    阶段 1: 滚动收集所有候选人并筛选（不打招呼）
    阶段 1.5: AI 辅助评估（可选，对通过筛选的候选人进行 LLM 二次评分）
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
        progress_callback: 进度回调 callable(percentage, description)，percentage 0-100
        stop_event: threading.Event，设位时立即停止
        ai_eval: 是否启用 AI 辅助评估
        api_config: API 配置字典（base_url, model），AI 评估时使用
        api_key: API Key 字符串，AI 评估时使用
        captcha_callback: callable(detail) -> bool，检测到验证码时调用，
            用于 GUI 弹窗通知用户。返回 True 继续等待，False 中止。
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
    raw_candidates = extract_candidates_by_comprehensive_analysis(page, max_rounds=max_rounds, progress_callback=progress_callback, stop_event=stop_event, captcha_callback=captcha_callback)
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

    # 构建淘汰原因的动态描述（基于实际招聘要求）
    rule = job_info['rule']
    exp_requirement = f"经验不足（{rule.get('min_exp', 0)}年以上工作经验）"
    # 学历要求：优先取 required_conditions 中的统招本科，否则取 edu 字段
    edu_requirement = rule.get('edu', '不限')
    req_conds = rule.get('required_conditions', [])
    for cond in req_conds:
        if isinstance(cond, str) and '统招' in cond:
            edu_requirement = cond
            break
    edu_requirement = f"学历不符/不足（{edu_requirement}）"

    for i, candidate in enumerate(raw_candidates):
        if stop_event and stop_event.is_set():
            raise StopRequested()
        passed, score, details = filter_candidate(candidate['summary'], job_info['rule'])
        if passed and score >= SCORE_THRESHOLD_PASS:
            # 计算推荐等级
            if score >= SCORE_THRESHOLD_STRONG:
                recommend_level = "强烈推荐"
            elif score >= SCORE_THRESHOLD_RECOMMEND:
                recommend_level = "推荐"
            else:
                recommend_level = "待定"

            candidate_record = {
                "geek_id": candidate['geek_id'],
                "name": candidate['name'],
                "summary": candidate['summary'],
                "job_id": job_info['job_id'],
                "job_name": job_name.replace(" ", ""),  # 去除岗位名称中的空格
                "city": _extract_city(candidate['summary']),
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
            if passed:
                # 通过了硬性筛选但评分 < 55，按分数段归类
                if score >= 50:
                    reason = "评分不足(50-54分)"
                elif score >= 40:
                    reason = "评分不足(40-49分)"
                elif score >= 30:
                    reason = "评分不足(30-39分)"
                else:
                    reason = "评分不足(<30分)"
            else:
                reason = details.get('reason', '未知')
                # 合并同类淘汰原因
                if '经验不足' in reason:
                    reason = exp_requirement
                elif '学历不足' in reason or '学历不符' in reason:
                    reason = edu_requirement
            failed_reasons[reason] = failed_reasons.get(reason, 0) + 1

        if (i + 1) % 20 == 0:
            print(f"  已筛选 {i + 1}/{len(raw_candidates)} 个，通过 {len(passed_candidates)} 个")
            if progress_callback:
                pct = int((i + 1) / len(raw_candidates) * 100)
                progress_callback(pct, f"正在智能筛选... {i + 1}/{len(raw_candidates)}")

    # 按分数从高到低排序
    passed_candidates.sort(key=lambda x: x.get('match_score', 0), reverse=True)

    print(f"\n筛选完成：通过 {len(passed_candidates)}/{len(raw_candidates)} 个")
    if failed_reasons:
        total_failed = sum(failed_reasons.values())
        print(f"淘汰原因（共 {total_failed} 人）:")
        def _reason_order(item):
            reason = item[0]
            if '经验不足' in reason:
                return (0, -item[1])
            if '学历' in reason:
                return (1, -item[1])
            if '评分不足' in reason:
                return (2, -item[1])
            return (3, -item[1])

        for reason, count in sorted(failed_reasons.items(), key=_reason_order):
            print(f"  - {reason}: {count} 人")
        # 总数校验
        accounted = len(passed_candidates) + total_failed
        if accounted != len(raw_candidates):
            print(f"⚠️  数量不一致：通过({len(passed_candidates)}) + 淘汰({total_failed}) = {accounted} ≠ 原始({len(raw_candidates)})")

    # === 阶段 1.5: AI 辅助评估（可选）===
    if ai_eval and api_config and api_key and passed_candidates:
        from llm_eval import evaluate_batch
        rule = job_info['rule']
        job_requirement = rule.get('original_requirement', '')
        if not job_requirement:
            job_requirement = f"岗位：{job_name}，{rule.get('min_exp', 0)}年经验，{rule.get('edu', '不限')}学历"

        print(f"\n=== AI 辅助评估（共 {len(passed_candidates)} 人，最多评估 50 人）===")
        passed_candidates = evaluate_batch(
            passed_candidates, job_requirement, api_config, api_key,
            max_candidates=50,
            progress_callback=progress_callback,
            stop_event=stop_event,
        )
        # 重新排序（分数可能变化）
        passed_candidates.sort(key=lambda x: x.get('match_score', 0), reverse=True)
        llm_count = sum(1 for c in passed_candidates if c.get('llm_evaluated'))
        print(f"AI 评估完成：{llm_count} 人已评估")

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

        # 温和刷新：小幅度滚动触发懒加载渲染，不滚回顶部破坏虚拟列表
        iframe = get_iframe(page)
        target = iframe if iframe else page
        target.run_js('window.scrollBy(0, 200)')
        time.sleep(_human_delay(0.3, 0.25))
        target.run_js('window.scrollBy(0, -100)')
        time.sleep(_human_delay(0.3, 0.25))

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

        try:
            for i, candidate in enumerate(to_greet_list):
                if stop_event and stop_event.is_set():
                    raise StopRequested()
                action = "补打招呼" if candidate['geek_id'] in all_existing_ids else "打招呼"

                # 检查连续失败，如果连续失败 3 次则停止
                if consecutive_failures >= GREET_FAIL_LIMIT:
                    print(f"\n⚠️  连续 {consecutive_failures} 次失败，停止打招呼")
                    break

                # 打招呼进度
                if progress_callback:
                    pct = int((i + 1) / len(to_greet_list) * 100)
                    progress_callback(pct, f"正在打招呼... {i + 1}/{len(to_greet_list)}")

                # 每个打招呼间隔 ~0.5 秒（带随机抖动）
                if i > 0:
                    time.sleep(_human_delay(0.5, 0.4))

                print(f"  [{i+1}/{len(to_greet_list)}] {candidate['name']} ({candidate['recommend_level']}, {candidate['match_score']}分) {action}...", end=" ")

                # 每 5 个招呼间歇性滚一下，保持虚拟列表持续渲染后续卡片
                if i > 0 and i % 5 == 0:
                    iframe = get_iframe(page)
                    (iframe if iframe else page).run_js('window.scrollBy(0, 400)')
                    time.sleep(_human_delay(0.2, 0.15))

                success, msg = send_greeting_on_list_page(page, candidate['geek_id'], stop_event=stop_event, captcha_callback=captcha_callback)

                if success:
                    greet_success_count += 1
                    consecutive_failures = 0  # 重置连续失败计数
                    candidate['greet_sent'] = True
                    candidates_all.append(candidate)
                    greeted_in_this_run.append(candidate['geek_id'])
                    print(f"OK")
                else:
                    greet_fail_count += 1
                    consecutive_failures += 1  # 累加连续失败计数
                    candidate['greet_sent'] = False
                    candidates_all.append(candidate)
                    print(f"失败：{msg}")

                    # 沟通次数上限是终端条件：达到上限后所有后续打招呼都不会成功
                    if "上限" in msg or "次数" in msg:
                        print(f"\n{'='*60}")
                        print(f"⚠️  今日沟通次数已达上限！")
                        print(f"   BOSS 直聘已弹出升级套餐页面，后续打招呼不会真正发送")
                        print(f"   本次已成功打招呼：{greet_success_count} 人")
                        print(f"{'='*60}")
                        break

                    # 安全验证（滑块/图形验证码）：暂停自动化，等待人工处理
                    if "验证" in msg:
                        print(f"\n{'='*60}")
                        print(f"⚠️  检测到安全验证弹窗！")
                        print(f"   请手动完成验证码后再继续。")
                        print(f"   本次已成功打招呼：{greet_success_count} 人，{greet_fail_count} 人失败")
                        print(f"{'='*60}")
                        break

        except KeyboardInterrupt:
            print(f"\n\n⚠️  检测到中断，保存当前进度...")
            # 中断时立即保存所有数据
            save_candidates_all(candidates_all)
            if greeted_in_this_run:
                print(f"  本次运行已打招呼 {len(greeted_in_this_run)} 人")
            print(f"✅ 候选人总数：{len(candidates_all)}")
            raise

        print(f"\n打招呼完成：成功 {greet_success_count} 人，失败 {greet_fail_count} 人")

    # 保存所有通过的候选人（包含未打招呼的）
    # 用字典索引避免 O(n²) 查找
    existing_index = {c.get('geek_id'): c for c in candidates_all}
    for c in passed_candidates:
        if not c.get('greet_sent'):
            if c.get('geek_id') not in existing_index:
                candidates_all.append(c)
                existing_index[c.get('geek_id')] = c
    save_candidates_all(candidates_all)

    return passed_candidates


def _show_job_navigation_prompt(current_idx, total, next_job_name, confirm_callback=None):
    """多岗位间页面导航提示

    在切换到下一个岗位之前，提示用户手动导航到新岗位的推荐页面。
    - CLI 模式：等待用户按 Enter 确认
    - GUI 模式：通过 confirm_callback 等待用户确认（无倒计时）
    """
    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║  🔄 岗位切换：请导航到下一个岗位的推荐页面                      ║
╠══════════════════════════════════════════════════════════════╣
║  进度：{current_idx}/{total}                                       ║
║  下一个岗位：{next_job_name}
╠══════════════════════════════════════════════════════════════╣
║  BOSS 直聘每个岗位有独立的推荐页面 URL，请手动切换              ║
║  例如：https://www.zhipin.com/web/geek/recommend?jobId=xxxx  ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)

    if confirm_callback:
        # GUI 模式：通过回调等待用户确认（阻塞式，无倒计时）
        confirmed = confirm_callback(current_idx, total, next_job_name)
        if confirmed:
            print("已确认，继续处理...\n")
        else:
            print("用户取消岗位切换\n")
            raise KeyboardInterrupt
    else:
        # CLI 模式：等待 Enter，失败则倒计时
        try:
            input("请导航到新页面后按 Enter 继续...")
            print("已确认，继续处理...\n")
        except (EOFError, OSError):
            # GUI 模式或无终端环境，给用户 15 秒切换页面
            print("(GUI 模式) 请在 15 秒内手动切换到新岗位的推荐页面...")
            for remaining in range(15, 0, -1):
                print(f"  {remaining} 秒后自动继续...", end="\r")
                time.sleep(1)
            print("  继续处理...\n")


def run_smart_scan(args=None, progress_callback=None, confirm_callback=None, stop_event=None, existing_page=None, captcha_callback=None):
    """运行智能扫描（支持多岗位）

    参数：
        args: argparse.Namespace 对象，如果为 None 则从命令行解析
        progress_callback: 进度回调 callable(percentage, description)，GUI 模式使用
        confirm_callback: 岗位切换确认回调 callable(current_idx, total, next_job_name) -> bool，GUI 模式使用
        stop_event: threading.Event，设置时立即停止扫描
        existing_page: 已有的浏览器页面对象（GUI 模式传入，避免重复连接）
        captcha_callback: callable(detail) -> bool，检测到验证码时调用，
            用于 GUI 弹窗通知用户。返回 True 继续等待，False 中止。
    """
    import argparse

    # 如果没有传入参数，从命令行解析
    if args is None:
        parser = argparse.ArgumentParser(description='BOSS 直聘候选人智能提取工具')
        parser.add_argument('--clear', action='store_true', help='清空 candidates_all.json 后全新跑')
        parser.add_argument('--keep-greeted', action='store_true', help='清空时保留已打招呼的候选人（仅与 --clear 配合使用）')
        parser.add_argument('--job', type=str, help='指定岗位名称，只跑该岗位')
        parser.add_argument('--greet', action='store_true', help='自动打招呼：对新匹配的候选人自动发送消息')
        parser.add_argument('--re-greet', action='store_true', help='补打招呼：给已匹配但未打招呼的候选人发送消息')
        parser.add_argument('--greet-level', type=str, choices=['strong', 'normal'], default='normal',
                            help='打招呼等级（仅补打招呼模式有效）：strong=仅强烈推荐，normal=强烈推荐 + 推荐（默认）')
        parser.add_argument('--greet-names', type=str, help='点对点打招呼（仅补打招呼模式有效）：指定候选人姓名，多个用逗号分隔')
        parser.add_argument('--list-candidates', action='store_true', help='仅列出候选人，不打招呼')
        parser.add_argument('--rounds', type=int, default=100, help='最大滚动轮次（默认 100，推荐 50-200）')
        parser.add_argument('--verbose', action='store_true', help='输出详细评分信息（显示技能匹配详情）')
        parser.add_argument('--ai-eval', action='store_true', help='启用 AI 辅助评估：对通过筛选的候选人进行 LLM 二次评分')
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
    mode_text = "补打招呼模式" if re_greet_mode else ("全新模式（保留已沟通）" if (args.clear and args.keep_greeted) else ("全新模式" if args.clear else "增量模式"))
    if point_to_point_mode:
        mode_text = f"点对点打招呼模式 ({args.greet_names})"
    greet_text = ""
    if auto_greet_scan:
        greet_level_display = "仅强烈推荐" if args.greet_level == 'strong' else "强烈推荐 + 推荐"
        greet_text = f" + 自动打招呼 ({greet_level_display})"
    elif re_greet_mode:
        greet_text = f" + 打招呼等级 ({greet_level_text})"
    print(f">>> BOSS 直聘候选人智能提取工具 v2.9.1 [{mode_text}{greet_text}]")
    print("="*50)

    # 清空 candidates_all.json（如果指定 --clear）
    if args.clear and os.path.exists(CANDIDATES_PATH):
        if args.keep_greeted:
            # 保留已打招呼的候选人
            candidates_all = load_candidates_all()
            kept = [c for c in candidates_all if c.get('greet_sent')]
            kept_count = len(kept)
            removed = len(candidates_all) - kept_count
            if kept_count > 0:
                save_candidates_all(kept)
            else:
                os.remove(CANDIDATES_PATH)
            print(f"已清空 candidates_all.json（保留 {kept_count} 条已打招呼记录，删除 {removed} 条）")
        else:
            os.remove(CANDIDATES_PATH)
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
                if existing_page:
                    page = existing_page
                    print("使用 GUI 已连接的浏览器")
                else:
                    page = ChromiumPage()
                    print("\n浏览器已打开，请手动导航到候选人推荐页面")
                print("等待 3 秒...")
                time.sleep(_human_delay(3.0, 2.0))

                # 执行补打招呼
                success_count = 0
                fail_count = 0
                skip_count = 0

                try:
                    for i, c in enumerate(to_greet):
                        geek_id = c.get('geek_id')
                        name = c.get('name', '未知')
                        print(f"[{i+1}/{len(to_greet)}] 正在向 {name} 打招呼...", end=" ")
                        success, msg = send_greeting_on_list_page(page, geek_id, stop_event=stop_event, captcha_callback=captcha_callback)
                        if success:
                            # 检查是否真的成功（不是"可能需手动确认"）
                            if "可能需手动确认" in msg:
                                skip_count += 1
                                print(f"待确认：{msg}")
                            else:
                                success_count += 1
                                c['greet_sent'] = True
                                print("OK")
                        else:
                            fail_count += 1
                            print(f"失败：{msg}")
                            # 沟通次数上限是终端条件
                            if "上限" in msg or "次数" in msg:
                                print(f"\n{'='*60}")
                                print(f"⚠️  今日沟通次数已达上限！")
                                print(f"   BOSS 直聘已弹出升级套餐页面，后续打招呼不会真正发送")
                                print(f"   本次已成功打招呼：{success_count} 人")
                                print(f"{'='*60}")
                                break

                except KeyboardInterrupt:
                    print(f"\n\n检测到中断，保存当前进度...")
                    save_candidates_all(candidates_all)
                    # 生成 Excel 文件
                    if export_to_excel(candidates_all, CANDIDATES_XLSX_PATH):
                        print(f"[SAVE] Excel 文件：{CANDIDATES_XLSX_PATH.name}")
                    print(f"已保存 {success_count} 个成功打招呼的候选人状态")
                    raise

                print(f"\n补打招呼完成：成功 {success_count} 人，失败 {fail_count} 人，待确认 {skip_count} 人")
                print(f"已更新 candidates_all.json")

        print("\n--- 浏览器保持打开 ---")
        return  # 补打招呼模式结束，直接返回

    page = None
    all_candidates = []  # 保存所有岗位的候选人

    # 加载 AI 评估所需的 API 配置
    ai_api_config = getattr(args, 'api_config', None)
    ai_api_key = getattr(args, 'api_key', None)
    if getattr(args, 'ai_eval', False) and (ai_api_config is None or ai_api_key is None):
        try:
            with open('api_config.json', 'r', encoding='utf-8') as f:
                ai_api_config = json.load(f)
            from security import get_api_key
            ai_api_key = get_api_key(ai_api_config.get('api_provider', ''))
            if not ai_api_key:
                print("⚠️  AI 评估需要 API Key，但未配置，将跳过 AI 评估")
                args.ai_eval = False
            else:
                model_name = ai_api_config.get('model', 'unknown')
                print(f"AI 辅助评估已启用（模型：{model_name}）")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"⚠️  加载 API 配置失败：{e}，将跳过 AI 评估")
            args.ai_eval = False
    elif getattr(args, 'ai_eval', False):
        model_name = ai_api_config.get('model', 'unknown') if ai_api_config else 'unknown'
        print(f"AI 辅助评估已启用（模型：{model_name}）")

    try:
        if existing_page:
            page = existing_page
            print("使用 GUI 已连接的浏览器")
        else:
            print("正在连接到浏览器...")
            page = ChromiumPage()
            print("\n浏览器已打开，请手动导航到候选人推荐页面")
            print("例如：https://www.zhipin.com/web/chat/recommend")
        print("请确保页面完全加载后，等待 3 秒...")
        time.sleep(_human_delay(3.0, 2.0))

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
            # 多岗位间页面导航提示（第一个岗位之前不需要）
            if idx > 1:
                _show_job_navigation_prompt(idx, len(jobs_to_run), job_name, confirm_callback=confirm_callback)

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
                                               list_candidates=args.list_candidates,
                                               progress_callback=progress_callback,
                                               stop_event=stop_event,
                                               ai_eval=getattr(args, 'ai_eval', False),
                                               api_config=ai_api_config,
                                               api_key=ai_api_key,
                                               captcha_callback=captcha_callback)
            all_candidates.extend(candidates)

        # 最后生成 Excel 文件
        existing_all = load_candidates_all()
        excel_file = CANDIDATES_XLSX_PATH
        if export_to_excel(existing_all, excel_file):
            print(f"[SAVE] Excel 文件：{excel_file.name}")
        else:
            print("[WARN] Excel 导出失败")

    except StopRequested:
        print(f"\n\n⏹ 用户停止，保存当前进度...")
        existing_all = load_candidates_all()
        excel_file = CANDIDATES_XLSX_PATH
        if export_to_excel(existing_all, excel_file):
            print(f"[SAVE] Excel 文件：{excel_file.name}")
        print(f"已保存 {len(existing_all)} 个候选人的状态")

    except KeyboardInterrupt:
        print(f"\n\n检测到中断，保存当前进度...")
        # 生成 Excel 文件
        existing_all = load_candidates_all()
        excel_file = CANDIDATES_XLSX_PATH
        if export_to_excel(existing_all, excel_file):
            print(f"[SAVE] Excel 文件：{excel_file.name}")
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
