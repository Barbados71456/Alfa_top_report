// Report 3: Анализ статей расходов/доходов

let sunburstChart = null;
let articlesData = [];

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация
    initDatePicker();
    initFilters();
    initArticlesModal();
    loadReportData();
});

// Инициализация выбора периода
function initDatePicker() {
    const today = new Date();
    const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
    const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
    
    flatpickr("#report3-period", {
        locale: "ru",
        mode: "range",
        dateFormat: "Y-m-d",
        defaultDate: [firstDay, lastDay],
        maxDate: today
    });
    
    // Устанавливаем значение по умолчанию
    const dateRange = `${formatDateForInput(firstDay)} по ${formatDateForInput(lastDay)}`;
    document.getElementById('report3-period').value = dateRange;
}

// Инициализация фильтров
function initFilters() {
    // Применение анализа
    document.getElementById('apply-analysis').addEventListener('click', loadReportData);
    
    // Сброс анализа
    document.getElementById('reset-analysis').addEventListener('click', resetAnalysis);
    
    // Изменение уровня детализации
    document.getElementById('detail-level').addEventListener('change', function() {
        if (articlesData.length > 0) {
            updateSunburstChart();
        }
    });
    
    // Изменение типа операции
    document.getElementById('operation-type').addEventListener('change', function() {
        if (articlesData.length > 0) {
            updateSunburstChart();
            updateTopLists();
        }
    });
    
    // Редактирование статей
    document.getElementById('edit-articles').addEventListener('click', showArticlesModal);
}

// Загрузка данных отчета
async function loadReportData() {
    showLoadingState();
    
    try {
        const response = await fetch('/api/report3/data');
        const data = await response.json();
        
        if (data.success) {
            articlesData = data.sunburst;
            updateSunburstChart();
            updateTopLists(data);
            updateStats(data);
            updateArticlesTable(data);
            showNotification('Данные загружены успешно', 'success');
        } else {
            showErrorState(data.error);
        }
    } catch (error) {
        console.error('Error loading report data:', error);
        showErrorState('Ошибка загрузки данных');
    }
}

// Показать состояние загрузки
function showLoadingState() {
    const sunburstContainer = document.getElementById('sunburst-container');
    const topExpenses = document.getElementById('top-expenses-list');
    const topIncomes = document.getElementById('top-incomes-list');
    
    if (sunburstContainer) {
        sunburstContainer.innerHTML = `
            <div class="loading-chart">
                <div class="spinner"></div>
                <p>Загрузка данных для солнечной диаграммы...</p>
            </div>
        `;
    }
    
    if (topExpenses) {
        topExpenses.innerHTML = `
            <div class="loading-analytics">
                <div class="spinner small"></div>
                <span>Загрузка данных...</span>
            </div>
        `;
    }
    
    if (topIncomes) {
        topIncomes.innerHTML = `
            <div class="loading-analytics">
                <div class="spinner small"></div>
                <span>Загрузка данных...</span>
            </div>
        `;
    }
}

// Показать состояние ошибки
function showErrorState(message) {
    const sunburstContainer = document.getElementById('sunburst-container');
    
    if (sunburstContainer) {
        sunburstContainer.innerHTML = `
            <div class="error-chart">
                <i class="fas fa-exclamation-triangle"></i>
                <h4>${message}</h4>
                <button class="btn-secondary" onclick="loadReportData()">
                    <i class="fas fa-redo"></i> Попробовать снова
                </button>
            </div>
        `;
    }
}

