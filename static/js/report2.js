// Report 2: Сводная таблица всех проектов

let projectsData = [];
let projectsTable = null;

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация
    initTable();
    initFilters();
    initCharts();
    loadReportData();
    
    // Обновление данных каждые 5 минут
    setInterval(loadReportData, 300000);
});

// Инициализация DataTable
function initTable() {
    projectsTable = $('#projects-table').DataTable({
        language: {
            url: '//cdn.datatables.net/plug-ins/1.13.6/i18n/ru.json'
        },
        pageLength: 25,
        lengthMenu: [10, 25, 50, 100],
        order: [[5, 'desc']], // Сортировка по ROI по умолчанию
        columnDefs: [
            {
                targets: [2, 3, 4], // Колонки с суммами
                render: function(data, type) {
                    if (type === 'display' || type === 'filter') {
                        return formatCurrency(data);
                    }
                    return data;
                }
            },
            {
                targets: [5, 6], // Колонки с процентами
                render: function(data, type) {
                    if (type === 'display' || type === 'filter') {
                        const value = parseFloat(data);
                        const sign = value > 0 ? '+' : '';
                        const colorClass = value >= 0 ? 'positive' : 'negative';
                        return `<span class="${colorClass}">${sign}${value.toFixed(1)}%</span>`;
                    }
                    return data;
                }
            },
            {
                targets: [7], // Колонка действий
                orderable: false,
                searchable: false
            }
        ],
        dom: 'Bfrtip',
        buttons: [
            {
                extend: 'excel',
                text: '<i class="fas fa-file-excel"></i> Excel',
                className: 'btn-success'
            },
            {
                extend: 'pdf',
                text: '<i class="fas fa-file-pdf"></i> PDF',
                className: 'btn-danger'
            },
            {
                extend: 'print',
                text: '<i class="fas fa-print"></i> Печать',
                className: 'btn-secondary'
            }
        ]
    });
}

// Инициализация фильтров
function initFilters() {
    // Фильтрация по вкладкам
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            
            const filter = this.dataset.filter;
            filterProjects(filter);
        });
    });
    
    // Поиск по проектам
    const searchInput = document.getElementById('project-search');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(function() {
            projectsTable.search(this.value).draw();
        }, 300));
    }
    
    // Обновление данных
    document.getElementById('refresh-data')?.addEventListener('click', loadReportData);
    
    // Экспорт таблицы
    document.getElementById('export-table')?.addEventListener('click', function() {
        projectsTable.button('.buttons-excel').trigger();
    });
    
    // Печать таблицы
    document.getElementById('print-table')?.addEventListener('click', function() {
        projectsTable.button('.buttons-print').trigger();
    });
}

// Загрузка данных отчета
async function loadReportData() {
    showLoadingTable();
    
    try {
        const response = await fetch('/api/report2/data');
        const data = await response.json();
        
        if (data.success) {
            projectsData = data.projects;
            updateTable(data.projects);
            updateCharts(data.projects);
            updateFooterTotals(data.projects);
            showNotification('Данные обновлены', 'success');
        } else {
            showErrorTable(data.error);
        }
    } catch (error) {
        console.error('Error loading report data:', error);
        showErrorTable('Ошибка загрузки данных');
    }
}

// Показать загрузку в таблице
function showLoadingTable() {
    if (projectsTable) {
        projectsTable.clear().draw();
        
        const rowNode = projectsTable.row.add([
            '',
            '',
            '<div class="loading-cell"><div class="spinner small"></div><span>Загрузка данных...</span></div>',
            '',
            '',
            '',
            '',
            ''
        ]).node();
        
        $(rowNode).addClass('loading-row');
        projectsTable.draw();
    }
}

// Показать ошибку в таблице
function showErrorTable(message) {
    if (projectsTable) {
        projectsTable.clear().draw();
        
        const rowNode = projectsTable.row.add([
            '',
            '',
            `<div class="error-cell"><i class="fas fa-exclamation-triangle"></i><span>${message}</span></div>`,
            '',
            '',
            '',
            '',
            ''
        ]).node();
        
        $(rowNode).addClass('error-row');
        projectsTable.draw();
    }
}

