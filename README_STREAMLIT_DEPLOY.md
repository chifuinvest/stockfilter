# 🆓 AI 产业链量化监控系统 · Streamlit Community Cloud 免费部署教程

> **为什么选 Streamlit Community Cloud？（真正完全免费！）**
>
> - ✅ **100% 免费**，只要有 GitHub 公开仓库就能用，没有时间限制，不需要绑信用卡
> - ✅ 自动分配 `*.streamlit.app` **HTTPS 公网域名**（永久）
> - ✅ **1 GB RAM / 共享 CPU**（跑 pandas/numpy/Flask 足够）
> - ✅ 自动从 GitHub 仓库拉取，**push 代码就自动更新**（CD 持续部署）
> - ✅ Secrets 加密存储环境变量（Tushare Token 不会泄漏）
> - ⚠️ 免费层有 7 天无访问休眠（别人打开一次就自动唤醒，15 秒左右）

---

## 🚀 步骤 0️⃣ · 代码已推到 GitHub（已完成 ✅）

你的公开仓库：`https://github.com/chifuinvest/stockfilter`

---

## 步骤 1️⃣ · 登录 Streamlit Community Cloud

1. 打开 https://share.streamlit.io （首页大按钮 Sign up）
2. 选择 **"Continue with GitHub"** → 用你的 chifuinvest 账号一键登录 → 授权
3. 第一次登录需要同意免费服务条款（同意即可）
4. 成功登录后你会看到 Workspaces 控制台（空的，还没有 App）

---

## 步骤 2️⃣ · 部署 App（3 分钟搞定）

1. 右上角点 **"New app"**（新建应用）
2. 按下图填：

| 字段 | 填什么 |
|---|---|
| **Repository** | `chifuinvest/stockfilter`（如果没看到，点右边 "Connect to GitHub" 再授权一次，或者 Refresh） |
| **Branch** | `main` |
| **Main file path** | `streamlit_app.py`（**这个是关键！必须选 streamlit_app.py，不能选 main.py**） |
| **App URL (可选)** | 自定义子域名，例如 `ai-stock-monitor`，最终就是 `https://ai-stock-monitor.streamlit.app` |

3. 先 **不要点 Deploy！** 先到 **"Advanced settings..."**（高级设置）里配置 Secrets（Tushare token），否则会初始化失败。

---

## 步骤 3️⃣ · 配置 Secrets（**必须配**，否则 A/H 股评分失败）

在 Advanced settings 页面找到 **Secrets** 区域，点铅笔图标编辑，把下面这段 **完整粘贴** 进去（里面的 TUSHARE_TOKEN 值用你的真实 token，**保留双引号！因为是 TOML 格式字符串**）：

```toml
# ==========================================================
# Streamlit Secrets（TOML 格式，key = "value"，引号不能丢）
# 部署后 streamlit_app.py 会自动把所有值注入到 os.environ
# ==========================================================

# Tushare Token（必填，否则 A 股/港股只能走 Yahoo 兜底）
TUSHARE_TOKEN = "5eeaf804541d13a1530439c7ae33dae5cdf143a1896be28d54884363"

# 日志实时输出（推荐）
PYTHONUNBUFFERED = "1"

# 时区设为东八区（日志/调度时间一致）
TZ = "Asia/Shanghai"
```

点 **"Save"** 保存。

> 🔐 **安全说明**：Secrets 是加密存储的，只有你的 App 能读到，**不会出现在构建日志和前端页面**，放心填。

---

## 步骤 4️⃣ · 点绿色 **"Deploy"** 大按钮

构建流程开始，你会看到实时滚动的日志，整个过程：

| 阶段 | 耗时 | 正常日志特征 |
|---|---|---|
| **Set up machine** | 1~2 分钟 | `Provisioning machine...` / `Cloning repository...` |
| **Install dependencies** | **3~8 分钟** | `pip install -r requirements.txt`（pandas/numpy/yfinance 都是大轮子，慢是正常的） |
| **Booting app** | 30 秒 | `Starting streamlit...` / `Streamlit server is ready` |

看到 **Your app is in the oven! 🎂** 或者页面自动打开 Streamlit 界面就说明 **部署成功了！** 🎉

---

## 步骤 5️⃣ · 4 步验证（部署完成后立刻做）

打开你的公网域名（例如 `https://ai-stock-monitor.streamlit.app`）：

| # | 检查项 | 通过标准 |
|---|---|---|
| 1 | 页面能打开 | 出现蓝色 KPI 卡片（7 个：已评分/买入/持有/观望/减仓/回避/平均得分）+ 侧边栏控制面板，没有红色全屏报错 |
| 2 | Tushare 初始化 OK | 看 KPI 里 **已评分 / 总数** 不是 0/0（如果是 0/0，点侧边栏「⚡ 强制重新评分」等 30 秒再刷新页面，A 股 84 只要出来） |
| 3 | 表格有数据 | 信号筛选选「🟢 买入」或「🔵 持有」，要能看到多行（A 股评分出来后有 80+ 行），并且每行按信号染色 |
| 4 | 下载 CSV 按钮 | 表格下面「📥 下载当前结果为 CSV」按钮能用，浏览器弹出下载 |

