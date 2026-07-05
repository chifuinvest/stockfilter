# 🚀 AI 产业链量化监控系统 · Railway 一键部署教程

> **最快上线方案 A（推荐）：** 推代码到 GitHub 后，直接点下面的按钮，5 分钟自动部署完成，不用手动配环境变量

---

## 🌟 方案 A · 一键点按钮上线（90% 用户选这个）

> 前置条件：先把代码 push 到 GitHub（【步骤 0️⃣】完成后，仓库必须**非空**，否则 Railway 找不到代码 → 会 404！）
>
> 把下面模板 URL 里的 `<YOUR_GITHUB_USERNAME>` 替换成你自己的 GitHub 用户名，**整个 URL 复制到浏览器地址栏**（注意是 /new?template= 开头），回车即可：

```text
https://railway.app/new?template=https%3A%2F%2Fgithub.com%2F<YOUR_GITHUB_USERNAME>%2Fstockfilter&plugins=&envs=TUSHARE_TOKEN,PYTHONUNBUFFERED,HOME,TZ&envDescription=Tushare%E4%B8%8E%E7%B3%BB%E7%BB%9F%E7%8E%AF%E5%A2%83%E5%8F%98%E9%87%8F%E8%AF%B4%E6%98%8E&envLink=https%3A%2F%2Fgithub.com%2F<YOUR_GITHUB_USERNAME>%2Fstockfilter%2Fblob%2Fmain%2F.env.example
```

举个例子，你的 GitHub 用户名是 `chifuinvest`，**直接打开下面这个链接就能用**（复制粘贴到浏览器）：

```
https://railway.app/new?template=https%3A%2F%2Fgithub.com%2Fchifuinvest%2Fstockfilter&plugins=&envs=TUSHARE_TOKEN,PYTHONUNBUFFERED,HOME,TZ&envDescription=Tushare%E4%B8%8E%E7%B3%BB%E7%BB%9F%E7%8E%AF%E5%A2%83%E5%8F%98%E9%87%8F%E8%AF%B4%E6%98%8E&envLink=https%3A%2F%2Fgithub.com%2Fchifuinvest%2Fstockfilter%2Fblob%2Fmain%2F.env.example
```

点进去后：
1. Railway 会自动识别本仓库的 Procfile/railway.json/nixpacks.toml，并预填 4 个环境变量（TUSHARE_TOKEN、PYTHONUNBUFFERED、HOME、TZ）
2. 你只需要：
   - 把 `TUSHARE_TOKEN` 的值填进去（你的 Token：5eeaf804541d13a1530439c7ae33dae5cdf143a1896be28d54884363）
   - `PYTHONUNBUFFERED` 填 `1`
   - `HOME` 填 `/app`
   - `TZ` 填 `Asia/Shanghai`
3. 点 **"Deploy"** 绿色大按钮，5~10 分钟后自动上线！

---

## 方案 B · 标准手动部署（按钮找不到或想细调配置时用）

> **目标：5 分钟上线，全程网页操作，不用 SSH，不用命令行**
>
> 部署前需要准备：
> 1. 你的 GitHub 账号（代码已经 commit 到本地，记得 `git push` 到 GitHub）
> 2. 你的 Railway 账号（https://railway.app，可用 GitHub 一键登录）
> 3. 你的 Tushare Token（填到环境变量即可，不会公开）
> 4. 支付方式（首次使用 Railway 新用户有 **$5 免费额度**，跑这个项目一个月大约 $2~$5，小流量用不完免费额度）

---

## 步骤 0️⃣ · 把本地代码推到 GitHub（若已完成可跳过）

在本机 PowerShell 执行下面 4 行，把 `<你的GitHub用户名>` 换成你自己的：

```powershell
cd C:\Users\Bart\Documents\trae_projects\stockfilter

# 如果还没在 GitHub 创建仓库，先去 https://github.com/new 建一个空仓库
# 建好后执行：
git remote add origin https://github.com/<你的GitHub用户名>/stockfilter.git
git branch -M main
git push -u origin main
```

推完后在 GitHub 打开仓库，确认能看到 `Procfile`、`railway.json`、`nixpacks.toml` 这 3 个文件，就可以继续了。

---

## 步骤 1️⃣ · 打开 Railway 控制台，新建项目

1. 打开 https://railway.app/new （用 GitHub 登录）
2. 选 **"Deploy from GitHub repo"**（从 GitHub 仓库部署）
3. 点击 **"Configure GitHub App"**，授权 Railway 访问你的 `stockfilter` 仓库（可以选"Only select repositories"只授权这一个仓库，更安全）
4. 回到 Railway，选中你刚授权的 `stockfilter` 仓库
5. 先**不要点"Deploy"！** 我们先配置环境变量（见下一步），否则 Tushare 会初始化失败

---

## 步骤 2️⃣ · 添加环境变量（**必须配，否则 90% 概率部署失败**）

