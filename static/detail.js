// Общий JS для подсказки при наведении и модалки-детализации на Свод1/Dashboard2.
// Ячейка суммы помечается классом amount-cell и data-атрибутами:
//   data-lines (JSON-массив "Строка отчета"), data-year, data-month, data-pf,
//   data-label, data-focus (projects|statya)
//   data-projects (JSON-массив, опционально — фильтр по проектам)
//   data-detail (JSON [{stat3, val}, ...], опционально — для подсказки без похода на сервер)

function fmtAmount(v) {
    return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(v);
}

function buildTooltipHtml(detail) {
    if (!detail || !detail.length) return null;
    const rows = detail.slice(0, 8).map(d => `<div class="d-flex justify-content-between gap-3">
        <span>${d.stat3}</span><span>${fmtAmount(d.val)}</span></div>`).join('');
    return `<div class="text-start">${rows}</div>`;
}

function initAmountCells(root) {
    (root || document).querySelectorAll('td.amount-cell').forEach(td => {
        if (td.dataset.tooltipInit) return;
        td.dataset.tooltipInit = '1';

        if (td.dataset.detail) {
            let detail;
            try { detail = JSON.parse(td.dataset.detail); } catch (e) { detail = null; }
            const html = buildTooltipHtml(detail);
            if (html) {
                new bootstrap.Tooltip(td, { title: html, html: true, container: 'body', placement: 'top' });
            }
        }

        td.addEventListener('click', () => {
            showCellDetail({
                lines: JSON.parse(td.dataset.lines),
                year: td.dataset.year,
                month: td.dataset.month,
                pf: td.dataset.pf,
                projects: td.dataset.projects ? JSON.parse(td.dataset.projects) : null,
                focus: td.dataset.focus || 'statya',
                label: td.dataset.label,
            });
        });
    });
}

let detailModalInstance = null;

function showCellDetail(opts) {
    const modalEl = document.getElementById('detailModal');
    detailModalInstance = detailModalInstance || new bootstrap.Modal(modalEl);
    document.getElementById('detailModalTitle').textContent = `${opts.label} — ${opts.month}.${opts.year} (${opts.pf})`;
    document.getElementById('detailModalSummary').textContent = '';
    document.getElementById('detailModalTabs').style.display = '';
    document.getElementById('detailModalBody').innerHTML = '<div class="text-secondary">Загрузка…</div>';
    detailModalInstance.show();

    const params = new URLSearchParams({ year: opts.year, month: opts.month, pf: opts.pf });
    opts.lines.forEach(l => params.append('line', l));
    if (opts.projects) opts.projects.forEach(p => params.append('project', p));

    fetch('/api/cell_detail?' + params.toString())
        .then(r => r.json())
        .then(data => renderCellDetail(data, opts))
        .catch(() => {
            document.getElementById('detailModalBody').innerHTML = '<div class="text-danger">Не удалось загрузить детализацию.</div>';
        });
}

function renderCellDetail(data, opts) {
    if (data.error) {
        document.getElementById('detailModalBody').innerHTML = `<div class="text-danger">${data.error}</div>`;
        return;
    }
    document.getElementById('detailModalSummary').textContent =
        `Итого: ${fmtAmount(data.total)} (${data.row_count} операций)`;

    const projectsHtml = `<table class="table table-sm"><thead><tr><th>Проект</th><th class="text-end">Сумма</th></tr></thead><tbody>` +
        data.by_project.map(p => `<tr><td>${p.project}</td><td class="text-end">${fmtAmount(p.total)}</td></tr>`).join('') +
        `</tbody></table>`;

    const statyaHtml = `<div class="accordion" id="statyaAccordion">` + data.by_statya3.map((s, i) => `
        <div class="accordion-item">
            <h2 class="accordion-header">
                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#stat3-${i}">
                    <span class="flex-grow-1">${s.stat3}</span><span class="me-2">${fmtAmount(s.total)}</span>
                </button>
            </h2>
            <div id="stat3-${i}" class="accordion-collapse collapse" data-bs-parent="#statyaAccordion">
                <div class="accordion-body p-2">
                    <div class="accordion" id="contragentAccordion-${i}">
                    ${s.contragents.map((c, j) => `
                        <div class="accordion-item">
                            <h2 class="accordion-header">
                                <button class="accordion-button collapsed py-1" type="button" data-bs-toggle="collapse" data-bs-target="#c-${i}-${j}">
                                    <span class="flex-grow-1">${c.contragent}</span><span class="me-2">${fmtAmount(c.total)}</span>
                                </button>
                            </h2>
                            <div id="c-${i}-${j}" class="accordion-collapse collapse" data-bs-parent="#contragentAccordion-${i}">
                                <div class="accordion-body p-2">
                                    ${c.comments.length ? `<ul class="list-unstyled mb-0">` +
                                        c.comments.map(cm => `<li class="d-flex justify-content-between gap-2 border-bottom py-1">
                                            <span class="text-secondary">${cm.comment || '—'} <span class="badge bg-light text-dark">${cm.project}</span></span>
                                            <span>${fmtAmount(cm.amount)}</span></li>`).join('') + `</ul>`
                                        : '<span class="text-secondary">Без комментариев</span>'}
                                </div>
                            </div>
                        </div>`).join('')}
                    </div>
                </div>
            </div>
        </div>`).join('') + `</div>`;

    const body = document.getElementById('detailModalBody');
    body.innerHTML = `
        <div data-pane="projects">${projectsHtml}</div>
        <div data-pane="statya" style="display:none">${statyaHtml}</div>`;

    const tabs = document.getElementById('detailModalTabs');
    tabs.querySelectorAll('.nav-link').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === opts.focus);
        btn.onclick = () => {
            tabs.querySelectorAll('.nav-link').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            body.querySelectorAll('[data-pane]').forEach(p => p.style.display = p.dataset.pane === btn.dataset.tab ? '' : 'none');
        };
    });
    body.querySelectorAll('[data-pane]').forEach(p => p.style.display = p.dataset.pane === opts.focus ? '' : 'none');
}