// Обновление таблицы
function updateTable(projects) {
    if (!projectsTable) return;
    
    projectsTable.clear();
    
    projects.forEach(project => {
        const row = [
            project.project,
            `<span class="project-group ${project.group.toLowerCase()}">${project.group}</span>`,
            project.income,
            project.expense,
            project.net,
            project.margin,
            project.roi,
            createActionButtons(project.project)
        ];
        
        projectsTable.row.add(row);
    });
    
    projectsTable.draw();
}

// Создание кнопок действий
function createActionButtons(projectName) {
    return `
        <div class="action-buttons">
            <button class="btn-icon small" onclick="showProjectDetails('${projectName}')" title="Детали">
                <i class="fas fa-eye"></i>
            </button>
            <button class="btn-icon small" onclick="analyzeProject('${projectName}')" title="Анализ">
                <i class="fas fa-chart-bar"></i>
            </button>
            ${getProjectGroup(projectName) === 'Прочие' ? `
                <button class="btn-icon small" onclick="assignToGroup('${projectName}')" title="Назначить группу">
                    <i class="fas fa-tag"></i>
                </button>
            ` : ''}
        </div>
    `;
}

// Фильтрация проектов
function filterProjects(filterType) {
    if (!projectsTable) return;
    
    switch(filterType) {
        case 'all':
            projectsTable.search('').draw();
            break;
        case 'DCA':
        case 'DP':
        case 'Прочие':
            projectsTable.columns(1).search(filterType).draw();
            break;
        case 'negative':
            projectsTable.columns(4).search('^-', true, false).draw();
            break;
        case 'positive':
            projectsTable.columns(4).search('^[^-]', true, false).draw();
            break;
    }
}

// Обновление итогов в футере
function updateFooterTotals(projects) {
    if (!projects || projects.length === 0) {
        resetFooterTotals();
        return;
    }
    
    let totalIncome = 0;
    let totalExpense = 0;
    let totalNet = 0;
    let avgMargin = 0;
    let avgRoi = 0;
    
    projects.forEach(project => {
        totalIncome += project.income;
        totalExpense += project.expense;
        totalNet += project.net;
        avgMargin += project.margin;
        avgRoi += project.roi;
    });
    
    avgMargin = projects.length > 0 ? avgMargin / projects.length : 0;
    avgRoi = projects.length > 0 ? avgRoi / projects.length : 0;
    
    document.getElementById('total-income').textContent = formatCurrency(totalIncome);
    document.getElementById('total-expense').textContent = formatCurrency(totalExpense);
    document.getElementById('total-net').textContent = formatCurrency(totalNet);
    document.getElementById('avg-margin').textContent = `${avgMargin.toFixed(1)}%`;
    document.getElementById('avg-roi').textContent = `${avgRoi.toFixed(1)}%`;
}

// Сброс итогов
function resetFooterTotals() {
    document.getElementById('total-income').textContent = '0';
    document.getElementById('total-expense').textContent = '0';
    document.getElementById('total-net').textContent = '0';
    document.getElementById('avg-margin').textContent = '0%';
    document.getElementById('avg-roi').textContent = '0%';
}

// Инициализация графиков
function initCharts() {
    // Топ-5 по ROI
    initTopRoiChart();
    
    // Распределение по группам
    initGroupsChart();
    
    // Динамика маржинальности
    initTrendChart();
}