// Обновление солнечной диаграммы
function updateSunburstChart() {
    const canvas = document.getElementById('sunburst-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Фильтруем данные по выбранным параметрам
    const operationType = document.getElementById('operation-type').value;
    const filteredData = filterArticlesData(operationType);
    
    if (filteredData.length === 0) {
        canvas.parentElement.innerHTML = `
            <div class="no-data">
                <i class="fas fa-chart-pie"></i>
                <p>Нет данных для отображения</p>
            </div>
        `;
        return;
    }
    
    // Создаем структуру для sunburst
    const sunburstStructure = createSunburstStructure(filteredData);
    
    // Уничтожаем предыдущий график, если он есть
    if (sunburstChart) {
        sunburstChart.destroy();
    }
    
    // Создаем новый график
    sunburstChart = new Chart(ctx, {
        type: 'sunburst',
        data: {
            datasets: [{
                data: sunburstStructure.data,
                backgroundColor: sunburstStructure.colors,
                borderWidth: 1,
                borderColor: '#fff',
                labels: {
                    display: true,
                    formatter: (ctx) => {
                        return ctx.raw.label + '\n' + formatCurrency(ctx.raw.value);
                    },
                    color: '#fff',
                    font: {
                        size: 10
                    }
                }
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.raw.label || '';
                            const value = context.raw.value || 0;
                            const percentage = context.raw.percentage || 0;
                            return [
                                label,
                                `Сумма: ${formatCurrency(value)}`,
                                `Доля: ${percentage.toFixed(1)}%`
                            ];
                        }
                    }
                }
            },
            onClick: function(evt, elements) {
                if (elements.length > 0) {
                    const element = elements[0];
                    const data = this.data.datasets[0].data[element.index];
                    showArticleDetails(data);
                }
            }
        }
    });
    
    // Обновляем легенду
    updateSunburstLegend(sunburstStructure);
}

// Фильтрация данных статей
function filterArticlesData(operationType) {
    if (operationType === 'all') {
        return articlesData;
    }
    
    return articlesData.filter(item => {
        if (operationType === 'income') {
            return item.type === 'income';
        } else if (operationType === 'expense') {
            return item.type === 'expense';
        }
        return true;
    });
}

// Создание структуры для sunburst
function createSunburstStructure(data) {
    const structure = {
        data: [],
        colors: [],
        legend: []
    };
    
    // Группируем по уровням
    const level1Data = {};
    const level2Data = {};
    
    data.forEach(item => {
        const parts = item.ids.split('/');
        if (parts.length >= 3) {
            const level1 = parts[0];
            const level2 = parts[1];
            const level4 = parts[2];
            
            // Уровень 1
            if (!level1Data[level1]) {
                level1Data[level1] = {
                    value: 0,
                    type: item.type,
                    children: {}
                };
            }
            level1Data[level1].value += item.values;
            
            // Уровень 2
            if (!level1Data[level1].children[level2]) {
                level1Data[level1].children[level2] = {
                    value: 0,
                    type: item.type,
                    children: {}
                };
            }
            level1Data[level1].children[level2].value += item.values;
            
            // Уровень 4
            level1Data[level1].children[level2].children[level4] = {
                value: item.values,
                type: item.type
            };
        }
    });
    
    // Преобразуем в структуру для Chart.js
    let index = 0;
    const totalValue = Object.values(level1Data).reduce((sum, item) => sum + item.value, 0);
    
    Object.keys(level1Data).forEach(level1 => {
        const level1Item = level1Data[level1];
        const level1Percentage = (level1Item.value / totalValue * 100);
        
        // Добавляем уровень 1
        structure.data.push({
            label: level1,
            value: level1Item.value,
            percentage: level1Percentage,
            parent: ''
        });
        
        const level1Color = getColorForType(level1Item.type, index);
        structure.colors.push(level1Color);
        structure.legend.push({
            label: level1,
            value: level1Item.value,
            percentage: level1Percentage,
            color: level1Color
        });
        
        const level1Index = index;
        index++;
        
        // Добавляем уровень 2
        Object.keys(level1Item.children).forEach(level2 => {
            const level2Item = level1Item.children[level2];
            const level2Percentage = (level2Item.value / level1Item.value * 100);
            
            structure.data.push({
                label: level2,
                value: level2Item.value,
                percentage: level2Percentage,
                parent: level1
            });
            
            const level2Color = adjustColor(level1Color, 20);
            structure.colors.push(level2Color);
            
            const level2Index = index;
            index++;
            
            // Добавляем уровень 4 (если выбран)
            const detailLevel = parseInt(document.getElementById('detail-level').value);
            if (detailLevel >= 4) {
                Object.keys(level2Item.children).forEach(level4 => {
                    const level4Item = level2Item.children[level4];
                    const level4Percentage = (level4Item.value / level2Item.value * 100);
                    
                    structure.data.push({
                        label: level4,
                        value: level4Item.value,
                        percentage: level4Percentage,
                        parent: level2
                    });
                    
                    const level4Color = adjustColor(level2Color, 40);
                    structure.colors.push(level4Color);
                    index++;
                });
            }
        });
    });
    
    return structure;
}

