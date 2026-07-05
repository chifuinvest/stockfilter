import os
import io
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_file, session
from stock_filter import StockFilter
import pandas as pd

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'stockfilter-secret-key-2024')

_stock_filter = None
_last_load_time = 0


def get_filter(force_reload=False):
    global _stock_filter, _last_load_time
    use_mock = os.environ.get('USE_MOCK_DATA', '1') != '0'
    if _stock_filter is None or force_reload:
        _stock_filter = StockFilter(use_mock=use_mock)
        _stock_filter.load_data()
        _last_load_time = time.time()
    elif time.time() - _last_load_time > 3600:
        _stock_filter.load_data()
        _last_load_time = time.time()
    return _stock_filter


def _parse_number(val, cast_type=float):
    if val is None or val == '':
        return None
    try:
        return cast_type(val)
    except (ValueError, TypeError):
        return None


def _parse_bool(val):
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    if isinstance(val, str):
        return val.lower() in ('1', 'true', 'yes', 'on')
    return False


def build_conditions_from_request(req):
    data = req.get_json(silent=True) or req.form.to_dict() or {}

    basic = {}
    for k in ['price_min', 'price_max', 'pe_min', 'pe_max', 'pb_min', 'pb_max',
              'total_mv_min', 'total_mv_max', 'circ_mv_min', 'circ_mv_max']:
        v = _parse_number(data.get(k))
        if v is not None:
            basic[k] = v
    markets = data.get('markets')
    if markets:
        if isinstance(markets, str):
            markets = [m.strip() for m in markets.split(',') if m.strip()]
        basic['markets'] = markets
    industries = data.get('industries')
    if industries:
        if isinstance(industries, str):
            industries = [i.strip() for i in industries.split(',') if i.strip()]
        basic['industries'] = industries
    is_hs = data.get('is_hs')
    if is_hs:
        basic['is_hs'] = is_hs

    market = {}
    for k in ['pct_chg_min', 'pct_chg_max', 'turnover_min', 'turnover_max',
              'volume_ratio_min', 'volume_ratio_max', 'amplitude_min', 'amplitude_max',
              'amount_min', 'amount_max', 'dv_ratio_min', 'dv_ratio_max']:
        v = _parse_number(data.get(k))
        if v is not None:
            market[k] = v

    technical = {}
    for k in ['close_vs_ma5_min', 'close_vs_ma5_max', 'close_vs_ma20_min', 'close_vs_ma20_max',
              'rsi_min', 'rsi_max']:
        v = _parse_number(data.get(k))
        if v is not None:
            technical[k] = v
    for k in ['ma_bull', 'ma_bear', 'price_above_ma20', 'price_below_ma20',
              'macd_gold', 'macd_dead', 'rsi_oversold', 'rsi_overbought',
              'kdj_gold', 'kdj_dead']:
        if _parse_bool(data.get(k)):
            technical[k] = True

    financial = {}
    for k in ['roe_min', 'roe_max', 'roa_min', 'roa_max',
              'gross_margin_min', 'gross_margin_max',
              'net_margin_min', 'net_margin_max',
              'debt_ratio_min', 'debt_ratio_max',
              'current_ratio_min', 'quick_ratio_min',
              'np_growth_min', 'np_growth_max',
              'tr_growth_min', 'tr_growth_max']:
        v = _parse_number(data.get(k))
        if v is not None:
            financial[k] = v

    return {
        'basic': basic,
        'market': market,
        'technical': technical,
        'financial': financial
    }


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/meta')
def api_meta():
    sf = get_filter()
    industries = sf.get_industries()
    markets = sf.get_markets()
    return jsonify({
        'industries': industries,
        'markets': markets,
        'total_stocks': len(sf.data) if sf.data is not None else 0,
        'last_update': datetime.fromtimestamp(_last_load_time).strftime('%Y-%m-%d %H:%M:%S') if _last_load_time else None,
        'use_mock': os.environ.get('USE_MOCK_DATA', '1') != '0'
    })


