"""Shared constants for BOSS resume screening."""

# ========== 评分模型参数 ==========
SCORE_BASE = 25                    # 基础分
SCORE_SKILL_MAX = 50               # 技能匹配上限
SCORE_EXP_MAX = 15                 # 经验超额上限
SCORE_EDU_MAX = 10                 # 学历加分上限

# ========== 评分阈值 ==========
SCORE_THRESHOLD_PASS = 55          # 通过筛选（待定及以上）
SCORE_THRESHOLD_RECOMMEND = 65     # 推荐
SCORE_THRESHOLD_STRONG = 75        # 强烈推荐

# ========== 非统招学历关键词 ==========
NON_REGULAR_EDU = [
    "自考", "成教", "函授", "夜大", "网络教育", "继续教育", "非统招",
    "专升本", "电大", "远程教育", "成人高考", "成人教育", "脱产", "业余",
]

# ========== 中文数字映射 ==========
CHINESE_NUMERALS = {
    '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
}

# ========== HTTP ==========
USER_AGENT = "BossResumeFilter/1.0"

# ========== LLM API 参数 ==========
LLM_MAX_TOKENS = 256               # 最大返回 token 数
LLM_TEMPERATURE = 0.3              # 采样温度（低 = 更确定）
LLM_TIMEOUT = (8, 30)              # HTTP 超时（连接秒, 读取秒）
LLM_MAX_RETRIES = 3                # API 调用最大重试次数

# ========== 自动更新超时（秒） ==========
UPDATE_TIMEOUT_GITEE = 8           # Gitee latest.json 请求
UPDATE_TIMEOUT_GITHUB = 10         # GitHub Releases API 请求
UPDATE_TIMEOUT_DOWNLOAD = 30       # 文件下载（含国内镜像）
UPDATE_TIMEOUT_CHANGELOG = 8       # 远端 CHANGELOG.md 获取
UPDATE_TIMEOUT_GIT_PULL = 30       # git pull subprocess 超时

# ========== 城市列表 ==========
# 中国主要城市列表（按长度降序，优先匹配长名如"哈尔滨"）
MAJOR_CITIES = sorted([
    '北京', '上海', '广州', '深圳', '杭州', '南京', '成都', '武汉',
    '西安', '苏州', '重庆', '长沙', '合肥', '郑州', '天津', '济南',
    '青岛', '厦门', '福州', '珠海', '东莞', '无锡', '宁波', '大连',
    '沈阳', '昆明', '贵阳', '南宁', '海口', '南昌', '太原', '长春',
    '哈尔滨', '石家庄',
], key=len, reverse=True)
