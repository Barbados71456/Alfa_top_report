// Report 4: Анализ ФОТ и сотрудников

let fotData = [];
let fotChart = null;
let employeesChart = null;
let fotResultChart = null;
let trendChart = null;

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация
    initTable();
    initCharts();
    loadReportData();
    
    // Обновление данных каждые 5 минут
    setInterval(loadReportData, 300000);
});

// Инициализация таблицы
function initTable() {
    const table = document.getElementById('fot-table');
    if (!table) return;
    
    // Добавляем обработчики для строк таблицы
    table.addEventListener('click', function(e) {
        const row = e.target.closest('tr');
        if (row && !row.classList.contains('loading-cell') && !row.closest('thead') && !row.closest('tfoot')) {
            const projectName = row.cells[0].textContent;
            if (projectName && projectName !== 'Загрузка данных...') {
                showProjectDetails(projectName);
            }
        }
    });
}

// Загрузка данных отчета
async function loadReportData() {
    showLoadingState();
    
    try {
        const response = await fetch('/api/report4/data');
        const data = await response.json();
        
        if (data.success) {
            fotData = data.projects;
            updateSummaryCards(data);
            updateTable(data.projects);
            updateCharts(data);
            updateAnalytics(data);
            showNotification('Данные ФОТ обновлены', 'success');
        } else {
            showErrorState(data.error);
        }
    } catch (error) {
        console.error('Error loading FOT data:', error);
        showErrorState('Ошибка загрузки данных ФОТ');
    }
}

// Показать состояние загрузки
function showLoadingState() {
    const tableBody = document.getElementById('fot-table-body');
    const summaryCards = document.querySelectorAll('.summary-value');
    
    if (tableBody) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="8" class="loading-cell">
                    <div class="spinner"></div>
                    <span>Загрузка данных...</span>
                </td>
            </tr>
        `;
    }
    
    summaryCards.forEach(card => {
        card.textContent = '...';
    });
}

// Показать состояние ошибки
function showErrorState(message) {
    const tableBody = document.getElementById('fot-table-body');
    
    if (tableBody) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="8" class="error-cell">
                    <i class="fas fa-exclamation-triangle"></i>
                    <span>${message}</span>
                    <button class="btn-secondary small" onclick="loadReportData()">
                        <i class="fas fa-redo"></i> Повторить
                    </button>
                </td>
            </tr>
        `;
    }
}

// Обновление сводных карточек
function updateSummaryCards(data) {
    const totalEmployees = data.projects.reduce((sum, project) => sum + project.employees, 0);
    const totalFot = data.projects.reduce((sum, project) => sum + project.fot_total, 0);
    const avgFot = totalEmployees > 0 ? totalFot / totalEmployees : 0;
    const projectsCount = data.projects.length;
    
    document.getElementById('total-employees').textContent = totalEmployees;
    document.getElementById('total-fot').textContent = formatCurrency(totalFot);
    document.getElementById('avg-fot').textContent = formatCurrency(avgFot);
    document.getElementById('projects-count').textContent = projectsCount;
    
    // Обновляем изменения
    updateSummaryChanges(totalEmployees, totalFot, avgFot, projectsCount);
}

// Обновление изменений в сводных карточках
function updateSummaryChanges(employees, fot, avgFot, projects) {
    // Здесь можно добавить логику сравнения с предыдущим периодом
    // Пока используем фиктивные данные
    const employeesChange = document.getElementById('employees-change');
    const fotChange = document.getElementById('fot-change');
    const avgFotChange = document.getElementById('avg-fot-change');
    const projectsChange = document.getElementById('projects-change');
    
    if (employeesChange) {
        employeesChange.innerHTML = `<span class="positive">+5 с прошлого месяца</span>`;
    }
    
    if (fotChange) {
        fotChange.innerHTML = `<span class="positive">+12% с прошлого месяца</span>`;
    }
    
    if (avgFotChange) {
        avgFotChange.innerHTML = `<span class="positive">+8% с прошлого месяца</span>`;
    }
    
    if (projectsChange) {
        projectsChange.innerHTML = `<span class="positive">+2 новых проекта</span>`;
    }
}