// График топ-5 по ROI
function initTopRoiChart() {
    const ctx = document.getElementById('top-roi-chart').getContext('2d');
    window.topRoiChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'ROI (%)',
                data: [],
                backgroundColor: 'rgba(0, 122, 255, 0.8)',
                borderColor: 'rgba(0, 122, 255, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
    
    // Изменение типа графика
    document.getElementById('chart1-type')?.addEventListener('change', function() {
        if (window.topRoiChart) {
            window.topRoiChart.destroy();
            const ctx = document.getElementById('top-roi-chart').getContext('2d');
            window.topRoiChart = new Chart(ctx, {
                type: this.value,
                data: window.topRoiChart.data,
                options: window.topRoiChart.options
            });
        }
    });
}

// График распределения по группам
function initGroupsChart() {
    const ctx = document.getElementById('groups-chart').getContext('2d');
    window.groupsChart = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: ['DCA', 'DP', 'Прочие'],
            datasets: [{
                data: [0, 0, 0],
                backgroundColor: [
                    'rgba(0, 122, 255, 0.8)',
                    'rgba(52, 199, 89, 0.8)',
                    'rgba(255, 149, 0, 0.8)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
    
    // Изменение типа графика
    document.getElementById('chart2-type')?.addEventListener('change', function() {
        if (window.groupsChart) {
            window.groupsChart.destroy();
            const ctx = document.getElementById('groups-chart').getContext('2d');
            window.groupsChart = new Chart(ctx, {
                type: this.value,
                data: window.groupsChart.data,
                options: window.groupsChart.options
            });
        }
    });
}

// График динамики маржинальности
function initTrendChart() {
    const ctx = document.getElementById('trend-chart').getContext('2d');
    window.trendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Маржинальность (%)',
                data: [],
                borderColor: 'rgba(0, 122, 255, 1)',
                backgroundColor: 'rgba(0, 122, 255, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                }
            }
        }
    });
}

// Обновление графиков
function updateCharts(projects) {
    updateTopRoiChart(projects);
    updateGroupsChart(projects);
    updateTrendChart(projects);
}

// Обновление графика топ-5 по ROI
function updateTopRoiChart(projects) {
    if (!window.topRoiChart || !projects) return;
    
    const sortedProjects = [...projects]
        .filter(p => p.roi !== null && p.roi !== undefined)
        .sort((a, b) => b.roi - a.roi)
        .slice(0, 5);
    
    const labels = sortedProjects.map(p => p.project);
    const data = sortedProjects.map(p => p.roi);
    
    window.topRoiChart.data.labels = labels;
    window.topRoiChart.data.datasets[0].data = data;
    window.topRoiChart.update();
}

// Обновление графика распределения по группам
function updateGroupsChart(projects) {
    if (!window.groupsChart || !projects) return;
    
    const groups = {
        'DCA': 0,
        'DP': 0,
        'Прочие': 0
    };
    
    let totalNet = 0;
    projects.forEach(project => {
        groups[project.group] = (groups[project.group] || 0) + project.net;
        totalNet += project.net;
    });
    
    // Преобразуем в проценты от общего результата
    const labels = [];
    const data = [];
    const backgroundColors = [];
    
    Object.keys(groups).forEach(group => {
        if (groups[group] !== 0) {
            labels.push(group);
            data.push(groups[group]);
            
            // Цвета в зависимости от группы
            if (group === 'DCA') backgroundColors.push('rgba(0, 122, 255, 0.8)');
            else if (group === 'DP') backgroundColors.push('rgba(52, 199, 89, 0.8)');
            else backgroundColors.push('rgba(255, 149, 0, 0.8)');
        }
    });
    
    window.groupsChart.data.labels = labels;
    window.groupsChart.data.datasets[0].data = data;
    window.groupsChart.data.datasets[0].backgroundColor = backgroundColors;
    window.groupsChart.update();
}

// Обновление графика динамики маржинальности
function updateTrendChart(projects) {
    if (!window.trendChart || !projects) return;
    
    // Здесь нужно будет добавить логику получения данных по месяцам
    // Пока используем фиктивные данные для демонстрации
    
    const months = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'];
    const currentMonth = new Date().getMonth();
    const labels = months.slice(0, currentMonth + 1);
    
    // Генерируем случайные данные для демонстрации
    const data = labels.map(() => Math.floor(Math.random() * 30) + 10);
    
    window.trendChart.data.labels = labels;
    window.trendChart.data.datasets[0].data = data;
    window.trendChart.update();
}

