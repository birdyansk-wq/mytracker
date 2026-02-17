// Инициализация Telegram Web App
const tg = window.Telegram.WebApp;
tg.expand();
tg.enableClosingConfirmation();

// Применяем тему Telegram
document.documentElement.style.setProperty('--tg-theme-bg-color', tg.themeParams.bg_color || '#ffffff');
document.documentElement.style.setProperty('--tg-theme-text-color', tg.themeParams.text_color || '#000000');
document.documentElement.style.setProperty('--tg-theme-hint-color', tg.themeParams.hint_color || '#999999');
document.documentElement.style.setProperty('--tg-theme-link-color', tg.themeParams.link_color || '#2481cc');
document.documentElement.style.setProperty('--tg-theme-button-color', tg.themeParams.button_color || '#2481cc');
document.documentElement.style.setProperty('--tg-theme-button-text-color', tg.themeParams.button_text_color || '#ffffff');
document.documentElement.style.setProperty('--tg-theme-secondary-bg-color', tg.themeParams.secondary_bg_color || '#f4f4f5');

// API базовый URL (замени на свой при деплое)
const API_BASE_URL = 'http://localhost:5001';

// Текущий активный таб целей
let currentGoalTab = 'daily';

// Навигация между экранами
const screens = ['goals', 'progress', 'alcohol', 'settings'];
const screenTitles = {
    goals: 'Цели',
    progress: 'Прогресс',
    alcohol: 'Алкоголь',
    settings: 'Настройки'
};

function switchScreen(screenName) {
    // Скрываем все экраны
    screens.forEach(s => {
        document.getElementById(`screen-${s}`).classList.remove('active');
    });

    // Показываем нужный
    document.getElementById(`screen-${screenName}`).classList.add('active');

    // Обновляем заголовок
    document.getElementById('page-title').textContent = screenTitles[screenName];

    // Обновляем навигацию
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-screen="${screenName}"]`).classList.add('active');

    // Загружаем данные для экрана
    loadScreenData(screenName);
}

// Загрузка данных для экрана
async function loadScreenData(screenName) {
    if (screenName === 'goals') {
        await loadGoals(currentGoalTab);
    } else if (screenName === 'progress') {
        await loadProgress();
    } else if (screenName === 'alcohol') {
        await loadAlcoholStats();
    }
}

// Табы целей
function switchGoalTab(tabName) {
    currentGoalTab = tabName;

    // Обновляем табы
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    // Обновляем списки
    document.querySelectorAll('.goals-list').forEach(list => {
        list.classList.remove('active');
    });
    document.getElementById(`${tabName}-goals`).classList.add('active');

    // Загружаем цели
    loadGoals(tabName);
}

// Загрузка целей
async function loadGoals(type) {
    const container = document.getElementById(`${type}-goals`);
    container.innerHTML = '<div class="loading">Загрузка...</div>';

    try {
        const response = await fetch(`${API_BASE_URL}/api/goals/${type}`);
        const data = await response.json();

        if (data.success) {
            displayGoals(container, data.goals, type);
        } else {
            container.innerHTML = '<div class="loading">Ошибка загрузки</div>';
        }
    } catch (error) {
        console.error('Error loading goals:', error);
        container.innerHTML = '<div class="loading">Ошибка соединения</div>';
    }
}

// Отображение целей
function displayGoals(container, goals, type) {
    if (goals.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🎯</div>
                <div class="empty-state-text">Нет целей</div>
                <div class="empty-state-hint">Добавьте новые цели</div>
            </div>
        `;
        return;
    }

    container.innerHTML = goals.map(goal => `
        <div class="goal-item ${goal.completed ? 'completed' : ''}" data-id="${goal.id}" data-type="${type}">
            <div class="goal-checkbox">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
            </div>
            <div class="goal-text">${escapeHtml(goal.text)}</div>
        </div>
    `).join('');

    // Добавляем обработчики
    container.querySelectorAll('.goal-item').forEach(item => {
        item.addEventListener('click', () => toggleGoal(item));
    });
}

// Переключение статуса цели
async function toggleGoal(element) {
    const goalId = element.dataset.id;
    const goalType = element.dataset.type;

    // Анимация
    element.classList.toggle('completed');

    try {
        const response = await fetch(`${API_BASE_URL}/api/goals/${goalType}/${goalId}/toggle`, {
            method: 'POST'
        });

        const data = await response.json();

        if (!data.success) {
            // Откатываем если ошибка
            element.classList.toggle('completed');
            tg.showAlert('Ошибка при сохранении');
        } else {
            // Вибрация при успехе
            tg.HapticFeedback.impactOccurred('light');
        }
    } catch (error) {
        console.error('Error toggling goal:', error);
        element.classList.toggle('completed');
        tg.showAlert('Ошибка соединения');
    }
}

