// Telegram Mini App init
const tg = window.Telegram?.WebApp;

if (tg) {
  tg.ready();
  tg.expand();

  // Применяем тему Telegram
  document.documentElement.style.setProperty('--tg-theme-bg-color', tg.themeParams?.bg_color || '#1c1c1e');
  document.documentElement.style.setProperty('--tg-theme-text-color', tg.themeParams?.text_color || '#ffffff');
  document.documentElement.style.setProperty('--tg-theme-hint-color', tg.themeParams?.hint_color || '#8e8e93');
  document.documentElement.style.setProperty('--tg-theme-link-color', tg.themeParams?.link_color || '#0a84ff');
  document.documentElement.style.setProperty('--tg-theme-secondary-bg-color', tg.themeParams?.secondary_bg_color || '#2c2c2e');

  // Light theme overrides
  if (tg.colorScheme === 'light') {
    document.documentElement.style.setProperty('--tg-theme-bg-color', tg.themeParams?.bg_color || '#ffffff');
    document.documentElement.style.setProperty('--tg-theme-text-color', tg.themeParams?.text_color || '#000000');
    document.documentElement.style.setProperty('--tg-theme-secondary-bg-color', tg.themeParams?.secondary_bg_color || '#f2f2f7');
  }
}

// Открытие команды — бот получает /start с параметром и показывает нужные данные
const BOT_USERNAME = getBotUsername();

function getBotUsername() {
  const params = new URLSearchParams(window.location.search);
  return params.get('bot') || '';
}

document.querySelectorAll('.menu-item').forEach(item => {
  item.addEventListener('click', (e) => {
    e.preventDefault();
    const cmd = item.dataset.cmd;

    if (tg?.HapticFeedback) {
      tg.HapticFeedback.impactOccurred('light');
    }

    if (BOT_USERNAME) {
      tg?.openTelegramLink(`https://t.me/${BOT_USERNAME}?start=${cmd}`);
      tg?.close();
    } else if (tg) {
      tg.showAlert('Отправь /' + cmd + ' боту в чате');
    }
  });
});
