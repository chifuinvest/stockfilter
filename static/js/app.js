const App = {
    meta: null,
    presets: [],
    lastResult: null,
    currentSort: { key: null, asc: true },
    activePresetId: null,

    async init() {
        this.bindTabEvents();
        this.bindFilterEvents();
        this.bindPresetEvents();
        this.bindExportEvents();
        this.bindRefreshEvents();
        await this.loadMeta();
        await this.loadPresets();
    },

    bindTabEvents() {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tab = btn.dataset.tab;
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.filter-panel').forEach(p => p.classList.remove('active'));
                btn.classList.add('active');
                document.querySelector(`.filter-panel[data-panel="${tab}"]`).classList.add('active');
            });
        });
    },

    bindFilterEvents() {
        document.getElementById('filterBtn').addEventListener('click', () => this.runFilter());
        document.getElementById('clearPresetBtn').addEventListener('click', () => this.clearAllConditions());
    },

    bindPresetEvents() {
    },

    bindExportEvents() {
        document.getElementById('exportCsvBtn').addEventListener('click', () => this.exportData('csv'));
        document.getElementById('exportXlsxBtn').addEventListener('click', () => this.exportData('xlsx'));
    },

    bindRefreshEvents() {
        document.getElementById('refreshBtn').addEventListener('click', () => this.refreshData());
    },

    async loadMeta() {
        try {
            const res = await fetch('/api/meta');
            const data = await res.json();
            this.meta = data;
            this.renderMeta();
            this.renderIndustryOptions(data.industries || []);
            this.renderMarketOptions(data.markets || []);
        } catch (e) {
            this.showToast('加载元数据失败: ' + e.message, 'error');
        }
    },

    renderMeta() {
        if (!this.meta) return;
        const modeEl = document.getElementById('dataMode');
        if (this.meta.use_mock) {
            modeEl.textContent = '模拟数据模式';
            modeEl.className = 'badge badge-mock';
        } else {
            modeEl.textContent = 'Tushare 实盘数据';
            modeEl.className = 'badge badge-live';
        }
        const timeEl = document.getElementById('updateTime');
        if (this.meta.last_update) {
            timeEl.textContent = `数据更新于 ${this.meta.last_update}`;
        } else {
            timeEl.textContent = `股票总数: ${this.meta.total_stocks || 0}`;
        }
    },

    renderIndustryOptions(industries) {
        const select = document.getElementById('industrySelect');
        select.innerHTML = '';
        industries.forEach(ind => {
            const opt = document.createElement('option');
            opt.value = ind;
            opt.textContent = ind;
            select.appendChild(opt);
        });
    },

    renderMarketOptions(markets) {
        const container = document.getElementById('marketCheckboxes');
        container.innerHTML = '';
        markets.forEach(m => {
            const label = document.createElement('label');
            label.className = 'checkbox-item';
            label.innerHTML = `
                <input type="checkbox" name="market_${m}" value="${m}">
                <span>${m}</span>
            `;
            container.appendChild(label);
        });
    },

    async loadPresets() {
        try {
            const res = await fetch('/api/presets');
            const data = await res.json();
            this.presets = data.presets || [];
            this.renderPresets();
        } catch (e) {
            console.error('加载预设失败:', e);
        }
    },

    renderPresets() {
        const list = document.getElementById('presetList');
        list.innerHTML = '';
        this.presets.forEach(preset => {
            const chip = document.createElement('div');
            chip.className = 'preset-chip';
            chip.textContent = preset.name;
            chip.title = preset.description;
            chip.dataset.id = preset.id;
            chip.addEventListener('click', () => this.applyPreset(preset));
            list.appendChild(chip);
        });
    },

    applyPreset(preset) {
        this.clearAllConditions(true);
        this.activePresetId = preset.id;
        document.querySelectorAll('.preset-chip').forEach(c => {
            c.classList.toggle('active', c.dataset.id === preset.id);
        });

        const conds = preset.conditions || {};

        Object.entries(conds.basic || {}).forEach(([k, v]) => {
            if (k === 'markets' && Array.isArray(v)) {
                v.forEach(m => {
                    const cb = document.querySelector(`input[name="market_${m}"]`);
                    if (cb) cb.checked = true;
                });
            } else if (k === 'industries' && Array.isArray(v)) {
                const sel = document.getElementById('industrySelect');
                Array.from(sel.options).forEach(opt => {
                    opt.selected = v.includes(opt.value);
                });
            } else {
                const input = document.querySelector(`input[name="${k}"], select[name="${k}"]`);
                if (input) input.value = v;
            }
        });

        ['market', 'technical', 'financial'].forEach(cat => {
            Object.entries(conds[cat] || {}).forEach(([k, v]) => {
                const input = document.querySelector(`input[name="${k}"], select[name="${k}"]`);
                if (!input) return;
                if (input.type === 'checkbox') {
                    input.checked = !!v;
                } else {
                    input.value = v;
                }
            });
        });

        this.showToast(`已加载预设: ${preset.name}`, 'info');
        this.runFilter();
    },

    clearAllConditions(silent = false) {
        this.activePresetId = null;
        document.querySelectorAll('.preset-chip').forEach(c => c.classList.remove('active'));

        document.querySelectorAll('.filter-panel input[type="number"], .filter-panel input[type="text"]').forEach(i => {
            if (!i.disabled) i.value = '';
        });
        document.querySelectorAll('.filter-panel input[type="checkbox"]').forEach(cb => {
            cb.checked = false;
        });
        document.querySelectorAll('.filter-panel select').forEach(s => {
            if (s.multiple) {
                Array.from(s.options).forEach(o => o.selected = false);
            } else if (s.name && s.name !== 'is_hs') {
                s.selectedIndex = 0;
            } else if (s.name === 'is_hs') {
                s.value = '';
            }
        });

        if (!silent) {
            this.showToast('已清空所有筛选条件', 'info');
        }
    },

    collectConditions() {
        const data = {};

        document.querySelectorAll('.filter-panel input[type="number"]').forEach(i => {
            if (i.disabled || i.value === '') return;
            data[i.name] = parseFloat(i.value);
        });
        document.querySelectorAll('.filter-panel input[type="checkbox"]').forEach(cb => {
            data[cb.name] = cb.checked;
        });
        document.querySelectorAll('.filter-panel select[name="is_hs"]').forEach(s => {
            if (s.value) data[s.name] = s.value;
        });

        const markets = [];
        document.querySelectorAll('#marketCheckboxes input[type="checkbox"]:checked').forEach(cb => {
            markets.push(cb.value);
        });
        if (markets.length > 0) data.markets = markets;

        const sel = document.getElementById('industrySelect');
        const industries = Array.from(sel.selectedOptions).map(o => o.value);
        if (industries.length > 0) data.industries = industries;

        return data;
    },

    async runFilter() {
        const conditions = this.collectConditions();
        this.showLoading(true);
        this.hideError();
        this.hideResults();

        try {
            const res = await fetch('/api/filter', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...conditions, limit: 500 })
            });
            const result = await res.json();
            if (!result.success) {
                throw new Error(result.message || '筛选失败');
            }
            this.lastResult = {
                data: result.data,
                total: result.total,
                stats: result.stats,
                conditions: conditions
            };
            this.currentSort = { key: null, asc: true };
            this.renderStats(result.stats, result.total, result.returned);
            this.renderTable(result.data);
            this.showResults();
        } catch (e) {
            this.showError('筛选出错: ' + e.message);
            this.showToast('筛选失败', 'error');
        } finally {
            this.showLoading(false);
        }
    },

    renderStats(stats, total, returned) {
        const container = document.getElementById('statsSummary');
        if (!stats) {
            container.innerHTML = '';
            return;
        }
        const items = [
            { label: '股票总数', value: stats.total || 0 },
            { label: '基础筛选后', value: stats.after_basic || 0 },
            { label: '行情筛选后', value: stats.after_market || 0 },
            { label: '技术筛选后', value: stats.after_technical || 0 },
            { label: '财务筛选后', value: stats.after_financial || 0, highlight: true }
        ];
        container.innerHTML = items.map(it => `
            <div class="stat-item">
                <span class="stat-label">${it.label}</span>
                <span class="stat-value ${it.highlight ? 'highlight' : ''}">${it.value.toLocaleString()}</span>
            </div>
        `).join('') + `
            <div class="stat-item">
                <span class="stat-label">显示结果</span>
                <span class="stat-value">${returned.toLocaleString()} / ${total.toLocaleString()}</span>
            </div>
        `;
    },

    getColumnConfig() {
        return [
            { key: 'ts_code', label: 'TS代码', width: '100px', className: 'code-cell' },
            { key: 'name', label: '名称', width: '100px', className: 'name-cell' },
            { key: 'industry', label: '行业', width: '80px' },
            { key: 'market', label: '板块', width: '70px', render: v => this.renderMarketTag(v) },
            { key: 'close', label: '收盘价', width: '80px', numeric: true, digits: 2 },
            { key: 'pct_chg', label: '涨跌幅', width: '80px', numeric: true, digits: 2,
              render: v => this.renderPercent(v, true) },
            { key: 'total_mv', label: '总市值(亿)', width: '100px', numeric: true, digits: 2 },
            { key: 'circ_mv', label: '流通市值(亿)', width: '110px', numeric: true, digits: 2 },
            { key: 'pe_ttm', label: 'PE(TTM)', width: '85px', numeric: true, digits: 1 },
            { key: 'pb', label: 'PB', width: '70px', numeric: true, digits: 2 },
            { key: 'turnover_rate_f', label: '换手率(%)', width: '90px', numeric: true, digits: 2 },
            { key: 'volume_ratio', label: '量比', width: '70px', numeric: true, digits: 2 },
            { key: 'amplitude', label: '振幅(%)', width: '80px', numeric: true, digits: 2 },
            { key: 'ma5', label: 'MA5', width: '75px', numeric: true, digits: 2 },
            { key: 'ma10', label: 'MA10', width: '75px', numeric: true, digits: 2 },
            { key: 'ma20', label: 'MA20', width: '75px', numeric: true, digits: 2 },
            { key: 'dif', label: 'DIF', width: '75px', numeric: true, digits: 3 },
            { key: 'dea', label: 'DEA', width: '75px', numeric: true, digits: 3 },
            { key: 'macd', label: 'MACD', width: '75px', numeric: true, digits: 3 },
            { key: 'rsi', label: 'RSI', width: '65px', numeric: true, digits: 1 },
            { key: 'k', label: 'K', width: '60px', numeric: true, digits: 1 },
            { key: 'd', label: 'D', width: '60px', numeric: true, digits: 1 },
            { key: 'j', label: 'J', width: '60px', numeric: true, digits: 1 },
            { key: 'roe', label: 'ROE(%)', width: '80px', numeric: true, digits: 1,
              render: v => this.renderPercent(v) },
            { key: 'grossprofit_margin', label: '毛利率(%)', width: '95px', numeric: true, digits: 1,
              render: v => this.renderPercent(v) },
            { key: 'debt_to_assets', label: '资产负债率(%)', width: '110px', numeric: true, digits: 1,
              render: v => this.renderPercent(v) },
            { key: 'netprofit_yoy', label: '净利润同比', width: '100px', numeric: true, digits: 1,
              render: v => this.renderPercent(v, true) },
            { key: 'tr_yoy', label: '营收同比', width: '100px', numeric: true, digits: 1,
              render: v => this.renderPercent(v, true) }
        ];
    },

    renderMarketTag(v) {
        if (!v) return '<span class="null-cell">-</span>';
        const map = {
            '主板': 'tag-main',
            '创业板': 'tag-gem',
            '科创板': 'tag-star',
            '北交所': 'tag-tech'
        };
        const cls = map[v] || 'tag-main';
        return `<span class="tag ${cls}">${v}</span>`;
    },

    renderPercent(v, withSign = false) {
        if (v === null || v === undefined || isNaN(v)) {
            return '<span class="null-cell">-</span>';
        }
        const num = Number(v);
        const cls = num > 0 ? 'up' : num < 0 ? 'down' : '';
        const sign = withSign && num > 0 ? '+' : '';
        return `<span class="${cls}">${sign}${num.toFixed(2)}%</span>`;
    },

    renderTable(data) {
        const columns = this.getColumnConfig();
        const availableCols = columns.filter(c => data.length === 0 || (data[0] && c.key in data[0]));

        const thead = document.getElementById('tableHeader');
        thead.innerHTML = availableCols.map(c => {
            const sortCls = this.currentSort.key === c.key
                ? (this.currentSort.asc ? 'sorted-asc' : 'sorted-desc') : '';
            const arrow = this.currentSort.key === c.key
                ? (this.currentSort.asc ? '▲' : '▼') : '↕';
            return `
                <th class="${sortCls}" style="width:${c.width || 'auto'}" data-key="${c.key}" data-numeric="${c.numeric ? '1' : '0'}">
                    ${c.label}
                    <span class="sort-icon">${arrow}</span>
                </th>
            `;
        }).join('');

        thead.querySelectorAll('th').forEach(th => {
            th.addEventListener('click', () => {
                const key = th.dataset.key;
                const numeric = th.dataset.numeric === '1';
                if (this.currentSort.key === key) {
                    this.currentSort.asc = !this.currentSort.asc;
                } else {
                    this.currentSort.key = key;
                    this.currentSort.asc = numeric ? false : true;
                }
                this.sortData(key, this.currentSort.asc, numeric);
                this.renderTable(this.lastResult.data);
            });
        });

        const tbody = document.getElementById('tableBody');
        if (data.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="${availableCols.length}" style="text-align:center;padding:60px 20px;color:#9ca3af">
                        没有找到符合条件的股票，请尝试调整筛选条件
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = data.map(row => `
            <tr>
                ${availableCols.map(c => {
                    let val = row[c.key];
                    let html;
                    if (c.render) {
                        html = c.render(val);
                    } else if (val === null || val === undefined || (typeof val === 'number' && isNaN(val))) {
                        html = '<span class="null-cell">-</span>';
                    } else if (c.numeric && c.digits !== undefined) {
                        html = Number(val).toFixed(c.digits);
                    } else {
                        html = String(val);
                    }
                    const cls = c.className || '';
                    return `<td class="${cls}">${html}</td>`;
                }).join('')}
            </tr>
        `).join('');
    },

    sortData(key, asc, numeric) {
        if (!this.lastResult || !this.lastResult.data) return;
        this.lastResult.data.sort((a, b) => {
            let va = a[key];
            let vb = b[key];
            if (numeric) {
                va = (va === null || va === undefined || isNaN(va)) ? (asc ? -Infinity : Infinity) : Number(va);
                vb = (vb === null || vb === undefined || isNaN(vb)) ? (asc ? -Infinity : Infinity) : Number(vb);
            } else {
                va = va === null || va === undefined ? '' : String(va);
                vb = vb === null || vb === undefined ? '' : String(vb);
            }
            if (va < vb) return asc ? -1 : 1;
            if (va > vb) return asc ? 1 : -1;
            return 0;
        });
    },

    async exportData(format) {
        if (!this.lastResult) {
            this.showToast('请先执行筛选再导出', 'warning');
            return;
        }
        try {
            const conditions = this.lastResult.conditions || {};
            const formData = { ...conditions, format };
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = `/api/export?format=${format}`;
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'data';
            input.value = JSON.stringify(formData);
            form.appendChild(input);
            document.body.appendChild(form);

            const res = await fetch(`/api/export?format=${format}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.message || '导出失败');
            }
            const blob = await res.blob();
            const disposition = res.headers.get('Content-Disposition') || '';
            const match = disposition.match(/filename\*?=([^;]+)/i);
            let filename = match ? match[1].replace(/"/g, '').trim() : `stock_filter.${format}`;
            if (filename.startsWith("UTF-8''")) filename = decodeURIComponent(filename.slice(7));

            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(() => URL.revokeObjectURL(url), 1000);

            this.showToast(`已导出 ${format.toUpperCase()} 文件`, 'success');
        } catch (e) {
            this.showToast('导出失败: ' + e.message, 'error');
        }
    },

    async refreshData() {
        const btn = document.getElementById('refreshBtn');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span>⏳</span> 刷新中...';
        try {
            const res = await fetch('/api/refresh', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                await this.loadMeta();
                this.showToast('数据刷新成功', 'success');
            } else {
                throw new Error(data.message || '刷新失败');
            }
        } catch (e) {
            this.showToast('刷新失败: ' + e.message, 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    },

    showLoading(show) {
        const el = document.getElementById('loadingIndicator');
        el.classList.toggle('hidden', !show);
    },

    showResults() {
        document.getElementById('resultsPlaceholder').classList.add('hidden');
        document.getElementById('resultsWrapper').classList.remove('hidden');
    },

    hideResults() {
        document.getElementById('resultsWrapper').classList.add('hidden');
        document.getElementById('resultsPlaceholder').classList.remove('hidden');
    },

    showError(msg) {
        const el = document.getElementById('errorMessage');
        el.textContent = msg;
        el.classList.remove('hidden');
        document.getElementById('resultsPlaceholder').classList.add('hidden');
        document.getElementById('resultsWrapper').classList.add('hidden');
    },

    hideError() {
        document.getElementById('errorMessage').classList.add('hidden');
    },

    showToast(msg, type = 'info') {
        const toast = document.getElementById('toast');
        toast.className = `toast toast-${type}`;
        toast.textContent = msg;
        toast.classList.remove('hidden');
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => {
            toast.classList.add('hidden');
        }, 2500);
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
