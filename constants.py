"""Shared constants for BOSS resume screening."""

# ========== 评分阈值 ==========
SCORE_THRESHOLD_PASS = 55          # 通过筛选（待定及以上）
SCORE_THRESHOLD_RECOMMEND = 65     # 推荐
SCORE_THRESHOLD_STRONG = 75        # 强烈推荐

# ========== 城市列表 ==========
# 中国主要城市列表（按长度降序，优先匹配长名如"哈尔滨"）
MAJOR_CITIES = sorted([
    '北京', '上海', '广州', '深圳', '杭州', '南京', '成都', '武汉',
    '西安', '苏州', '重庆', '长沙', '合肥', '郑州', '天津', '济南',
    '青岛', '厦门', '福州', '珠海', '东莞', '无锡', '宁波', '大连',
    '沈阳', '昆明', '贵阳', '南宁', '海口', '南昌', '太原', '长春',
    '哈尔滨', '石家庄',
], key=len, reverse=True)
