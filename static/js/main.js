// Main JavaScript file - общие функции для всего приложения

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация
    initMobileMenu();
    initAlerts();
    initAdminForm();
    updateDateTime();
    
    // Установка интервалов обновления
    setInterval(updateDateTime, 60000); // Обновлять время каждую минуту
});

// Мобильное меню
function initMobileMenu() {
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const mobileMenu = document.querySelector('.mobile-menu');
    
    if (mobileMenuBtn && mobileMenu) {
        mobileMenuBtn.addEventListener('click', function() {
            mobileMenu.style.display = mobileMenu.style.display === 'block' ? 'none' : 'block';
        });
        
        // Закрытие меню при клике вне его
        document.addEventListener('click', function(event) {
            if (!mobileMenu.contains(event.target) && !mobileMenuBtn.contains(event.target)) {
                mobileMenu.style.display = 'none';
            }
        });
    }
}

// Уведомления
function initAlerts() {
    // Закрытие алертов
    document.querySelectorAll('.alert-close').forEach(button => {
        button.addEventListener('click', function() {
            this.closest('.alert').style.display = 'none';
        });
    });
    
    // Автоматическое скрытие алертов через 5 секунд
    setTimeout(() => {
        document.querySelectorAll('.alert').forEach(alert => {
            alert.style.opacity = '0';
            setTimeout(() => alert.style.display = 'none', 300);
        });
    }, 5000);
}

// Форма добавления пользователя (для админа)
function initAdminForm() {
    const form = document.getElementById('addUserForm');
    if (!form) return;
    
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData(this);
        const data = {
            username: formData.get('username'),
            password: formData.get('password'),
            email: formData.get('email'),
            role: formData.get('role')
        };
        
        try {
            const response = await fetch('/admin/add_user', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            });
            
            if (response.ok) {
                alert('Пользователь успешно добавлен');
                this.reset();
                // Перезагружаем страницу для обновления данных
                setTimeout(() => location.reload(), 1000);
            } else {
                const error = await response.json();
                alert(error.error || 'Ошибка при добавлении пользователя');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Ошибка сети. Проверьте подключение к интернету.');
        }
    });
}

// Обновление времени в футере
function updateDateTime() {
    const now = new Date();
    const timeElement = document.getElementById('data-update-time');
    if (timeElement) {
        const timeString = now.toLocaleTimeString('ru-RU', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        timeElement.textContent = `Обновлено: ${timeString}`;
    }
}

// Форматирование валюты
function formatCurrency(value, currency = 'RUB') {
    if (value === null || value === undefined) return '0 ₽';
    
    const numValue = parseFloat(value);
    if (isNaN(numValue)) return '0 ₽';
    
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(numValue);
}

// Форматирование процентов
function formatPercent(value) {
    if (value === null || value === undefined) return '0%';
    
    const numValue = parseFloat(value);
    if (isNaN(numValue)) return '0%';
    
    const sign = numValue > 0 ? '+' : '';
    return `${sign}${numValue.toFixed(1)}%`;
}

// Форматирование даты
function formatDate(dateString) {
    if (!dateString) return '';
    
    const date = new Date(dateString);
    return date.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    });
}

// Показать уведомление
function showNotification(message, type = 'info') {
    const container = document.createElement('div');
    container.className = `notification notification-${type}`;
    container.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
            <button class="notification-close">&times;</button>
        </div>
    `;
    
    document.body.appendChild(container);
    
    // Анимация появления
    setTimeout(() => container.classList.add('show'), 10);
    
    // Закрытие
    container.querySelector('.notification-close').addEventListener('click', () => {
        container.classList.remove('show');
        setTimeout(() => container.remove(), 300);
    });
    
    // Автоматическое закрытие
    setTimeout(() => {
        if (container.parentNode) {
            container.classList.remove('show');
            setTimeout(() => container.remove(), 300);
        }
    }, 5000);
}

// Загрузка с индикатором
function showLoading(container) {
    if (!container) return;
    
    container.innerHTML = `
        <div class="loading">
            <div class="spinner"></div>
            <p>Загрузка данных...</p>
        </div>
    `;
}

// Показать ошибку загрузки
function showError(container, message = 'Ошибка загрузки данных') {
    if (!container) return;
    
    container.innerHTML = `
        <div class="error">
            <i class="fas fa-exclamation-triangle"></i>
            <h4>${message}</h4>
            <p>Попробуйте обновить страницу или повторить попытку позже</p>
            <button class="btn-secondary" onclick="location.reload()">
                <i class="fas fa-redo"></i> Обновить
            </button>
        </div>
    `;
}

// Открытие модального окна
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden'; // Блокируем скролл
    }
}

// Закрытие модального окна
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = ''; // Восстанавливаем скролл
    }
}

// Закрытие всех модальных окон
function closeAllModals() {
    document.querySelectorAll('.modal').forEach(modal => {
        modal.style.display = 'none';
    });
    document.body.style.overflow = '';
}

// Навешиваем обработчики закрытия модальных окон
document.addEventListener('DOMContentLoaded', function() {
    // Закрытие по клику на фон
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                closeModal(this.id);
            }
        });
    });
    
    // Закрытие по кнопке
    document.querySelectorAll('.modal-close').forEach(button => {
        button.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (modal) {
                closeModal(modal.id);
            }
        });
    });
    
    // Закрытие по Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeAllModals();
        }
    });
});

// Экспорт данных в CSV
function exportToCSV(data, filename) {
    if (!data || !data.length) {
        showNotification('Нет данных для экспорта', 'error');
        return;
    }
    
    // Создаем CSV строку
    const headers = Object.keys(data[0]);
    const csvRows = [
        headers.join(','),
        ...data.map(row => headers.map(header => {
            const value = row[header];
            // Экранируем кавычки и запятые
            return typeof value === 'string' && (value.includes(',') || value.includes('"'))
                ? `"${value.replace(/"/g, '""')}"`
                : value;
        }).join(','))
    ];
    
    const csvString = csvRows.join('\n');
    
    // Создаем Blob и скачиваем
    const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    
    if (navigator.msSaveBlob) { // IE 10+
        navigator.msSaveBlob(blob, filename);
    } else {
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }
    
    showNotification('Файл успешно экспортирован', 'success');
}

