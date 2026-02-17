/**
 * Telegram Mini App — Habit Tracker
 * Полностью по гайдлайнам Telegram: themeParams, safe area, нативные паттерны
 */
const tg = window.Telegram?.WebApp;
if (!tg) {
    console.error('Telegram WebApp API not available');
}

// Инициализация
if (tg) {
    tg.expand();
    tg.enableClosingConfirmation();
    tg.ready();

    // Header и background — только цвета из темы Telegram
    if (tg.themeParams?.bg_color) {
        tg.setBackgroundColor(tg.themeParams.bg_color);
    }
    if (tg.themeParams?.secondary_bg_color || tg.themeParams?.bg_color) {
        tg.setHeaderColor(tg.themeParams.secondary_bg_color || tg.themeParams.bg_color);
    }
}

// Применяем ВСЕ theme params из Telegram (без выдуманных цветов)
function applyTheme() {
    const p = tg?.themeParams || {};
    const root = document.documentElement;

    root.style.setProperty('--tg-bg-color', p.bg_color || '#ffffff');
    root.style.setProperty('--tg-secondary-bg-color', p.secondary_bg_color || '#f4f4f5');
    root.style.setProperty('--tg-text-color', p.text_color || '#000000');
    root.style.setProperty('--tg-hint-color', p.hint_color || '#999999');
    root.style.setProperty('--tg-link-color', p.link_color || '#2481cc');
    root.style.setProperty('--tg-button-color', p.button_color || '#2481cc');
    root.style.setProperty('--tg-button-text-color', p.button_text_color || '#ffffff');
    root.style.setProperty('--tg-header-bg-color', p.header_bg_color || p.bg_color || '#ffffff');
    root.style.setProperty('--tg-accent-text-color', p.accent_text_color || p.link_color || '#2481cc');
    root.style.setProperty('--tg-section-bg-color', p.section_bg_color || p.secondary_bg_color || '#f4f4f5');
    root.style.setProperty('--tg-section-header-text-color', p.section_header_text_color || p.hint_color || '#999999');
    root.style.setProperty('--tg-subtitle-text-color', p.subtitle_text_color || p.hint_color || '#999999');
    root.style.setProperty('--tg-destructive-text-color', p.destructive_text_color || '#ff3b30');
    root.style.setProperty('--tg-section-separator-color', p.section_separator_color || 'rgba(0,0,0,0.08)');
    root.style.setProperty('--tg-bottom-bar-bg-color', p.bottom_bar_bg_color || p.bg_color || '#ffffff');
}

if (tg) {
    applyTheme();
    tg.onEvent('themeChanged', applyTheme);
}

// API
const API_BASE_URL = 'http://localhost:5001';

let currentGoalTab = 'daily';

const screens = ['home', 'goals', 'stats', 'settings'];
const screenTitles = { home: 'Главная', goals: 'Цели', stats: 'Статистика', settings: 'Настройки' };

function switchScreen(screenName) {
    screens.forEach(s => {
        document.getElementById(`screen-${s}`)?.classList.remove('active');
    });
    const screenEl = document.getElementById(`screen-${screenName}`);
    if (screenEl) screenEl.classList.add('active');

    const titleEl = document.getElementById('page-title');
    if (titleEl) titleEl.textContent = screenTitles[screenName] || screenName;

    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.screen === screenName);
    });

    loadScreenData(screenName);
}

async function loadScreenData(screenName) {
    try {
        if (screenName === 'home') await loadHomeData();
        else if (screenName === 'goals') await loadGoals(currentGoalTab);
        else if (screenName === 'stats') await loadStatsData();
    } catch (e) {
        console.error('loadScreenData', e);
    }
}

async function loadHomeData() {
    try {
        const [progressRes, alcoholRes] = await Promise.all([
            fetch(`${API_BASE_URL}/api/stats/progress`),
            fetch(`${API_BASE_URL}/api/stats/alcohol`)
        ]);
        const progress = progressRes.ok ? await progressRes.json() : null;
        const alcohol = alcoholRes.ok ? await alcoholRes.json() : null;

        if (progress?.success) {
            const s = progress.stats;
            setText('home-daily-progress', `${s.daily_goals?.completed ?? 0}/${s.daily_goals?.total ?? 0}`);
            setText('home-energy', '-');
            setText('home-walk', '-');
            setText('home-weekly-goals', `${s.weekly_goals?.completed ?? 0}/${s.weekly_goals?.total ?? 0}`);
            setText('home-avg-energy', s.avg_energy != null ? String(s.avg_energy.toFixed(1)) : '-');
            setText('home-walks', s.walks_count ?? '-');
            setText('home-monthly-goals', `${s.monthly_goals?.completed ?? 0}/${s.monthly_goals?.total ?? 0}`);
        }

        if (alcohol?.success) {
            const s = alcohol.stats;
            setText('home-days-sober', s.days_sober ?? '-');
            setText('home-money-saved', s.money_saved != null ? `${Number(s.money_saved).toLocaleString('ru-RU')} ₽` : '-');
        }
    } catch (e) {
        console.error('loadHomeData', e);
    }
}

