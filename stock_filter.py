import pandas as pd
import numpy as np
from utils import safe_float, safe_int
from data_fetcher import DataFetcher


class StockFilter:
    def __init__(self, use_mock=True):
        self.fetcher = DataFetcher(use_mock=use_mock)
        self.data = None

    def load_data(self):
        self.data = self.fetcher.get_merged_stock_data()
        return self.data

    def _filter_range(self, df, column, min_val=None, max_val=None):
        if df is None or df.empty:
            return df
        if min_val is not None:
            df = df[df[column].apply(lambda x: safe_float(x, float('inf')) >= min_val)]
        if max_val is not None:
            df = df[df[column].apply(lambda x: safe_float(x, float('-inf')) <= max_val)]
        return df

    def filter_basic(self, df, conditions):
        if df is None or df.empty:
            return df

        if 'price_min' in conditions or 'price_max' in conditions:
            df = self._filter_range(df, 'close', conditions.get('price_min'), conditions.get('price_max'))

        if 'pe_min' in conditions or 'pe_max' in conditions:
            pe_col = 'pe_ttm' if 'pe_ttm' in df.columns else 'pe'
            df = self._filter_range(df, pe_col, conditions.get('pe_min'), conditions.get('pe_max'))

        if 'pb_min' in conditions or 'pb_max' in conditions:
            df = self._filter_range(df, 'pb', conditions.get('pb_min'), conditions.get('pb_max'))

        if 'total_mv_min' in conditions or 'total_mv_max' in conditions:
            df = self._filter_range(df, 'total_mv', conditions.get('total_mv_min'), conditions.get('total_mv_max'))

        if 'circ_mv_min' in conditions or 'circ_mv_max' in conditions:
            df = self._filter_range(df, 'circ_mv', conditions.get('circ_mv_min'), conditions.get('circ_mv_max'))

        if 'markets' in conditions and conditions['markets']:
            df = df[df['market'].isin(conditions['markets'])]

        if 'industries' in conditions and conditions['industries']:
            df = df[df['industry'].isin(conditions['industries'])]

        if 'is_hs' in conditions and conditions['is_hs']:
            hs_val = conditions['is_hs']
            if hs_val in ['H', 'S']:
                df = df[df['is_hs'] == hs_val]

        return df

    def filter_market(self, df, conditions):
        if df is None or df.empty:
            return df

        if 'pct_chg_min' in conditions or 'pct_chg_max' in conditions:
            df = self._filter_range(df, 'pct_chg', conditions.get('pct_chg_min'), conditions.get('pct_chg_max'))

        if 'turnover_min' in conditions or 'turnover_max' in conditions:
            tr_col = 'turnover_rate_f' if 'turnover_rate_f' in df.columns else 'turnover_rate'
            df = self._filter_range(df, tr_col, conditions.get('turnover_min'), conditions.get('turnover_max'))

        if 'volume_ratio_min' in conditions or 'volume_ratio_max' in conditions:
            df = self._filter_range(df, 'volume_ratio', conditions.get('volume_ratio_min'), conditions.get('volume_ratio_max'))

        if 'amplitude_min' in conditions or 'amplitude_max' in conditions:
            df = self._filter_range(df, 'amplitude', conditions.get('amplitude_min'), conditions.get('amplitude_max'))

        if 'amount_min' in conditions or 'amount_max' in conditions:
            df = self._filter_range(df, 'amount', conditions.get('amount_min'), conditions.get('amount_max'))

        if 'dv_ratio_min' in conditions or 'dv_ratio_max' in conditions:
            dv_col = 'dv_ttm' if 'dv_ttm' in df.columns else 'dv_ratio'
            df = self._filter_range(df, dv_col, conditions.get('dv_ratio_min'), conditions.get('dv_ratio_max'))

        return df

    def filter_technical(self, df, conditions):
        if df is None or df.empty:
            return df

        if 'ma_bull' in conditions and conditions['ma_bull']:
            if all(c in df.columns for c in ['ma5', 'ma10', 'ma20', 'ma60']):
                df = df[df['ma5'].notna() & df['ma10'].notna() & df['ma20'].notna() & df['ma60'].notna()]
                if not df.empty:
                    df = df[(df['ma5'] > df['ma10']) & (df['ma10'] > df['ma20']) & (df['ma20'] > df['ma60'])]

        if 'ma_bear' in conditions and conditions['ma_bear']:
            if all(c in df.columns for c in ['ma5', 'ma10', 'ma20', 'ma60']):
                df = df[df['ma5'].notna() & df['ma10'].notna() & df['ma20'].notna() & df['ma60'].notna()]
                if not df.empty:
                    df = df[(df['ma5'] < df['ma10']) & (df['ma10'] < df['ma20']) & (df['ma20'] < df['ma60'])]

        if 'price_above_ma20' in conditions and conditions['price_above_ma20']:
            if 'close_vs_ma20' in df.columns:
                df = df[df['close_vs_ma20'].notna() & (df['close_vs_ma20'] > 0)]

        if 'price_below_ma20' in conditions and conditions['price_below_ma20']:
            if 'close_vs_ma20' in df.columns:
                df = df[df['close_vs_ma20'].notna() & (df['close_vs_ma20'] < 0)]

        if 'close_vs_ma5_min' in conditions or 'close_vs_ma5_max' in conditions:
            if 'close_vs_ma5' in df.columns:
                df = self._filter_range(df, 'close_vs_ma5',
                                        conditions.get('close_vs_ma5_min'),
                                        conditions.get('close_vs_ma5_max'))

        if 'macd_gold' in conditions and conditions['macd_gold']:
            if all(c in df.columns for c in ['dif', 'dea', 'macd']):
                df = df[df['dif'].notna() & df['dea'].notna() & df['macd'].notna()]
                if not df.empty:
                    df = df[(df['dif'] > df['dea']) & (df['macd'] > 0)]

        if 'macd_dead' in conditions and conditions['macd_dead']:
            if all(c in df.columns for c in ['dif', 'dea', 'macd']):
                df = df[df['dif'].notna() & df['dea'].notna() & df['macd'].notna()]
                if not df.empty:
                    df = df[(df['dif'] < df['dea']) & (df['macd'] < 0)]

        if 'rsi_min' in conditions or 'rsi_max' in conditions:
            if 'rsi' in df.columns:
                df = self._filter_range(df, 'rsi', conditions.get('rsi_min'), conditions.get('rsi_max'))

        if 'rsi_oversold' in conditions and conditions['rsi_oversold']:
            if 'rsi' in df.columns:
                df = df[df['rsi'].notna() & (df['rsi'] < 30)]

        if 'rsi_overbought' in conditions and conditions['rsi_overbought']:
            if 'rsi' in df.columns:
                df = df[df['rsi'].notna() & (df['rsi'] > 70)]

        if 'kdj_gold' in conditions and conditions['kdj_gold']:
            if all(c in df.columns for c in ['k', 'd', 'j']):
                df = df[df['k'].notna() & df['d'].notna() & df['j'].notna()]
                if not df.empty:
                    df = df[(df['k'] > df['d']) & (df['j'] > df['k'])]

        if 'kdj_dead' in conditions and conditions['kdj_dead']:
            if all(c in df.columns for c in ['k', 'd', 'j']):
                df = df[df['k'].notna() & df['d'].notna() & df['j'].notna()]
                if not df.empty:
                    df = df[(df['k'] < df['d']) & (df['j'] < df['k'])]

        if 'close_vs_ma20_min' in conditions or 'close_vs_ma20_max' in conditions:
            if 'close_vs_ma20' in df.columns:
                df = self._filter_range(df, 'close_vs_ma20',
                                        conditions.get('close_vs_ma20_min'),
                                        conditions.get('close_vs_ma20_max'))

        return df

    def filter_financial(self, df, conditions):
        if df is None or df.empty:
            return df

        roe_col = None
        for c in ['roe', 'roe_ttm', 'roe_avg']:
            if c in df.columns:
                roe_col = c
                break
        if roe_col and ('roe_min' in conditions or 'roe_max' in conditions):
            df = self._filter_range(df, roe_col, conditions.get('roe_min'), conditions.get('roe_max'))

        roa_col = None
        for c in ['roa', 'roa_ttm']:
            if c in df.columns:
                roa_col = c
                break
        if roa_col and ('roa_min' in conditions or 'roa_max' in conditions):
            df = self._filter_range(df, roa_col, conditions.get('roa_min'), conditions.get('roa_max'))

        gm_col = None
        for c in ['gross_margin', 'grossprofit_margin']:
            if c in df.columns:
                gm_col = c
                break
        if gm_col and ('gross_margin_min' in conditions or 'gross_margin_max' in conditions):
            df = self._filter_range(df, gm_col,
                                    conditions.get('gross_margin_min'),
                                    conditions.get('gross_margin_max'))

        nm_col = None
        for c in ['net_margin', 'netprofit_margin']:
            if c in df.columns:
                nm_col = c
                break
        if nm_col and ('net_margin_min' in conditions or 'net_margin_max' in conditions):
            df = self._filter_range(df, nm_col,
                                    conditions.get('net_margin_min'),
                                    conditions.get('net_margin_max'))

        dr_col = None
        for c in ['debt_to_assets', 'debt_ratio']:
            if c in df.columns:
                dr_col = c
                break
        if dr_col and ('debt_ratio_min' in conditions or 'debt_ratio_max' in conditions):
            df = self._filter_range(df, dr_col,
                                    conditions.get('debt_ratio_min'),
                                    conditions.get('debt_ratio_max'))

        if 'current_ratio_min' in conditions and 'current_ratio' in df.columns:
            df = self._filter_range(df, 'current_ratio', conditions.get('current_ratio_min'), None)

        if 'quick_ratio_min' in conditions and 'quick_ratio' in df.columns:
            df = self._filter_range(df, 'quick_ratio', conditions.get('quick_ratio_min'), None)

        npg_col = None
        for c in ['netprofit_yoy', 'np_growth']:
            if c in df.columns:
                npg_col = c
                break
        if npg_col and ('np_growth_min' in conditions or 'np_growth_max' in conditions):
            df = self._filter_range(df, npg_col,
                                    conditions.get('np_growth_min'),
                                    conditions.get('np_growth_max'))

        trg_col = None
        for c in ['tr_yoy', 'tr_growth']:
            if c in df.columns:
                trg_col = c
                break
        if trg_col and ('tr_growth_min' in conditions or 'tr_growth_max' in conditions):
            df = self._filter_range(df, trg_col,
                                    conditions.get('tr_growth_min'),
                                    conditions.get('tr_growth_max'))

        return df

    def apply_filters(self, all_conditions):
        if self.data is None:
            self.load_data()

        df = self.data.copy()
        total_before = len(df)

        basic_cond = all_conditions.get('basic', {})
        df = self.filter_basic(df, basic_cond)
        after_basic = len(df)

        market_cond = all_conditions.get('market', {})
        df = self.filter_market(df, market_cond)
        after_market = len(df)

        tech_cond = all_conditions.get('technical', {})
        df = self.filter_technical(df, tech_cond)
        after_tech = len(df)

        fin_cond = all_conditions.get('financial', {})
        df = self.filter_financial(df, fin_cond)
        after_fin = len(df)

        stats = {
            'total': total_before,
            'after_basic': after_basic,
            'after_market': after_market,
            'after_technical': after_tech,
            'after_financial': after_fin
        }

        return df, stats

    def get_industries(self):
        if self.data is None:
            self.load_data()
        return sorted(self.data['industry'].dropna().unique().tolist())

    def get_markets(self):
        if self.data is None:
            self.load_data()
        return sorted(self.data['market'].dropna().unique().tolist())

    def format_result(self, df, limit=200):
        if df is None or df.empty:
            return [], 0

        display_cols = [
            'ts_code', 'symbol', 'name', 'industry', 'market',
            'close', 'pct_chg', 'total_mv', 'circ_mv',
            'pe_ttm', 'pe', 'pb',
            'turnover_rate_f', 'turnover_rate', 'volume_ratio', 'amplitude', 'amount',
            'ma5', 'ma10', 'ma20', 'ma60',
            'dif', 'dea', 'macd', 'rsi', 'k', 'd', 'j',
            'roe', 'roa', 'gross_margin', 'grossprofit_margin',
            'net_margin', 'netprofit_margin',
            'debt_to_assets', 'debt_ratio',
            'netprofit_yoy', 'np_growth',
            'tr_yoy', 'tr_growth'
        ]

        available_cols = [c for c in display_cols if c in df.columns]
        result_df = df[available_cols].head(limit).copy()

        for c in ['close', 'pct_chg', 'total_mv', 'circ_mv', 'pe_ttm', 'pe', 'pb',
                  'turnover_rate_f', 'turnover_rate', 'volume_ratio', 'amplitude', 'amount',
                  'ma5', 'ma10', 'ma20', 'ma60', 'dif', 'dea', 'macd', 'rsi', 'k', 'd', 'j']:
            if c in result_df.columns:
                result_df[c] = pd.to_numeric(result_df[c], errors='coerce')

        for c in ['roe', 'roa', 'gross_margin', 'grossprofit_margin', 'net_margin',
                  'netprofit_margin', 'debt_to_assets', 'debt_ratio',
                  'netprofit_yoy', 'np_growth', 'tr_yoy', 'tr_growth']:
            if c in result_df.columns:
                result_df[c] = pd.to_numeric(result_df[c], errors='coerce')

        raw_records = result_df.to_dict('records')
        records = []
        for rec in raw_records:
            clean = {}
            for k, v in rec.items():
                if v is None:
                    clean[k] = None
                elif isinstance(v, (float, np.floating)):
                    clean[k] = None if np.isnan(v) else float(v)
                elif isinstance(v, (int, np.integer)):
                    clean[k] = None if np.isnan(v) else int(v)
                elif isinstance(v, (pd.Timestamp, np.datetime64)):
                    try:
                        clean[k] = str(v) if pd.notna(v) else None
                    except Exception:
                        clean[k] = None
                else:
                    clean[k] = None if (isinstance(v, float) and np.isnan(v)) else v
            records.append(clean)
        return records, len(df)