// Показать детали проекта
function showProjectDetails(projectName) {
    const project = projectsData.find(p => p.project === projectName);
    if (!project) {
        showNotification('Проект не найден', 'error');
        return;
    }
    
    const modal = document.getElementById('project-modal');
    if (!modal) return;
    
    // Обновляем заголовок
    document.getElementById('modal-project-name').textContent = projectName;
    
    // Обновляем вкладку "Обзор"
    updateOverviewTab(project);
    
    // Обновляем вкладку "Метрики"
    updateMetricsTab(project);
    
    // Обновляем вкладку "История"
    updateHistoryTab(projectName);
    
    // Показываем модальное окно
    modal.style.display = 'block';
    
    // Инициализируем вкладки
    initModalTabs();
}

// Обновление вкладки "Обзор"
function updateOverviewTab(project) {
    const basicMetrics = document.getElementById('basic-metrics');
    const projectInfo = document.getElementById('project-info');
    const projectStatus = document.getElementById('project-status');
    
    if (!basicMetrics || !projectInfo || !projectStatus) return;
    
    // Основные показатели
    basicMetrics.innerHTML = `
        <div class="metric-row">
            <span class="metric-label">Поступления:</span>
            <span class="metric-value positive">${formatCurrency(project.income)}</span>
        </div>
        <div class="metric-row">
            <span class="metric-label">Отток:</span>
            <span class="metric-value negative">${formatCurrency(project.expense)}</span>
        </div>
        <div class="metric-row">
            <span class="metric-label">Чистый результат:</span>
            <span class="metric-value ${project.net >= 0 ? 'positive' : 'negative'}">
                ${formatCurrency(project.net)}
            </span>
        </div>
        <div class="metric-row">
            <span class="metric-label">Маржинальность:</span>
            <span class="metric-value ${project.margin >= 0 ? 'positive' : 'negative'}">
                ${project.margin.toFixed(1)}%
            </span>
        </div>
        <div class="metric-row">
            <span class="metric-label">ROI:</span>
            <span class="metric-value ${project.roi >= 0 ? 'positive' : 'negative'}">
                ${project.roi.toFixed(1)}%
            </span>
        </div>
    `;
    
    // Информация о проекте
    projectInfo.innerHTML = `
        <div class="info-row">
            <span class="info-label">Группа:</span>
            <span class="info-value project-group ${project.group.toLowerCase()}">${project.group}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Тип:</span>
            <span class="info-value">${getProjectType(project.project)}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Статус:</span>
            <span class="info-value">${project.net >= 0 ? 'Активный' : 'Требует внимания'}</span>
        </div>
    `;
    
    // Статус проекта
    const statusClass = project.net >= 0 ? 'status-positive' : 'status-negative';
    const statusText = project.net >= 0 ? 'Прибыльный' : 'Убыточный';
    const statusIcon = project.net >= 0 ? 'fa-check-circle' : 'fa-exclamation-triangle';
    
    projectStatus.innerHTML = `
        <div class="status-indicator ${statusClass}">
            <i class="fas ${statusIcon}"></i>
            <span>${statusText}</span>
        </div>
        ${project.net < 0 ? `
            <div class="status-warning">
                <p>Рекомендуется провести анализ расходов</p>
                <button class="btn-secondary small" onclick="showTopExpenses('${project.project}')">
                    <i class="fas fa-chart-pie"></i> Анализ расходов
                </button>
            </div>
        ` : ''}
    `;
}