// Акт-анализ отклонений: ячейка с классом delta-cell и data-атрибутами
//   data-lines (JSON-массив), data-projects (JSON-массив, опционально),
//   data-month, data-a, data-b (каждый "pf:год"), data-label

function initDeltaCells(root) {
    (root || document).querySelectorAll('td.delta-cell').forEach(td => {
        if (td.dataset.deltaInit) return;
        td.dataset.deltaInit = '1';
        td.addEventListener('click', () => {
            showDeviationDetail({
                lines: JSON.parse(td.dataset.lines),
                projects: td.dataset.projects ? JSON.parse(td.dataset.projects) : null,
                month: td.dataset.month,
                a: td.dataset.a,
                b: td.dataset.b,
                label: td.dataset.label,
            });
        });
    });
}

function showDeviationDetail(opts) {
    const modalEl = document.getElementById('detailModal');
    detailModalInstance = detailModalInstance || new bootstrap.Modal(modalEl);
    document.getElementById('detailModalTitle').textContent = `Акт-анализ: ${opts.label} (${opts.a} − ${opts.b})`;
    document.getElementById('detailModalSummary').textContent = '';
    document.getElementById('detailModalTabs').style.display = 'none';
    document.getElementById('detailModalBody').innerHTML = '<div class="text-secondary">Загрузка…</div>';
    detailModalInstance.show();

    const params = new URLSearchParams({ month: opts.month, a: opts.a, b: opts.b });
    opts.lines.forEach(l => params.append('line', l));
    if (opts.projects) opts.projects.forEach(p => params.append('project', p));

    fetch('/api/deviation_detail?' + params.toString())
        .then(r => r.json())
        .then(data => renderDeviationDetail(data))
        .catch(() => {
            document.getElementById('detailModalBody').innerHTML = '<div class="text-danger">Не удалось загрузить акт-анализ.</div>';
        });
}

function renderDeviationDetail(data) {
    if (data.error) {
        document.getElementById('detailModalBody').innerHTML = `<div class="text-danger">${data.error}</div>`;
        return;
    }
    document.getElementById('detailModalSummary').textContent = `Итого отклонение: ${fmtAmount(data.total_delta)}`;
    const rows = data.drivers.map(d => `<tr>
        <td>${d.project}</td><td>${d.stat3}</td><td>${d.contragent}</td>
        <td class="text-end">${fmtAmount(d.a)}</td><td class="text-end">${fmtAmount(d.b)}</td>
        <td class="text-end fw-bold ${d.delta > 0 ? 'val-pos' : 'val-neg'}">${fmtAmount(d.delta)}</td>
        </tr>`).join('');
    document.getElementById('detailModalBody').innerHTML = `
        <p class="text-secondary small">Топ-${data.drivers.length} драйверов отклонения по модулю разницы (руб.).</p>
        <table class="table table-sm">
            <thead><tr><th>Проект</th><th>Статья</th><th>Контрагент</th><th class="text-end">Значение A</th><th class="text-end">Значение B</th><th class="text-end">Δ</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
}

document.addEventListener('DOMContentLoaded', () => {
    initAmountCells(document);
    initDeltaCells(document);
});
