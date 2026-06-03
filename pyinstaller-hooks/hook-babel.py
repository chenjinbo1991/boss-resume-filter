"""
自定义 PyInstaller hook: 只收集 babel 实际需要的 locale 数据。

tkcalendar 只用 babel.dates 的日期格式化，实际运行只需要：
- zh_CN (中文简体)
- en_US (英文)
- global.dat (全局数据)

不收集全部 1086 个 locale .dat 文件，减少约 10MB 体积。
"""
from PyInstaller.utils.hooks import collect_data_files


# 只收集 global.dat，不收集 locale-data 目录
datas = collect_data_files('babel', include_only=['global.dat', 'py.typed'])
