"""
BOSS 直聘浏览器管理模块
负责浏览器启动、登录态管理、页面导航
"""
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright, Browser, Page
from dotenv import load_dotenv
import os

load_dotenv()


class BossBrowser:
    """BOSS 直聘浏览器管理器"""

    BASE_URL = "https://www.zhipin.com"
    LOGIN_URL = "https://login.zhipin.com/"

    def __init__(self, resume_save_dir: str = "./resumes"):
        self.browser: Browser | None = None
        self.page: Page | None = None
        self.resume_save_dir = Path(resume_save_dir)
        self.resume_save_dir.mkdir(parents=True, exist_ok=True)

        # 登录态存储路径
        self.storage_dir = Path("./.storage")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.cookie_file = self.storage_dir / "boss_cookies.json"

    async def launch(self, headless: bool = False) -> None:
        """启动浏览器（优先 Chrome，带独立用户数据目录）"""
        playwright = await async_playwright().start()

        # 确保用户数据目录唯一
        import uuid
        session_id = str(uuid.uuid4())[:8]
        user_data_dir = self.storage_dir / f"chromium_user_data_{session_id}"
        user_data_dir.mkdir(parents=True, exist_ok=True)

        browser_launched = False

        # 尝试 Chrome -> Edge
        for channel in ["chrome", "msedge"]:
            if browser_launched:
                break
            try:
                self.browser = await playwright.chromium.launch_persistent_context(
                    user_data_dir=str(user_data_dir),
                    headless=headless,
                    channel=channel,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-extensions",
                        "--disable-popup-blocking",
                    ],
                )
                print(f"[BossBrowser] 使用 {channel} 浏览器成功")
                browser_launched = True
            except Exception as e:
                print(f"[BossBrowser] {channel} 启动失败：{e}")
                continue

        if not self.browser:
            raise RuntimeError("无法启动浏览器，请确保安装了 Google Chrome 或 Microsoft Edge")

        # 创建新页面
        self.page = await self.browser.new_page()

        # 注入反检测脚本
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

    async def goto(self, url: str) -> None:
        """导航到指定页面"""
        if self.page:
            await self.page.goto(url, wait_until="networkidle")

    async def login_with_qr(self) -> bool:
        """
        扫码登录
        返回 True 表示登录成功
        """
        if not self.page:
            return False

        await self.goto(self.LOGIN_URL)

        # 等待扫码登录完成（最多等待 120 秒）
        print("请在 120 秒内完成扫码登录...")

        try:
            # 等待登录成功后的跳转
            await self.page.wait_for_url(self.BASE_URL, timeout=120000)
            await asyncio.sleep(2)  # 等待页面完全加载

            # 保存登录态
            await self._save_cookies()
            print("登录成功，已保存登录态")
            return True
        except asyncio.TimeoutError:
            print("登录超时，请重新启动")
            return False

    async def login_with_account(self, username: str, password: str) -> bool:
        """
        账号密码登录（可能触发验证码，建议用扫码）
        """
        if not self.page:
            return False

        await self.goto(self.LOGIN_URL)
        await asyncio.sleep(2)

        try:
            # 尝试找到账号密码登录入口
            # 注意：BOSS 直聘的登录表单选择器可能变化，需要定期维护
            await self.page.fill('input[type="text"], input[name="account"]', username)
            await self.page.fill('input[type="password"]', password)
            await self.page.click('button[type="submit"]')

            # 等待登录成功
            await self.page.wait_for_url(self.BASE_URL, timeout=30000)
            await self._save_cookies()
            return True
        except Exception as e:
            print(f"账号登录失败：{e}")
            return False

    async def _save_cookies(self) -> None:
        """保存 cookies"""
        if not self.page:
            return

        cookies = await self.page.context.cookies()
        with open(self.cookie_file, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

    async def load_cookies(self) -> bool:
        """加载保存的 cookies"""
        if not self.cookie_file.exists():
            return False

        try:
            with open(self.cookie_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)

            if self.browser:
                await self.browser.add_cookies(cookies)
                return True
        except Exception as e:
            print(f"加载 cookies 失败：{e}")

        return False

    async def is_logged_in(self) -> bool:
        """检查是否已登录"""
        if not self.page:
            return False

        # 检查页面是否包含登录用户信息
        await self.goto(self.BASE_URL)
        await asyncio.sleep(2)

        try:
            # 尝试查找用户头像或用户名元素
            await self.page.wait_for_selector('.user-avatar, .user-name', timeout=5000)
            return True
        except:
            return False

    async def search_candidates(
        self,
        keywords: str,
        city: str = "北京",
        experience: str | None = None,
        education: str | None = None,
    ) -> None:
        """
        搜索候选人

        Args:
            keywords: 搜索关键词（如职位名）
            city: 城市
            experience: 经验要求（如"3-5 年"）
            education: 学历要求（如"本科"）
        """
        if not self.page:
            return

        # 构建搜索 URL
        # BOSS 直聘的搜索 URL 格式示例：
        # https://www.zhipin.com/web/geek/job?query=Python&city=101010100
        search_url = f"{self.BASE_URL}/web/geek/job?query={keywords}"

        # 添加城市参数（需要城市代码，这里简化处理）
        # 实际使用时可能需要查询城市代码表

        await self.goto(search_url)
        await asyncio.sleep(2)

    async def download_resume(self, candidate_id: str, candidate_name: str) -> str | None:
        """
        下载候选人简历

        Args:
            candidate_id: 候选人 ID
            candidate_name: 候选人姓名

        Returns:
            保存的文件路径，失败返回 None
        """
        if not self.page:
            return None

        try:
            # 进入候选人详情页
            resume_url = f"{self.BASE_URL}/web/geek/job/apply/{candidate_id}"
            await self.goto(resume_url)
            await asyncio.sleep(2)

            # 点击下载简历按钮（选择器需要根据实际页面调整）
            download_btn = await self.page.query_selector(
                'button:has-text("下载简历"), .download-btn, [class*="download"]'
            )

            if download_btn:
                # 设置下载路径
                async with self.page.expect_download() as download_info:
                    await download_btn.click()

                download = await download_info.value
                save_path = self.resume_save_dir / f"{candidate_name}_{candidate_id}.pdf"
                await download.save_as(str(save_path))

                print(f"简历已保存：{save_path}")
                return str(save_path)
            else:
                print("未找到下载按钮")
                return None

        except Exception as e:
            print(f"下载简历失败：{e}")
            return None

    async def close(self) -> None:
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.page = None
