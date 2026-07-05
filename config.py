import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN', '')

CACHE_DURATION = 3600

STOCK_LIST_CACHE_FILE = os.path.join(DATA_DIR, 'stock_list.pkl')
DAILY_BASIC_CACHE_FILE = os.path.join(DATA_DIR, 'daily_basic.pkl')
FINANCIAL_CACHE_FILE = os.path.join(DATA_DIR, 'financial_data.pkl')