点击刚才选中的仓库卡片右下角的 **"Configure"** 小齿轮 → 选 **"Variables"** 标签页，一条一条 Add 下面 5 条：

| 变量名 | 值 | 是否必填 | 说明 |
|---|---|---|---|
| `TUSHARE_TOKEN` | `你的56位TushareToken` | ✅ **必填** | 你之前的 Token：`5eeaf804541d13a1530439c7ae33dae5cdf143a1896be28d54884363` |
| `PORT` | **留空，不填** | — | Railway 会自动注入随机端口，不要自己写 |
| `PYTHONUNBUFFERED` | `1` | ⭐ 推荐 | 让日志实时输出，不被缓冲，便于排查部署问题 |
| `HOME` | `/app` | ⭐ 推荐 | Railway 容器默认就是 `/app`，显式声明可确保 Tushare/yfinance 写路径不崩 |
| `TZ` | `Asia/Shanghai` | ⭐ 推荐 | 设定时区为东八区，日志时间/调度和国内一致 |

> 🔐 **安全提醒**：Railway 的 Variables 是加密存储的，只有你的项目能读到，**不会出现在构建日志或公开页面**，放心填。

---

## 步骤 3️⃣ · 启动构建部署

1. 回到 Railway 项目的 **"Settings"** 标签页，确认：
   - **Root Directory** 留空（仓库根目录）
   - **Builder** 自动是 **Nixpacks**（如果不是，改成 Nixpacks）
2. 回到 **"Deployments"** 标签页，点击 **"Deploy"**（或点击右上角 "+ New Deployment" → "Deploy latest commit"）
3. 构建开始！你会看到实时滚动的日志，整个过程大约 5~10 分钟（pandas/numpy/yfinance 都是大轮子，慢是正常的）

### 构建过程中会经历的 3 个阶段（别慌，耐心等）
| 阶段 | 耗时 | 正常日志特征 |
|---|---|---|
| **Setup** | 1~2 min | `Fetching nixpkgs` / `Installing python311` |
| **Install** | 3~6 min | `pip install -r requirements.txt` 一堆 Successfully installed |
| **Deploy** | 1~3 min | `Starting PIDs` / `Booting worker with pid` |

---

## 步骤 4️⃣ · 分配公网域名（Railway 免费子域名）

1. 构建成功后（卡片显示绿色 **"Deployed"** / **"Active"**），点击卡片 → 选 **"Settings"** 标签页
2. 找到 **"Networking"** → **"Public Networking"** → 点击 **"Generate Domain"**
3. Railway 会给你一个免费域名，类似 `https://stockfilter-production-xxxx.up.railway.app`（也可以点域名后面的编辑换成自定义名字）
4. **⭐ 重要**：点击域名右边的 **📋 Copy** 复制下来，下一步要用

> 高级用法：如果你有自己的域名（比如 `ai-stock.yourdomain.com`），在同一页面点 **"Add Custom Domain"**，按提示去域名服务商加一条 CNAME 记录即可自动签发 HTTPS 证书。

---

## 步骤 5️⃣ · 验证部署成功（4 步检查清单）

打开刚才复制的 Railway 公网域名，按顺序检查：

- **✅ 检查 1：页面能打开**
  - 访问首页 `https://xxxx.up.railway.app/`，看是否出现了蓝色 KPI 卡片（买入/持有/观望/减仓回避）和股票表格
  - 如果是 502 Bad Gateway → 等 30 秒再刷新（gunicorn 还在启动 Worker）

- **✅ 检查 2：Tushare 初始化成功**
  - Railway Dashboard → 项目卡片 → **"Deployments"** → 点当前部署的 **"View Logs"** 按钮
  - 日志里搜关键词 `Tushare token 初始化成功` → ✅ 有说明环境变量配对了
  - 如果看到 `Tushare 初始化失败: Permission denied` 或别的错误 → 检查 Variables 里 TUSHARE_TOKEN 的值是否对（别多复制空格）

- **✅ 检查 3：接口返回评分**
  - 浏览器新开标签页访问 `https://xxxx.up.railway.app/api/scores`
  - 看返回 JSON 里 `scored_count > 0`、`results` 数组里至少有 80+ 条 A 股 → ✅ 说明打分引擎工作正常
  - 如果 `scored_count = 0` → 先别急，点页面右上角 🔄 **刷新** 按钮触发一次评分，等 30 秒再查 /api/scores

- **✅ 检查 4：手动刷新按钮能用**
  - 回到首页点右上角 🔄 **刷新** → 页面右上角进度条会开始动
  - 等 20~40 秒，看进度条里 `ok / done` 是否在涨（A股涨得最快，港股/美股可能因为限流退避慢一些）

以上 4 条都 ✅ 就说明部署完成了！🎉 把域名发给朋友直接用就行。

---

## 步骤 6️⃣ · 查看美股/港股评分何时补全（Yahoo 限流的客观限制）