@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    try:
        get_filter(force_reload=True)
        return jsonify({'success': True, 'message': '数据刷新成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/filter', methods=['GET', 'POST'])
def api_filter():
    sf = get_filter()
    conditions = build_conditions_from_request(request)
    limit = _parse_number(request.args.get('limit') or (request.get_json(silent=True) or {}).get('limit'), int)
    if limit is None:
        limit = 200

    try:
        result_df, stats = sf.apply_filters(conditions)
        records, total = sf.format_result(result_df, limit=limit)
        return jsonify({
            'success': True,
            'data': records,
            'total': total,
            'stats': stats,
            'returned': len(records)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/export', methods=['GET', 'POST'])
def api_export():
    sf = get_filter()
    conditions = build_conditions_from_request(request)
    fmt = request.args.get('format') or (request.get_json(silent=True) or {}).get('format') or 'csv'

    try:
        result_df, stats = sf.apply_filters(conditions)
        if result_df is None or result_df.empty:
            return jsonify({'success': False, 'message': '没有符合条件的股票可导出'}), 400

        export_cols = [
            'ts_code', 'symbol', 'name', 'industry', 'market',
            'close', 'pct_chg', 'total_mv', 'circ_mv',
            'pe_ttm', 'pe', 'pb',
            'turnover_rate_f', 'turnover_rate', 'volume_ratio', 'amplitude', 'amount',
            'ma5', 'ma10', 'ma20', 'ma60',
            'dif', 'dea', 'macd', 'rsi', 'k', 'd', 'j',
            'roe', 'roa', 'gross_margin', 'grossprofit_margin',
            'net_margin', 'netprofit_margin',
            'debt_to_assets', 'debt_ratio',
            'netprofit_yoy', 'tr_yoy'
        ]
        available_cols = [c for c in export_cols if c in result_df.columns]
        export_df = result_df[available_cols].copy()

        col_names = {
            'ts_code': '代码', 'symbol': '股票代码', 'name': '名称',
            'industry': '行业', 'market': '板块',
            'close': '收盘价', 'pct_chg': '涨跌幅(%)',
            'total_mv': '总市值(亿)', 'circ_mv': '流通市值(亿)',
            'pe_ttm': '市盈率(TTM)', 'pe': '市盈率', 'pb': '市净率',
            'turnover_rate_f': '换手率(%)', 'turnover_rate': '换手率(旧)',
            'volume_ratio': '量比', 'amplitude': '振幅(%)', 'amount': '成交额(亿)',
            'ma5': 'MA5', 'ma10': 'MA10', 'ma20': 'MA20', 'ma60': 'MA60',
            'dif': 'DIF', 'dea': 'DEA', 'macd': 'MACD', 'rsi': 'RSI(14)',
            'k': 'K', 'd': 'D', 'j': 'J',
            'roe': 'ROE(%)', 'roa': 'ROA(%)',
            'gross_margin': '毛利率(%)', 'grossprofit_margin': '毛利率(TTM)(%)',
            'net_margin': '净利率(%)', 'netprofit_margin': '净利率(TTM)(%)',
            'debt_to_assets': '资产负债率(%)', 'debt_ratio': '资产负债率(%)',
            'netprofit_yoy': '净利润同比(%)', 'tr_yoy': '营收同比(%)'
        }
        export_df = export_df.rename(columns={c: col_names.get(c, c) for c in export_df.columns})

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if fmt.lower() == 'xlsx' or fmt.lower() == 'excel':
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                export_df.to_excel(writer, index=False, sheet_name='筛选结果')
            output.seek(0)
            filename = f'stock_filter_{timestamp}.xlsx'
            return send_file(output,
                             as_attachment=True,
                             download_name=filename,
                             mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        else:
            csv_data = export_df.to_csv(index=False, encoding='utf-8-sig')
            output = io.BytesIO(csv_data.encode('utf-8-sig'))
            filename = f'stock_filter_{timestamp}.csv'
            return send_file(output,
                             as_attachment=True,
                             download_name=filename,
                             mimetype='text/csv')

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/presets')
def api_presets():
    presets = [
        {
            'id': 'low_pe_value',
            'name': '低估值价值股',
            'description': 'PE(TTM) 0-20，PB 0.3-3，ROE > 10%，市值 > 100亿',
            'conditions': {
                'basic': {'pe_min': 0, 'pe_max': 20, 'pb_min': 0.3, 'pb_max': 3, 'total_mv_min': 100},
                'financial': {'roe_min': 10},
                'market': {}, 'technical': {}
            }
        },
        {
            'id': 'high_growth',
            'name': '高成长股',
            'description': '净利润同比 > 30%，营收同比 > 20%，ROE > 15%，毛利率 > 30%',
            'conditions': {
                'financial': {
                    'np_growth_min': 30, 'tr_growth_min': 20,
                    'roe_min': 15, 'gross_margin_min': 30
                },
                'basic': {}, 'market': {}, 'technical': {}
            }
        },
        {
            'id': 'ma_bull_break',
            'name': '均线多头排列',
            'description': 'MA5>MA10>MA20>MA60，股价在MA20上方，MACD金叉',
            'conditions': {
                'technical': {'ma_bull': True, 'price_above_ma20': True, 'macd_gold': True},
                'basic': {}, 'market': {}, 'financial': {}
            }
        },
        {
            'id': 'rsi_oversold_rebound',
            'name': 'RSI超跌反弹',
            'description': 'RSI<30 超卖，KDJ金叉，换手率适中 1-10%',
            'conditions': {
                'technical': {'rsi_oversold': True, 'kdj_gold': True},
                'market': {'turnover_min': 1, 'turnover_max': 10},
                'basic': {}, 'financial': {}
            }
        },
        {
            'id': 'high_turnover_momentum',
            'name': '高换手强势股',
            'description': '换手率 5-20%，量比 > 2，涨幅 3-9%，价格 > 5元',
            'conditions': {
                'market': {'turnover_min': 5, 'turnover_max': 20, 'volume_ratio_min': 2,
                           'pct_chg_min': 3, 'pct_chg_max': 9},
                'basic': {'price_min': 5},
                'technical': {}, 'financial': {}
            }
        },
        {
            'id': 'dividend_value',
            'name': '高股息价值',
            'description': '股息率(TTM) > 3%，PE < 15，资产负债率 < 60%',
            'conditions': {
                'market': {'dv_ratio_min': 3},
                'basic': {'pe_max': 15},
                'financial': {'debt_ratio_max': 60},
                'technical': {}
            }
        }
    ]
    return jsonify({'presets': presets})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)
