"""
BOSS 职位获取脚本（独立运行，避免与 Streamlit 事件循环冲突）
"""
import asyncio
import json
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置环境变量，确保 playwright 能找到浏览器
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")

from src.boss.browser import BossBrowser


async def fetch_jobs():
    """获取职位列表并输出 JSON"""
    browser = BossBrowser()
    try:
        await browser.launch(headless=False)

        # 等待用户扫码登录 (最多 120 秒)
        print("请在 120 秒内扫码登录 BOSS 直聘...")
        logged_in = False
        for i in range(24):
            await asyncio.sleep(5)
            logged_in = await browser.is_logged_in()
            if logged_in:
                print("登录成功!")
                break

        if not logged_in:
            print("ERROR: 登录超时")
            return

        # 进入职位管理页面
        print("正在进入职位管理页面...")
        await browser.goto("https://www.zhipin.com/web/geek/job/")
        await asyncio.sleep(8)

        # 使用 JavaScript 提取职位信息
        page = browser.page
        if not page:
            print("ERROR: 页面对象为空")
            return

        job_data = await page.evaluate("""
            () => {
                const jobs = [];
                // 尝试多种选择器
                const selectors = [
                    '.job-card',
                    '.position-item',
                    '[class*="job-item"]',
                    '[data-testid="job-item"]',
                    '.job-list > div',
                    '.position-list > div'
                ];

                let items = [];
                for (const sel of selectors) {
                    items = document.querySelectorAll(sel);
                    if (items.length > 0) {
                        console.log("Found with selector:", sel, "count:", items.length);
                        break;
                    }
                }

                // 如果还没找到，尝试更通用的选择器
                if (items.length === 0) {
                    const allDivs = document.querySelectorAll('div');
                    items = Array.from(allDivs).filter(div => {
                        const text = div.textContent.toLowerCase();
                        return text.includes('招聘') || text.includes('职位') || text.includes('管理');
                    }).slice(0, 20);
                }

                items.forEach((item, idx) => {
                    const titleEl = item.querySelector('h3, .job-title, a[href*="/job/"], [class*="title"]');
                    const title = titleEl?.textContent?.trim() || '';

                    if (title && title.length < 50) {  // 过滤太长的标题
                        const link = item.querySelector('a[href*="/job/"]')?.href || '';
                        const match = link.match(/(\\d+)/);
                        const id = match ? match[1] : `job_${idx}`;

                        jobs.push({
                            job_id: id,
                            job_name: title,
                            department: item.querySelector('.department, .dept')?.textContent?.trim() || '',
                            city: item.querySelector('.city, .work-city')?.textContent?.trim() || '',
                            salary: item.querySelector('.salary, .pay')?.textContent?.trim() || '',
                            experience: item.querySelector('.experience, .exp')?.textContent?.trim() || '',
                            education: item.querySelector('.education, .edu')?.textContent?.trim() || '',
                            status: item.querySelector('.status, .job-status')?.textContent?.trim() || '招聘中',
                            description: '',
                            requirements: ''
                        });
                    }
                });
                console.log("Extracted jobs:", jobs.length);
                return jobs;
            }
        """)

        # 输出 JSON 结果
        output = {
            "status": "success",
            "jobs": job_data if job_data else [],
            "count": len(job_data) if job_data else 0
        }

        print("RESULT:" + json.dumps(output, ensure_ascii=False))

    except Exception as e:
        import traceback
        output = {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print("RESULT:" + json.dumps(output, ensure_ascii=False))
    finally:
        await browser.close()


if __name__ == "__main__":
    # 使用标准 ProactorEventLoop
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(fetch_jobs())