// Генерация уникального ID
function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

// Валидация email
function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

// Дебаунс функция
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Ограничение частоты вызова (троттлинг)
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Копирование в буфер обмена
function copyToClipboard(text) {
    navigator.clipboard.writeText(text)
        .then(() => showNotification('Скопировано в буфер обмена', 'success'))
        .catch(err => {
            console.error('Ошибка копирования: ', err);
            showNotification('Ошибка копирования', 'error');
        });
}

// Получение параметров из URL
function getUrlParams() {
    const params = new URLSearchParams(window.location.search);
    const result = {};
    for (const [key, value] of params.entries()) {
        result[key] = value;
    }
    return result;
}

// Установка параметров в URL
function setUrlParams(params) {
    const url = new URL(window.location);
    Object.keys(params).forEach(key => {
        if (params[key]) {
            url.searchParams.set(key, params[key]);
        } else {
            url.searchParams.delete(key);
        }
    });
    window.history.pushState({}, '', url);
}

// Загрузка данных с обработкой ошибок
async function fetchWithErrorHandling(url, options = {}) {
    try {
        const response = await fetch(url, options);
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.error || `HTTP error ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Fetch error:', error);
        showNotification(error.message || 'Ошибка загрузки данных', 'error');
        throw error;
    }
}

// Инициализация тултипов
function initTooltips() {
    const tooltips = document.querySelectorAll('[data-tooltip]');
    
    tooltips.forEach(element => {
        element.addEventListener('mouseenter', function() {
            const tooltip = document.createElement('div');
            tooltip.className = 'tooltip';
            tooltip.textContent = this.dataset.tooltip;
            document.body.appendChild(tooltip);
            
            const rect = this.getBoundingClientRect();
            tooltip.style.left = rect.left + rect.width / 2 - tooltip.offsetWidth / 2 + 'px';
            tooltip.style.top = rect.top - tooltip.offsetHeight - 5 + 'px';
            
            this.dataset.tooltipId = tooltip.id = 'tooltip-' + generateId();
        });
        
        element.addEventListener('mouseleave', function() {
            const tooltipId = this.dataset.tooltipId;
            if (tooltipId) {
                const tooltip = document.getElementById(tooltipId);
                if (tooltip) {
                    tooltip.remove();
                }
            }
        });
    });
}

// Анимация чисел
function animateNumber(element, targetValue, duration = 1000) {
    const startValue = parseFloat(element.textContent.replace(/[^\d.-]/g, '')) || 0;
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const currentValue = startValue + (targetValue - startValue) * progress;
        element.textContent = formatCurrency(currentValue);
        
        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            element.textContent = formatCurrency(targetValue);
        }
    }
    
    requestAnimationFrame(update);
}

// Добавляем стили для уведомлений
const notificationStyles = document.createElement('style');
notificationStyles.textContent = `
    .notification {
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        transform: translateX(100%);
        transition: transform 0.3s ease;
        max-width: 350px;
    }
    
    .notification.show {
        transform: translateX(0);
    }
    
    .notification-content {
        background: var(--apple-card);
        border-radius: var(--radius-md);
        padding: var(--spacing-md);
        box-shadow: var(--apple-shadow-hover);
        display: flex;
        align-items: center;
        gap: var(--spacing-md);
    }
    
    .notification-success {
        border-left: 4px solid var(--apple-green);
    }
    
    .notification-error {
        border-left: 4px solid var(--apple-red);
    }
    
    .notification-info {
        border-left: 4px solid var(--apple-blue);
    }
    
    .notification-close {
        margin-left: auto;
        background: none;
        border: none;
        font-size: 1.2rem;
        cursor: pointer;
        color: var(--apple-text-secondary);
    }
    
    .tooltip {
        position: absolute;
        background: var(--apple-text);
        color: white;
        padding: var(--spacing-xs) var(--spacing-sm);
        border-radius: var(--radius-sm);
        font-size: 0.8rem;
        white-space: nowrap;
        z-index: 10000;
        pointer-events: none;
    }
    
    .tooltip:after {
        content: '';
        position: absolute;
        top: 100%;
        left: 50%;
        margin-left: -5px;
        border-width: 5px;
        border-style: solid;
        border-color: var(--apple-text) transparent transparent transparent;
    }
`;
document.head.appendChild(notificationStyles);

// Глобальные обработчики ошибок
window.addEventListener('error', function(event) {
    console.error('Global error:', event.error);
    showNotification('Произошла ошибка в приложении', 'error');
});

window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled promise rejection:', event.reason);
    showNotification('Ошибка выполнения операции', 'error');
});