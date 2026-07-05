# 🇨🇳 AI 产业链量化监控系统 · Zeabur 一键部署教程

> **为什么选 Zeabur？** 国内团队开发 → 国内访问速度最快（海外平台 RENDER/RAILWAY 国内打开卡半天）
> 中文界面 + 微信/支付宝付款 + 客服响应快，**免费层额度个人用足够**
>
> 部署全程网页点按钮，不用命令行，不用 SSH，5~10 分钟上线

---

## 🌟 方案 A · 一键直达部署页面（最快，推荐）

> 前置条件：代码已推到 GitHub（已完成 ✅，仓库 `https://github.com/chifuinvest/stockfilter`）

**直接复制下面这个链接，粘贴到浏览器（Chrome/Edge）地址栏，回车即可：**

```
https://zeabur.com/new?repository=chifuinvest%2Fstockfilter&branch=main&type=fromTemplate&name=ai-stock-monitor
```

如果上面链接打不开（Zeabur 版本更新 URL 格式可能微调），用下面**方案 B 手动流程**（效果完全一样，只是多点点按钮）。

---

## 🛡️ 方案 B · 标准手动流程（链接不通时用）

1. 打开 https://zeabur.com ，用 GitHub 账号一键登录（右上角"登录"→"使用 GitHub 登录"→ 授权）
2. 登录后点右上角 **"+ 新建项目"**
3. 选 **"从 GitHub 仓库部署"**
4. 授权 Zeabur 访问你的 GitHub（选"Only select repositories"→ 勾上 `chifuinvest/stockfilter` → 点"Install"）
5. 选中 `chifuinvest/stockfilter` 仓库，Branch 选 `main`，Framework 自动识别（应该会识别为 **Nixpacks / Python**）
6. 到 **Variables / 环境变量** 页面，按下面表格填 4 个变量（Zeabur 读取到了我们仓库根目录的 `zeabur.yaml`，变量名已经帮你填好！只需填值）：

| 变量名 | 值 | 必填 |
|---|---|---|
| `TUSHARE_TOKEN` | `5eeaf804541d13a1530439c7ae33dae5cdf143a1896be28d54884363` | ✅ **必填，A股/港股评分都靠它** |
| `PYTHONUNBUFFERED` | `1`（已默认填好） | ⭐ 推荐 |
| `HOME` | `/app`（已默认填好） | ⭐ 推荐 |
| `TZ` | `Asia/Shanghai`（已默认填好） | ⭐ 推荐 |

7. 点 **"部署 / Deploy"**

---

## ⏳ 构建与启动时间（耐心等）

Zeabur 会自动：
1. 拉取 GitHub 代码 → **30 秒**
2. `pip install -r requirements.txt` 装依赖（pandas/numpy/yfinance 都是大轮子）→ **3~8 分钟**（看网络情况，慢正常）
3. 启动 gunicorn（2 Workers + 4 Threads + 300s 超时）→ **30 秒**

你会看到实时滚动的构建日志，看到 `✅ Deployment successful` 或 `gunicorn Booting worker with pid` 就说明启动成功了！

---

## 🌐 分配国内 HTTPS 公网域名（免费）

1. 部署成功后，点项目卡片 → 选 **"网络 / Networking"**
2. 点 **"生成域名 / Generate Domain"** → 获得免费 `*.zeabur.app` 域名，例如 `https://ai-stock-monitor-abc123.zeabur.app`
3. **⭐ 高级**：如果你有自己的域名（比如 `ai-stock.你的域名.com`），点 **"绑定自定义域名 / Bind Custom Domain"** → 按提示去域名服务商加一条 CNAME 记录，Zeabur 自动签发 HTTPS 证书（免费，自动续期）

---

## ✅ 部署成功 4 步验证清单（照做就行）

打开分配到的公网域名（例 `https://xxx.zeabur.app`），按顺序检查：