// Обновление таблицы
function updateTable(projects) {
    const tbody = document.getElementById('fot-table-body');
    const totalEmployeesFooter = document.getElementById('total-employees-footer');
    const totalFotFooter = document.getElementById('total-fot-footer');
    const avgFotFooter = document.getElementById('avg-fot-footer');
    
    if (!tbody) return;
    
    let html = '';
    let totalEmployees = 0;
    let totalFot = 0;
    
    projects.forEach(project => {
        const efficiency = calculateFOTEfficiency(project);
        const efficiencyClass = getEfficiencyClass(efficiency);
        
        html += `
            <tr data-project="${project.project}">
                <td>
                    <div class="project-name">
                        ${project.project}
                        ${project.fot_total > 100000 ? '<i class="fas fa-star premium"></i>' : ''}
                    </div>
                </td>
                <td>
                    <span class="project-group ${project.group.toLowerCase()}">
                        ${project.group}
                    </span>
                </td>
                <td class="center">
                    <span class="employee-count">${project.employees}</span>
                    ${project.employees > 10 ? '<i class="fas fa-users"></i>' : ''}
                </td>
                <td class="right ${project.fot_total > 50000 ? 'highlight' : ''}">
                    ${formatCurrency(project.fot_total)}
                </td>
                <td class="right">
                    ${formatCurrency(project.fot_per_employee)}
                </td>
                <td class="center">
                    <div class="percentage-bar">
                        <div class="percentage-fill" style="width: ${project.fot_percentage}%"></div>
                        <span class="percentage-text">${project.fot_percentage.toFixed(1)}%</span>
                    </div>
                </td>
                <td class="center">
                    <span class="efficiency-badge ${efficiencyClass}">
                        ${efficiency}
                    </span>
                </td>
                <td class="center">
                    <div class="action-buttons">
                        <button class="btn-icon small" onclick="showEmployeeList('${project.project}')" title="Сотрудники">
                            <i class="fas fa-user-friends"></i>
                        </button>
                        <button class="btn-icon small" onclick="showProjectDetails('${project.project}')" title="Детали">
                            <i class="fas fa-chart-bar"></i>
                        </button>
                        <button class="btn-icon small ${efficiencyClass === 'low' ? 'warning' : ''}" 
                                onclick="showFOTAnalysis('${project.project}')" title="Анализ">
                            <i class="fas fa-search"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
        
        totalEmployees += project.employees;
        totalFot += project.fot_total;
    });
    
    tbody.innerHTML = html;
    
    // Обновляем футер
    if (totalEmployeesFooter) {
        totalEmployeesFooter.textContent = totalEmployees;
    }
    
    if (totalFotFooter) {
        totalFotFooter.textContent = formatCurrency(totalFot);
    }
    
    if (avgFotFooter) {
        const avgFot = totalEmployees > 0 ? totalFot / totalEmployees : 0;
        avgFotFooter.textContent = formatCurrency(avgFot);
    }
}

// Расчет эффективности ФОТ
function calculateFOTEfficiency(project) {
    // Простая формула эффективности
    // В реальном приложении нужно использовать более сложную логику
    const fotPerEmployee = project.fot_per_employee;
    
    if (fotPerEmployee < 30000) return 'Высокая';
    if (fotPerEmployee < 60000) return 'Средняя';
    return 'Низкая';
}

// Получение класса эффективности
function getEfficiencyClass(efficiency) {
    switch(efficiency) {
        case 'Высокая': return 'high';
        case 'Средняя': return 'medium';
        case 'Низкая': return 'low';
        default: return 'medium';
    }
}

// Инициализация графиков
function initCharts() {
    initEmployeesChart();
    initFOTResultChart();
    initTrendChart();
}

// График распределения сотрудников
function initEmployeesChart() {
    const canvas = document.getElementById('employees-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    employeesChart = new Chart(ctx, {
        type: 'doughnut',
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
    document.getElementById('employees-chart-type')?.addEventListener('change', function() {
        if (employeesChart) {
            const newType = this.value;
            employeesChart.destroy();
            
            const ctx = canvas.getContext('2d');
            employeesChart = new Chart(ctx, {
                type: newType,
                data: employeesChart.data,
                options: employeesChart.options
            });
        }
    });
}

// График соотношения ФОТ/Результат
function initFOTResultChart() {
    const canvas = document.getElementById('fot-result-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    fotResultChart = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: []
        },
        options: {
            responsive: true,
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'ФОТ (тыс. руб.)'
                    },
                    ticks: {
                        callback: function(value) {
                            return value / 1000 + 'k';
                        }
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Результат (тыс. руб.)'
                    },
                    ticks: {
                        callback: function(value) {
                            return value / 1000 + 'k';
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const project = context.raw.project;
                            const fot = context.parsed.x;
                            const result = context.parsed.y;
                            return [
                                `Проект: ${project}`,
                                `ФОТ: ${formatCurrency(fot)}`,
                                `Результат: ${formatCurrency(result)}`
                            ];
                        }
                    }
                }
            }
        }
    });
}

// График динамики ФОТ
function initTrendChart() {
    const canvas = document.getElementById('fot-trend-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    trendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Общий ФОТ',
                    data: [],
                    borderColor: 'rgba(0, 122, 255, 1)',
                    backgroundColor: 'rgba(0, 122, 255, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'ФОТ на сотрудника',
                    data: [],
                    borderColor: 'rgba(52, 199, 89, 1)',
                    backgroundColor: 'rgba(52, 199, 89, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }
            ]
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
    
    // Изменение периода
    document.getElementById('trend-period')?.addEventListener('change', function() {
        // Здесь можно загрузить данные за выбранный период
        updateTrendChart(this.value);
    });
}

// Обновление графиков
function updateCharts(data) {
    updateEmployeesChart(data.groups);
    updateFOTResultChart(data.projects);
    updateTrendChart();
}

// Обновление графика сотрудников
function updateEmployeesChart(groups) {
    if (!employeesChart || !groups) return;
    
    const labels = [];
    const data = [];
    const backgroundColors = [];
    
    Object.keys(groups).forEach(group => {
        if (groups[group].employees > 0) {
            labels.push(group);
            data.push(groups[group].employees);
            
            // Цвета по группам
            if (group === 'DCA') backgroundColors.push('rgba(0, 122, 255, 0.8)');
            else if (group === 'DP') backgroundColors.push('rgba(52, 199, 89, 0.8)');
            else backgroundColors.push('rgba(255, 149, 0, 0.8)');
        }
    });
    
    employeesChart.data.labels = labels;
    employeesChart.data.datasets[0].data = data;
    employeesChart.data.datasets[0].backgroundColor = backgroundColors;
    employeesChart.update();
}

// Обновление графика ФОТ/Результат
function updateFOTResultChart(projects) {
    if (!fotResultChart || !projects) return;
    
    const datasets = [
        {
            label: 'DCA',
            data: [],
            backgroundColor: 'rgba(0, 122, 255, 0.6)',
            borderColor: 'rgba(0, 122, 255, 1)',
            borderWidth: 1
        },
        {
            label: 'DP',
            data: [],
            backgroundColor: 'rgba(52, 199, 89, 0.6)',
            borderColor: 'rgba(52, 199, 89, 1)',
            borderWidth: 1
        },
        {
            label: 'Прочие',
            data: [],
            backgroundColor: 'rgba(255, 149, 0, 0.6)',
            borderColor: 'rgba(255, 149, 0, 1)',
            borderWidth: 1
        }
    ];
    
    // Нужны данные о результатах проектов
    // Пока используем фиктивные данные
    projects.forEach(project => {
        const datasetIndex = project.group === 'DCA' ? 0 : project.group === 'DP' ? 1 : 2;
        
        // Фиктивный результат (в реальном приложении нужно загрузить из API)
        const result = project.fot_total * (Math.random() * 2 + 0.5);
        
        datasets[datasetIndex].data.push({
            x: project.fot_total,
            y: result,
            project: project.project
        });
    });
    
    fotResultChart.data.datasets = datasets;
    fotResultChart.update();
}

// Обновление графика тренда
function updateTrendChart(period = '6') {
    if (!trendChart) return;
    
    // Генерируем фиктивные данные для демонстрации
    // В реальном приложении нужно загрузить из API
    const months = getMonths(parseInt(period));
    const totalFOTData = months.map(() => Math.floor(Math.random() * 1000000) + 500000);
    const avgFOTData = months.map(() => Math.floor(Math.random() * 100000) + 30000);
    
    trendChart.data.labels = months;
    trendChart.data.datasets[0].data = totalFOTData;
    trendChart.data.datasets[1].data = avgFOTData;
    trendChart.update();
}

// Получение списка месяцев
function getMonths(count) {
    const months = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн', 'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек'];
    const today = new Date();
    const result = [];
    
    for (let i = count - 1; i >= 0; i--) {
        const date = new Date(today.getFullYear(), today.getMonth() - i, 1);
        const monthIndex = date.getMonth();
        result.push(months[monthIndex]);
    }
    
    return result;
}

// Обновление аналитики
function updateAnalytics(data) {
    updateTopEfficiency(data.projects);
    updateHighFOTProjects(data.projects);
    updateRecommendations(data.projects);
}

// Обновление топа по эффективности
function updateTopEfficiency(projects) {
    const container = document.getElementById('top-fot-efficiency');
    if (!container) return;
    
    // Сортируем по эффективности (ФОТ на сотрудника, чем меньше - тем лучше)
    const sortedProjects = [...projects]
        .sort((a, b) => a.fot_per_employee - b.fot_per_employee)
        .slice(0, 5);
    
    let html = '<div class="top-efficiency-list">';
    
    sortedProjects.forEach((project, index) => {
        html += `
            <div class="efficiency-item">
                <div class="efficiency-rank">${index + 1}</div>
                <div class="efficiency-info">
                    <div class="efficiency-project">${project.project}</div>
                    <div class="efficiency-details">
                        <span class="fot-per-employee">${formatCurrency(project.fot_per_employee)}</span>
                        <span class="employee-count">${project.employees} чел.</span>
                    </div>
                </div>
                <div class="efficiency-score high">
                    <i class="fas fa-trophy"></i>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

// Обновление списка проектов с высоким ФОТ
function updateHighFOTProjects(projects) {
    const container = document.getElementById('high-fot-projects');
    if (!container) return;
    
    // Проекты с ФОТ выше среднего
    const totalFOT = projects.reduce((sum, project) => sum + project.fot_total, 0);
    const avgFOT = totalFOT / projects.length;
    
    const highFOTProjects = projects
        .filter(project => project.fot_total > avgFOT)
        .sort((a, b) => b.fot_total - a.fot_total)
        .slice(0, 5);
    
    if (highFOTProjects.length === 0) {
        container.innerHTML = `
            <div class="no-warnings">
                <i class="fas fa-check-circle positive"></i>
                <p>Нет проектов с аномально высоким ФОТ</p>
            </div>
        `;
        return;
    }
    
    let html = '<div class="warning-list">';
    
    highFOTProjects.forEach(project => {
        const percentageAboveAvg = ((project.fot_total - avgFOT) / avgFOT * 100).toFixed(1);
        
        html += `
            <div class="warning-item">
                <div class="warning-icon">
                    <i class="fas fa-exclamation-triangle"></i>
                </div>
                <div class="warning-info">
                    <div class="warning-project">${project.project}</div>
                    <div class="warning-details">
                        ФОТ выше среднего на ${percentageAboveAvg}%
                    </div>
                </div>
                <div class="warning-action">
                    <button class="btn-icon small" onclick="optimizeFOT('${project.project}')">
                        <i class="fas fa-cog"></i>
                    </button>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

// Обновление рекомендаций
function updateRecommendations(projects) {
    const container = document.getElementById('fot-recommendations');
    if (!container) return;
    
    // Анализируем данные и формируем рекомендации
    const recommendations = analyzeFOTData(projects);
    
    let html = '<div class="recommendations-list">';
    
    recommendations.forEach((rec, index) => {
        html += `
            <div class="recommendation-item">
                <div class="recommendation-icon ${rec.priority}">
                    <i class="fas fa-${rec.icon}"></i>
                </div>
                <div class="recommendation-content">
                    <h5>${rec.title}</h5>
                    <p>${rec.description}</p>
                    ${rec.action ? `
                        <button class="btn-secondary small" onclick="${rec.action}">
                            ${rec.actionText}
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

// Анализ данных ФОТ для рекомендаций
function analyzeFOTData(projects) {
    const recommendations = [];
    
    // 1. Проверяем дисбаланс распределения
    const groupDistribution = {};
    let totalEmployees = 0;
    
    projects.forEach(project => {
        if (!groupDistribution[project.group]) {
            groupDistribution[project.group] = 0;
        }
        groupDistribution[project.group] += project.employees;
        totalEmployees += project.employees;
    });
    
    // Проверяем, если одна группа имеет > 60% сотрудников
    Object.keys(groupDistribution).forEach(group => {
        const percentage = (groupDistribution[group] / totalEmployees * 100);
        if (percentage > 60) {
            recommendations.push({
                title: 'Дисбаланс распределения',
                description: `Группа ${group} составляет ${percentage.toFixed(1)}% всех сотрудников. Рассмотрите перераспределение.`,
                icon: 'balance-scale',
                priority: 'high',
                action: 'showDistributionAnalysis()',
                actionText: 'Анализ распределения'
            });
        }
    });
    
    // 2. Проверяем высокий ФОТ на сотрудника
    const highFOTProjects = projects.filter(p => p.fot_per_employee > 80000);
    if (highFOTProjects.length > 0) {
        recommendations.push({
            title: 'Высокий ФОТ на сотрудника',
            description: `${highFOTProjects.length} проект(ов) имеет ФОТ на сотрудника выше 80,000 руб.`,
            icon: 'money-bill-wave',
            priority: 'medium',
            action: 'showHighFOTAnalysis()',
            actionText: 'Детальный анализ'
        });
    }
    
    // 3. Проверяем низкую эффективность
    const lowEfficiencyProjects = projects.filter(p => {
        const efficiency = calculateFOTEfficiency(p);
        return efficiency === 'Низкая';
    });
    
    if (lowEfficiencyProjects.length > 0) {
        recommendations.push({
            title: 'Низкая эффективность ФОТ',
            description: `${lowEfficiencyProjects.length} проект(ов) имеет низкую эффективность затрат на персонал.`,
            icon: 'chart-line',
            priority: 'high',
            action: 'showEfficiencyAnalysis()',
            actionText: 'Анализ эффективности'
        });
    }
    
    // 4. Общие рекомендации
    recommendations.push({
        title: 'Внедрение KPI',
        description: 'Рекомендуется внедрить систему ключевых показателей для оценки эффективности сотрудников.',
        icon: 'bullseye',
        priority: 'low',
        action: null,
        actionText: null
    });
    
    recommendations.push({
        title: 'Оптимизация процессов',
        description: 'Автоматизация рутинных задач может снизить потребность в персонале на 15-20%.',
        icon: 'robot',
        priority: 'medium',
        action: null,
        actionText: null
    });
    
    return recommendations;
}

// Показать детали проекта
async function showProjectDetails(projectName) {
    const project = fotData.find(p => p.project === projectName);
    if (!project) {
        showNotification('Проект не найден', 'error');
        return;
    }
    
    const section = document.getElementById('project-details-section');
    if (!section) return;
    
    // Загружаем дополнительные данные о проекте
    const projectDetails = await loadProjectDetails(projectName);
    
    // Обновляем заголовок
    document.getElementById('details-project-name').textContent = projectName;
    
    // Обновляем информацию о сотрудниках
    updateProjectEmployees(project, projectDetails);
    
    // Обновляем детализацию ФОТ
    updateProjectFOTDetails(project, projectDetails);
    
    // Обновляем эффективность
    updateProjectEfficiency(project, projectDetails);
    
    // Обновляем историю
    updateProjectHistory(projectName);
    
    // Показываем секцию
    section.style.display = 'block';
    
    // Прокручиваем к секции
    section.scrollIntoView({ behavior: 'smooth' });
}

// Загрузка дополнительных данных о проекте
async function loadProjectDetails(projectName) {
    try {
        // Здесь можно загрузить дополнительные данные из API
        // Пока возвращаем фиктивные данные
        return {
            employees: [
                { name: 'Иванов И.И.', position: 'Менеджер', fot: 85000 },
                { name: 'Петрова А.С.', position: 'Аналитик', fot: 75000 },
                { name: 'Сидоров Д.В.', position: 'Разработчик', fot: 95000 }
            ],
            fot_breakdown: [
                { category: 'Оклад', amount: 200000 },
                { category: 'Премии', amount: 50000 },
                { category: 'Соцпакет', amount: 30000 }
            ],
            metrics: {
                productivity: 85,
                utilization: 92,
                satisfaction: 78
            }
        };
    } catch (error) {
        console.error('Error loading project details:', error);
        return null;
    }
}

// Обновление информации о сотрудниках проекта
function updateProjectEmployees(project, details) {
    const container = document.getElementById('project-employees');
    if (!container) return;
    
    let html = `
        <div class="employees-summary">
            <div class="summary-item">
                <span class="label">Всего:</span>
                <span class="value">${project.employees} чел.</span>
            </div>
            <div class="summary-item">
                <span class="label">Средний ФОТ:</span>
                <span class="value">${formatCurrency(project.fot_per_employee)}</span>
            </div>
            <div class="summary-item">
                <span class="label">Группа:</span>
                <span class="value project-group ${project.group.toLowerCase()}">${project.group}</span>
            </div>
        </div>
    `;
    
    if (details && details.employees) {
        html += '<div class="employees-list">';
        html += '<h5>Ключевые сотрудники:</h5>';
        
        details.employees.forEach(employee => {
            html += `
                <div class="employee-card" onclick="showEmployeeModal('${employee.name}', '${project.project}')">
                    <div class="employee-avatar">
                        <i class="fas fa-user-circle"></i>
                    </div>
                    <div class="employee-info">
                        <div class="employee-name">${employee.name}</div>
                        <div class="employee-position">${employee.position}</div>
                    </div>
                    <div class="employee-fot">
                        ${formatCurrency(employee.fot)}
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
    }
    
    container.innerHTML = html;
}

// Обновление детализации ФОТ проекта
function updateProjectFOTDetails(project, details) {
    const container = document.getElementById('project-fot-details');
    if (!container) return;
    
    let html = `
        <div class="fot-summary">
            <div class="summary-item large">
                <span class="label">Общий ФОТ:</span>
                <span class="value highlight">${formatCurrency(project.fot_total)}</span>
            </div>
            <div class="summary-item">
                <span class="label">% от общего:</span>
                <span class="value">${project.fot_percentage.toFixed(1)}%</span>
            </div>
        </div>
    `;
    
    if (details && details.fot_breakdown) {
        html += '<div class="fot-breakdown">';
        html += '<h5>Структура ФОТ:</h5>';
        
        details.fot_breakdown.forEach(item => {
            const percentage = (item.amount / project.fot_total * 100).toFixed(1);
            html += `
                <div class="breakdown-item">
                    <div class="breakdown-header">
                        <span class="category">${item.category}</span>
                        <span class="amount">${formatCurrency(item.amount)}</span>
                    </div>
                    <div class="breakdown-bar">
                        <div class="bar-fill" style="width: ${percentage}%"></div>
                        <span class="percentage">${percentage}%</span>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
    }
    
    container.innerHTML = html;
}

// Обновление эффективности проекта
function updateProjectEfficiency(project, details) {
    const container = document.getElementById('project-efficiency');
    if (!container) return;
    
    const efficiency = calculateFOTEfficiency(project);
    const efficiencyClass = getEfficiencyClass(efficiency);
    
    let html = `
        <div class="efficiency-score-card ${efficiencyClass}">
            <div class="score-icon">
                <i class="fas fa-${efficiencyClass === 'high' ? 'trophy' : efficiencyClass === 'medium' ? 'chart-line' : 'exclamation-triangle'}"></i>
            </div>
            <div class="score-content">
                <div class="score-title">Эффективность ФОТ</div>
                <div class="score-value">${efficiency}</div>
                <div class="score-subtitle">${project.fot_per_employee.toLocaleString()} руб./чел.</div>
            </div>
        </div>
    `;
    
    if (details && details.metrics) {
        html += '<div class="efficiency-metrics">';
        html += '<h5>Дополнительные метрики:</h5>';
        
        Object.keys(details.metrics).forEach(key => {
            const value = details.metrics[key];
            const metricName = {
                productivity: 'Продуктивность',
                utilization: 'Загрузка',
                satisfaction: 'Удовлетворенность'
            }[key] || key;
            
            html += `
                <div class="metric-item">
                    <span class="metric-label">${metricName}:</span>
                    <div class="metric-bar">
                        <div class="bar-fill" style="width: ${value}%"></div>
                        <span class="metric-value">${value}%</span>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
    }
    
    html += `
        <div class="efficiency-actions">
            <button class="btn-secondary" onclick="showFOTAnalysis('${project.project}')">
                <i class="fas fa-chart-pie"></i> Детальный анализ
            </button>
            <button class="btn-primary" onclick="optimizeFOT('${project.project}')">
                <i class="fas fa-cog"></i> Оптимизировать
            </button>
        </div>
    `;
    
    container.innerHTML = html;
}

// Обновление истории проекта
function updateProjectHistory(projectName) {
    const canvas = document.getElementById('project-history-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Создаем временный график для демонстрации
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн'],
            datasets: [
                {
                    label: 'ФОТ',
                    data: [80000, 85000, 82000, 90000, 95000, 92000],
                    borderColor: 'rgba(0, 122, 255, 1)',
                    backgroundColor: 'rgba(0, 122, 255, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Сотрудники',
                    data: [3, 3, 4, 4, 5, 5],
                    borderColor: 'rgba(52, 199, 89, 1)',
                    backgroundColor: 'rgba(52, 199, 89, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'ФОТ (руб.)'
                    },
                    ticks: {
                        callback: function(value) {
                            return formatCurrency(value);
                        }
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Сотрудники (чел.)'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                }
            }
        }
    });
}

// Скрыть детали проекта
function hideProjectDetails() {
    const section = document.getElementById('project-details-section');
    if (section) {
        section.style.display = 'none';
    }
}

// Показать список сотрудников проекта
function showEmployeeList(projectName) {
    const project = fotData.find(p => p.project === projectName);
    if (!project) return;
    
    openModal('employee-modal');
    
    // Обновляем информацию в модальном окне
    document.getElementById('employee-name').textContent = `Сотрудники: ${projectName}`;
    document.getElementById('modal-project').textContent = projectName;
    document.getElementById('modal-group').textContent = project.group;
    document.getElementById('modal-fot').textContent = formatCurrency(project.fot_total);
    document.getElementById('modal-period').textContent = 'Текущий месяц';
    document.getElementById('modal-comments').textContent = `${project.employees} сотрудников, средний ФОТ: ${formatCurrency(project.fot_per_employee)}`;
    
    // Создаем график активности
    createEmployeeActivityChart();
}

// Создание графика активности сотрудников
function createEmployeeActivityChart() {
    const canvas = document.getElementById('employee-activity-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
            datasets: [{
                label: 'Активность',
                data: [85, 92, 78, 95, 88, 45, 20],
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
                    max: 100,
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

// Закрытие модального окна сотрудника
function closeEmployeeModal() {
    closeModal('employee-modal');
}

// Показать анализ ФОТ
function showFOTAnalysis(projectName) {
    const project = fotData.find(p => p.project === projectName);
    if (!project) return;
    
    let analysis = `
        <h4>Анализ ФОТ: ${projectName}</h4>
        <div class="analysis-content">
            <div class="analysis-section">
                <h5>Основные показатели:</h5>
                <ul>
                    <li>Общий ФОТ: ${formatCurrency(project.fot_total)}</li>
                    <li>Сотрудников: ${project.employees} чел.</li>
                    <li>ФОТ на сотрудника: ${formatCurrency(project.fot_per_employee)}</li>
                    <li>Доля от общего ФОТ: ${project.fot_percentage.toFixed(1)}%</li>
                </ul>
            </div>
            
            <div class="analysis-section">
                <h5>Оценка эффективности:</h5>
                <p>Эффективность: <strong class="${getEfficiencyClass(calculateFOTEfficiency(project))}">${calculateFOTEfficiency(project)}</strong></p>
                <p>${getEfficiencyDescription(project)}</p>
            </div>
            
            <div class="analysis-section">
                <h5>Рекомендации:</h5>
                <ol>
                    ${getFOTRecommendations(project)}
                </ol>
            </div>
        </div>
    `;
    
    openModal('analysis-modal');
    document.getElementById('analysis-modal-content').innerHTML = analysis;
}

// Получение описания эффективности
function getEfficiencyDescription(project) {
    const efficiency = calculateFOTEfficiency(project);
    const avgFOT = project.fot_per_employee;
    
    switch(efficiency) {
        case 'Высокая':
            return `ФОТ на сотрудника (${formatCurrency(avgFOT)}) ниже среднего по компании. Эффективное использование ресурсов.`;
        case 'Средняя':
            return `ФОТ на сотрудника (${formatCurrency(avgFOT)}) соответствует средним показателям.`;
        case 'Низкая':
            return `ФОТ на сотрудника (${formatCurrency(avgFOT)}) выше среднего. Рекомендуется оптимизация.`;
        default:
            return '';
    }
}

// Получение рекомендаций по ФОТ
function getFOTRecommendations(project) {
    const efficiency = calculateFOTEfficiency(project);
    let recommendations = '';
    
    if (efficiency === 'Низкая') {
        recommendations += `
            <li>Рассмотреть возможность сокращения непроизводительных затрат</li>
            <li>Оптимизировать структуру команды</li>
            <li>Внедрить систему KPI для повышения эффективности</li>
            <li>Рассмотреть аутсорсинг части функций</li>
        `;
    } else if (efficiency === 'Средняя') {
        recommendations += `
            <li>Мониторить динамику ФОТ на сотрудника</li>
            <li>Провести сравнительный анализ с аналогичными проектами</li>
            <li>Рассмотреть возможности для повышения эффективности</li>
        `;
    } else {
        recommendations += `
            <li>Поддерживать текущий уровень эффективности</li>
            <li>Изучить возможности для масштабирования успешной модели</li>
            <li>Делиться лучшими практиками с другими проектами</li>
        `;
    }
    
    return recommendations;
}

// Оптимизация ФОТ
function optimizeFOT(projectName) {
    const project = fotData.find(p => p.project === projectName);
    if (!project) return;
    
    let optimization = `
        <h4>План оптимизации ФОТ: ${projectName}</h4>
        <div class="optimization-content">
            <div class="optimization-current">
                <h5>Текущее состояние:</h5>
                <ul>
                    <li>ФОТ: ${formatCurrency(project.fot_total)}</li>
                    <li>Сотрудников: ${project.employees}</li>
                    <li>ФОТ на сотрудника: ${formatCurrency(project.fot_per_employee)}</li>
                </ul>
            </div>
            
            <div class="optimization-target">
                <h5>Целевые показатели:</h5>
                <ul>
                    <li>Сокращение ФОТ на 15%</li>
                    <li>Оптимизация команды: -1 сотрудник</li>
                    <li>Целевой ФОТ на сотрудника: ${formatCurrency(project.fot_per_employee * 0.85)}</li>
                </ul>
            </div>
            
            <div class="optimization-steps">
                <h5>Шаги оптимизации:</h5>
                <ol>
                    <li>Анализ текущей загрузки сотрудников</li>
                    <li>Выявление дублирующих функций</li>
                    <li>Автоматизация рутинных процессов</li>
                    <li>Пересмотр системы премирования</li>
                    <li>Внедрение системы учета рабочего времени</li>
                </ol>
            </div>
            
            <div class="optimization-actions">
                <button class="btn-primary" onclick="startOptimization('${projectName}')">
                    <i class="fas fa-play"></i> Запустить оптимизацию
                </button>
                <button class="btn-secondary" onclick="closeModal('optimization-modal')">
                    <i class="fas fa-times"></i> Отмена
                </button>
            </div>
        </div>
    `;
    
    openModal('optimization-modal');
    document.getElementById('optimization-modal-content').innerHTML = optimization;
}

// Запуск оптимизации
function startOptimization(projectName) {
    showNotification(`Запущена оптимизация ФОТ для проекта "${projectName}"`, 'success');
    closeModal('optimization-modal');
    
    // Здесь можно добавить логику сохранения плана оптимизации
}

// Обновление данных
document.getElementById('refresh-fot')?.addEventListener('click', loadReportData);

// Экспорт данных
document.getElementById('export-fot')?.addEventListener('click', function() {
    if (fotData.length === 0) {
        showNotification('Нет данных для экспорта', 'error');
        return;
    }
    
    const exportData = fotData.map(project => ({
        'Проект': project.project,
        'Группа': project.group,
        'Сотрудников': project.employees,
        'ФОТ общий': project.fot_total,
        'ФОТ на сотрудника': project.fot_per_employee,
        'Доля от общего ФОТ': project.fot_percentage.toFixed(1) + '%',
        'Эффективность': calculateFOTEfficiency(project)
    }));
    
    exportToCSV(exportData, `fot_analysis_${new Date().toISOString().split('T')[0]}.csv`);
});

// Добавляем стили для отчета 4
const report4Styles = document.createElement('style');
report4Styles.textContent = `
    .summary-cards {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: var(--spacing-lg);
        margin-bottom: var(--spacing-xl);
    }
    
    .summary-card {
        background: var(--apple-card);
        border-radius: var(--radius-lg);
        padding: var(--spacing-lg);
        display: flex;
        gap: var(--spacing-lg);
        align-items: center;
        transition: var(--transition-normal);
    }
    
    .summary-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--apple-shadow-hover);
    }
    
    .summary-icon {
        width: 60px;
        height: 60px;
        border-radius: var(--radius-lg);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
    }
    
    .summary-icon.employees {
        background-color: rgba(0, 122, 255, 0.1);
        color: var(--apple-blue);
    }
    
    .summary-icon.fot {
        background-color: rgba(52, 199, 89, 0.1);
        color: var(--apple-green);
    }
    
    .summary-icon.avg {
        background-color: rgba(255, 149, 0, 0.1);
        color: var(--apple-orange);
    }
    
    .summary-icon.projects {
        background-color: rgba(175, 82, 222, 0.1);
        color: var(--apple-purple);
    }
    
    .summary-value {
        font-size: 2rem;
        font-weight: 700;
        margin: var(--spacing-xs) 0;
    }
    
    .summary-change {
        font-size: 0.9rem;
        color: var(--apple-text-secondary);
    }
    
    .data-table td.center {
        text-align: center;
    }
    
    .data-table td.right {
        text-align: right;
    }
    
    .employee-count {
        font-weight: 600;
        color: var(--apple-blue);
    }
    
    .highlight {
        font-weight: 700;
        color: var(--apple-orange);
    }
    
    .percentage-bar {
        position: relative;
        height: 24px;
        background: var(--apple-border);
        border-radius: var(--radius-sm);
        overflow: hidden;
    }
    
    .percentage-fill {
        height: 100%;
        background: var(--apple-blue);
        transition: width 0.3s ease;
    }
    
    .percentage-text {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.8rem;
        font-weight: 600;
        color: white;
        text-shadow: 0 1px 1px rgba(0,0,0,0.3);
    }
    
    .efficiency-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: var(--radius-full);
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    .efficiency-badge.high {
        background-color: rgba(52, 199, 89, 0.1);
        color: var(--apple-green);
    }
    
    .efficiency-badge.medium {
        background-color: rgba(255, 149, 0, 0.1);
        color: var(--apple-orange);
    }
    
    .efficiency-badge.low {
        background-color: rgba(255, 59, 48, 0.1);
        color: var(--apple-red);
    }
    
    .premium {
        color: var(--apple-yellow);
        margin-left: 4px;
    }
    
    .warning {
        color: var(--apple-red);
    }
    
    /* Детализация проекта */
    .details-section {
        background: var(--apple-card);
        border-radius: var(--radius-lg);
        padding: var(--spacing-lg);
        margin-top: var(--spacing-xl);
        box-shadow: var(--apple-shadow);
    }
    
    .details-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: var(--spacing-lg);
        padding-bottom: var(--spacing-md);
        border-bottom: 1px solid var(--apple-border);
    }
    
    .details-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: var(--spacing-lg);
    }
    
    .details-card {
        padding: var(--spacing-lg);
        border: 1px solid var(--apple-border);
        border-radius: var(--radius-md);
    }
    
    .details-card.full-width {
        grid-column: 1 / -1;
    }
    
    .employees-summary {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: var(--spacing-md);
        margin-bottom: var(--spacing-lg);
    }
    
    .summary-item {
        padding: var(--spacing-md);
        background: var(--apple-bg);
        border-radius: var(--radius-sm);
    }
    
    .summary-item.large .value {
        font-size: 1.5rem;
    }
    
    .employees-list {
        margin-top: var(--spacing-lg);
    }
    
    .employee-card {
        display: flex;
        align-items: center;
        gap: var(--spacing-md);
        padding: var(--spacing-md);
        border: 1px solid var(--apple-border);
        border-radius: var(--radius-sm);
        margin-bottom: var(--spacing-sm);
        cursor: pointer;
        transition: var(--transition-fast);
    }
    
    .employee-card:hover {
        background: var(--apple-bg);
        transform: translateX(4px);
    }
    
    .employee-avatar {
        font-size: 2rem;
        color: var(--apple-blue);
    }
    
    .fot-breakdown {
        margin-top: var(--spacing-lg);
    }
    
    .breakdown-item {
        margin-bottom: var(--spacing-md);
    }
    
    .breakdown-header {
        display: flex;
        justify-content: space-between;
        margin-bottom: var(--spacing-xs);
    }
    
    .breakdown-bar {
        position: relative;
        height: 20px;
        background: var(--apple-border);
        border-radius: var(--radius-sm);
        overflow: hidden;
    }
    
    .bar-fill {
        height: 100%;
        background: var(--apple-blue);
        transition: width 0.3s ease;
    }
    
    .efficiency-score-card {
        display: flex;
        align-items: center;
        gap: var(--spacing-lg);
        padding: var(--spacing-lg);
        border-radius: var(--radius-md);
        margin-bottom: var(--spacing-lg);
    }
    
    .efficiency-score-card.high {
        background-color: rgba(52, 199, 89, 0.1);
        border-left: 4px solid var(--apple-green);
    }
    
    .efficiency-score-card.medium {
        background-color: rgba(255, 149, 0, 0.1);
        border-left: 4px solid var(--apple-orange);
    }
    
    .efficiency-score-card.low {
        background-color: rgba(255, 59, 48, 0.1);
        border-left: 4px solid var(--apple-red);
    }
    
    .score-icon {
        font-size: 2.5rem;
    }
    
    .score-title {
        font-size: 0.9rem;
        color: var(--apple-text-secondary);
        margin-bottom: var(--spacing-xs);
    }
    
    .score-value {
        font-size: 1.8rem;
        font-weight: 700;
        margin-bottom: var(--spacing-xs);
    }
    
    .efficiency-metrics {
        margin: var(--spacing-lg) 0;
    }
    
    .metric-item {
        margin-bottom: var(--spacing-md);
    }
    
    .metric-bar {
        position: relative;
        height: 20px;
        background: var(--apple-border);
        border-radius: var(--radius-sm);
        overflow: hidden;
        margin-top: var(--spacing-xs);
    }
    
    .metric-bar .bar-fill {
        background: var(--apple-green);
    }
    
    .metric-value {
        position: absolute;
        top: 0;
        right: var(--spacing-sm);
        bottom: 0;
        display: flex;
        align-items: center;
        font-size: 0.8rem;
        font-weight: 600;
        color: white;
        text-shadow: 0 1px 1px rgba(0,0,0,0.3);
    }
    
    .efficiency-actions {
        display: flex;
        gap: var(--spacing-md);
        margin-top: var(--spacing-lg);
    }
    
    /* Аналитика */
    .analytics-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: var(--spacing-lg);
        margin-top: var(--spacing-lg);
    }
    
    .top-efficiency-list, .warning-list, .recommendations-list {
        max-height: 300px;
        overflow-y: auto;
    }
    
    .efficiency-item, .warning-item, .recommendation-item {
        display: flex;
        align-items: center;
        gap: var(--spacing-md);
        padding: var(--spacing-md);
        border-bottom: 1px solid var(--apple-border);
    }
    
    .efficiency-item:last-child,
    .warning-item:last-child,
    .recommendation-item:last-child {
        border-bottom: none;
    }
    
    .efficiency-rank {
        width: 30px;
        height: 30px;
        background: var(--apple-border);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 600;
    }
    
    .warning-icon {
        color: var(--apple-red);
        font-size: 1.2rem;
    }
    
    .recommendation-icon {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
    }
    
    .recommendation-icon.high {
        background-color: rgba(255, 59, 48, 0.1);
        color: var(--apple-red);
    }
    
    .recommendation-icon.medium {
        background-color: rgba(255, 149, 0, 0.1);
        color: var(--apple-orange);
    }
    
    .recommendation-icon.low {
        background-color: rgba(0, 122, 255, 0.1);
        color: var(--apple-blue);
    }
    
    /* Модальные окна */
    .employee-details {
        display: flex;
        gap: var(--spacing-lg);
        margin-bottom: var(--spacing-lg);
    }
    
    .employee-photo {
        font-size: 4rem;
        color: var(--apple-blue);
    }
    
    .info-row {
        display: flex;
        justify-content: space-between;
        padding: var(--spacing-xs) 0;
        border-bottom: 1px solid var(--apple-border);
    }
    
    .info-row:last-child {
        border-bottom: none;
    }
    
    .info-label {
        color: var(--apple-text-secondary);
    }
    
    .analysis-content, .optimization-content {
        max-height: 400px;
        overflow-y: auto;
        padding-right: var(--spacing-md);
    }
    
    .analysis-section, .optimization-current, .optimization-target, .optimization-steps {
        margin-bottom: var(--spacing-lg);
        padding: var(--spacing-md);
        background: var(--apple-bg);
        border-radius: var(--radius-md);
    }
    
    .optimization-actions {
        display: flex;
        gap: var(--spacing-md);
        justify-content: flex-end;
        margin-top: var(--spacing-lg);
    }
    
    @media (max-width: 768px) {
        .summary-cards {
            grid-template-columns: 1fr;
        }
        
        .details-grid {
            grid-template-columns: 1fr;
        }
        
        .analytics-grid {
            grid-template-columns: 1fr;
        }
        
        .employee-details {
            flex-direction: column;
        }
        
        .efficiency-actions {
            flex-direction: column;
        }
        
        .data-table {
            font-size: 0.8rem;
        }
        
        .percentage-bar {
            height: 20px;
        }
        
        .percentage-text {
            font-size: 0.7rem;
        }
    }
`;
document.head.appendChild(report4Styles);