// Получение цвета по типу операции
function getColorForType(type, index) {
    const colorSets = {
        income: [
            'rgba(52, 199, 89, 0.8)',    // Зеленый
            'rgba(50, 173, 80, 0.8)',    // Темно-зеленый
            'rgba(48, 150, 72, 0.8)',    // Еще темнее
            'rgba(46, 130, 65, 0.8)'     // Самый темный
        ],
        expense: [
            'rgba(255, 59, 48, 0.8)',    // Красный
            'rgba(220, 50, 40, 0.8)',    // Темно-красный
            'rgba(190, 45, 35, 0.8)',    // Еще темнее
            'rgba(160, 40, 30, 0.8)'     // Самый темный
        ]
    };
    
    const colors = colorSets[type] || [
        'rgba(0, 122, 255, 0.8)',        // Синий
        'rgba(0, 105, 220, 0.8)',
        'rgba(0, 90, 190, 0.8)',
        'rgba(0, 75, 160, 0.8)'
    ];
    
    return colors[index % colors.length];
}

// Корректировка цвета
function adjustColor(color, adjustment) {
    // Простая корректировка цвета для создания градиента
    const match = color.match(/rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)/);
    if (match) {
        const r = Math.max(0, Math.min(255, parseInt(match[1]) - adjustment));
        const g = Math.max(0, Math.min(255, parseInt(match[2]) - adjustment));
        const b = Math.max(0, Math.min(255, parseInt(match[3]) - adjustment));
        const a = parseFloat(match[4]);
        return `rgba(${r}, ${g}, ${b}, ${a})`;
    }
    return color;
}

// Обновление легенды sunburst
function updateSunburstLegend(structure) {
    const legendContainer = document.getElementById('sunburst-legend');
    if (!legendContainer) return;
    
    let html = '<div class="sunburst-legend-content">';
    html += '<h4>Легенда</h4>';
    html += '<div class="legend-items">';
    
    structure.legend.forEach(item => {
        html += `
            <div class="legend-item">
                <span class="legend-color" style="background-color: ${item.color}"></span>
                <span class="legend-label">${item.label}</span>
                <span class="legend-value">${formatCurrency(item.value)}</span>
                <span class="legend-percentage">${item.percentage.toFixed(1)}%</span>
            </div>
        `;
    });
    
    html += '</div></div>';
    legendContainer.innerHTML = html;
}

// Обновление топ-листов
function updateTopLists(data) {
    updateTopExpenses(data.top_expenses);
    updateTopIncomes(data.top_incomes);
}