| # | 检查项 | 怎么做 | 通过标准 |
|---|---|---|---|
| 1 | 首页能打开 | 浏览器直接访问域名 | 出现蓝色 KPI 卡片（买入/持有/观望/减仓回避）和股票表格，**不是 404/502/504** |
| 2 | Tushare 初始化成功 | 项目卡片 → **"日志 / Logs"** → 搜关键词 `Tushare` | ✅ 看到 `Tushare token 初始化成功`，没有 `Permission denied` 报错 |
| 3 | /api/scores 有评分 | 打开 `https://<你的域名>/api/scores` | JSON 里 `scored_count > 0`（A股 84 只要有） |
| 4 | 手动刷新按钮能用 | 回到首页，点右上角 🔄 **"刷新"** | 进度条开始动，`ok/done` 数字在涨（A股最快，港股/美股因限流慢一些） |

4 条全通过 → **部署成功！🎉 把域名发给朋友用就行**

---

## 💰 费用说明（2025 年中参考，以 Zeabur 官网为准）

| 套餐 | 价格 | RAM | CPU | 适合 |
|---|---|---|---|---|
| **免费额度（新用户）** | 0 元，7 天 Pro 试用 | 512MB ~ 1GB | 共享 | 测试/小项目 |
| 学生认证 | 长期免费额度 | 512MB | 共享 | 学生党（需提供教育邮箱/学信网） |
| Hobby 档 | ~¥20~50/月 | 1GB | 1 vCPU | 个人长期使用 |
| Pro 档 | ~¥80/月 | 2GB+ | 共享/独享 | 团队/生产使用 |

> **省钱小技巧**：测试完不想续费 → 在 **"项目设置"** → **"停机 / Suspend"** 就不扣费了，代码和配置都保留，下次点"开机"直接恢复。

---

## 💥 常见报错 & 快速解决

| 现象 | 可能原因 | 解决 |
|---|---|---|
| 打开域名显示 **502 Bad Gateway / 504 Gateway Timeout** | gunicorn Worker 还没启动完，或首次评分超时被杀 | 等 30~60 秒再刷新；如果一直超时 → Variables 加 `GUNICORN_CMD_ARGS="--timeout 600"` 把超时加到 10 分钟 |
| 构建日志里 `ModuleNotFoundError: No module named 'flask'` | 依赖没安装成功 | 重新点 **"Redeploy"** 重试一次；看 Install 阶段有没有红色报错（网络超时） |
| 日志里 `Tushare 初始化失败` / `Permission denied` | Variables 里 TUSHARE_TOKEN 没填对（多了空格/少了字符） | Variables 里删掉该变量 → 重新 Add（值两边不要有空格/换行），保存后自动重新部署 |
| A股有评分，但美股/港股一直没评分 | Yahoo 限流（429）+ Tushare hk_daily 1次/分钟限制 | 正常现象，等后台退避结束（10~60 分钟），每 15~20 分钟点一次 🔄 刷新手动触发补齐 |
| 页面一直转圈（loading），但 /api/scores 有数据 | 前端 JS 读取字段不匹配 | 按 F12 打开开发者工具 → Console 看有没有红色报错 → 把报错内容贴给我 |

---

## 🎯 一键部署 URL（chifuinvest 专用，再贴一次）

把下面整个 URL 复制粘贴到浏览器地址栏（和方案 A 效果一致）：

```
https://zeabur.com/new?repository=chifuinvest%2Fstockfilter&branch=main&type=fromTemplate&name=ai-stock-monitor
```

---

**部署遇到红色报错？把构建日志里的红字发给我，30 秒内帮你定位！** 🚀

---

## 📜 免责声明与版权

### 免责声明
本系统及其输出内容（包括但不限于评分、信号、涨跌幅、技术指标、股票池、数据可视化结果等）**仅供研究和学习使用，不构成任何投资建议或承诺**。

市场有风险，投资需谨慎。任何单位或个人基于本系统进行的实盘交易行为，盈亏自负，本项目作者及版权方**不承担任何直接或间接的法律责任与经济损失**。

### 版权信息
&copy; 2025 **Yan Ying**. All rights reserved.

📧 **联系方式：** [yanying76@gmail.com](mailto:yanying76@gmail.com)