部署到云端后，美股/韩股/港股面临和本地一样的外部限流：

| 市场 | 数据源 | 客观配额 | 预计补齐时间 |
|---|---|---|---|
| 🇨🇳 A股 | Tushare daily | 200次/分钟（用不完） | ✅ 部署后 2 分钟内 84 只全部完成 |
| 🇭🇰 港股 | Tushare hk_daily | **1次/分钟 + 5次/天**免费 | ⏳ 约 20 分钟起（代码里自动 sleep 65s 等窗口） |
| 🇺🇸 美股 | Yahoo Finance | 429 限流（自动指数退避） | ⏳ 部署当天（15~90 分钟内随退避结束陆续补齐） |
| 🇰🇷 韩股 | Yahoo Finance | 同上 | ⏳ 同上 |

> **小技巧**：部署后每隔 15~20 分钟去点一次 🔄 **刷新**，能更快触发退避结束后的新一轮请求。

---

## 💥 常见报错 & 快速解决方案

| 现象 | 可能原因 | 解决 |
|---|---|---|
| 打开域名显示 **Application Error** / **502** | gunicorn 没启动起来，Worker 超时被杀 | 1. 看 Logs 里的 Traceback；2. 确认 Procfile 存在；3. 确认 railway.json `startCommand` 正确 |
| 部署日志里 `ModuleNotFoundError: No module named 'flask'` | requirements.txt 没读到或构建失败 | 重开一次 Deploy → 确认 Install 阶段 `pip install -r requirements.txt` 成功 |
| 日志里 `Tushare 初始化失败` | Variables 没配 TUSHARE_TOKEN 或复制多了空格 | 去 Variables 编辑 TUSHARE_TOKEN，保存后自动触发重新部署 |
| 部署日志 `port already in use` / app 启动后立刻 Crash | 启动命令里硬写了 `5000` 端口 | 检查不要改 Procfile，用默认的 `$PORT` 变量 |
| 评分触发就 **504 Gateway Timeout** | 首次评分耗时过长（>300s）触发 gunicorn 超时 | 已经在 Procfile 里设 `--timeout 300`（5 分钟）了，如果仍超时 → 先访问首页让它后台评分，等 2 分钟再查 /api/scores（不用等 HTTP 返回） |
| 打开页面股票表格 **一直 loading** | 前端轮询 /api/scores 返回空 | 点一次右上角 🔄 刷新 → 等 30 秒再刷新页面 |
| 美股一只都没有评分 | Yahoo 429 限流中 | 等退避窗口过去（看 Railway Logs 关键字 `[YF 退避] 至 xx:xx`），到点再点一次 🔄 刷新 |

---

## 💰 成本估算（参考）

Railway 的定价按"使用量（CPU + 内存 + 网络）"计费，这个项目是中等内存消耗（pandas/numpy 常驻 ~500MB RAM，CPU 大部分时间空闲，只有拉行情/算分时会短暂冲高）：

| 实例规格 | 月成本估算 | 备注 |
|---|---|---|
| **Developer（默认，1 CPU / 1G RAM）** | ~$2~$5 / 月 | 新用户 $5 免费额度可用 1~2 个月 |
| Hobby（2 CPU / 4G RAM） | ~$10 / 月 | 拉行情/算分时更流畅 |

> **省钱小技巧**：非公开分享期间，去项目 Settings → **Sleep Application** 开起来（15 分钟无请求自动休眠，有请求自动唤醒），可以省一半以上费用。缺点是第一次请求要等 ~15 秒唤醒。

---

## 🎯 一键部署命令速查（CLI 达人版）

如果你装了 Railway CLI（`npm i -g @railway/cli`），上面的步骤可以压缩成 4 条命令：

```bash
# 1) 登录（浏览器授权）
railway login

# 2) 新建项目 + 关联本地
cd C:\Users\Bart\Documents\trae_projects\stockfilter
railway init

# 3) 写环境变量（CLI 方式）
railway variables set TUSHARE_TOKEN=你的token PYTHONUNBUFFERED=1 TZ=Asia/Shanghai HOME=/app

# 4) 推代码 + 启动部署
railway up -d
```

完成后 `railway open` 直接在浏览器打开公网域名。

---

**祝部署顺利！有任何报错直接把 Railway Deployments 里的错误日志贴出来我帮你定位。** 🚀

---

## 📜 免责声明与版权

### 免责声明
本系统及其输出内容（包括但不限于评分、信号、涨跌幅、技术指标、股票池、数据可视化结果等）**仅供研究和学习使用，不构成任何投资建议或承诺**。

市场有风险，投资需谨慎。任何单位或个人基于本系统进行的实盘交易行为，盈亏自负，本项目作者及版权方**不承担任何直接或间接的法律责任与经济损失**。

### 版权信息
&copy; 2025 **Bart**. All rights reserved.

📧 **联系方式：** [yanying76@gmail.com](mailto:yanying76@gmail.com)
