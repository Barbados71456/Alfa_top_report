const { useState, useEffect, useCallback } = React;

// API базовый URL
const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : '';

// Компонент заголовка
function Header({ user, onLogout }) {
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
    
    return (
        <header className="apple-header">
            <div className="header-content">
                <div className="header-title">
                    <i className="fas fa-chart-line"></i>
                    <span>Аналитика эффективности проектов</span>
                </div>
                
                <div className="header-actions">
                    {user ? (
                        <>
                            <div className="flex items-center gap-2">
                                <i className="fas fa-user text-apple-blue"></i>
                                <span className="mobile-hidden">{user.username}</span>
                                <span className="badge badge-dca">{user.role}</span>
                            </div>
                            <button 
                                className="apple-button button-secondary"
                                onClick={onLogout}
                            >
                                <i className="fas fa-sign-out-alt"></i>
                                <span className="mobile-hidden">Выйти</span>
                            </button>
                        </>
                    ) : (
                        <div className="text-apple-text-secondary">
                            <i className="fas fa-user-clock"></i>
                            <span className="mobile-hidden">Гость</span>
                        </div>
                    )}
                    
                    <button 
                        className="mobile-block apple-button button-secondary"
                        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                    >
                        <i className="fas fa-bars"></i>
                    </button>
                </div>
            </div>
        </header>
    );
}

// Компонент навигации
function Navigation({ activeReport, onReportChange }) {
    const reports = [
        { id: 'report1', label: 'Эффективность проектов', icon: 'fas fa-project-diagram' },
        { id: 'report2', label: 'Сводные показатели', icon: 'fas fa-table' },
        { id: 'report3', label: 'Анализ статей', icon: 'fas fa-chart-pie' },
        { id: 'report4', label: 'ФОТ и сотрудники', icon: 'fas fa-users' }
    ];
    
    return (
        <nav className="apple-nav">
            {reports.map(report => (
                <button
                    key={report.id}
                    className={`nav-button ${activeReport === report.id ? 'active' : ''}`}
                    onClick={() => onReportChange(report.id)}
                >
                    <i className={report.icon}></i>
                    <span>{report.label}</span>
                </button>
            ))}
        </nav>
    );
}

// Компонент фильтров периода
function DateFilter({ startDate, endDate, onStartDateChange, onEndDateChange }) {
    return (
        <div className="filters-container">
            <div className="filter-row">
                <div className="filter-group">
                    <label className="apple-label">Начальная дата</label>
                    <input
                        type="date"
                        className="apple-input"
                        value={startDate}
                        onChange={(e) => onStartDateChange(e.target.value)}
                    />
                </div>
                
                <div className="filter-group">
                    <label className="apple-label">Конечная дата</label>
                    <input
                        type="date"
                        className="apple-input"
                        value={endDate}
                        onChange={(e) => onEndDateChange(e.target.value)}
                    />
                </div>
            </div>
        </div>
    );
}

