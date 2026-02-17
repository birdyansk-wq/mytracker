"""
Простой Flask API для Telegram Mini App
Обрабатывает запросы из Mini App для работы с данными
"""

import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

logging.basicConfig(
    format="%(asctime)s [API] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
import hmac
import hashlib
from urllib.parse import parse_qs
from bot.config import BOT_TOKEN
from bot.database import (
    get_daily_goals, toggle_daily_goal_completion, add_daily_goals,
    get_weekly_goals, toggle_goal_completion, add_weekly_goals,
    get_monthly_goals, toggle_monthly_goal_completion, add_monthly_goals,
    get_today_log, get_last_n_days
)
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)


@app.before_request
def log_request():
    logger.info("→ %s %s", request.method, request.path)


@app.after_request
def log_response(response):
    logger.info("← %s %s → %d", request.method, request.path, response.status_code)
    return response


def verify_telegram_web_app_data(init_data: str) -> bool:
    """
    Проверяет подлинность данных от Telegram Mini App
    """
    try:
        parsed = parse_qs(init_data)
        hash_value = parsed.get('hash', [''])[0]
        
        # Создаем строку для проверки
        data_check_string = '\n'.join([
            f"{k}={v[0]}" 
            for k, v in sorted(parsed.items()) 
            if k != 'hash'
        ])
        
        # Вычисляем hash
        secret_key = hmac.new(
            "WebAppData".encode(),
            BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return calculated_hash == hash_value
    except:
        return False


@app.route('/api/goals/daily', methods=['GET'])
def get_daily_goals_api():
    """Получить дневные цели"""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        goals = get_daily_goals(today)
        logger.info("daily goals: %d шт.", len(goals))
        return jsonify({
            'success': True,
            'goals': [
                {
                    'id': g['id'],
                    'text': g['task_text'],
                    'completed': bool(g['is_completed'])
                }
                for g in goals
            ]
        })
    except Exception as e:
        logger.exception("get_daily_goals error")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/goals/daily/<int:goal_id>/toggle', methods=['POST'])
def toggle_daily_goal_api(goal_id):
    """Переключить статус дневной цели"""
    try:
        toggle_daily_goal_completion(goal_id)
        logger.info("toggle daily goal id=%s", goal_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("toggle_daily_goal error")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/goals/daily', methods=['POST'])
def add_daily_goals_api():
    """Добавить дневные цели"""
    try:
        data = request.json or {}
        goals = data.get('goals', [])
        logger.info("add_daily_goals: %s", goals)
        add_daily_goals(goals)
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("add_daily_goals error")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/goals/weekly', methods=['GET'])
def get_weekly_goals_api():
    """Получить недельные цели"""
    try:
        goals = get_weekly_goals()
        return jsonify({
            'success': True,
            'goals': [
                {
                    'id': g['id'],
                    'text': g['task_text'],
                    'completed': bool(g['is_completed'])
                }
                for g in goals
            ]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/goals/weekly/<int:goal_id>/toggle', methods=['POST'])
def toggle_weekly_goal_api(goal_id):
    """Переключить статус недельной цели"""
    try:
        toggle_goal_completion(goal_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/goals/weekly', methods=['POST'])
def add_weekly_goals_api():
    """Добавить недельные цели"""
    try:
        data = request.json
        goals = data.get('goals', [])
        add_weekly_goals(goals)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/goals/monthly', methods=['GET'])
def get_monthly_goals_api():
    """Получить месячные цели"""
    try:
        goals = get_monthly_goals()
        return jsonify({
            'success': True,
            'goals': [
                {
                    'id': g['id'],
                    'text': g['task_text'],
                    'completed': bool(g['is_completed'])
                }
                for g in goals
            ]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/goals/monthly/<int:goal_id>/toggle', methods=['POST'])
def toggle_monthly_goal_api(goal_id):
    """Переключить статус месячной цели"""
    try:
        toggle_monthly_goal_completion(goal_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/goals/monthly', methods=['POST'])
def add_monthly_goals_api():
    """Добавить месячные цели"""
    try:
        data = request.json
        goals = data.get('goals', [])
        add_monthly_goals(goals)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stats/progress', methods=['GET'])
def get_progress_stats():
    """Получить статистику прогресса"""
    try:
        logs = get_last_n_days(7)
        
        # Подсчет статистики
        total_days = len(logs)
        energy_values = [log.get('energy') for log in logs if log.get('energy') is not None]
        avg_energy = round(sum(energy_values) / total_days, 1) if total_days > 0 else 0
        
        walks = sum(1 for log in logs if log.get('walk'))
        
        # Цели
        daily_goals = get_daily_goals(datetime.now().strftime("%Y-%m-%d"))
        daily_completed = sum(1 for g in daily_goals if g['is_completed'])
        daily_total = len(daily_goals)
        
        weekly_goals = get_weekly_goals()
        weekly_completed = sum(1 for g in weekly_goals if g['is_completed'])
        weekly_total = len(weekly_goals)
        
        monthly_goals = get_monthly_goals()
        monthly_completed = sum(1 for g in monthly_goals if g['is_completed'])
        monthly_total = len(monthly_goals)
        
        return jsonify({
            'success': True,
            'stats': {
                'avg_energy': avg_energy,
                'walks_count': walks,
                'daily_goals': {'completed': daily_completed, 'total': daily_total},
                'weekly_goals': {'completed': weekly_completed, 'total': weekly_total},
                'monthly_goals': {'completed': monthly_completed, 'total': monthly_total}
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stats/alcohol', methods=['GET'])
def get_alcohol_stats():
    """Получить статистику по алкоголю"""
    try:
        logs = get_last_n_days(30)
        
        # Находим последний день с алкоголем
        last_alcohol_day = None
        for log in reversed(logs):
            if log.get('alcohol'):
                last_alcohol_day = datetime.strptime(log['date'], "%Y-%m-%d")
                break
        
        # Считаем дни без алкоголя
        if last_alcohol_day:
            days_sober = (datetime.now() - last_alcohol_day).days
        else:
            days_sober = len(logs) if logs else 0
        
        # Считаем экономию (3000 за эпизод)
        money_saved = days_sober * (3000 / 3.5)  # примерно 2-3 раза в неделю
        
        # Статистика за месяц
        alcohol_episodes = sum(1 for log in logs if log.get('alcohol'))
        money_spent = alcohol_episodes * 3000
        
        return jsonify({
            'success': True,
            'stats': {
                'days_sober': days_sober,
                'money_saved': int(money_saved),
                'episodes_this_month': alcohol_episodes,
                'money_spent_this_month': money_spent
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
