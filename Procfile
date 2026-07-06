# Railway 一键启动命令（正式环境）
# 关键参数说明：
#   $PORT         Railway 会自动注入，**不要硬写 5000**
#   main:app      指 main.py 中的模块级 Flask app 变量（app = Flask(__name__)）
#   --workers 2   小实例推荐 2 个 Worker（每个 Worker 可处理 ~4 并发请求）
#   --timeout 300 首次评分/拉数据耗时较长，给 5 分钟超时（默认 30s 会超时被杀）
#   --threads 4   每 Worker 开 4 线程，提高 I/O（拉行情/算指标）并发能力
#   --preload     预加载 app，减少 Worker 启动时间
web: gunicorn main:app \
  -b 0.0.0.0:$PORT \
  --worker-class gthread \
  --workers 1 \
  --threads 4 \
  --timeout 300 \
  --preload \
  --access-logfile - \
  --error-logfile -