// Обновление вкладки "Метрики"
function updateMetricsTab(project) {
    const container = document.getElementById('detailed-metrics');
    if (!container) return;
    
    // Рассчитываем дополнительные метрики
    const efficiencyScore = calculateEfficiencyScore(project);
    const riskLevel = calculateRiskLevel(project);
    const growthPotential = calculateGrowthPotential(project);
    
    container.innerHTML = `
        <div class="metrics-grid">
            <div class="metric-card detailed">
                <div class="metric-icon">
                    <i class="fas fa-bolt"></i>
                </div>
                <div class="metric-content">
                    <h4>Эффективность</h4>
                    <div class="metric-score">${efficiencyScore}/100</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${efficiencyScore}%"></div>
                    </div>
                </div>
            </div>
            
            <div class="metric-card detailed">
                <div class="metric-icon">
                    <i class="fas fa-shield-alt"></i>
                </div>
                <div class="metric-content">
                    <h4>Уровень риска</h4>
                    <div class="metric-score ${riskLevel.color}">${riskLevel.text}</div>
                    <div class="risk-indicator ${riskLevel.color}"></div>
                </div>
            </div>
            
            <div class="metric-card detailed">
                <div class="metric-icon">
                    <i class="fas fa-chart-line"></i>
                </div>
                <div class="metric-content">
                    <h4>Потенциал роста</h4>
                    <div class="metric-score ${growthPotential >= 0 ? 'positive' : 'negative'}">
                        ${growthPotential >= 0 ? '+' : ''}${growthPotential}%
                    </div>
                    <div class="trend-indicator ${growthPotential >= 0 ? 'positive' : 'negative'}">
                        <i class="fas fa-${growthPotential >= 0 ? 'arrow-up' : 'arrow-down'}"></i>
                    </div>
                </div>
            </div>
            
            <div class="metric-card detailed">
                <div class="metric-icon">
                    <i class="fas fa-balance-scale"></i>
                </div>
                <div class="metric-content">
                    <h4>Баланс затрат/доходов</h4>
                    <div class="balance-ratio">${(project.income / project.expense).toFixed(2)}:1</div>
                    <div class="balance-bar">
                        <div class="income-part" style="width: ${(project.income / (project.income + project.expense) * 100)}%"></div>
                        <div class="expense-part" style="width: ${(project.expense / (project.income + project.expense) * 100)}%"></div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Обновление вкладки "История"
function updateHistoryTab(projectName) {
    const canvas = document.getElementById('history-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Создаем временный график для демонстрации
    // В реальном приложении здесь нужно загружать исторические данные
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн'],
            datasets: [{
                label: 'Чистый результат',
                data: [10000, 15000, 12000, 18000, 20000, 25000],
                borderColor: 'rgba(0, 122, 255, 1)',
                backgroundColor: 'rgba(0, 122, 255, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return formatCurrency(value);
                        }
                    }
                }
            }
        }
    });
}

// Инициализация вкладок модального окна
function initModalTabs() {
    const tabs = document.querySelectorAll('.modal-tab');
    const panes = document.querySelectorAll('.tab-pane');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            const tabName = this.dataset.tab;
            
            // Обновляем активную вкладку
            tabs.forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            
            // Показываем соответствующую панель
            panes.forEach(pane => {
                pane.classList.remove('active');
                if (pane.id === tabName + '-tab') {
                    pane.classList.add('active');
                }
            });
        });
    });
}

// Закрытие модального окна
function closeModal() {
    const modal = document.getElementById('project-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Анализ проекта
function analyzeProject(projectName) {
    showNotification(`Запущен анализ проекта "${projectName}"`, 'info');
    // Здесь можно добавить логику глубокого анализа
}

// Назначение проекта в группу
function assignToGroup(projectName) {
    const groups = ['DCA', 'DP', 'Прочие'];
    const currentGroup = getProjectGroup(projectName);
    
    let html = `<div class="group-selection">`;
    html += `<p>Выберите группу для проекта "${projectName}":</p>`;
    html += `<div class="group-options">`;
    
    groups.forEach(group => {
        const isCurrent = group === currentGroup;
        html += `
            <label class="group-option ${isCurrent ? 'current' : ''}">
                <input type="radio" name="project-group" value="${group}" ${isCurrent ? 'checked' : ''}>
                <span class="group-label ${group.toLowerCase()}">${group}</span>
            </label>
        `;
    });
    
    html += `</div></div>`;
    
    if (confirm(html.replace(/<[^>]*>/g, ''))) {
        const selectedGroup = document.querySelector('input[name="project-group"]:checked')?.value;
        if (selectedGroup && selectedGroup !== currentGroup) {
            // Здесь можно добавить логику сохранения изменений
            showNotification(`Проект "${projectName}" перемещен в группу "${selectedGroup}"`, 'success');
            // Перезагружаем данные
            setTimeout(() => loadReportData(), 1000);
        }
    }
}

// Показать ТОП-10 расходов для проекта
async function showTopExpenses(projectName) {
    try {
        const response = await fetch(`/api/top_expenses/${encodeURIComponent(projectName)}`);
        const data = await response.json();
        
        if (data.success && data.expenses.length > 0) {
            let html = `<h4>ТОП-10 расходов: ${projectName}</h4>`;
            html += `<div class="expenses-list-modal">`;
            
            data.expenses.forEach((expense, index) => {
                html += `
                    <div class="expense-item-modal">
                        <span class="expense-rank">${index + 1}</span>
                        <span class="expense-name">${expense.level4}</span>
                        <span class="expense-amount negative">${formatCurrency(expense.total)}</span>
                    </div>
                `;
            });
            
            html += `</div>`;
            
            // Показываем в модальном окне или уведомлении
            openModal('expenses-modal');
            document.getElementById('expenses-modal-content').innerHTML = html;
        } else {
            showNotification('Нет данных о расходах для этого проекта', 'info');
        }
    } catch (error) {
        console.error('Error loading expenses:', error);
        showNotification('Ошибка загрузки данных о расходах', 'error');
    }
}

// Вспомогательные функции
function getProjectGroup(projectName) {
    const name = projectName.toUpperCase();
    if (name.includes('DCA')) return 'DCA';
    if (name.includes('DP')) return 'DP';
    return 'Прочие';
}

function getProjectType(projectName) {
    // Определяем тип проекта по названию
    const name = projectName.toLowerCase();
    if (name.includes('alfa') || name.includes('bmw') || name.includes('mercedes')) {
        return 'Автокредиты';
    } else if (name.includes('mkk') || name.includes('sms')) {
        return 'Микрокредиты';
    } else if (name.includes('тендер') || name.includes('участие')) {
        return 'Тендеры';
    } else {
        return 'Общий';
    }
}

function calculateEfficiencyScore(project) {
    // Простая формула для расчета эффективности
    let score = 50; // Базовый балл
    
    // Добавляем баллы за положительные метрики
    if (project.margin > 0) score += project.margin;
    if (project.roi > 0) score += Math.min(project.roi / 10, 20);
    
    // Вычитаем баллы за отрицательные метрики
    if (project.margin < 0) score += project.margin; // margin отрицательный
    if (project.roi < 0) score += project.roi; // roi отрицательный
    
    // Ограничиваем от 0 до 100
    return Math.max(0, Math.min(100, Math.round(score)));
}

function calculateRiskLevel(project) {
    if (project.margin < 0) {
        return { text: 'Высокий', color: 'negative' };
    } else if (project.margin < 10) {
        return { text: 'Средний', color: 'warning' };
    } else {
        return { text: 'Низкий', color: 'positive' };
    }
}

function calculateGrowthPotential(project) {
    // Простой расчет потенциала роста на основе ROI
    if (project.roi > 50) return 30;
    if (project.roi > 20) return 15;
    if (project.roi > 0) return 5;
    if (project.roi > -10) return -5;
    if (project.roi > -30) return -15;
    return -30;
}

// Добавляем обработчики закрытия модальных окон
document.addEventListener('DOMContentLoaded', function() {
    // Закрытие модального окна проекта
    document.querySelector('.modal-close')?.addEventListener('click', closeModal);
    
    // Закрытие при клике на фон
    document.getElementById('project-modal')?.addEventListener('click', function(e) {
        if (e.target === this) {
            closeModal();
        }
    });
    
    // Закрытие по Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeModal();
        }
    });
});

// Добавляем стили для отчета 2
const report2Styles = document.createElement('style');
report2Styles.textContent = `
    .quick-filters {
        background: var(--apple-card);
        border-radius: var(--radius-lg);
        padding: var(--spacing-lg);
        margin-bottom: var(--spacing-lg);
    }
    
    .filter-tabs {
        display: flex;
        gap: var(--spacing-sm);
        margin-bottom: var(--spacing-md);
        flex-wrap: wrap;
    }
    
    .filter-tab {
        background: none;
        border: 1px solid var(--apple-border);
        border-radius: var(--radius-md);
        padding: var(--spacing-sm) var(--spacing-md);
        cursor: pointer;
        color: var(--apple-text);
        transition: var(--transition-fast);
        font-size: 0.9rem;
    }
    
    .filter-tab:hover {
        background-color: var(--apple-bg);
    }
    
    .filter-tab.active {
        background-color: var(--apple-blue);
        color: white;
        border-color: var(--apple-blue);
    }
    
    .filter-tab.negative.active {
        background-color: var(--apple-red);
        border-color: var(--apple-red);
    }
    
    .filter-tab.positive.active {
        background-color: var(--apple-green);
        border-color: var(--apple-green);
    }
    
    .filter-controls {
        display: flex;
        gap: var(--spacing-md);
        align-items: center;
    }
    
    .search-box {
        flex: 1;
        position: relative;
    }
    
    .search-box i {
        position: absolute;
        left: var(--spacing-md);
        top: 50%;
        transform: translateY(-50%);
        color: var(--apple-text-secondary);
    }
    
    .search-box input {
        width: 100%;
        padding: var(--spacing-md) var(--spacing-md) var(--spacing-md) var(--spacing-xl);
        border: 1px solid var(--apple-border);
        border-radius: var(--radius-md);
        font-family: inherit;
    }
    
    .loading-cell, .error-cell {
        display: flex;
        align-items: center;
        gap: var(--spacing-md);
        padding: var(--spacing-lg);
        justify-content: center;
        grid-column: 1 / -1;
    }
    
    .action-buttons {
        display: flex;
        gap: var(--spacing-xs);
    }
    
    .btn-icon.small {
        padding: 4px;
        font-size: 0.9rem;
    }
    
    .charts-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: var(--spacing-lg);
        margin-top: var(--spacing-lg);
    }
    
    .chart-card {
        background: var(--apple-card);
        border-radius: var(--radius-lg);
        padding: var(--spacing-lg);
    }
    
    .chart-card.full-width {
        grid-column: 1 / -1;
    }
    
    .chart-select {
        padding: var(--spacing-xs) var(--spacing-sm);
        border: 1px solid var(--apple-border);
        border-radius: var(--radius-sm);
        background: white;
        font-size: 0.9rem;
    }
    
    .chart-controls {
        display: flex;
        gap: var(--spacing-sm);
    }
    
    /* Модальное окно проекта */
    #project-modal {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.5);
        z-index: 2000;
        display: none;
        align-items: center;
        justify-content: center;
    }
    
    #project-modal .modal-content {
        background: var(--apple-card);
        border-radius: var(--radius-lg);
        width: 90%;
        max-width: 900px;
        max-height: 90vh;
        overflow-y: auto;
    }
    
    .modal-tabs {
        display: flex;
        gap: var(--spacing-sm);
        border-bottom: 1px solid var(--apple-border);
        margin-bottom: var(--spacing-lg);
    }
    
    .modal-tab {
        background: none;
        border: none;
        padding: var(--spacing-md) var(--spacing-lg);
        cursor: pointer;
        color: var(--apple-text-secondary);
        border-bottom: 2px solid transparent;
        transition: var(--transition-fast);
    }
    
    .modal-tab:hover {
        color: var(--apple-text);
    }
    
    .modal-tab.active {
        color: var(--apple-blue);
        border-bottom-color: var(--apple-blue);
    }
    
    .tab-pane {
        display: none;
    }
    
    .tab-pane.active {
        display: block;
    }
    
    .overview-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: var(--spacing-lg);
    }
    
    .overview-card {
        padding: var(--spacing-lg);
        border: 1px solid var(--apple-border);
        border-radius: var(--radius-md);
    }
    
    .metric-row {
        display: flex;
        justify-content: space-between;
        padding: var(--spacing-xs) 0;
        border-bottom: 1px solid var(--apple-border);
    }
    
    .metric-row:last-child {
        border-bottom: none;
    }
    
    .info-row {
        display: flex;
        justify-content: space-between;
        padding: var(--spacing-xs) 0;
    }
    
    .status-indicator {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-md);
        border-radius: var(--radius-md);
        margin-bottom: var(--spacing-md);
    }
    
    .status-positive {
        background-color: rgba(52, 199, 89, 0.1);
        color: var(--apple-green);
    }
    
    .status-negative {
        background-color: rgba(255, 59, 48, 0.1);
        color: var(--apple-red);
    }
    
    .status-warning {
        padding: var(--spacing-md);
        background-color: rgba(255, 149, 0, 0.1);
        border-radius: var(--radius-md);
        border-left: 4px solid var(--apple-orange);
    }
    
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: var(--spacing-lg);
    }
    
    .metric-card.detailed {
        text-align: center;
        padding: var(--spacing-lg);
        border: 1px solid var(--apple-border);
        border-radius: var(--radius-md);
    }
    
    .metric-icon {
        font-size: 2rem;
        color: var(--apple-blue);
        margin-bottom: var(--spacing-md);
    }
    
    .progress-bar {
        height: 8px;
        background: var(--apple-border);
        border-radius: 4px;
        overflow: hidden;
        margin-top: var(--spacing-sm);
    }
    
    .progress-fill {
        height: 100%;
        background: var(--apple-blue);
        transition: width 0.3s ease;
    }
    
    .risk-indicator {
        width: 100%;
        height: 4px;
        border-radius: 2px;
        margin-top: var(--spacing-sm);
    }
    
    .risk-indicator.negative {
        background: var(--apple-red);
    }
    
    .risk-indicator.warning {
        background: var(--apple-orange);
    }
    
    .risk-indicator.positive {
        background: var(--apple-green);
    }
    
    .trend-indicator {
        font-size: 1.5rem;
        margin-top: var(--spacing-sm);
    }
    
    .balance-bar {
        display: flex;
        height: 8px;
        border-radius: 4px;
        overflow: hidden;
        margin-top: var(--spacing-sm);
    }
    
    .income-part {
        background: var(--apple-green);
    }
    
    .expense-part {
        background: var(--apple-red);
    }
    
    .expenses-list-modal {
        max-height: 400px;
        overflow-y: auto;
    }
    
    .expense-item-modal {
        display: flex;
        align-items: center;
        padding: var(--spacing-md);
        border-bottom: 1px solid var(--apple-border);
    }
    
    .expense-rank {
        width: 30px;
        font-weight: bold;
        color: var(--apple-text-secondary);
    }
    
    .expense-name {
        flex: 1;
    }
    
    @media (max-width: 768px) {
        .filter-tabs {
            justify-content: center;
        }
        
        .filter-controls {
            flex-direction: column;
        }
        
        .charts-grid {
            grid-template-columns: 1fr;
        }
        
        .overview-grid {
            grid-template-columns: 1fr;
        }
        
        .metrics-grid {
            grid-template-columns: 1fr;
        }
        
        #project-modal .modal-content {
            width: 95%;
            margin: var(--spacing-md);
        }
    }
`;
document.head.appendChild(report2Styles);