async function loadStatsData() {
    try {
        const [progressRes, alcoholRes] = await Promise.all([
            fetch(`${API_BASE_URL}/api/stats/progress`),
            fetch(`${API_BASE_URL}/api/stats/alcohol`)
        ]);
        const progress = progressRes.ok ? await progressRes.json() : null;
        const alcohol = alcoholRes.ok ? await alcoholRes.json() : null;

        if (progress?.success) {
            const s = progress.stats;
            setText('stats-avg-energy', s.avg_energy != null ? String(s.avg_energy.toFixed(1)) : '-');
            setText('stats-walks', s.walks_count ?? '-');
        }

        if (alcohol?.success) {
            const s = alcohol.stats;
            setText('days-sober', s.days_sober ?? '-');
            setText('money-saved', s.money_saved != null ? `${Number(s.money_saved).toLocaleString('ru-RU')} ₽` : '-');
            setText('episodes-month', s.episodes_this_month ?? '-');
            setText('spent-month', s.money_spent_this_month != null ? `${Number(s.money_spent_this_month).toLocaleString('ru-RU')} ₽` : '-');
        }
    } catch (e) {
        console.error('loadStatsData', e);
    }
}

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function switchGoalTab(tabName) {
    currentGoalTab = tabName;
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tabName));
    document.querySelectorAll('.goals-list').forEach(l => l.classList.remove('active'));
    const list = document.getElementById(`${tabName}-goals`);
    if (list) list.classList.add('active');
    loadGoals(tabName);
}

async function loadGoals(type) {
    const container = document.getElementById(`${type}-goals`);
    if (!container) return;
    container.innerHTML = '<div class="loading">Загрузка...</div>';

    try {
        const res = await fetch(`${API_BASE_URL}/api/goals/${type}`);
        const data = res.ok ? await res.json() : null;

        if (data?.success && Array.isArray(data.goals)) {
            displayGoals(container, data.goals, type);
        } else {
            container.innerHTML = '<div class="loading">Ошибка загрузки</div>';
        }
    } catch (e) {
        console.error('loadGoals', e);
        container.innerHTML = '<div class="loading">Ошибка соединения</div>';
    }
}

function displayGoals(container, goals, type) {
    if (!goals.length) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-text">Нет целей</div><div class="empty-state-hint">Добавьте новые цели</div></div>';
        return;
    }

    container.innerHTML = goals.map(g => `
        <div class="list-item goal-item ${g.completed ? 'completed' : ''}" data-id="${g.id}" data-type="${type}">
            <div class="goal-checkbox" aria-hidden="true">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
            </div>
            <span class="goal-text">${escapeHtml(g.text)}</span>
        </div>
    `).join('');

    container.querySelectorAll('.goal-item').forEach(item => {
        item.addEventListener('click', () => toggleGoal(item));
    });
}

async function toggleGoal(element) {
    const goalId = element.dataset.id;
    const goalType = element.dataset.type;
    if (!goalId || !goalType) return;

    element.classList.toggle('completed');

    try {
        const res = await fetch(`${API_BASE_URL}/api/goals/${goalType}/${goalId}/toggle`, { method: 'POST' });
        const data = res.ok ? await res.json() : null;

        if (!data?.success) {
            element.classList.toggle('completed');
            tg?.showAlert?.('Ошибка при сохранении');
        } else {
            tg?.HapticFeedback?.impactOccurred?.('light');
            const active = document.querySelector('.screen.active');
            if (active?.id === 'screen-home') loadHomeData();
        }
    } catch (e) {
        element.classList.toggle('completed');
        tg?.showAlert?.('Ошибка соединения');
    }
}

function escapeHtml(text) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}

// Модалка
const modal = document.getElementById('add-goal-modal');
const goalInput = document.getElementById('goal-input');
const modalTitle = document.getElementById('modal-title');
const modalTitles = { daily: 'Дневные цели', weekly: 'Недельные цели', monthly: 'Месячные цели' };

document.getElementById('add-goal-btn')?.addEventListener('click', () => {
    if (modalTitle) modalTitle.textContent = modalTitles[currentGoalTab] || 'Добавить цель';
    if (goalInput) goalInput.value = '';
    modal?.classList.add('active');
});

document.getElementById('close-modal')?.addEventListener('click', () => modal?.classList.remove('active'));
document.getElementById('cancel-modal')?.addEventListener('click', () => modal?.classList.remove('active'));

document.getElementById('save-goal')?.addEventListener('click', async () => {
    const text = goalInput?.value?.trim() || '';
    const goals = text.split('\n').map(g => g.trim()).filter(Boolean);
    if (!goals.length) {
        tg?.showAlert?.('Введите хотя бы одну цель');
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/goals/${currentGoalTab}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ goals })
        });
        const data = res.ok ? await res.json() : null;

        if (data?.success) {
            modal?.classList.remove('active');
            tg?.HapticFeedback?.notificationOccurred?.('success');
            await loadGoals(currentGoalTab);
            if (document.querySelector('.screen.active')?.id === 'screen-home') loadHomeData();
        } else {
            tg?.showAlert?.('Ошибка при сохранении');
        }
    } catch (e) {
        tg?.showAlert?.('Ошибка соединения');
    }
});

modal?.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('active'); });

// Навигация
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
        switchScreen(item.dataset.screen);
        tg?.HapticFeedback?.impactOccurred?.('light');
    });
});

document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        switchGoalTab(tab.dataset.tab);
        tg?.HapticFeedback?.impactOccurred?.('light');
    });
});

// Настройки
document.getElementById('edit-questions-btn')?.addEventListener('click', () => {
    tg?.sendData?.('edit_questions');
    tg?.HapticFeedback?.impactOccurred?.('medium');
});

document.getElementById('reset-btn')?.addEventListener('click', () => {
    tg?.showConfirm?.('Вы уверены? Все данные будут удалены.', (ok) => {
        if (ok) { tg?.sendData?.('reset'); tg?.HapticFeedback?.notificationOccurred?.('warning'); }
    });
});

document.getElementById('help-btn')?.addEventListener('click', () => {
    tg?.showAlert?.('Используйте бот для ежедневного трекинга привычек. Ставьте цели и отмечайте их выполнение!');
    tg?.HapticFeedback?.impactOccurred?.('light');
});

// Старт
switchScreen('home');