// Обновление топ-5 расходов
function updateTopExpenses(expenses) {
    const container = document.getElementById('top-expenses-list');
    if (!container) return;
    
    if (!expenses || expenses.length === 0) {
        container.innerHTML = `
            <div class="no-data">
                <i class="fas fa-check-circle positive"></i>
                <p>Нет данных о расходах</p>
            </div>
        `;
        return;
    }
    
    let html = '<div class="top-list">';
    
    expenses.forEach((expense, index) => {
        html += `
            <div class="top-item" onclick="showArticleDetailsByName('${expense.article}', 'expense')">
                <div class="top-rank">${index + 1}</div>
                <div class="top-info">
                    <div class="top-name">${expense.article}</div>
                    <div class="top-value negative">${formatCurrency(expense.total)}</div>
                </div>
                <div class="top-trend">
                    <i class="fas fa-arrow-down"></i>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

// Обновление топ-5 доходов
function updateTopIncomes(incomes) {
    const container = document.getElementById('top-incomes-list');
    if (!container) return;
    
    if (!incomes || incomes.length === 0) {
        container.innerHTML = `
            <div class="no-data">
                <i class="fas fa-check-circle positive"></i>
                <p>Нет данных о доходах</p>
            </div>
        `;
        return;
    }
    
    let html = '<div class="top-list">';
    
    incomes.forEach((income, index) => {
        html += `
            <div class="top-item" onclick="showArticleDetailsByName('${income.article}', 'income')">
                <div class="top-rank">${index + 1}</div>
                <div class="top-info">
                    <div class="top-name">${income.article}</div>
                    <div class="top-value positive">${formatCurrency(income.total)}</div>
                </div>
                <div class="top-trend">
                    <i class="fas fa-arrow-up"></i>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

// Обновление статистики
function updateStats(data) {
    // Рассчитываем статистику
    const totalArticles = articlesData.length;
    const incomeArticles = articlesData.filter(item => item.type === 'income').length;
    const expenseArticles = articlesData.filter(item => item.type === 'expense').length;
    const totalAmount = articlesData.reduce((sum, item) => sum + item.values, 0);
    
    document.getElementById('total-articles').textContent = totalArticles;
    document.getElementById('income-articles').textContent = incomeArticles;
    document.getElementById('expense-articles').textContent = expenseArticles;
    document.getElementById('total-amount').textContent = formatCurrency(totalAmount);
}

// Обновление таблицы статей
function updateArticlesTable(data) {
    const tbody = document.getElementById('articles-table-body');
    if (!tbody) return;
    
    // Собираем все статьи в плоский список
    const allArticles = [];
    
    data.sunburst.forEach(item => {
        const parts = item.ids.split('/');
        if (parts.length >= 3) {
            allArticles.push({
                level1: parts[0],
                level2: parts[1],
                level4: parts[2],
                type: item.type === 'income' ? 'Доход' : 'Расход',
                amount: item.values,
                percentage: 0 // Рассчитаем ниже
            });
        }
    });
    
    // Рассчитываем общую сумму и проценты
    const totalAmount = allArticles.reduce((sum, article) => sum + article.amount, 0);
    allArticles.forEach(article => {
        article.percentage = totalAmount > 0 ? (article.amount / totalAmount * 100) : 0;
    });
    
    // Сортируем по сумме (по убыванию)
    allArticles.sort((a, b) => b.amount - a.amount);
    
    // Отображаем
    let html = '';
    
    allArticles.forEach((article, index) => {
        if (index < 50) { // Ограничиваем количество строк
            html += `
                <tr>
                    <td>${article.level1}</td>
                    <td>${article.level2}</td>
                    <td>${article.level4}</td>
                    <td>
                        <span class="article-type ${article.type === 'Доход' ? 'income' : 'expense'}">
                            ${article.type}
                        </span>
                    </td>
                    <td class="${article.type === 'Доход' ? 'positive' : 'negative'}">
                        ${formatCurrency(article.amount)}
                    </td>
                    <td>${article.percentage.toFixed(1)}%</td>
                    <td>
                        <button class="btn-icon small" onclick="showArticleDetailsByName('${article.level4}', '${article.type === 'Доход' ? 'income' : 'expense'}')">
                            <i class="fas fa-eye"></i>
                        </button>
                    </td>
                </tr>
            `;
        }
    });
    
    tbody.innerHTML = html;
}

// Показать детали статьи по имени
function showArticleDetailsByName(articleName, type) {
    // Находим статью в данных
    const article = articlesData.find(item => {
        const parts = item.ids.split('/');
        return parts[2] === articleName && item.type === type;
    });
    
    if (article) {
        showArticleDetails({
            label: articleName,
            value: item.values,
            type: type
        });
    }
}

// Показать детали статьи
function showArticleDetails(data) {
    const container = document.getElementById('article-details');
    if (!container) return;
    
    // Парсим данные статьи
    const parts = data.label ? data.label.split('/') : [];
    const level1 = parts[0] || data.label;
    const level2 = parts[1] || '';
    const level4 = parts[2] || data.label;
    
    const html = `
        <div class="article-details-content">
            <div class="article-header">
                <h4>${level4}</h4>
                <span class="article-type ${data.type}">${data.type === 'income' ? 'Доход' : 'Расход'}</span>
            </div>
            
            <div class="article-info-grid">
                <div class="info-item">
                    <span class="info-label">Уровень 1:</span>
                    <span class="info-value">${level1}</span>
                </div>
                ${level2 ? `
                <div class="info-item">
                    <span class="info-label">Уровень 2:</span>
                    <span class="info-value">${level2}</span>
                </div>
                ` : ''}
                <div class="info-item">
                    <span class="info-label">Сумма:</span>
                    <span class="info-value ${data.type}">${formatCurrency(data.value)}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Доля:</span>
                    <span class="info-value">${data.percentage ? data.percentage.toFixed(1) + '%' : '—'}</span>
                </div>
            </div>
            
            <div class="article-chart-container">
                <h5>Динамика по месяцам</h5>
                <canvas id="article-trend-chart" height="120"></canvas>
            </div>
            
            <div class="article-actions">
                <button class="btn-secondary" onclick="exportArticleData('${level4}')">
                    <i class="fas fa-download"></i> Экспорт
                </button>
                <button class="btn-primary" onclick="analyzeArticleTrend('${level4}')">
                    <i class="fas fa-chart-line"></i> Анализ тренда
                </button>
            </div>
        </div>
    `;
    
    container.innerHTML = html;
    container.style.display = 'block';
    
    // Создаем график тренда
    createArticleTrendChart(level4, data.type);
}

// Скрыть детали статьи
function hideArticleDetails() {
    const container = document.getElementById('article-details');
    if (container) {
        container.style.display = 'none';
    }
}

// Создание графика тренда для статьи
function createArticleTrendChart(articleName, type) {
    const canvas = document.getElementById('article-trend-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Фиктивные данные для демонстрации
    // В реальном приложении нужно загружать исторические данные
    const months = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн'];
    const data = months.map(() => Math.floor(Math.random() * 100000) + 50000);
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: months,
            datasets: [{
                label: articleName,
                data: data,
                borderColor: type === 'income' ? 'rgba(52, 199, 89, 1)' : 'rgba(255, 59, 48, 1)',
                backgroundColor: type === 'income' ? 'rgba(52, 199, 89, 0.1)' : 'rgba(255, 59, 48, 0.1)',
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

// Инициализация модального окна статей
function initArticlesModal() {
    const modal = document.getElementById('articles-modal');
    if (!modal) return;
    
    // Закрытие по клику на фон
    modal.addEventListener('click', function(e) {
        if (e.target === this) {
            closeArticlesModal();
        }
    });
    
    // Закрытие по кнопке
    modal.querySelector('.modal-close')?.addEventListener('click', closeArticlesModal);
    
    // Поиск статей
    const searchInput = document.getElementById('search-articles');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(function() {
            filterArticlesInModal(this.value);
        }, 300));
    }
}

// Показать модальное окно выбора статей
function showArticlesModal() {
    openModal('articles-modal');
    loadArticlesForModal();
}

// Закрыть модальное окно статей
function closeArticlesModal() {
    closeModal('articles-modal');
}

// Загрузка статей для модального окна
function loadArticlesForModal() {
    const incomeList = document.getElementById('income-articles-list');
    const expenseList = document.getElementById('expense-articles-list');
    
    if (!incomeList || !expenseList || articlesData.length === 0) return;
    
    // Собираем уникальные статьи
    const incomeArticles = new Set();
    const expenseArticles = new Set();
    
    articlesData.forEach(item => {
        const parts = item.ids.split('/');
        if (parts.length >= 3) {
            const articleName = parts[2];
            if (item.type === 'income') {
                incomeArticles.add(articleName);
            } else {
                expenseArticles.add(articleName);
            }
        }
    });
    
    // Отображаем доходные статьи
    let incomeHtml = '<div class="articles-checkbox-list">';
    Array.from(incomeArticles).sort().forEach(article => {
        incomeHtml += `
            <label class="checkbox-item">
                <input type="checkbox" value="${article}" checked>
                <span>${article}</span>
            </label>
        `;
    });
    incomeHtml += '</div>';
    incomeList.innerHTML = incomeHtml;
    
    // Отображаем расходные статьи
    let expenseHtml = '<div class="articles-checkbox-list">';
    Array.from(expenseArticles).sort().forEach(article => {
        expenseHtml += `
            <label class="checkbox-item">
                <input type="checkbox" value="${article}" checked>
                <span>${article}</span>
            </label>
        `;
    });
    expenseHtml += '</div>';
    expenseList.innerHTML = expenseHtml;
}

// Фильтрация статей в модальном окне
function filterArticlesInModal(searchTerm) {
    const term = searchTerm.toLowerCase().trim();
    
    document.querySelectorAll('.checkbox-item').forEach(item => {
        const text = item.textContent.toLowerCase();
        if (term === '' || text.includes(term)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

// Сохранение выбора статей
function saveArticlesSelection() {
    const selectedArticles = [];
    
    // Собираем выбранные статьи
    document.querySelectorAll('.checkbox-item input:checked').forEach(checkbox => {
        selectedArticles.push(checkbox.value);
    });
    
    // Обновляем отображение выбранных статей
    const container = document.getElementById('selected-articles');
    if (container) {
        if (selectedArticles.length === 0) {
            container.innerHTML = '<span class="tag">Все статьи</span>';
        } else if (selectedArticles.length <= 3) {
            container.innerHTML = selectedArticles.map(article => 
                `<span class="tag">${article}</span>`
            ).join('');
        } else {
            container.innerHTML = `
                <span class="tag">${selectedArticles[0]}</span>
                <span class="tag">${selectedArticles[1]}</span>
                <span class="tag">+${selectedArticles.length - 2} еще</span>
            `;
        }
    }
    
    closeArticlesModal();
    showNotification('Выбор статей сохранен', 'success');
    
    // Обновляем диаграмму с учетом выбранных статей
    if (articlesData.length > 0) {
        updateSunburstChart();
    }
}

// Сброс анализа
function resetAnalysis() {
    // Сброс даты
    const today = new Date();
    const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
    const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
    const dateRange = `${formatDateForInput(firstDay)} по ${formatDateForInput(lastDay)}`;
    document.getElementById('report3-period').value = dateRange;
    
    // Сброс фильтров
    document.getElementById('operation-type').value = 'all';
    document.getElementById('detail-level').value = '1';
    
    // Сброс выбора статей
    document.getElementById('selected-articles').innerHTML = '<span class="tag">Все статьи</span>';
    
    // Перезагрузка данных
    loadReportData();
    
    showNotification('Анализ сброшен', 'info');
}

// Экспорт данных статьи
function exportArticleData(articleName) {
    // Здесь можно добавить логику экспорта
    showNotification(`Экспорт данных для "${articleName}"`, 'info');
}

// Анализ тренда статьи
function analyzeArticleTrend(articleName) {
    // Здесь можно добавить логику анализа тренда
    showNotification(`Анализ тренда для "${articleName}"`, 'info');
}

// Управление зумом диаграммы
document.addEventListener('DOMContentLoaded', function() {
    // Увеличение
    document.getElementById('zoom-in')?.addEventListener('click', function() {
        if (sunburstChart) {
            sunburstChart.options.scales.r.ticks.stepSize *= 0.8;
            sunburstChart.update();
        }
    });
    
    // Уменьшение
    document.getElementById('zoom-out')?.addEventListener('click', function() {
        if (sunburstChart) {
            sunburstChart.options.scales.r.ticks.stepSize *= 1.2;
            sunburstChart.update();
        }
    });
    
    // Сброс зума
    document.getElementById('reset-zoom')?.addEventListener('click', function() {
        if (sunburstChart) {
            sunburstChart.resetZoom();
        }
    });
});

// Экспорт таблицы
document.getElementById('export-table')?.addEventListener('click', function() {
    if (articlesData.length === 0) {
        showNotification('Нет данных для экспорта', 'error');
        return;
    }
    
    // Собираем данные для экспорта
    const exportData = articlesData.map(item => {
        const parts = item.ids.split('/');
        return {
            'Уровень 1': parts[0] || '',
            'Уровень 2': parts[1] || '',
            'Уровень 4': parts[2] || '',
            'Тип': item.type === 'income' ? 'Доход' : 'Расход',
            'Сумма': item.values,
            'ID': item.ids
        };
    });
    
    exportToCSV(exportData, `articles_${new Date().toISOString().split('T')[0]}.csv`);
});

// Добавляем стили для отчета 3
const report3Styles = document.createElement('style');
report3Styles.textContent = `
    .date-range-input {
        padding: var(--spacing-md);
        border: 1px solid var(--apple-border);
        border-radius: var(--radius-md);
        width: 100%;
        font-family: inherit;
    }
    
    .select-input {
        padding: var(--spacing-md);
        border: 1px solid var(--apple-border);
        border-radius: var(--radius-md);
        width: 100%;
        font-family: inherit;
        background: white;
    }
    
    .tags-container {
        display: flex;
        align-items: center;
        gap: var(--spacing-md);
    }
    
    .tags-list {
        flex: 1;
        display: flex;
        flex-wrap: wrap;
        gap: var(--spacing-xs);
    }
    
    .tag {
        background: var(--apple-bg);
        padding: 4px 12px;
        border-radius: var(--radius-full);
        font-size: 0.9rem;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    
    .sunburst-container {
        position: relative;
        min-height: 600px;
    }
    
    .chart-container {
        width: 100%;
        height: 600px;
        position: relative;
    }
    
    .sunburst-legend {
        margin-top: var(--spacing-lg);
        padding: var(--spacing-md);
        background: var(--apple-bg);
        border-radius: var(--radius-md);
        max-height: 300px;
        overflow-y: auto;
    }
    
    .legend-items {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
    }
    
    .legend-item {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-xs) 0;
        border-bottom: 1px solid var(--apple-border);
    }
    
    .legend-item:last-child {
        border-bottom: none;
    }
    
    .legend-color {
        width: 16px;
        height: 16px;
        border-radius: 4px;
    }
    
    .legend-label {
        flex: 1;
        font-size: 0.9rem;
    }
    
    .legend-value {
        font-weight: 600;
        font-size: 0.9rem;
    }
    
    .legend-percentage {
        color: var(--apple-text-secondary);
        font-size: 0.8rem;
        min-width: 40px;
        text-align: right;
    }
    
    .analytics-list {
        max-height: 200px;
        overflow-y: auto;
    }
    
    .top-list {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
    }
    
    .top-item {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-sm);
        border-radius: var(--radius-sm);
        cursor: pointer;
        transition: var(--transition-fast);
    }
    
    .top-item:hover {
        background: var(--apple-bg);
    }
    
    .top-rank {
        width: 24px;
        height: 24px;
        background: var(--apple-border);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    .top-info {
        flex: 1;
    }
    
    .top-name {
        font-size: 0.9rem;
        margin-bottom: 2px;
    }
    
    .top-value {
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    .top-trend {
        color: var(--apple-text-secondary);
    }
    
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: var(--spacing-md);
    }
    
    .stat-item {
        text-align: center;
        padding: var(--spacing-md);
        background: var(--apple-bg);
        border-radius: var(--radius-md);
    }
    
    .stat-label {
        display: block;
        font-size: 0.8rem;
        color: var(--apple-text-secondary);
        margin-bottom: var(--spacing-xs);
    }
    
    .stat-value {
        display: block;
        font-size: 1.5rem;
        font-weight: 700;
    }
    
    .compact-table {
        font-size: 0.9rem;
    }
    
    .compact-table th,
    .compact-table td {
        padding: var(--spacing-sm);
    }
    
    .article-type {
        padding: 2px 8px;
        border-radius: var(--radius-sm);
        font-size: 0.8rem;
        font-weight: 500;
    }
    
    .article-type.income {
        background: rgba(52, 199, 89, 0.1);
        color: var(--apple-green);
    }
    
    .article-type.expense {
        background: rgba(255, 59, 48, 0.1);
        color: var(--apple-red);
    }
    
    /* Модальное окно статей */
    .articles-list-container {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: var(--spacing-lg);
        max-height: 400px;
        overflow-y: auto;
        margin: var(--spacing-md) 0;
    }
    
    .articles-column h4 {
        margin-bottom: var(--spacing-md);
        font-size: 1rem;
    }
    
    .articles-checkbox-list {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
    }
    
    .checkbox-item {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-xs);
        cursor: pointer;
    }
    
    .checkbox-item:hover {
        background: var(--apple-bg);
        border-radius: var(--radius-sm);
    }
    
    @media (max-width: 768px) {
        .filter-row {
            flex-direction: column;
        }
        
        .articles-list-container {
            grid-template-columns: 1fr;
        }
        
        .chart-container {
            height: 400px;
        }
        
        .stats-grid {
            grid-template-columns: 1fr;
        }
        
        .compact-table {
            font-size: 0.8rem;
        }
    }
`;
document.head.appendChild(report3Styles);