// Компонент выбора проектов
function ProjectSelector({ groupedProjects, selectedProjects, onProjectToggle, onSelectGroup }) {
    return (
        <div className="apple-card">
            <div className="card-header">
                <h3 className="card-title">
                    <i className="fas fa-folder-open"></i>
                    Выбор проектов
                </h3>
                <div className="flex gap-2">
                    <button 
                        className="apple-button button-secondary"
                        onClick={() => onSelectGroup('all')}
                    >
                        Все
                    </button>
                    <button 
                        className="apple-button button-secondary"
                        onClick={() => onSelectGroup('none')}
                    >
                        Ничего
                    </button>
                </div>
            </div>
            
            {Object.entries(groupedProjects).map(([group, projects]) => (
                <div key={group} className="mb-4">
                    <div className="flex items-center justify-between mb-2">
                        <h4 className="font-semibold text-apple-text">
                            <i className={`fas fa-users mr-2 ${
                                group === 'DCA' ? 'text-apple-blue' :
                                group === 'DP' ? 'text-apple-green' :
                                'text-apple-text-secondary'
                            }`}></i>
                            Группа {group} ({projects.length})
                        </h4>
                        <button 
                            className="text-sm apple-button button-secondary"
                            onClick={() => onSelectGroup(group)}
                        >
                            Выбрать все
                        </button>
                    </div>
                    
                    <div className="projects-selector">
                        {projects.map(project => (
                            <label 
                                key={project} 
                                className="project-checkbox"
                            >
                                <input
                                    type="checkbox"
                                    checked={selectedProjects.includes(project)}
                                    onChange={() => onProjectToggle(project)}
                                />
                                <span className="project-label">{project}</span>
                                <span className={`tree-badge badge-${group.toLowerCase()}`}>
                                    {group}
                                </span>
                            </label>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}

// Компонент метрик
function MetricsPanel({ metrics }) {
    return (
        <div className="apple-card">
            <div className="card-header">
                <h3 className="card-title">
                    <i className="fas fa-chart-bar"></i>
                    Ключевые метрики
                </h3>
            </div>
            
            <div className="metrics-grid">
                <div className="metric-card">
                    <div className="metric-title">
                        <i className="fas fa-percentage"></i>
                        Средний ROI
                    </div>
                    <div className={`metric-value ${
                        metrics?.avg_roi > 0 ? 'text-success' : 'text-danger'
                    }`}>
                        {metrics?.avg_roi ? metrics.avg_roi.toFixed(2) : '0.00'}%
                    </div>
                    <div className="metric-change">
                        {metrics?.avg_roi > 0 ? '↗ Положительный' : '↘ Отрицательный'}
                    </div>
                </div>
                
                <div className="metric-card">
                    <div className="metric-title">
                        <i className="fas fa-chart-line"></i>
                        Средняя маржинальность
                    </div>
                    <div className={`metric-value ${
                        metrics?.avg_margin > 20 ? 'text-success' : 
                        metrics?.avg_margin > 0 ? 'text-warning' : 'text-danger'
                    }`}>
                        {metrics?.avg_margin ? metrics.avg_margin.toFixed(2) : '0.00'}%
                    </div>
                    <div className="metric-change">
                        {metrics?.avg_margin > 20 ? 'Высокая' : 
                         metrics?.avg_margin > 0 ? 'Средняя' : 'Низкая'}
                    </div>
                </div>
                
                <div className="metric-card">
                    <div className="metric-title">
                        <i className="fas fa-money-bill-wave"></i>
                        Общие поступления
                    </div>
                    <div className="metric-value text-info">
                        {metrics?.total_revenue ? formatCurrency(metrics.total_revenue) : '0 ₽'}
                    </div>
                    <div className="metric-change">
                        {metrics?.project_count || 0} проектов
                    </div>
                </div>
                
                <div className="metric-card">
                    <div className="metric-title">
                        <i className="fas fa-hand-holding-usd"></i>
                        Чистый результат
                    </div>
                    <div className={`metric-value ${
                        metrics?.total_net > 0 ? 'text-success' : 'text-danger'
                    }`}>
                        {metrics?.total_net ? formatCurrency(metrics.total_net) : '0 ₽'}
                    </div>
                    <div className="metric-change">
                        {metrics?.total_net > 0 ? 'Прибыль' : 'Убыток'}
                    </div>
                </div>
            </div>
        </div>
    );
}

// Компонент дерева проектов
function ProjectTree({ treeData, metrics, onProjectClick }) {
    const [expanded, setExpanded] = useState({});
    
    const toggleExpand = (path) => {
        setExpanded(prev => ({
            ...prev,
            [path]: !prev[path]
        }));
    };
    
    const renderTree = (data, level = 0, path = '') => {
        if (!data) return null;
        
        return Object.entries(data).map(([key, value]) => {
            const currentPath = path ? `${path}.${key}` : key;
            const isExpanded = expanded[currentPath];
            
            if (typeof value === 'object' && !Array.isArray(value)) {
                // Это узел (проект или уровень1 или уровень2)
                const isProject = level === 0;
                const isLevel1 = level === 1;
                const isLevel2 = level === 2;
                
                let сумма = 0;
                if (isProject) {
                    const metric = metrics?.find(m => m.проект === key);
                    сумма = metric?.результат_од || 0;
                }
                
                return (
                    <div key={currentPath} className={`tree-row ${
                        isProject && сумма < 0 ? 'negative' : ''
                    } ${isProject ? `group-${metric?.группа?.toLowerCase() || 'other'}` : ''}`}>
                        <div 
                            className="tree-toggle"
                            onClick={() => toggleExpand(currentPath)}
                        >
                            <i className={`fas fa-chevron-${isExpanded ? 'down' : 'right'}`}></i>
                        </div>
                        
                        <div className="tree-label">
                            {isProject && (
                                <i className="fas fa-project-diagram mr-2 text-apple-blue"></i>
                            )}
                            {isLevel1 && (
                                <i className="fas fa-folder mr-2 text-apple-orange"></i>
                            )}
                            {isLevel2 && (
                                <i className="fas fa-folder-open mr-2 text-apple-purple"></i>
                            )}
                            {key}
                            
                            {isProject && metric?.группа && (
                                <span className={`tree-badge badge-${metric.группа.toLowerCase()} ml-2`}>
                                    {metric.группа}
                                </span>
                            )}
                        </div>
                        
                        {isProject && (
                            <div className={`tree-value ${
                                сумма >= 0 ? 'text-success' : 'text-danger'
                            }`}>
                                {formatCurrency(сумма)}
                            </div>
                        )}
                        
                        {isProject && сумма < 0 && (
                            <button 
                                className="apple-button button-danger ml-2"
                                onClick={() => onProjectClick(key)}
                                title="Показать ТОП-10 расходов"
                            >
                                <i className="fas fa-search"></i>
                            </button>
                        )}
                        
                        {isExpanded && (
                            <div className="tree-children">
                                {renderTree(value, level + 1, currentPath)}
                            </div>
                        )}
                    </div>
                );
            } else if (Array.isArray(value)) {
                // Это листья (статьи уровня 4)
                return (
                    <div key={currentPath} className="tree-children">
                        {value.map((item, index) => (
                            <div key={index} className="tree-row">
                                <div className="tree-label pl-8">
                                    <i className="fas fa-file-invoice-dollar mr-2 text-apple-green"></i>
                                    {item.article}
                                    {item.comments_count > 0 && (
                                        <span className="text-xs text-apple-text-secondary ml-2">
                                            ({item.comments_count} коммент.)
                                        </span>
                                    )}
                                </div>
                                <div className={`tree-value ${
                                    item.amount >= 0 ? 'text-success' : 'text-danger'
                                }`}>
                                    {formatCurrency(item.amount)}
                                </div>
                            </div>
                        ))}
                    </div>
                );
            }
            
            return null;
        });
    };
    
    return (
        <div className="apple-card">
            <div className="card-header">
                <h3 className="card-title">
                    <i className="fas fa-sitemap"></i>
                    Детализация проектов
                </h3>
                <div className="text-sm text-apple-text-secondary">
                    {Object.keys(treeData).length} проектов
                </div>
            </div>
            
            <div className="tree-container">
                {treeData && Object.keys(treeData).length > 0 ? (
                    renderTree(treeData)
                ) : (
                    <div className="p-8 text-center text-apple-text-secondary">
                        <i className="fas fa-inbox text-4xl mb-4"></i>
                        <p>Выберите проекты для отображения данных</p>
                    </div>
                )}
            </div>
        </div>
    );
}

// Модальное окно с ТОП-10 расходов
function TopExpensesModal({ project, startDate, endDate, onClose }) {
    const [expenses, setExpenses] = useState([]);
    const [loading, setLoading] = useState(true);
    
    useEffect(() => {
        if (project) {
            fetchTopExpenses();
        }
    }, [project]);
    
    const fetchTopExpenses = async () => {
        try {
            setLoading(true);
            const response = await fetch(
                `${API_BASE}/api/report1/top-expenses?` +
                `project=${encodeURIComponent(project)}&` +
                `start_date=${startDate}&` +
                `end_date=${endDate}`
            );
            const data = await response.json();
            setExpenses(data);
        } catch (error) {
            console.error('Error fetching top expenses:', error);
        } finally {
            setLoading(false);
        }
    };
    
    return (
        <div className="modal-overlay">
            <div className="modal-content">
                <div className="modal-header">
                    <h3 className="modal-title">
                        <i className="fas fa-exclamation-triangle text-apple-red mr-2"></i>
                        ТОП-10 расходов: {project}
                    </h3>
                    <button className="modal-close" onClick={onClose}>
                        <i className="fas fa-times"></i>
                    </button>
                </div>
                
                {loading ? (
                    <div className="loading">
                        <div className="loading-spinner"></div>
                        <p>Загрузка данных...</p>
                    </div>
                ) : (
                    <div>
                        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                            <div className="flex items-center gap-2 text-red-700">
                                <i className="fas fa-info-circle"></i>
                                <p className="text-sm">
                                    Этот проект имеет отрицательный результат. Вот его основные статьи расходов:
                                </p>
                            </div>
                        </div>
                        
                        <table className="apple-table">
                            <thead>
                                <tr>
                                    <th>Статья</th>
                                    <th>Категория</th>
                                    <th>Сумма</th>
                                    <th>Комментарии</th>
                                </tr>
                            </thead>
                            <tbody>
                                {expenses.map((expense, index) => (
                                    <tr key={index}>
                                        <td>
                                            <div className="flex items-center gap-2">
                                                <span className="font-semibold">#{index + 1}</span>
                                                {expense.статья}
                                            </div>
                                        </td>
                                        <td>{expense.категория}</td>
                                        <td className="text-danger font-semibold">
                                            {formatCurrency(expense.сумма)}
                                        </td>
                                        <td className="text-sm text-apple-text-secondary">
                                            {expense.комментарии || 'Нет комментариев'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        
                        <div className="mt-6 p-4 bg-gray-50 border border-apple-border rounded-lg">
                            <h4 className="font-semibold mb-2">Рекомендации:</h4>
                            <ul className="text-sm space-y-1 text-apple-text-secondary">
                                <li>• Рассмотрите возможность сокращения расходов по топовым статьям</li>
                                <li>• Проверьте комментарии для понимания природы расходов</li>
                                <li>• Проанализируйте эффективность данного проекта</li>
                                <li>• Рассмотрите перераспределение ресурсов</li>
                            </ul>
                        </div>
                    </div>
                )}
                
                <div className="flex justify-end gap-2 mt-6">
                    <button 
                        className="apple-button button-secondary"
                        onClick={onClose}
                    >
                        Закрыть
                    </button>
                    <button 
                        className="apple-button button-primary"
                        onClick={() => window.print()}
                    >
                        <i className="fas fa-print"></i>
                        Печать отчета
                    </button>
                </div>
            </div>
        </div>
    );
}

// Отчет 1: Эффективность проектов
function Report1({ startDate, endDate, user }) {
    const [groupedProjects, setGroupedProjects] = useState({ DCA: [], DP: [], Прочие: [] });
    const [selectedProjects, setSelectedProjects] = useState([]);
    const [treeData, setTreeData] = useState({});
    const [metrics, setMetrics] = useState([]);
    const [loading, setLoading] = useState(false);
    const [selectedProjectForExpenses, setSelectedProjectForExpenses] = useState(null);
    
    // Загружаем список проектов при монтировании
    useEffect(() => {
        fetchProjects();
    }, []);
    
    // Загружаем данные при изменении выбранных проектов
    useEffect(() => {
        if (selectedProjects.length > 0) {
            fetchReportData();
        } else {
            setTreeData({});
            setMetrics([]);
        }
    }, [selectedProjects, startDate, endDate]);
    
    const fetchProjects = async () => {
        try {
            const response = await fetch(`${API_BASE}/api/report1/projects`, {
                method: 'POST'
            });
            const data = await response.json();
            setGroupedProjects(data);
        } catch (error) {
            console.error('Error fetching projects:', error);
        }
    };
    
    const fetchReportData = async () => {
        setLoading(true);
        try {
            // Параллельно загружаем дерево и метрики
            const [treeResponse, metricsResponse] = await Promise.all([
                fetch(`${API_BASE}/api/report1/tree`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        project_names: selectedProjects,
                        start_date: startDate,
                        end_date: endDate
                    })
                }),
                fetch(`${API_BASE}/api/report1/metrics`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        project_names: selectedProjects,
                        start_date: startDate,
                        end_date: endDate
                    })
                })
            ]);
            
            const treeData = await treeResponse.json();
            const metricsData = await metricsResponse.json();
            
            setTreeData(treeData);
            setMetrics(metricsData);
        } catch (error) {
            console.error('Error fetching report data:', error);
        } finally {
            setLoading(false);
        }
    };
    
    const handleProjectToggle = (project) => {
        setSelectedProjects(prev => 
            prev.includes(project) 
                ? prev.filter(p => p !== project)
                : [...prev, project]
        );
    };
    
    const handleSelectGroup = (group) => {
        if (group === 'all') {
            // Выбираем все проекты из всех групп
            const allProjects = Object.values(groupedProjects).flat();
            setSelectedProjects(allProjects);
        } else if (group === 'none') {
            // Снимаем все выделения
            setSelectedProjects([]);
        } else {
            // Выбираем все проекты из конкретной группы
            const groupProjects = groupedProjects[group] || [];
            setSelectedProjects(prev => {
                // Добавляем только те, которых еще нет в выбранных
                const newProjects = groupProjects.filter(p => !prev.includes(p));
                return [...prev, ...newProjects];
            });
        }
    };
    
    // Рассчитываем общие метрики
    const overallMetrics = metrics.length > 0 ? {
        avg_roi: metrics.reduce((sum, m) => sum + m.roi, 0) / metrics.length,
        avg_margin: metrics.reduce((sum, m) => sum + m.маржинальность, 0) / metrics.length,
        total_revenue: metrics.reduce((sum, m) => sum + m.поступления, 0),
        total_net: metrics.reduce((sum, m) => sum + m.результат_од, 0),
        project_count: metrics.length
    } : null;
    
    return (
        <div>
            <DateFilter
                startDate={startDate}
                endDate={endDate}
                onStartDateChange={(date) => {/* обновить в родителе */}}
                onEndDateChange={(date) => {/* обновить в родителе */}}
            />
            
            <div className="report1-container">
                <ProjectSelector
                    groupedProjects={groupedProjects}
                    selectedProjects={selectedProjects}
                    onProjectToggle={handleProjectToggle}
                    onSelectGroup={handleSelectGroup}
                />
                
                <div>
                    <MetricsPanel metrics={overallMetrics} />
                    
                    {loading ? (
                        <div className="loading">
                            <div className="loading-spinner"></div>
                            <p>Загрузка данных проектов...</p>
                        </div>
                    ) : (
                        <ProjectTree
                            treeData={treeData}
                            metrics={metrics}
                            onProjectClick={setSelectedProjectForExpenses}
                        />
                    )}
                </div>
            </div>
            
            {selectedProjectForExpenses && (
                <TopExpensesModal
                    project={selectedProjectForExpenses}
                    startDate={startDate}
                    endDate={endDate}
                    onClose={() => setSelectedProjectForExpenses(null)}
                />
            )}
        </div>
    );
}

// Отчет 2: Сводные показатели
function Report2({ startDate, endDate, user }) {
    const [summaryData, setSummaryData] = useState(null);
    const [monthlyTrend, setMonthlyTrend] = useState([]);
    const [loading, setLoading] = useState(false);
    const [chartInstance, setChartInstance] = useState(null);
    
    useEffect(() => {
        fetchSummaryData();
    }, [startDate, endDate]);
    
    const fetchSummaryData = async () => {
        setLoading(true);
        try {
            const [summaryResponse, trendResponse] = await Promise.all([
                fetch(`${API_BASE}/api/report2/summary?start_date=${startDate}&end_date=${endDate}`),
                fetch(`${API_BASE}/api/report2/monthly-trend?start_date=${startDate}&end_date=${endDate}`)
            ]);
            
            const summary = await summaryResponse.json();
            const trend = await trendResponse.json();
            
            setSummaryData(summary);
            setMonthlyTrend(trend);
            
            // Обновляем графики
            updateCharts(summary, trend);
        } catch (error) {
            console.error('Error fetching summary data:', error);
        } finally {
            setLoading(false);
        }
    };
    
    const updateCharts = (summary, trend) => {
        // ROI распределение
        const roiCtx = document.getElementById('roiChart');
        if (roiCtx && summary?.projects) {
            if (chartInstance) {
                chartInstance.destroy();
            }
            
            const roiData = summary.projects
                .filter(p => !isNaN(p.roi))
                .map(p => p.roi)
                .sort((a, b) => a - b);
            
            const chart = new Chart(roiCtx.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: roiData.map((_, i) => `Проект ${i + 1}`),
                    datasets: [{
                        label: 'ROI по проектам (%)',
                        data: roiData,
                        backgroundColor: roiData.map(roi => 
                            roi >= 50 ? 'rgba(52, 199, 89, 0.7)' :
                            roi >= 20 ? 'rgba(255, 149, 0, 0.7)' :
                            roi >= 0 ? 'rgba(255, 204, 0, 0.7)' :
                            'rgba(255, 59, 48, 0.7)'
                        ),
                        borderColor: roiData.map(roi => 
                            roi >= 50 ? '#34c759' :
                            roi >= 20 ? '#ff9500' :
                            roi >= 0 ? '#ffcc00' :
                            '#ff3b30'
                        ),
                        borderWidth: 1
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
                                label: (context) => `ROI: ${context.raw.toFixed(2)}%`
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'ROI (%)'
                            }
                        }
                    }
                }
            });
            
            setChartInstance(chart);
        }
        
        // Круговая диаграмма групп
        const groupsCtx = document.getElementById('groupsChart');
        if (groupsCtx && summary?.groups_distribution) {
            const groups = summary.groups_distribution;
            const groupsChart = new Chart(groupsCtx.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: Object.keys(groups),
                    datasets: [{
                        data: Object.values(groups).map(g => g.count),
                        backgroundColor: [
                            'rgba(0, 122, 255, 0.8)',
                            'rgba(52, 199, 89, 0.8)',
                            'rgba(142, 142, 147, 0.8)'
                        ],
                        borderColor: [
                            '#007aff',
                            '#34c759',
                            '#8e8e93'
                        ],
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        },
                        tooltip: {
                            callbacks: {
                                label: (context) => {
                                    const group = context.label;
                                    const data = groups[group];
                                    return [
                                        `Проектов: ${data.count}`,
                                        `Выручка: ${formatCurrency(data.revenue)}`,
                                        `Прибыль: ${formatCurrency(data.profit)}`
                                    ];
                                }
                            }
                        }
                    }
                }
            });
        }
        
        // Линейный график тренда
        const trendCtx = document.getElementById('trendChart');
        if (trendCtx && trend.length > 0) {
            const trendChart = new Chart(trendCtx.getContext('2d'), {
                type: 'line',
                data: {
                    labels: trend.map(t => t.месяц),
                    datasets: [
                        {
                            label: 'Поступления',
                            data: trend.map(t => t.поступления),
                            borderColor: '#007aff',
                            backgroundColor: 'rgba(0, 122, 255, 0.1)',
                            tension: 0.4,
                            fill: true
                        },
                        {
                            label: 'Отток',
                            data: trend.map(t => t.отток),
                            borderColor: '#ff3b30',
                            backgroundColor: 'rgba(255, 59, 48, 0.1)',
                            tension: 0.4,
                            fill: true
                        },
                        {
                            label: 'Маржинальность',
                            data: trend.map(t => t.маржинальность),
                            borderColor: '#34c759',
                            backgroundColor: 'rgba(52, 199, 89, 0.1)',
                            tension: 0.4,
                            fill: true,
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    scales: {
                        x: {
                            grid: {
                                display: false
                            }
                        },
                        y: {
                            type: 'linear',
                            display: true,
                            position: 'left',
                            title: {
                                display: true,
                                text: 'Сумма (₽)'
                            }
                        },
                        y1: {
                            type: 'linear',
                            display: true,
                            position: 'right',
                            title: {
                                display: true,
                                text: 'Маржинальность (%)'
                            },
                            grid: {
                                drawOnChartArea: false
                            }
                        }
                    }
                }
            });
        }
    };
    
    if (loading) {
        return (
            <div className="loading">
                <div className="loading-spinner"></div>
                <p>Загрузка сводных данных...</p>
            </div>
        );
    }
    
    return (
        <div>
            <DateFilter
                startDate={startDate}
                endDate={endDate}
                onStartDateChange={(date) => {/* обновить в родителе */}}
                onEndDateChange={(date) => {/* обновить в родителе */}}
            />
            
            {summaryData && (
                <>
                    <div className="apple-card">
                        <div className="card-header">
                            <h3 className="card-title">
                                <i className="fas fa-chart-bar"></i>
                                Общая статистика
                            </h3>
                        </div>
                        
                        <div className="metrics-grid">
                            <div className="metric-card">
                                <div className="metric-title">Всего проектов</div>
                                <div className="metric-value">{summaryData.total_metrics.total_projects}</div>
                                <div className="metric-change">
                                    {summaryData.projects.filter(p => p.чистый_результат > 0).length} прибыльных
                                </div>
                            </div>
                            
                            <div className="metric-card">
                                <div className="metric-title">Общая выручка</div>
                                <div className="metric-value text-info">
                                    {formatCurrency(summaryData.total_metrics.total_revenue)}
                                </div>
                                <div className="metric-change">
                                    {formatCurrency(summaryData.total_metrics.total_revenue / summaryData.total_metrics.total_projects || 0)} в среднем
                                </div>
                            </div>
                            
                            <div className="metric-card">
                                <div className="metric-title">Чистая прибыль</div>
                                <div className={`metric-value ${
                                    summaryData.total_metrics.total_net > 0 ? 'text-success' : 'text-danger'
                                }`}>
                                    {formatCurrency(summaryData.total_metrics.total_net)}
                                </div>
                                <div className="metric-change">
                                    {summaryData.total_metrics.avg_roi.toFixed(2)}% средний ROI
                                </div>
                            </div>
                            
                            <div className="metric-card">
                                <div className="metric-title">Средняя маржинальность</div>
                                <div className={`metric-value ${
                                    summaryData.total_metrics.avg_margin > 20 ? 'text-success' : 'text-warning'
                                }`}>
                                    {summaryData.total_metrics.avg_margin.toFixed(2)}%
                                </div>
                                <div className="metric-change">
                                    {summaryData.total_metrics.avg_margin > 20 ? 'Высокая' : 'Нормальная'}
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div className="chart-grid">
                        <div className="apple-card">
                            <div className="card-header">
                                <h3 className="card-title">
                                    <i className="fas fa-chart-line"></i>
                                    Распределение ROI по проектам
                                </h3>
                            </div>
                            <div className="chart-container">
                                <canvas id="roiChart"></canvas>
                            </div>
                        </div>
                        
                        <div className="apple-card">
                            <div className="card-header">
                                <h3 className="card-title">
                                    <i className="fas fa-chart-pie"></i>
                                    Распределение по группам
                                </h3>
                            </div>
                            <div className="chart-container">
                                <canvas id="groupsChart"></canvas>
                            </div>
                        </div>
                    </div>
                    
                    <div className="apple-card">
                        <div className="card-header">
                            <h3 className="card-title">
                                <i className="fas fa-trend-up"></i>
                                Динамика по месяцам
                            </h3>
                        </div>
                        <div className="chart-container">
                            <canvas id="trendChart"></canvas>
                        </div>
                    </div>
                    
                    <div className="apple-card">
                        <div className="card-header">
                            <h3 className="card-title">
                                <i className="fas fa-table"></i>
                                Сводная таблица проектов
                            </h3>
                        </div>
                        
                        <div className="overflow-x-auto">
                            <table className="apple-table">
                                <thead>
                                    <tr>
                                        <th>Проект</th>
                                        <th>Группа</th>
                                        <th>ROI</th>
                                        <th>Маржинальность</th>
                                        <th>Поступления</th>
                                        <th>Отток</th>
                                        <th>Чистый результат</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {summaryData.projects.map((project, index) => (
                                        <tr key={index} className={
                                            project.чистый_результат < 0 ? 'negative-row' : ''
                                        }>
                                            <td>
                                                <div className="flex items-center gap-2">
                                                    <i className="fas fa-project-diagram text-apple-blue"></i>
                                                    {project.проект}
                                                </div>
                                            </td>
                                            <td>
                                                <span className={`tree-badge badge-${project.группа.toLowerCase()}`}>
                                                    {project.группа}
                                                </span>
                                            </td>
                                            <td className={
                                                project.roi >= 50 ? 'text-success font-semibold' :
                                                project.roi >= 20 ? 'text-warning' :
                                                project.roi >= 0 ? 'text-muted' : 'text-danger'
                                            }>
                                                {project.roi.toFixed(2)}%
                                            </td>
                                            <td className={
                                                project.маржинальность >= 30 ? 'text-success font-semibold' :
                                                project.маржинальность >= 15 ? 'text-warning' :
                                                project.маржинальность >= 0 ? 'text-muted' : 'text-danger'
                                            }>
                                                {project.маржинальность.toFixed(2)}%
                                            </td>
                                            <td>{formatCurrency(project.поступления)}</td>
                                            <td>{formatCurrency(project.отток)}</td>
                                            <td className={
                                                project.чистый_результат >= 0 ? 'text-success font-semibold' : 'text-danger font-semibold'
                                            }>
                                                {formatCurrency(project.чистый_результат)}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}

// Отчет 3: Анализ статей
function Report3({ startDate, endDate, user }) {
    const [articlesData, setArticlesData] = useState(null);
    const [articleType, setArticleType] = useState('all');
    const [loading, setLoading] = useState(false);
    const [sunburstChart, setSunburstChart] = useState(null);
    
    useEffect(() => {
        fetchArticlesData();
    }, [startDate, endDate, articleType]);
    
    const fetchArticlesData = async () => {
        setLoading(true);
        try {
            const response = await fetch(
                `${API_BASE}/api/report3/articles-analysis?` +
                `start_date=${startDate}&` +
                `end_date=${endDate}&` +
                `article_type=${articleType}`
            );
            const data = await response.json();
            setArticlesData(data);
            updateSunburstChart(data.all_articles);
        } catch (error) {
            console.error('Error fetching articles data:', error);
        } finally {
            setLoading(false);
        }
    };
    
    const updateSunburstChart = (articles) => {
        const ctx = document.getElementById('sunburstChart');
        if (!ctx || !articles || articles.length === 0) return;
        
        if (sunburstChart) {
            sunburstChart.destroy();
        }
        
        // Группируем данные для солнечной диаграммы
        const groupedData = {};
        articles.forEach(article => {
            const level1 = article.уровень1;
            const level2 = article.уровень2;
            const level4 = article.уровень4;
            
            if (!groupedData[level1]) {
                groupedData[level1] = {
                    name: level1,
                    value: 0,
                    children: {}
                };
            }
            
            if (!groupedData[level1].children[level2]) {
                groupedData[level1].children[level2] = {
                    name: level2,
                    value: 0,
                    children: {}
                };
            }
            
            if (!groupedData[level1].children[level2].children[level4]) {
                groupedData[level1].children[level2].children[level4] = {
                    name: level4,
                    value: article.сумма
                };
            }
            
            groupedData[level1].value += article.сумма;
            groupedData[level1].children[level2].value += article.сумма;
        });
        
        // Для простоты используем круговую диаграмму
        const chart = new Chart(ctx.getContext('2d'), {
            type: 'pie',
            data: {
                labels: articles.slice(0, 10).map(a => a.уровень4),
                datasets: [{
                    data: articles.slice(0, 10).map(a => a.сумма),
                    backgroundColor: [
                        '#007aff', '#34c759', '#ff3b30', '#ff9500', '#af52de',
                        '#ffcc00', '#5856d6', '#ff2d55', '#8e8e93', '#a2845e'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const label = context.label || '';
                                const value = context.raw || 0;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = Math.round((value / total) * 100);
                                return `${label}: ${formatCurrency(value)} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
        
        setSunburstChart(chart);
    };
    
    if (loading) {
        return (
            <div className="loading">
                <div className="loading-spinner"></div>
                <p>Загрузка анализа статей...</p>
            </div>
        );
    }
    
    return (
        <div>
            <DateFilter
                startDate={startDate}
                endDate={endDate}
                onStartDateChange={(date) => {/* обновить в родителе */}}
                onEndDateChange={(date) => {/* обновить в родителе */}}
            />
            
            <div className="filters-container">
                <div className="filter-row">
                    <div className="filter-group">
                        <label className="apple-label">Тип статей</label>
                        <select 
                            className="apple-select"
                            value={articleType}
                            onChange={(e) => setArticleType(e.target.value)}
                        >
                            <option value="all">Все статьи</option>
                            <option value="доходы">Только доходы</option>
                            <option value="расходы">Только расходы</option>
                        </select>
                    </div>
                </div>
            </div>
            
            {articlesData && (
                <>
                    <div className="chart-grid">
                        <div className="apple-card">
                            <div className="card-header">
                                <h3 className="card-title">
                                    <i className="fas fa-sun"></i>
                                    Распределение по статьям
                                </h3>
                            </div>
                            <div className="chart-container">
                                <canvas id="sunburstChart"></canvas>
                            </div>
                        </div>
                        
                        <div className="apple-card">
                            <div className="card-header">
                                <h3 className="card-title">
                                    <i className="fas fa-trophy"></i>
                                    ТОП-5 статей доходов
                                </h3>
                            </div>
                            <div className="p-4">
                                {articlesData.top_income.map((item, index) => (
                                    <div key={index} className="mb-3 p-3 border border-apple-border rounded-lg">
                                        <div className="flex justify-between items-center">
                                            <div>
                                                <div className="font-semibold">
                                                    <span className="text-apple-blue mr-2">#{index + 1}</span>
                                                    {item.статья}
                                                </div>
                                            </div>
                                            <div className="text-success font-semibold">
                                                {formatCurrency(item.сумма)}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                        
                        <div className="apple-card">
                            <div className="card-header">
                                <h3 className="card-title">
                                    <i className="fas fa-exclamation-triangle"></i>
                                    ТОП-5 статей расходов
                                </h3>
                            </div>
                            <div className="p-4">
                                {articlesData.top_expense.map((item, index) => (
                                    <div key={index} className="mb-3 p-3 border border-apple-border rounded-lg">
                                        <div className="flex justify-between items-center">
                                            <div>
                                                <div className="font-semibold">
                                                    <span className="text-apple-red mr-2">#{index + 1}</span>
                                                    {item.статья}
                                                </div>
                                            </div>
                                            <div className="text-danger font-semibold">
                                                {formatCurrency(item.сумма)}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                    
                    <div className="apple-card">
                        <div className="card-header">
                            <h3 className="card-title">
                                <i className="fas fa-list-alt"></i>
                                Детальный анализ статей
                            </h3>
                            <div className="text-sm text-apple-text-secondary">
                                Всего статей: {articlesData.all_articles.length}
                            </div>
                        </div>
                        
                        <div className="overflow-x-auto">
                            <table className="apple-table">
                                <thead>
                                    <tr>
                                        <th>Уровень 1</th>
                                        <th>Уровень 2</th>
                                        <th>Уровень 4</th>
                                        <th>Сумма</th>
                                        <th>Количество записей</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {articlesData.all_articles.slice(0, 50).map((article, index) => (
                                        <tr key={index}>
                                            <td>
                                                <div className="flex items-center gap-2">
                                                    <i className={`fas ${
                                                        article.уровень1 === 'Поступления по ОД' ? 'fa-arrow-up text-success' :
                                                        article.уровень1 === 'Отток по ОД' ? 'fa-arrow-down text-danger' :
                                                        'fa-exchange-alt text-warning'
                                                    }`}></i>
                                                    {article.уровень1}
                                                </div>
                                            </td>
                                            <td>{article.уровень2}</td>
                                            <td>{article.уровень4}</td>
                                            <td className={
                                                article.уровень1 === 'Поступления по ОД' ? 'text-success font-semibold' : 'text-danger font-semibold'
                                            }>
                                                {formatCurrency(article.сумма)}
                                            </td>
                                            <td className="text-center">
                                                <span className="px-2 py-1 bg-gray-100 rounded text-sm">
                                                    {article.количество}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}

// Отчет 4: ФОТ и сотрудники
function Report4({ startDate, endDate, user }) {
    const [fotData, setFotData] = useState(null);
    const [employeeDistribution, setEmployeeDistribution] = useState([]);
    const [loading, setLoading] = useState(false);
    const [fotChart, setFotChart] = useState(null);
    
    useEffect(() => {
        fetchFotData();
    }, [startDate, endDate]);
    
    const fetchFotData = async () => {
        setLoading(true);
        try {
            const [fotResponse, distributionResponse] = await Promise.all([
                fetch(`${API_BASE}/api/report4/fot-analysis?start_date=${startDate}&end_date=${endDate}`),
                fetch(`${API_BASE}/api/report4/employee-distribution?start_date=${startDate}&end_date=${endDate}`)
            ]);
            
            const fot = await fotResponse.json();
            const distribution = await distributionResponse.json();
            
            setFotData(fot);
            setEmployeeDistribution(distribution);
            updateFotChart(fot);
        } catch (error) {
            console.error('Error fetching FOT data:', error);
        } finally {
            setLoading(false);
        }
    };
    
    const updateFotChart = (data) => {
        const ctx = document.getElementById('fotChart');
        if (!ctx || !data?.fot_data) return;
        
        if (fotChart) {
            fotChart.destroy();
        }
        
        const chart = new Chart(ctx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: data.fot_data.slice(0, 10).map(d => d.проект),
                datasets: [
                    {
                        label: 'ФОТ сумма',
                        data: data.fot_data.slice(0, 10).map(d => d.фот_сумма),
                        backgroundColor: 'rgba(0, 122, 255, 0.7)',
                        borderColor: '#007aff',
                        borderWidth: 1
                    },
                    {
                        label: 'Количество сотрудников',
                        data: data.fot_data.slice(0, 10).map(d => d.сотрудники_кол),
                        backgroundColor: 'rgba(52, 199, 89, 0.7)',
                        borderColor: '#34c759',
                        borderWidth: 1,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'ФОТ (₽)'
                        }
                    },
                    y1: {
                        beginAtZero: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: 'Сотрудники'
                        },
                        grid: {
                            drawOnChartArea: false
                        }
                    }
                }
            }
        });
        
        setFotChart(chart);
    };
    
    if (loading) {
        return (
            <div className="loading">
                <div className="loading-spinner"></div>
                <p>Загрузка данных ФОТ...</p>
            </div>
        );
    }
    
    return (
        <div>
            <DateFilter
                startDate={startDate}
                endDate={endDate}
                onStartDateChange={(date) => {/* обновить в родителе */}}
                onEndDateChange={(date) => {/* обновить в родителе */}}
            />
            
            {fotData && (
                <>
                    <div className="apple-card">
                        <div className="card-header">
                            <h3 className="card-title">
                                <i className="fas fa-money-bill-wave"></i>
                                Общая статистика ФОТ
                            </h3>
                        </div>
                        
                        <div className="metrics-grid">
                            <div className="metric-card">
                                <div className="metric-title">Общий ФОТ</div>
                                <div className="metric-value text-info">
                                    {formatCurrency(fotData.total_metrics.total_fot)}
                                </div>
                                <div className="metric-change">
                                    {formatCurrency(fotData.total_metrics.avg_fot_per_employee)} на сотрудника
                                </div>
                            </div>
                            
                            <div className="metric-card">
                                <div className="metric-title">Всего сотрудников</div>
                                <div className="metric-value">{fotData.total_metrics.total_employees}</div>
                                <div className="metric-change">
                                    {fotData.total_metrics.total_projects_with_fot} проектов с ФОТ
                                </div>
                            </div>
                            
                            <div className="metric-card">
                                <div className="metric-title">Средний ФОТ/сотр.</div>
                                <div className="metric-value">
                                    {formatCurrency(fotData.total_metrics.avg_fot_per_employee)}
                                </div>
                                <div className="metric-change">
                                    в месяц
                                </div>
                            </div>
                            
                            <div className="metric-card">
                                <div className="metric-title">Проектов с ФОТ</div>
                                <div className="metric-value">{fotData.total_metrics.total_projects_with_fot}</div>
                                <div className="metric-change">
                                    {fotData.fot_data.length} активных
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div className="chart-grid">
                        <div className="apple-card">
                            <div className="card-header">
                                <h3 className="card-title">
                                    <i className="fas fa-chart-bar"></i>
                                    ФОТ по проектам
                                </h3>
                            </div>
                            <div className="chart-container">
                                <canvas id="fotChart"></canvas>
                            </div>
                        </div>
                        
                        <div className="apple-card">
                            <div className="card-header">
                                <h3 className="card-title">
                                    <i className="fas fa-users"></i>
                                    Распределение сотрудников
                                </h3>
                            </div>
                            <div className="p-4">
                                {employeeDistribution.slice(0, 5).map((item, index) => (
                                    <div key={index} className="mb-4 p-3 border border-apple-border rounded-lg">
                                        <div className="flex justify-between items-center mb-2">
                                            <div className="font-semibold">
                                                <i className="fas fa-project-diagram text-apple-blue mr-2"></i>
                                                {item.проект}
                                            </div>
                                            <span className={`tree-badge badge-${item.группа.toLowerCase()}`}>
                                                {item.группа}
                                            </span>
                                        </div>
                                        <div className="text-sm text-apple-text-secondary mb-2">
                                            Сотрудников: <span className="font-semibold">{item.сотрудники_кол}</span>
                                        </div>
                                        <div className="flex flex-wrap gap-1">
                                            {item.сотрудники.slice(0, 5).map((emp, idx) => (
                                                <span key={idx} className="px-2 py-1 bg-gray-100 rounded text-xs">
                                                    {emp}
                                                </span>
                                            ))}
                                            {item.сотрудники.length > 5 && (
                                                <span className="px-2 py-1 bg-gray-100 rounded text-xs">
                                                    +{item.сотрудники.length - 5} еще
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                    
                    <div className="apple-card">
                        <div className="card-header">
                            <h3 className="card-title">
                                <i className="fas fa-table"></i>
                                Детальный анализ ФОТ по проектам
                            </h3>
                        </div>
                        
                        <div className="overflow-x-auto">
                            <table className="apple-table">
                                <thead>
                                    <tr>
                                        <th>Проект</th>
                                        <th>Группа</th>
                                        <th>ФОТ сумма</th>
                                        <th>Сотрудники</th>
                                        <th>ФОТ/сотр.</th>
                                        <th>% от общего</th>
                                        <th>Результат проекта</th>
                                        <th>ФОТ/Результат</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {fotData.fot_data.map((item, index) => (
                                        <tr key={index}>
                                            <td>
                                                <div className="flex items-center gap-2">
                                                    <i className="fas fa-project-diagram text-apple-blue"></i>
                                                    {item.проект}
                                                </div>
                                            </td>
                                            <td>
                                                <span className={`tree-badge badge-${item.группа.toLowerCase()}`}>
                                                    {item.группа}
                                                </span>
                                            </td>
                                            <td className="font-semibold">{formatCurrency(item.фот_сумма)}</td>
                                            <td className="text-center">
                                                <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded">
                                                    {item.сотрудники_кол}
                                                </span>
                                            </td>
                                            <td>{formatCurrency(item.фот_на_сотрудника)}</td>
                                            <td>
                                                <div className="flex items-center gap-2">
                                                    <span>{item.процент_от_общего}%</span>
                                                    <div className="flex-1 h-2 bg-gray-200 rounded overflow-hidden">
                                                        <div 
                                                            className="h-full bg-apple-blue"
                                                            style={{ width: `${Math.min(item.процент_от_общего, 100)}%` }}
                                                        ></div>
                                                    </div>
                                                </div>
                                            </td>
                                            <td className={
                                                item.результат >= 0 ? 'text-success font-semibold' : 'text-danger font-semibold'
                                            }>
                                                {formatCurrency(item.результат)}
                                            </td>
                                            <td className={
                                                item.фот_к_результату >= 100 ? 'text-success' :
                                                item.фот_к_результату >= 50 ? 'text-warning' : 'text-danger'
                                            }>
                                                {item.фот_к_результату.toFixed(1)}%
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}

// Главный компонент приложения
function App() {
    const [user, setUser] = useState(null);
    const [activeReport, setActiveReport] = useState('report1');
    const [startDate, setStartDate] = useState(getFirstDayOfYear());
    const [endDate, setEndDate] = useState(getToday());
    const [showLogin, setShowLogin] = useState(false);
    const [showRegister, setShowRegister] = useState(false);
    
    // Проверяем аутентификацию при загрузке
    useEffect(() => {
        const token = localStorage.getItem('token');
        if (token) {
            // В реальном приложении здесь была бы проверка токена
            const savedUser = localStorage.getItem('user');
            if (savedUser) {
                setUser(JSON.parse(savedUser));
            }
        }
    }, []);
    
    const handleLogin = async (username, password) => {
        try {
            const response = await fetch(`${API_BASE}/api/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            
            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('token', data.access_token);
                localStorage.setItem('user', JSON.stringify(data.user));
                setUser(data.user);
                setShowLogin(false);
                return true;
            } else {
                alert('Неверный логин или пароль');
                return false;
            }
        } catch (error) {
            console.error('Login error:', error);
            alert('Ошибка при входе');
            return false;
        }
    };
    
    const handleLogout = () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        setUser(null);
    };
    
    const renderReport = () => {
        const props = { startDate, endDate, user };
        
        switch (activeReport) {
            case 'report1':
                return <Report1 {...props} />;
            case 'report2':
                return <Report2 {...props} />;
            case 'report3':
                return <Report3 {...props} />;
            case 'report4':
                return <Report4 {...props} />;
            default:
                return <Report1 {...props} />;
        }
    };
    
    return (
        <div className="app-container">
            <Header user={user} onLogout={handleLogout} />
            
            <div className="main-content">
                {!user ? (
                    <div className="flex items-center justify-center min-h-[60vh]">
                        <div className="apple-card max-w-md w-full">
                            <div className="card-header">
                                <h3 className="card-title">
                                    <i className="fas fa-lock"></i>
                                    Требуется вход
                                </h3>
                            </div>
                            
                            <div className="p-6">
                                <p className="mb-6 text-apple-text-secondary">
                                    Для доступа к аналитике эффективности проектов требуется авторизация.
                                </p>
                                
                                <div className="space-y-4">
                                    <button 
                                        className="apple-button button-primary w-full"
                                        onClick={() => {
                                            // Автоматический вход для демо
                                            handleLogin('admin', 'admin123');
                                        }}
                                    >
                                        <i className="fas fa-sign-in-alt"></i>
                                        Войти как Администратор
                                    </button>
                                    
                                    <button 
                                        className="apple-button button-secondary w-full"
                                        onClick={() => {
                                            // Автоматический вход для демо
                                            handleLogin('user', 'user123');
                                        }}
                                    >
                                        <i className="fas fa-user"></i>
                                        Войти как Пользователь
                                    </button>
                                </div>
                                
                                <div className="mt-6 pt-6 border-t border-apple-border text-center text-sm text-apple-text-secondary">
                                    <p>Демо доступ:</p>
                                    <p className="mt-2">
                                        <strong>Админ:</strong> admin / admin123<br />
                                        <strong>Пользователь:</strong> user / user123
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                ) : (
                    <>
                        <Navigation 
                            activeReport={activeReport} 
                            onReportChange={setActiveReport} 
                        />
                        
                        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                            <div className="flex items-center gap-3">
                                <i className="fas fa-calendar-alt text-blue-600"></i>
                                <div>
                                    <div className="font-semibold">Период анализа</div>
                                    <div className="text-sm text-gray-600">
                                        {formatDate(startDate)} - {formatDate(endDate)}
                                    </div>
                                </div>
                                <div className="ml-auto flex gap-2">
                                    <button 
                                        className="apple-button button-secondary"
                                        onClick={() => {
                                            setStartDate(getFirstDayOfMonth());
                                            setEndDate(getToday());
                                        }}
                                    >
                                        Этот месяц
                                    </button>
                                    <button 
                                        className="apple-button button-secondary"
                                        onClick={() => {
                                            setStartDate(getFirstDayOfYear());
                                            setEndDate(getToday());
                                        }}
                                    >
                                        Этот год
                                    </button>
                                </div>
                            </div>
                        </div>
                        
                        {renderReport()}
                    </>
                )}
            </div>
            
            {/* Футер */}
            <footer className="mt-12 py-6 border-t border-apple-border bg-white">
                <div className="max-w-6xl mx-auto px-4">
                    <div className="flex flex-col md:flex-row justify-between items-center">
                        <div className="mb-4 md:mb-0">
                            <div className="flex items-center gap-2">
                                <i className="fas fa-chart-line text-apple-blue text-xl"></i>
                                <span className="font-semibold">Аналитика эффективности проектов</span>
                            </div>
                            <p className="text-sm text-gray-600 mt-1">
                                Система мониторинга и анализа финансовых показателей
                            </p>
                        </div>
                        
                        <div className="text-sm text-gray-600">
                            <p>© 2024 Все права защищены</p>
                            <p className="mt-1">Версия 1.0.0</p>
                        </div>
                    </div>
                </div>
            </footer>
        </div>
    );
}

// Вспомогательные функции
function formatCurrency(value) {
    if (value === null || value === undefined) return '0 ₽';
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(value);
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('ru-RU', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

function getFirstDayOfMonth() {
    const date = new Date();
    return new Date(date.getFullYear(), date.getMonth(), 1).toISOString().split('T')[0];
}

function getFirstDayOfYear() {
    const date = new Date();
    return new Date(date.getFullYear(), 0, 1).toISOString().split('T')[0];
}

function getToday() {
    return new Date().toISOString().split('T')[0];
}