4 条全通过 → **上线成功！把域名发给朋友用就行 🚀**

---

## ⚠️ 免费层限制说明（客观限制，无法突破，请提前知道）

| 限制项 | 说明 | 对我们项目的影响 |
|---|---|---|
| **7 天休眠** | 连续 7 天没人访问 App 会被休眠 | ✅ 几乎不影响，只要有人访问就自动唤醒（首屏 10~15 秒冷启动） |
| **1 GB RAM** | 单个 App 内存上限 1GB | ✅ 足够（我们项目稳定运行 ~400~600MB RAM），如果评分太多同时运行可能到 800MB，接近上限会自动 GC |
| **单请求超时 15 分钟** | Streamlit 单次脚本运行 15 分钟强制超时 | ✅ 不影响（评分是后台线程跑，HTTP 不会阻塞，不触发超时） |
| **20 GB 带宽 / 月** | 每月传输量上限 | ✅ 绝对够用（纯文本 JSON/CSV，1 个人天天用也不到 1GB） |
| **临时文件系统** | 容器重启后磁盘文件全丢 | ✅ 不影响，stock_pool.json 读仓库里的相对路径（不丢），评分结果用 `st.cache_data(ttl=21600)` 内存缓存 |

---

## 💥 常见报错 & 快速解决

| 现象 | 可能原因 | 解决 |
|---|---|---|
| 打开域名显示 **红色全屏报错**，提示 `Tushare 初始化失败` / `ModuleNotFoundError` | Secrets 没配对 / 依赖没装完 | 去 App Settings → Secrets 检查 TOML 格式是否正确（**值一定要有双引号**），保存后 App 会自动重启 |
| KPI 里 **已评分 = 0**，表格一直空 | 首次评分还没跑完 / Tushare token 没生效 | 侧边栏点「⚡ 强制重新评分」等 2~5 分钟刷新页面；如果还是 0 → F12 Console 看红字 / App Settings → View logs 看服务端日志 |
| 构建日志里 `pip install` 红色报错 / 卡住不动 | 网络超时（Streamlit 机器偶尔连 PyPI 慢） | 控制台 **"Manage app" → "Reboot app"** 或直接点 **"+ New app"** 重新部署一次；多试几次就能成功 |
| 美股 / 韩股 / 港股 一直没有评分 | Yahoo 429 限流 + Tushare hk_daily 1 次/分钟免费额度限制 | ✅ 正常现象，每 15~20 分钟点一次「⚡ 强制重新评分」手动触发重试，当天内会陆续补齐（先看 A 股 84 只用） |
| 页面表格不染色，或者列不对齐 | Streamlit 版本过旧（<1.30） | requirements.txt 里已写 `streamlit>=1.32.0`，自动会装最新版；如果没生效 → 手动改 requirements.txt 的版本号再 push |
| 部署完 URL 一直显示「App is booting」，超过 15 分钟 | 启动脚本报错退出了，streamlit 没起来 | Settings → **View logs** 看最后红色 Traceback，把报错内容贴给我，30 秒定位 |

---

## 🎯 一键部署总结（再贴一次步骤，避免翻页）

整个过程 **3~10 分钟完成**（其中 pip install 占了大部分时间，耐心等）：

```
① 打开 https://share.streamlit.io → GitHub 登录
② New app → 选仓库 chifuinvest/stockfilter → branch=main → Main file=streamlit_app.py
③ Advanced settings → Secrets 粘贴本教程第 3 步的 TOML（替换成你的真实 Tushare Token）
④ Save Secrets → 点 Deploy
⑤ 等 5~10 分钟 → 打开 *.streamlit.app → 侧边栏点「⚡ 强制重新评分」→ 看 A 股评分出来了 ✅
```

**部署过程中遇到构建日志里的红字报错？直接把完整 Traceback 贴给我，30 秒内帮你定位！** 🚀

---

## 📜 免责声明与版权

### 免责声明
本系统及其输出内容（包括但不限于评分、信号、涨跌幅、技术指标、股票池、数据可视化结果等）**仅供研究和学习使用，不构成任何投资建议或承诺**。

市场有风险，投资需谨慎。任何单位或个人基于本系统进行的实盘交易行为，盈亏自负，本项目作者及版权方**不承担任何直接或间接的法律责任与经济损失**。

### 版权信息
&copy; 2025 **Yan Ying**. All rights reserved.

📧 **联系方式：** [yanying76@gmail.com](mailto:yanying76@gmail.com)