// Загрузка прогресса
async function loadProgress() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/stats/progress`);
        const data = await response.json();

        if (data.success) {
            const stats = data.stats;
            document.getElementById('avg-energy').textContent = stats.avg_energy.toFixed(1);
            document.getElementById('walks-count').textContent = stats.walks_count;
            document.getElementById('daily-progress').textContent = 
                `${stats.daily_goals.completed}/${stats.daily_goals.total}`;
            document.getElementById('weekly-progress').textContent = 
                `${stats.weekly_goals.completed}/${stats.weekly_goals.total}`;
            document.getElementById('monthly-progress').textContent = 
                `${stats.monthly_goals.completed}/${stats.monthly_goals.total}`;
        }
    } catch (error) {
        console.error('Error loading progress:', error);
    }
}

// Загрузка статистики алкоголя
async function loadAlcoholStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/stats/alcohol`);
        const data = await response.json();

        if (data.success) {
            const stats = data.stats;
            document.getElementById('days-sober').textContent = stats.days_sober;
            document.getElementById('money-saved').textContent = 
                stats.money_saved.toLocaleString('ru-RU') + ' ₽';
            document.getElementById('episodes-month').textContent = stats.episodes_this_month;
            document.getElementById('spent-month').textContent = 
                stats.money_spent_this_month.toLocaleString('ru-RU') + ' ₽';
        }
    } catch (error) {
        console.error('Error loading alcohol stats:', error);
    }
}

// Модалка добавления целей
const modal = document.getElementById('add-goal-modal');
const addGoalBtn = document.getElementById('add-goal-btn');
const closeModalBtn = document.getElementById('close-modal');
const cancelModalBtn = document.getElementById('cancel-modal');
const saveGoalBtn = document.getElementById('save-goal');
const goalInput = document.getElementById('goal-input');
const modalTitle = document.getElementById('modal-title');

const modalTitles = {
    daily: 'Добавить дневные цели',
    weekly: 'Добавить недельные цели',
    monthly: 'Добавить месячные цели'
};

addGoalBtn.addEventListener('click', () => {
    modalTitle.textContent = modalTitles[currentGoalTab];
    goalInput.value = '';
    modal.classList.add('active');
});

closeModalBtn.addEventListener('click', () => {
    modal.classList.remove('active');
});

cancelModalBtn.addEventListener('click', () => {
    modal.classList.remove('active');
});

saveGoalBtn.addEventListener('click', async () => {
    const text = goalInput.value.trim();
    if (!text) {
        tg.showAlert('Введите хотя бы одну цель');
        return;
    }

    // Разбиваем на строки
    const goals = text.split('\n').map(g => g.trim()).filter(g => g);

    if (goals.length === 0) {
        tg.showAlert('Введите хотя бы одну цель');
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/goals/${currentGoalTab}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ goals })
        });

        const data = await response.json();

        if (data.success) {
            modal.classList.remove('active');
            tg.HapticFeedback.notificationOccurred('success');
            await loadGoals(currentGoalTab);
        } else {
            tg.showAlert('Ошибка при сохранении');
        }
    } catch (error) {
        console.error('Error adding goals:', error);
        tg.showAlert('Ошибка соединения');
    }
});

// Обработчики навигации
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
        const screen = item.dataset.screen;
        switchScreen(screen);
        tg.HapticFeedback.impactOccurred('light');
    });
});

// Обработчики табов целей
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        const tabName = tab.dataset.tab;
        switchGoalTab(tabName);
        tg.HapticFeedback.impactOccurred('light');
    });
});

// Настройки
document.getElementById('edit-questions-btn').addEventListener('click', () => {
    tg.sendData('edit_questions');
    tg.HapticFeedback.impactOccurred('medium');
});

document.getElementById('reset-btn').addEventListener('click', () => {
    tg.showConfirm('Вы уверены? Все данные будут удалены.', (confirmed) => {
        if (confirmed) {
            tg.sendData('reset');
            tg.HapticFeedback.notificationOccurred('warning');
        }
    });
});

document.getElementById('help-btn').addEventListener('click', () => {
    tg.showAlert('Используйте бот для ежедневного трекинга привычек. Ставьте цели и отмечайте их выполнение!');
    tg.HapticFeedback.impactOccurred('light');
});

// Utility функции
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// Закрытие модалки по клику вне её
modal.addEventListener('click', (e) => {
    if (e.target === modal) {
        modal.classList.remove('active');
    }
});

// Начальная загрузка
switchScreen('goals');
