import tushare as ts
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
from config import (
    TUSHARE_TOKEN, STOCK_LIST_CACHE_FILE,
    DAILY_BASIC_CACHE_FILE, FINANCIAL_CACHE_FILE,
    CACHE_DURATION
)
from utils import (
    save_cache, load_cache, get_trade_date,
    safe_float, safe_int, calc_ma, calc_macd, calc_rsi, calc_kdj
)


class DataFetcher:
    def __init__(self, use_mock=True):
        self.use_mock = use_mock
        self.pro = None
        if not use_mock and TUSHARE_TOKEN:
            ts.set_token(TUSHARE_TOKEN)
            self.pro = ts.pro_api()

    def _generate_mock_stock_list(self, count=200):
        stock_names = [
            '平安银行', '万科A', '格力电器', '贵州茅台', '五粮液',
            '美的集团', '招商银行', '兴业银行', '海康威视', '比亚迪',
            '宁德时代', '隆基绿能', '中国平安', '恒瑞医药', '伊利股份',
            '长江电力', '海尔智家', '药明康德', '紫金矿业', '中信证券',
            '东方财富', '立讯精密', '牧原股份', '迈瑞医疗', '智飞生物',
            '中国中免', '顺丰控股', '三一重工', '京东方A', 'TCL科技',
            '分众传媒', '片仔癀', '云南白药', '泸州老窖', '山西汾酒',
            '通威股份', '天齐锂业', '盐湖股份', '北方华创', '中芯国际'
        ]
        industries = ['银行', '房地产', '家用电器', '食品饮料', '白酒', '新能源',
                      '医药生物', '电子', '计算机', '通信', '传媒', '汽车',
                      '有色金属', '化工', '钢铁', '煤炭', '电力', '交通运输',
                      '机械设备', '国防军工', '农林牧渔', '纺织服装', '轻工制造']

        records = []
        used_codes = set()
        for i in range(count):
            while True:
                code = f"{random.randint(600000, 603999):06d}" if i % 3 == 0 else f"{random.randint(1, 2999):06d}"
                if code not in used_codes:
                    used_codes.add(code)
                    break
            ts_code = f"{code}.SH" if code.startswith('6') else f"{code}.SZ"
            name = stock_names[i % len(stock_names)] + (f"#{i}" if i >= len(stock_names) else "")
            industry = random.choice(industries)
            market = '主板' if random.random() > 0.3 else ('创业板' if code.startswith('3') else '科创板')
            records.append({
                'ts_code': ts_code,
                'symbol': code,
                'name': name,
                'area': random.choice(['广东', '上海', '北京', '浙江', '江苏', '深圳', '山东', '四川']),
                'industry': industry,
                'market': market,
                'list_date': f"{random.randint(2000, 2023):04d}{random.randint(1, 12):02d}{random.randint(1, 28):02d}",
                'is_hs': 'N' if random.random() > 0.4 else 'H'
            })
        return pd.DataFrame(records)

    def get_stock_list(self):
        if self.use_mock:
            cached = load_cache(STOCK_LIST_CACHE_FILE)
            if cached is not None:
                return cached
            df = self._generate_mock_stock_list()
            save_cache(df, STOCK_LIST_CACHE_FILE, CACHE_DURATION * 24)
            return df

        cached = load_cache(STOCK_LIST_CACHE_FILE)
        if cached is not None:
            return cached
        try:
            df = self.pro.stock_basic(exchange='', list_status='L',
                                      fields='ts_code,symbol,name,area,industry,market,list_date,is_hs')
            save_cache(df, STOCK_LIST_CACHE_FILE, CACHE_DURATION * 24)
            return df
        except Exception as e:
            print(f"Tushare获取股票列表失败: {e}，使用模拟数据")
            self.use_mock = True
            return self._generate_mock_stock_list()

    def _generate_mock_daily_basic(self, stock_list_df):
        records = []
        trade_date = get_trade_date(0)
        for _, row in stock_list_df.iterrows():
            price = round(random.uniform(2, 200), 2)
            total_mv = round(random.uniform(20, 5000), 2)
            circ_mv = round(total_mv * random.uniform(0.5, 1), 2)
            turnover_rate = round(random.uniform(0.1, 15), 2)
            volume_ratio = round(random.uniform(0.3, 5), 2)
            pe = round(random.uniform(-50, 200), 2)
            pb = round(random.uniform(0.3, 15), 2)
            total_share = round(total_mv / price * 10000, 2)
            float_share = round(circ_mv / price * 10000, 2)
            pct_chg = round(random.uniform(-10, 10), 2)
            amount = round(circ_mv * turnover_rate / 100 * random.uniform(0.8, 1.2), 2)
            records.append({
                'ts_code': row['ts_code'],
                'trade_date': trade_date,
                'close': price,
                'turnover_rate': turnover_rate,
                'turnover_rate_f': turnover_rate * random.uniform(0.9, 1.1),
                'volume_ratio': volume_ratio,
                'pe': pe if pe > 0 else None,
                'pe_ttm': pe * random.uniform(0.9, 1.1) if pe > 0 else None,
                'pb': pb,
                'ps': round(random.uniform(0.5, 20), 2),
                'ps_ttm': round(random.uniform(0.5, 20), 2),
                'dv_ratio': round(random.uniform(0, 8), 2),
                'dv_ttm': round(random.uniform(0, 8), 2),
                'total_share': total_share,
                'float_share': float_share,
                'free_share': float_share * random.uniform(0.7, 1),
                'total_mv': total_mv,
                'circ_mv': circ_mv,
                'pct_chg': pct_chg,
                'amount': amount
            })
        return pd.DataFrame(records)

    def get_daily_basic(self, trade_date=None):
        if trade_date is None:
            trade_date = get_trade_date(0)

        if self.use_mock:
            cached = load_cache(DAILY_BASIC_CACHE_FILE)
            if cached is not None:
                return cached
            stock_list = self.get_stock_list()
            df = self._generate_mock_daily_basic(stock_list)
            save_cache(df, DAILY_BASIC_CACHE_FILE, CACHE_DURATION)
            return df

        cached = load_cache(DAILY_BASIC_CACHE_FILE)
        if cached is not None:
            return cached
        try:
            df = self.pro.daily_basic(ts_code='', trade_date=trade_date,
                                      fields='ts_code,trade_date,close,turnover_rate,turnover_rate_f,'
                                             'volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,'
                                             'total_share,float_share,free_share,total_mv,circ_mv')
            daily = self.pro.daily(trade_date=trade_date, fields='ts_code,pct_chg,amount')
            if daily is not None and not daily.empty:
                df = df.merge(daily, on='ts_code', how='left')
            save_cache(df, DAILY_BASIC_CACHE_FILE, CACHE_DURATION)
            return df
        except Exception as e:
            print(f"Tushare获取每日指标失败: {e}，使用模拟数据")
            self.use_mock = True
            stock_list = self.get_stock_list()
            df = self._generate_mock_daily_basic(stock_list)
            save_cache(df, DAILY_BASIC_CACHE_FILE, CACHE_DURATION)
            return df

    def _generate_mock_kline(self, days=120):
        base_price = random.uniform(10, 100)
        prices = []
        current = base_price
        for _ in range(days):
            change_pct = random.uniform(-0.03, 0.03)
            current = current * (1 + change_pct)
            open_p = current * random.uniform(0.98, 1.02)
            high_p = max(open_p, current) * random.uniform(1, 1.02)
            low_p = min(open_p, current) * random.uniform(0.98, 1)
            vol = random.randint(50000, 500000)
            amount = vol * current / 100
            prices.append({
                'open': round(open_p, 2),
                'high': round(high_p, 2),
                'low': round(low_p, 2),
                'close': round(current, 2),
                'vol': vol,
                'amount': round(amount, 2)
            })
        return pd.DataFrame(prices)

    def get_kline_data(self, ts_code, start_date=None, end_date=None, days=120):
        if self.use_mock:
            return self._generate_mock_kline(days)

        if end_date is None:
            end_date = get_trade_date(0)
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y%m%d')
        try:
            df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date,
                                fields='trade_date,open,high,low,close,vol,amount')
            df = df.sort_values('trade_date').reset_index(drop=True)
            return df.tail(days)
        except Exception as e:
            print(f"Tushare获取K线失败 {ts_code}: {e}")
            return self._generate_mock_kline(days)

    def _generate_mock_financial(self, stock_list_df):
        records = []
        for _, row in stock_list_df.iterrows():
            total_mv = safe_float(row.get('total_mv'), 100)
            net_profit = round(total_mv * random.uniform(0.01, 0.15), 2)
            revenue = round(net_profit * random.uniform(3, 15), 2)
            roe = round(random.uniform(-20, 35), 2)
            roa = round(roe * random.uniform(0.1, 0.5), 2)
            gross_margin = round(random.uniform(10, 80), 2)
            net_margin = round(gross_margin * random.uniform(0.1, 0.5), 2)
            debt_ratio = round(random.uniform(10, 85), 2)
            current_ratio = round(random.uniform(0.5, 5), 2)
            quick_ratio = round(current_ratio * random.uniform(0.5, 0.9), 2)
            np_growth = round(random.uniform(-50, 100), 2)
            tr_growth = round(random.uniform(-30, 80), 2)
            records.append({
                'ts_code': row['ts_code'],
                'end_date': '20241231',
                'revenue': revenue * 10000,
                'n_income': net_profit * 10000,
                'total_hldr_eqy_exc_min_int': total_mv * 10000 * random.uniform(0.2, 0.8),
                'total_assets': total_mv * 10000 * random.uniform(0.5, 2),
                'total_liab': total_mv * 10000 * random.uniform(0.2, 1.5),
                'roe': roe,
                'roa': roa,
                'gross_margin': gross_margin,
                'net_margin': net_margin,
                'debt_to_assets': debt_ratio,
                'current_ratio': current_ratio,
                'quick_ratio': quick_ratio,
                'netprofit_yoy': np_growth,
                'tr_yoy': tr_growth
            })
        return pd.DataFrame(records)

    def get_financial_indicators(self):
        if self.use_mock:
            cached = load_cache(FINANCIAL_CACHE_FILE)
            if cached is not None:
                return cached
            stock_list = self.get_stock_list()
            df = self._generate_mock_financial(stock_list)
            save_cache(df, FINANCIAL_CACHE_FILE, CACHE_DURATION * 24)
            return df

        cached = load_cache(FINANCIAL_CACHE_FILE)
        if cached is not None:
            return cached
        try:
            end_date = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
            fina = self.pro.fina_indicator_vip(ts_code='', end_date=end_date,
                                               fields='ts_code,end_date,roe,roa,grossprofit_margin,'
                                                      'netprofit_margin,debt_to_assets,current_ratio,'
                                                      'quick_ratio,netprofit_yoy,tr_yoy')
            bs = self.pro.balancesheet_vip(ts_code='', end_date=end_date,
                                           fields='ts_code,end_date,total_hldr_eqy_exc_min_int,'
                                                  'total_assets,total_liab')
            ins = self.pro.income_vip(ts_code='', end_date=end_date,
                                      fields='ts_code,end_date,revenue,n_income')
            df = fina
            if bs is not None and not bs.empty:
                df = df.merge(bs, on=['ts_code', 'end_date'], how='left')
            if ins is not None and not ins.empty:
                df = df.merge(ins, on=['ts_code', 'end_date'], how='left')
            save_cache(df, FINANCIAL_CACHE_FILE, CACHE_DURATION * 24)
            return df
        except Exception as e:
            print(f"Tushare获取财务指标失败: {e}，使用模拟数据")
            self.use_mock = True
            stock_list = self.get_stock_list()
            df = self._generate_mock_financial(stock_list)
            save_cache(df, FINANCIAL_CACHE_FILE, CACHE_DURATION * 24)
            return df

    def get_merged_stock_data(self):
        stock_list = self.get_stock_list()
        daily_basic = self.get_daily_basic()
        financial = self.get_financial_indicators()

        merged = stock_list.merge(daily_basic, on='ts_code', how='left')

        if not financial.empty:
            fin_cols = [c for c in financial.columns if c not in ['end_date', 'ann_date', 'f_ann_date']]
            if 'ts_code' in fin_cols:
                fin_df = financial[fin_cols].groupby('ts_code').first().reset_index()
                merged = merged.merge(fin_df, on='ts_code', how='left')

        tech_data = []
        sample_codes = merged['ts_code'].head(50).tolist() if len(merged) > 50 else merged['ts_code'].tolist()
        for ts_code in sample_codes:
            kline = self.get_kline_data(ts_code, days=120)
            if kline is not None and not kline.empty:
                closes = kline['close'].tolist()
                highs = kline['high'].tolist()
                lows = kline['low'].tolist()
                ma5 = calc_ma(closes, 5)
                ma10 = calc_ma(closes, 10)
                ma20 = calc_ma(closes, 20)
                ma60 = calc_ma(closes, 60)
                dif, dea, macd_bar = calc_macd(closes)
                rsi = calc_rsi(closes)
                k, d, j = calc_kdj(highs, lows, closes)
                cur_close = closes[-1]
                amp = round((highs[-1] - lows[-1]) / lows[-1] * 100, 2) if len(lows) > 0 and lows[-1] > 0 else None
                tech_data.append({
                    'ts_code': ts_code,
                    'ma5': ma5,
                    'ma10': ma10,
                    'ma20': ma20,
                    'ma60': ma60,
                    'dif': dif,
                    'dea': dea,
                    'macd': macd_bar,
                    'rsi': rsi,
                    'k': k,
                    'd': d,
                    'j': j,
                    'close_vs_ma5': round((cur_close - ma5) / ma5 * 100, 2) if ma5 and ma5 > 0 else None,
                    'close_vs_ma20': round((cur_close - ma20) / ma20 * 100, 2) if ma20 and ma20 > 0 else None,
                    'amplitude': amp
                })
        tech_df = pd.DataFrame(tech_data)
        if not tech_df.empty:
            merged = merged.merge(tech_df, on='ts_code', how='left')

        return merged
