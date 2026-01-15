// Report 1: Эффективность выбранных проектов

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация
    initDateRange();
    initProjectSelector();
    initFilters();
    initHierarchyTable();
    
    // Загрузка проектов при загрузке страницы
    loadProjects();
});

// Инициализация диапазона дат
function initDateRange() {
    const today = new Date();
    const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
    const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
    
    flatpickr("#period-from", {
        locale: "ru",
        dateFormat: "Y-m-d",
        defaultDate: firstDay,
        maxDate: today
    });
    
    flatpickr("#period-to", {
        locale: "ru",
        dateFormat: "Y-m-d",
        defaultDate: lastDay,
        maxDate: today
    });
    
    // Устанавливаем значения по умолчанию
    document.getElementById('period-from').value = formatDateForInput(firstDay);
    document.getElementById('period-to').value = formatDateForInput(lastDay);
}

// Форматирование даты для input
function formatDateForInput(date) {
    return date.toISOString().split('T')[0];
}

// Загрузка списка проектов
async function loadProjects() {
    const container = document.getElementById('available-projects');
    showLoading(container);
    
    try {
        const response = await fetch('/api/projects');
        const data = await response.json();
        
        if (data) {
            renderProjects(data, container);
        }
    } catch (error) {
        console.error('Error loading projects:', error);
        showError(container, 'Ошибка загрузки проектов');
    }
}

// Отображение проектов
function renderProjects(groups, container) {
    let html = '';
    
    // Собираем все проекты в один массив с информацией о группе
    const allProjects = [];
    Object.keys(groups).forEach(group => {
        groups[group].forEach(project => {
            allProjects.push({
                name: project,
                group: group
            });
        });
    });
    
    // Сортируем по названию
    allProjects.sort((a, b) => a.name.localeCompare(b.name));
    
    // Группируем по первой букве для удобства
    const groupedByLetter = {};
    allProjects.forEach(project => {
        const firstLetter = project.name.charAt(0).toUpperCase();
        if (!groupedByLetter[firstLetter]) {
            groupedByLetter[firstLetter] = [];
        }
        groupedByLetter[firstLetter].push(project);
    });
    
    // Создаем HTML
    Object.keys(groupedByLetter).sort().forEach(letter => {
        html += `<div class="projects-letter-group">`;
        html += `<div class="letter-header">${letter}</div>`;
        html += `<div class="letter-projects">`;
        
        groupedByLetter[letter].forEach(project => {
            html += `
                <div class="project-item" data-project="${project.name}" data-group="${project.group}">
                    <div class="project-checkbox">
                        <input type="checkbox" id="project-${project.name}" value="${project.name}">
                    </div>
                    <label for="project-${project.name}" class="project-label">
                        <span class="project-name">${project.name}</span>
                        <span class="project-group ${project.group.toLowerCase()}">${project.group}</span>
                    </label>
                </div>
            `;
        });
        
        html += `</div></div>`;
    });
    
    container.innerHTML = html;
    
    // Добавляем обработчики для чекбоксов
    initProjectCheckboxes();
}

// Инициализация чекбоксов проектов
function initProjectCheckboxes() {
    const checkboxes = document.querySelectorAll('.project-item input[type="checkbox"]');
    
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            updateSelectedProjects();
        });
    });
}

