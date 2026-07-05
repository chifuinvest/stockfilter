# AI 产业链全市场量化监控系统 · 部署到 GitHub 后的 README 片段
# （本文件仅作为仓库发布的 README 建议，不强制使用；可删除或改名）

## 快速开始

```bash
# 1) 克隆仓库
git clone <你的GitHub仓库地址>
cd stockfilter

# 2) 安装依赖
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3) 配置 Tushare Token（二选一）
#  方式 A：写进用户目录（推荐，跨项目共享）
#    Windows: C:\Users\<你>\.tushare\token.txt
#    macOS/Linux: ~/.tushare/token.txt
#  方式 B：写进项目的 .env（复制 .env.example → .env，填入真实值）
#  方式 C：临时写进环境变量
#    PowerShell: $env:TUSHARE_TOKEN="你的token"
#    Bash: export TUSHARE_TOKEN="你的token"

# 4) 启动服务
python main.py --port 5000

# 5) 浏览器访问
# 本机: http://127.0.0.1:5000/
# 同局域网其他设备: http://<你的局域网IP>:5000/
```

## 功能特性（与仓库代码同步）

- 全市场覆盖：155 只 AI 全产业链股票（美股 43 / A股 85 / 港股 20 / 韩股 8）
- 多数据源：Tushare（A/H 首选）+ Yahoo Finance（美韩+兜底）
- 6 维度技术评分：MA30% + MACD20% + RSI15% + BOLL10% + 量能15% + KDJ10%
- 交易信号：买入(≥80) / 持有(65~79) / 观望(45~64) / 减仓(30~44) / 回避(<30)
- 数据缓存：价格缓存 6 小时 TTL；评分结果增量写盘，进度可监控
- 异常保护：DETACHED 进程下 HOME/USERPROFILE 自动修复 + yfinance SQLite 缓存路径重定向
- 自动退避：美股 0.8~1.5s 降 QPS + 指数退避；港股分钟级配额窗口自动等待
- Web 界面：Flask + Bootstrap 5，支持增删股票、信号筛选、增量刷新、进度条可视化

---

## 📜 免责声明与版权

### 免责声明
本系统及其输出内容（包括但不限于评分、信号、涨跌幅、技术指标、股票池、数据可视化结果等）**仅供研究和学习使用，不构成任何投资建议或承诺**。

市场有风险，投资需谨慎。任何单位或个人基于本系统进行的实盘交易行为，盈亏自负，本项目作者及版权方**不承担任何直接或间接的法律责任与经济损失**。

### 版权信息
&copy; 2025 **Bart**. All rights reserved.

本项目所有源代码、文档与配置（除非另有说明）均采用上述版权声明。若需用于商业用途或有任何疑问，请通过以下方式联系版权方：

📧 **电子邮箱：** [yanying76@gmail.com](mailto:yanying76@gmail.com)
