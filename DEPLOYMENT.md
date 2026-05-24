# BOSS 简历筛选器 - 部署说明

## 首次部署（新电脑）

### Windows 部署

#### 1. 复制文件
将 `dist/` 目录中的所有文件复制到目标电脑：
```
BOSS_ResumeFilter.exe
README.md
job_config.json
selectors.json
```

#### 2. 首次运行
双击 `BOSS_ResumeFilter.exe` 启动程序

### macOS 部署

#### 1. 下载安装
从 GitHub Release 下载 `BOSS_ResumeFilter.dmg`

#### 2. 安装应用
1. 双击打开 DMG 文件
2. 将 `BOSS_ResumeFilter.app` 拖拽到 Applications 文件夹
3. 推出 DMG

#### 3. 首次运行
1. 打开 Applications 文件夹
2. **右键**点击 `BOSS_ResumeFilter.app` → 选择「打开」
3. 在弹出的安全提示对话框中点击「打开」（绕过 Gatekeeper）
4. 后续启动可直接双击打开

#### 4. 自动更新
- macOS 版本支持自动更新
- 程序启动时会检查 GitHub Release
- 发现新版本后自动下载并替换 .app，完成后重启

### 配置 API Key（Windows 和 macOS 通用）
由于 API Key 加密存储在原电脑的系统钥匙串中，新电脑需要重新配置：

1. 进入「**岗位配置**」→「**API 配置**」
2. 选择服务商（如：通义千问）
3. 输入 API Key
4. 输入模型名称（如：qwen3.7-max）
5. 输入 Base URL
6. 点击「保存并添加到列表」按钮

### 验证配置
- 点击「测试连接」验证 API Key 是否有效
- 切换模型后，API Key 会自动从系统钥匙串读取

---

## API Key 安全说明

### 加密存储
- API Key 使用系统级加密（Windows DPAPI / macOS Keychain）
- 加密绑定到当前用户账户
- 按服务商统一管理（同一服务商的模型共享一个 Key）
- 配置文件 `api_config.json` 中不含明文 Key

### 跨电脑迁移
- ❌ **不支持**直接复制配置文件迁移 API Key
- ✅ **需要**在新电脑重新输入 API Key 并保存
- 🔒 这是安全特性，防止 API Key 被盗用

### 多电脑部署
如果需要在多台电脑使用：
1. 每台电脑首次运行时重新输入 API Key
2. API Key 会分别加密存储到各电脑的系统钥匙串
3. 后续使用无需重复输入

---

## 常见问题

### Q: 为什么不能直接复制 api_config.json？
A: API Key 加密存储在原电脑的系统钥匙串中，与用户账户绑定，复制配置文件到新电脑后无法解密。

### Q: 重新配置后，之前的筛选数据会丢失吗？
A: 不会。`candidates_all.json` 和 `candidates_all.xlsx` 独立存储，不受 API Key 影响。

### Q: 可以在公司内部多台电脑部署吗？
A: 可以。每台电脑首次运行时配置一次 API Key 即可。

---

## 技术支持
如遇问题，请检查：
1. API Key 是否正确
2. Base URL 是否正确
3. 网络连接是否正常
4. 模型服务是否可用