// Обновление списка выбранных проектов
function updateSelectedProjects() {
    const selectedContainer = document.getElementById('selected-projects');
    const selectedCheckboxes = document.querySelectorAll('.project-item input[type="checkbox"]:checked');
    
    if (selectedCheckboxes.length === 0) {
        selectedContainer.innerHTML = `
            <div class="empty-selection">
                <i class="fas fa-hand-pointer"></i>
                <p>Выберите проекты из списка слева</p>
            </div>
        `;
        document.getElementById('selected-count').textContent = '0';
        return;
    }
    
    let html = '';
    const selectedProjects = [];
    
    selectedCheckboxes.forEach(checkbox => {
        const projectItem = checkbox.closest('.project-item');
        const projectName = projectItem.dataset.project;
        const projectGroup = projectItem.dataset.group;
        
        selectedProjects.push({
            name: projectName,
            group: projectGroup
        });
        
        html += `
            <div class="selected-project" data-project="${projectName}">
                <span class="selected-project-name">${projectName}</span>
                <span class="selected-project-group ${projectGroup.toLowerCase()}">${projectGroup}</span>
                <button class="remove-project" data-project="${projectName}">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
    });
    
    selectedContainer.innerHTML = html;
    document.getElementById('selected-count').textContent = selectedProjects.length;
    
    // Добавляем обработчики для кнопок удаления
    document.querySelectorAll('.remove-project').forEach(button => {
        button.addEventListener('click', function() {
            const projectName = this.dataset.project;
            const checkbox = document.querySelector(`input[value="${projectName}"]`);
            if (checkbox) {
                checkbox.checked = false;
                updateSelectedProjects();
            }
        });
    });
}

// Инициализация селектора проектов
function initProjectSelector() {
    // Выбрать все
    document.getElementById('select-all').addEventListener('click', function() {
        document.querySelectorAll('.project-item input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = true;
        });
        updateSelectedProjects();
    });
    
    // Убрать все
    document.getElementById('deselect-all').addEventListener('click', function() {
        document.querySelectorAll('.project-item input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = false;
        });
        updateSelectedProjects();
    });
    
    // Очистить выбранные
    document.getElementById('clear-selected').addEventListener('click', function() {
        document.querySelectorAll('.project-item input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = false;
        });
        updateSelectedProjects();
    });
    
    // Поиск проектов
    const searchInput = document.getElementById('search-projects');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(function() {
            filterProjects(this.value);
        }, 300));
    }
}

// Фильтрация проектов по поиску
function filterProjects(searchTerm) {
    const projectItems = document.querySelectorAll('.project-item');
    const term = searchTerm.toLowerCase().trim();
    
    if (!term) {
        projectItems.forEach(item => {
            item.style.display = 'flex';
            item.closest('.projects-letter-group').style.display = 'block';
        });
        return;
    }
    
    projectItems.forEach(item => {
        const projectName = item.dataset.project.toLowerCase();
        const projectGroup = item.dataset.group.toLowerCase();
        
        if (projectName.includes(term) || projectGroup.includes(term)) {
            item.style.display = 'flex';
            item.closest('.projects-letter-group').style.display = 'block';
        } else {
            item.style.display = 'none';
        }
    });
    
    // Скрываем пустые группы
    document.querySelectorAll('.projects-letter-group').forEach(group => {
        const visibleItems = group.querySelectorAll('.project-item[style*="display: flex"]');
        if (visibleItems.length === 0) {
            group.style.display = 'none';
        }
    });
}

// Инициализация фильтров
function initFilters() {
    // Фильтрация по группам
    document.querySelectorAll('.group-btn').forEach(button => {
        button.addEventListener('click', function() {
            document.querySelectorAll('.group-btn').forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            
            const group = this.dataset.group;
            filterProjectsByGroup(group);
        });
    });
    
    // Применить фильтры
    document.getElementById('apply-filters').addEventListener('click', loadReportData);
    
    // Сбросить фильтры
    document.getElementById('reset-filters').addEventListener('click', resetFilters);
    
    // Экспорт данных
    document.getElementById('export-data').addEventListener('click', exportReportData);
}

// Фильтрация проектов по группе
function filterProjectsByGroup(group) {
    const projectItems = document.querySelectorAll('.project-item');
    
    if (group === 'all') {
        projectItems.forEach(item => {
            item.style.display = 'flex';
            item.closest('.projects-letter-group').style.display = 'block';
        });
        return;
    }
    
    projectItems.forEach(item => {
        const projectGroup = item.dataset.group;
        
        if (projectGroup === group) {
            item.style.display = 'flex';
            item.closest('.projects-letter-group').style.display = 'block';
        } else {
            item.style.display = 'none';
        }
    });
}

// Загрузка данных отчета
async function loadReportData() {
    const selectedProjects = getSelectedProjects();
    
    if (selectedProjects.length === 0) {
        showNotification('Выберите хотя бы один проект', 'error');
        return;
    }
    
    const periodFrom = document.getElementById('period-from').value;
    const periodTo = document.getElementById('period-to').value;
    
    if (!periodFrom || !periodTo) {
        showNotification('Выберите период', 'error');
        return;
    }
    
    const data = {
        projects: selectedProjects,
        period_from: periodFrom,
        period_to: periodTo
    };
    
    // Показываем загрузку
    const hierarchyContainer = document.getElementById('hierarchy-table');
    const metricsContainer = document.getElementById('metrics-container');
    
    showLoading(hierarchyContainer);
    showLoading(metricsContainer);
    
    try {
        const response = await fetch('/api/report1/data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (result.success) {
            renderHierarchyTable(result.hierarchy);
            renderMetrics(result.metrics);
            
            // Сохраняем период в сессию для ТОП-10 расходов
            sessionStorage.setItem('report1_period_from', periodFrom);
            sessionStorage.setItem('report1_period_to', periodTo);
            
            showNotification('Данные успешно загружены', 'success');
        } else {
            showError(hierarchyContainer, result.error);
            showError(metricsContainer, result.error);
        }
    } catch (error) {
        console.error('Error loading report data:', error);
        showError(hierarchyContainer, 'Ошибка загрузки данных');
        showError(metricsContainer, 'Ошибка загрузки данных');
    }
}

// Получение выбранных проектов
function getSelectedProjects() {
    const selectedCheckboxes = document.querySelectorAll('.project-item input[type="checkbox"]:checked');
    return Array.from(selectedCheckboxes).map(checkbox => checkbox.value);
}

// Отображение иерархической таблицы
function renderHierarchyTable(hierarchy) {
    const container = document.getElementById('hierarchy-table');
    
    if (!hierarchy || Object.keys(hierarchy).length === 0) {
        container.innerHTML = `
            <div class="no-data">
                <i class="fas fa-database"></i>
                <p>Нет данных для отображения</p>
            </div>
        `;
        return;
    }
    
    let html = '<div class="hierarchy-tree">';
    
    Object.keys(hierarchy).forEach(level1 => {
        const level1Data = hierarchy[level1];
        const level1Total = calculateLevelTotal(level1Data);
        
        html += `
            <div class="hierarchy-level level-1" data-level="1" data-name="${level1}">
                <div class="level-header" onclick="toggleLevel(this)">
                    <div class="level-info">
                        <span class="level-toggle">▶</span>
                        <span class="level-title">${level1}</span>
                    </div>
                    <div class="level-total">${formatCurrency(level1Total)}</div>
                </div>
                <div class="level-children" style="display: none;">
        `;
        
        Object.keys(level1Data).forEach(level2 => {
            const level2Data = level1Data[level2];
            const level2Total = calculateLevelTotal(level2Data);
            
            html += `
                <div class="hierarchy-level level-2" data-level="2" data-name="${level2}">
                    <div class="level-header" onclick="toggleLevel(this)">
                        <div class="level-info">
                            <span class="level-toggle">▶</span>
                            <span class="level-title">${level2}</span>
                        </div>
                        <div class="level-total">${formatCurrency(level2Total)}</div>
                    </div>
                    <div class="level-children" style="display: none;">
            `;
            
            Object.keys(level2Data).forEach(level4 => {
                const level4Data = level2Data[level4];
                const level4Total = calculateLevelTotal(level4Data);
                
                html += `
                    <div class="hierarchy-level level-4" data-level="4" data-name="${level4}">
                        <div class="level-header" onclick="toggleLevel(this)">
                            <div class="level-info">
                                <span class="level-toggle"></span>
                                <span class="level-title">${level4}</span>
                            </div>
                            <div class="level-total">${formatCurrency(level4Total)}</div>
                        </div>
                        <div class="level-children" style="display: none;">
                `;
                
                Object.keys(level4Data).forEach(project => {
                    const amount = level4Data[project];
                    const isNegative = amount < 0;
                    
                    html += `
                        <div class="project-item ${isNegative ? 'negative' : ''}" 
                             data-project="${project}" 
                             data-amount="${amount}"
                             onclick="showProjectDetails('${project}', ${amount})">
                            <div class="project-info">
                                <span class="project-name">${project}</span>
                                <span class="project-group ${getProjectGroup(project)}">${getProjectGroup(project)}</span>
                            </div>
                            <div class="project-amount ${isNegative ? 'negative' : ''}">
                                ${formatCurrency(amount)}
                            </div>
                        </div>
                    `;
                });
                
                html += `</div></div>`;
            });
            
            html += `</div></div>`;
        });
        
        html += `</div></div>`;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

// Расчет общей суммы для уровня
function calculateLevelTotal(levelData) {
    if (typeof levelData === 'object') {
        let total = 0;
        Object.keys(levelData).forEach(key => {
            if (typeof levelData[key] === 'object') {
                total += calculateLevelTotal(levelData[key]);
            } else if (typeof levelData[key] === 'number') {
                total += levelData[key];
            }
        });
        return total;
    }
    return 0;
}

// Переключение видимости уровня
function toggleLevel(element) {
    const parent = element.closest('.hierarchy-level');
    const children = parent.querySelector('.level-children');
    const toggle = parent.querySelector('.level-toggle');
    
    if (children.style.display === 'none') {
        children.style.display = 'block';
        toggle.textContent = '▼';
    } else {
        children.style.display = 'none';
        toggle.textContent = '▶';
    }
}

// Развернуть все уровни
function expandAllLevels() {
    document.querySelectorAll('.level-children').forEach(children => {
        children.style.display = 'block';
    });
    document.querySelectorAll('.level-toggle').forEach(toggle => {
        toggle.textContent = '▼';
    });
}

// Свернуть все уровни
function collapseAllLevels() {
    document.querySelectorAll('.level-children').forEach(children => {
        children.style.display = 'none';
    });
    document.querySelectorAll('.level-toggle').forEach(toggle => {
        toggle.textContent = '▶';
    });
}

// Инициализация иерархической таблицы
function initHierarchyTable() {
    // Развернуть все
    document.getElementById('expand-all')?.addEventListener('click', expandAllLevels);
    
    // Свернуть все
    document.getElementById('collapse-all')?.addEventListener('click', collapseAllLevels);
}

// Отображение метрик
function renderMetrics(metrics) {
    const container = document.getElementById('metrics-container');
    
    if (!metrics || Object.keys(metrics).length === 0) {
        container.innerHTML = `
            <div class="no-metrics">
                <i class="fas fa-calculator"></i>
                <p>Нет данных для расчета метрик</p>
            </div>
        `;
        return;
    }
    
    let html = '<div class="metrics-grid">';
    
    // Рассчитываем общие метрики
    let totalIncome = 0;
    let totalExpense = 0;
    let totalNet = 0;
    
    Object.values(metrics).forEach(metric => {
        totalIncome += metric.income;
        totalExpense += metric.expense;
        totalNet += metric.net;
    });
    
    const margin = totalIncome > 0 ? ((totalIncome - totalExpense) / totalIncome * 100) : 0;
    const roi = totalExpense > 0 ? ((totalIncome - totalExpense) / totalExpense * 100) : 0;
    
    html += `
        <div class="metric-card">
            <div class="metric-header">
                <i class="fas fa-chart-line"></i>
                <h4>Общие показатели</h4>
            </div>
            <div class="metric-body">
                <div class="metric-item">
                    <span class="metric-label">Поступления:</span>
                    <span class="metric-value positive">${formatCurrency(totalIncome)}</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">Отток:</span>
                    <span class="metric-value negative">${formatCurrency(totalExpense)}</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">Чистый результат:</span>
                    <span class="metric-value ${totalNet >= 0 ? 'positive' : 'negative'}">
                        ${formatCurrency(totalNet)}
                    </span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">Маржинальность:</span>
                    <span class="metric-value ${margin >= 0 ? 'positive' : 'negative'}">
                        ${margin.toFixed(1)}%
                    </span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">ROI:</span>
                    <span class="metric-value ${roi >= 0 ? 'positive' : 'negative'}">
                        ${roi.toFixed(1)}%
                    </span>
                </div>
            </div>
        </div>
    `;
    
    // Метрики по проектам
    html += '<div class="metric-card">';
    html += '<div class="metric-header">';
    html += '<i class="fas fa-project-diagram"></i>';
    html += '<h4>По проектам</h4>';
    html += '</div>';
    html += '<div class="metric-body">';
    
    Object.keys(metrics).forEach(project => {
        const metric = metrics[project];
        
        html += `
            <div class="project-metric" onclick="showProjectMetrics('${project}')">
                <div class="project-metric-header">
                    <span class="project-name">${project}</span>
                    <span class="project-net ${metric.net >= 0 ? 'positive' : 'negative'}">
                        ${formatCurrency(metric.net)}
                    </span>
                </div>
                <div class="project-metric-details">
                    <span class="metric-detail">Марж: ${metric.margin.toFixed(1)}%</span>
                    <span class="metric-detail">ROI: ${metric.roi.toFixed(1)}%</span>
                </div>
            </div>
        `;
    });
    
    html += '</div></div>';
    html += '</div>';
    
    container.innerHTML = html;
}

// Показать детали проекта
function showProjectDetails(project, amount) {
    const detailsContainer = document.getElementById('project-details');
    
    const html = `
        <div class="project-details-card">
            <div class="details-header">
                <h4>${project}</h4>
                <span class="project-group ${getProjectGroup(project)}">${getProjectGroup(project)}</span>
            </div>
            
            <div class="details-content">
                <div class="detail-item">
                    <span class="detail-label">Сумма:</span>
                    <span class="detail-value ${amount >= 0 ? 'positive' : 'negative'}">
                        ${formatCurrency(amount)}
                    </span>
                </div>
                
                <div class="detail-item">
                    <span class="detail-label">Статус:</span>
                    <span class="detail-value ${amount >= 0 ? 'status-positive' : 'status-negative'}">
                        ${amount >= 0 ? 'Прибыльный' : 'Убыточный'}
                    </span>
                </div>
            </div>
            
            ${amount < 0 ? `
                <div class="details-actions">
                    <button class="btn-secondary" onclick="showTopExpenses('${project}')">
                        <i class="fas fa-exclamation-triangle"></i>
                        Показать ТОП-10 расходов
                    </button>
                </div>
            ` : ''}
        </div>
    `;
    
    detailsContainer.innerHTML = html;
}

// Показать метрики проекта
function showProjectMetrics(project) {
    // Здесь можно добавить подробные метрики проекта
    showNotification(`Подробные метрики для ${project}`, 'info');
}

// Показать ТОП-10 расходов для проекта
async function showTopExpenses(project) {
    const container = document.getElementById('top-expenses-list');
    const card = document.querySelector('.top-expenses-card');
    
    showLoading(container);
    card.style.display = 'block';
    
    try {
        const response = await fetch(`/api/top_expenses/${encodeURIComponent(project)}`);
        const data = await response.json();
        
        if (data.success && data.expenses.length > 0) {
            let html = '<div class="expenses-list">';
            
            data.expenses.forEach((expense, index) => {
                html += `
                    <div class="expense-item">
                        <div class="expense-rank">${index + 1}</div>
                        <div class="expense-info">
                            <div class="expense-name">${expense.level4}</div>
                            <div class="expense-category">${expense.level2}</div>
                        </div>
                        <div class="expense-amount negative">
                            ${formatCurrency(expense.total)}
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
            container.innerHTML = html;
        } else {
            container.innerHTML = `
                <div class="no-expenses">
                    <i class="fas fa-check-circle positive"></i>
                    <p>Нет данных о расходах для этого проекта</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading top expenses:', error);
        showError(container, 'Ошибка загрузки расходов');
    }
}

// Получение группы проекта
function getProjectGroup(projectName) {
    const name = projectName.toUpperCase();
    if (name.includes('DCA')) return 'DCA';
    if (name.includes('DP')) return 'DP';
    return 'Прочие';
}

// Сброс фильтров
function resetFilters() {
    // Сброс дат
    const today = new Date();
    const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
    const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
    
    document.getElementById('period-from').value = formatDateForInput(firstDay);
    document.getElementById('period-to').value = formatDateForInput(lastDay);
    
    // Сброс групп
    document.querySelectorAll('.group-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector('.group-btn[data-group="all"]').classList.add('active');
    filterProjectsByGroup('all');
    
    // Сброс выбранных проектов
    document.querySelectorAll('.project-item input[type="checkbox"]').forEach(checkbox => {
        checkbox.checked = false;
    });
    updateSelectedProjects();
    
    // Очистка данных
    document.getElementById('hierarchy-table').innerHTML = `
        <div class="loading-data">
            <div class="spinner"></div>
            <p>Выберите проекты и нажмите "Применить фильтры"</p>
        </div>
    `;
    
    document.getElementById('metrics-container').innerHTML = `
        <div class="metrics-placeholder">
            <i class="fas fa-calculator"></i>
            <p>Метрики появятся после выбора проектов</p>
        </div>
    `;
    
    document.getElementById('project-details').innerHTML = `
        <div class="details-placeholder">
            <i class="fas fa-mouse-pointer"></i>
            <p>Кликните на проект для детализации</p>
        </div>
    `;
    
    // Скрываем карточку с расходами
    document.querySelector('.top-expenses-card').style.display = 'none';
    
    showNotification('Фильтры сброшены', 'info');
}

// Экспорт данных отчета
function exportReportData() {
    // Здесь можно добавить логику экспорта
    showNotification('Экспорт данных будет доступен в следующей версии', 'info');
}

// Закрытие карточки с расходами
document.getElementById('close-expenses')?.addEventListener('click', function() {
    document.querySelector('.top-expenses-card').style.display = 'none';
});

// Инициализация модального окна комментариев
document.querySelector('.modal-close')?.addEventListener('click', function() {
    closeModal('comments-modal');
});

// Добавляем стили для отчета 1
const report1Styles = document.createElement('style');
report1Styles.textContent = `
    .projects-selector {
        display: flex;
        gap: var(--spacing-lg);
        margin-top: var(--spacing-md);
    }
    
    .projects-column {
        flex: 1;
        min-height: 300px;
        border: 1px solid var(--apple-border);
        border-radius: var(--radius-md);
        display: flex;
        flex-direction: column;
    }
    
    .projects-column h4 {
        padding: var(--spacing-md);
        margin: 0;
        background: var(--apple-bg);
        border-bottom: 1px solid var(--apple-border);
        font-size: 1rem;
    }
    
    .projects-list {
        flex: 1;
        overflow-y: auto;
        padding: var(--spacing-md);
    }
    
    .loading-projects {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100%;
        color: var(--apple-text-secondary);
    }
    
    .project-item {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-sm);
        border-radius: var(--radius-sm);
        cursor: pointer;
        transition: var(--transition-fast);
    }
    
    .project-item:hover {
        background-color: var(--apple-bg);
    }
    
    .project-label {
        flex: 1;
        display: flex;
        justify-content: space-between;
        align-items: center;
        cursor: pointer;
    }
    
    .project-group {
        font-size: 0.8rem;
        padding: 2px 8px;
        border-radius: var(--radius-sm);
        background: var(--apple-bg);
    }
    
    .project-group.dca {
        background-color: rgba(0, 122, 255, 0.1);
        color: var(--apple-blue);
    }
    
    .project-group.dp {
        background-color: rgba(52, 199, 89, 0.1);
        color: var(--apple-green);
    }
    
    .project-group.прочие {
        background-color: rgba(255, 149, 0, 0.1);
        color: var(--apple-orange);
    }
    
    .projects-actions {
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: var(--spacing-sm);
    }
    
    .action-btn {
        background: none;
        border: 1px solid var(--apple-border);
        border-radius: var(--radius-sm);
        padding: var(--spacing-sm);
        cursor: pointer;
        color: var(--apple-text);
        transition: var(--transition-fast);
    }
    
    .action-btn:hover {
        background-color: var(--apple-bg);
    }
    
    .selected .project-item {
        display: none;
    }
    
    .selected-project {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: var(--spacing-sm);
        margin-bottom: var(--spacing-xs);
        background: var(--apple-bg);
        border-radius: var(--radius-sm);
    }
    
    .remove-project {
        background: none;
        border: none;
        color: var(--apple-text-secondary);
        cursor: pointer;
        padding: 2px;
    }
    
    .hierarchy-tree {
        padding: var(--spacing-md);
    }
    
    .hierarchy-level {
        margin-bottom: var(--spacing-xs);
    }
    
    .level-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: var(--spacing-sm) var(--spacing-md);
        background: var(--apple-bg);
        border-radius: var(--radius-sm);
        cursor: pointer;
        transition: var(--transition-fast);
    }
    
    .level-header:hover {
        background: rgba(0, 122, 255, 0.1);
    }
    
    .level-info {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
    }
    
    .level-toggle {
        width: 16px;
        text-align: center;
        font-size: 0.8rem;
        color: var(--apple-text-secondary);
    }
    
    .level-children {
        margin-left: var(--spacing-lg);
        padding: var(--spacing-sm) 0;
    }
    
    .project-item.negative {
        background-color: rgba(255, 59, 48, 0.05);
    }
    
    .project-item.negative:hover {
        background-color: rgba(255, 59, 48, 0.1);
    }
    
    .project-amount.negative {
        color: var(--apple-red);
        font-weight: 600;
    }
    
    .metrics-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: var(--spacing-md);
    }
    
    @media (max-width: 768px) {
        .metrics-grid {
            grid-template-columns: 1fr;
        }
        
        .projects-selector {
            flex-direction: column;
        }
    }
`;
document.head.appendChild(report1Styles);