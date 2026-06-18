import csv
import json
import os

from collections import defaultdict
from datetime import date, timedelta

from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

_BASE           = os.path.dirname(os.path.abspath(__file__))
TASKS_FILE      = os.path.join(_BASE, 'Violet Tasks.csv')
PHRASES_FILE    = os.path.join(_BASE, 'Violet Phrases.csv')
MILESTONES_FILE = os.path.join(_BASE, 'Violet Milestones.csv')
IMAGES_DIR      = os.path.join(_BASE, 'static', 'images')
CEL_DIR         = os.path.join(_BASE, 'static', 'celebration')
IMG_EXTS        = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
_DATA              = os.environ.get('DATA_DIR', _BASE)
LOG_FILE           = os.path.join(_DATA, 'Violet Log.csv')
LEVELUP_DATA_FILE  = os.path.join(_DATA, 'violet_data.json')
LEVELUP_SEED_FILE  = os.path.join(_BASE, 'violet_data.json')
LEVELUP_LOG_FILE   = os.path.join(_DATA, 'Violet Levelup Log.csv')


def list_images():
    try:
        return [f'/static/images/{f}' for f in sorted(os.listdir(IMAGES_DIR))
                if os.path.splitext(f)[1].lower() in IMG_EXTS]
    except FileNotFoundError:
        return []


def list_celebration_images():
    """Return { routine_id: [url, ...] } and { streak_str: url } for milestones."""
    routines = {}
    for folder in ('am', 'af', 'pm'):
        path = os.path.join(CEL_DIR, folder)
        try:
            routines[folder] = [
                f'/static/celebration/{folder}/{f}'
                for f in sorted(os.listdir(path))
                if os.path.splitext(f)[1].lower() in IMG_EXTS
            ]
        except FileNotFoundError:
            routines[folder] = []

    milestones = {}
    path = os.path.join(CEL_DIR, 'milestones')
    try:
        for f in os.listdir(path):
            stem, ext = os.path.splitext(f)
            if ext.lower() in IMG_EXTS:
                milestones[stem] = f'/static/celebration/milestones/{f}'
    except FileNotFoundError:
        pass

    return routines, milestones


def scan_csv(path, header_col):
    """Open a CSV, scan forward until a row whose first cell matches header_col, return rows."""
    rows = []
    try:
        with open(path, newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = None
            for raw in reader:
                if raw and raw[0].strip() == header_col:
                    header = [c.strip() for c in raw]
                    break
            if not header:
                return []
            for raw in reader:
                row = dict(zip(header, [c.strip() for c in raw]))
                rows.append(row)
    except FileNotFoundError:
        pass
    return rows


def load_routines():
    rows = scan_csv(TASKS_FILE, 'Routine')
    routines = []
    by_id = {}
    for row in rows:
        rid    = row.get('ID', '').strip()
        name   = row.get('Routine', '').strip()
        label  = row.get('Task', '').strip()
        parent = row.get('Parent', '').strip()
        if not rid or not label:
            continue
        if rid not in by_id:
            by_id[rid] = {
                'id':      rid,
                'name':    name,
                'icon':    row.get('Icon', '').strip(),
                'time':    row.get('Time', '').strip(),
                'banner':  row.get('Banner', '').strip(),
                'tasks':   [],
                '_map':    {},
            }
            routines.append(rid)
        r = by_id[rid]
        if parent and parent in r['_map']:
            r['_map'][parent]['subtasks'].append({'label': label})
        else:
            t = {'label': label, 'subtasks': []}
            r['tasks'].append(t)
            r['_map'][label] = t

    result = []
    for rid in routines:
        r = by_id[rid]
        del r['_map']
        for i, task in enumerate(r['tasks']):
            task['idx'] = str(i)
            for j, sub in enumerate(task['subtasks']):
                sub['idx'] = f'{i}-{j}'
        result.append(r)
    return result


def load_phrases():
    rows = scan_csv(PHRASES_FILE, 'Routine')
    phrases = {}
    for row in rows:
        rid    = row.get('Routine', '').strip()
        title  = row.get('Title', '').strip()
        reward = row.get('Reward', '').strip()
        if not rid or not title:
            continue
        if rid not in phrases:
            phrases[rid] = []
        phrases[rid].append({'title': title, 'reward': reward})
    return phrases


def load_milestones():
    rows = scan_csv(MILESTONES_FILE, 'Streak')
    milestones = {}
    for row in rows:
        streak   = row.get('Streak', '').strip()
        message  = (row.get('Reward Message') or row.get('Message', '')).strip()
        category = (row.get('Category') or row.get('Reward category', '')).strip()
        if streak and message:
            milestones[streak] = {'message': message, 'category': category}
    return milestones


def save_log_entry(date, routine_id, completed, total):
    """Write (or overwrite) today's entry for a routine in the log CSV."""
    rows = []
    existing = scan_csv(LOG_FILE, 'Date')
    rows = [r for r in existing if not (r.get('Date') == date and r.get('Routine') == routine_id)]
    rows.append({'Date': date, 'Routine': routine_id, 'Completed': completed, 'Total': total})
    with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Date', 'Routine', 'Completed', 'Total'])
        writer.writeheader()
        writer.writerows(rows)


def load_log():
    return scan_csv(LOG_FILE, 'Date')


def compute_stats(log_rows):
    today = date.today()
    entries = []
    for row in log_rows:
        try:
            d   = date.fromisoformat(row['Date'])
            tot = int(row['Total'])
            com = int(row['Completed'])
            entries.append({'date': d, 'routine': row['Routine'],
                            'completed': com, 'total': tot,
                            'pct': com / tot if tot else 0})
        except (ValueError, KeyError):
            continue

    by_date = defaultdict(list)
    for e in entries: by_date[e['date']].append(e)

    def day_pct(d):
        rows = by_date.get(d)
        if not rows: return None
        return sum(e['pct'] for e in rows) / len(rows)

    # Streak
    streak, d = 0, today
    while by_date.get(d):
        streak += 1; d -= timedelta(days=1)

    # Last 7 days
    week = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        week.append({'label': d.strftime('%a'), 'pct': day_pct(d)})

    # This month calendar
    first = today.replace(day=1)
    # pad to Monday start
    pad = first.weekday()
    cal_start = first - timedelta(days=pad)
    # enough weeks to cover the month
    last_day = (first.replace(month=first.month % 12 + 1, day=1) - timedelta(days=1)) if first.month < 12 else first.replace(month=12, day=31)
    cal_days = []
    d = cal_start
    while d <= last_day or len(cal_days) % 7 != 0:
        cal_days.append({'date': d, 'pct': day_pct(d), 'this_month': d.month == today.month})
        d += timedelta(days=1)

    # Per-routine all-time
    rt = defaultdict(lambda: {'c': 0, 't': 0})
    for e in entries:
        rt[e['routine']]['c'] += e['completed']
        rt[e['routine']]['t'] += e['total']
    routine_pct = {k: round(v['c'] / v['t'] * 100) if v['t'] else 0 for k, v in rt.items()}

    total_c = sum(e['completed'] for e in entries)
    total_t = sum(e['total'] for e in entries)

    return {
        'streak':      streak,
        'week':        week,
        'cal_days':    cal_days,
        'month_label': today.strftime('%B %Y'),
        'routine_pct': routine_pct,
        'total_days':  len(by_date),
        'overall_pct': round(total_c / total_t * 100) if total_t else 0,
    }


def load_levelup_data():
    for path in (LEVELUP_DATA_FILE, LEVELUP_SEED_FILE):
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                return json.load(f)
    return {'levelup_categories': []}


def save_levelup_data(data):
    with open(LEVELUP_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def log_levelup_entry(entry_date, category_id, category_label, win):
    rows = []
    try:
        with open(LEVELUP_LOG_FILE, newline='', encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
    except FileNotFoundError:
        pass
    rows.append({'Date': entry_date, 'CategoryID': category_id,
                 'Category': category_label, 'Win': win})
    with open(LEVELUP_LOG_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Date', 'CategoryID', 'Category', 'Win'])
        writer.writeheader()
        writer.writerows(rows)


def load_levelup_log():
    try:
        with open(LEVELUP_LOG_FILE, newline='', encoding='utf-8-sig') as f:
            return list(csv.DictReader(f))
    except FileNotFoundError:
        return []


@app.route('/sw.js')
def service_worker():
    return send_from_directory(_BASE, 'sw.js', mimetype='application/javascript')


@app.route('/admin/import-log', methods=['POST'])
def import_log():
    rows = request.get_json()
    existing = []
    try:
        with open(LOG_FILE, newline='', encoding='utf-8-sig') as f:
            existing = list(csv.DictReader(f))
    except FileNotFoundError:
        pass
    seen = {(r['Date'], r['Routine']) for r in existing}
    added = 0
    for row in rows:
        key = (row['Date'], row['Routine'])
        if key not in seen:
            existing.append(row)
            seen.add(key)
            added += 1
    existing.sort(key=lambda r: r['Date'])
    with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Date', 'Routine', 'Completed', 'Total'])
        writer.writeheader()
        writer.writerows(existing)
    return jsonify({'imported': added, 'total': len(existing)})


@app.route('/debug')
def debug():
    log_rows = load_log()
    return jsonify({
        'DATA_DIR': _DATA,
        'LOG_FILE': LOG_FILE,
        'log_exists': os.path.isfile(LOG_FILE),
        'log_row_count': len(log_rows),
        'last_5_rows': log_rows[-5:] if log_rows else [],
    })


@app.route('/log', methods=['POST'])
def log_entry():
    data = request.get_json()
    save_log_entry(data['date'], data['routine'], int(data['completed']), int(data['total']))
    return '', 204


@app.route('/')
def index():
    routines   = load_routines()
    phrases    = load_phrases()
    milestones = load_milestones()
    routines_cfg = {
        r['id']: {
            'total': len(r['tasks']),
            'emoji': r['icon'],
            'tasks': [{'idx': t['idx'], 'subs': [s['idx'] for s in t['subtasks']]} for t in r['tasks']],
        }
        for r in routines
    }
    levelup_data = load_levelup_data()
    cel_routines, cel_milestones = list_celebration_images()
    return render_template(
        'index.html',
        routines=routines,
        phrases_json=json.dumps(phrases),
        routines_json=json.dumps(routines_cfg),
        milestones_json=json.dumps(milestones),
        images_json=json.dumps(list_images()),
        cel_routines_json=json.dumps(cel_routines),
        cel_milestones_json=json.dumps(cel_milestones),
        levelup_categories_json=json.dumps(levelup_data.get('levelup_categories', [])),
        badges_json=json.dumps(BADGES),
    )


@app.route('/levelup', methods=['POST'])
def log_levelup():
    data = request.get_json()
    log_levelup_entry(data['date'], data['category_id'], data['category'], data['win'])
    return '', 204


@app.route('/levelup/today')
def levelup_today():
    today = date.today().isoformat()
    rows = [r for r in load_levelup_log() if r.get('Date') == today]
    return jsonify({'count': len(rows), 'wins': rows})


@app.route('/admin')
def admin():
    data = load_levelup_data()
    return render_template('admin.html', data=data)


@app.route('/admin/save', methods=['POST'])
def admin_save():
    data = request.get_json()
    save_levelup_data(data)
    return jsonify({'ok': True})


def load_tasks_raw():
    """Return routines as ordered list with metadata + task list for the task admin."""
    rows = scan_csv(TASKS_FILE, 'Routine')
    seen = {}
    order = []
    for row in rows:
        rid = row.get('ID', '').strip()
        if not rid:
            continue
        if rid not in seen:
            seen[rid] = {
                'id':     rid,
                'name':   row.get('Routine', '').strip(),
                'icon':   row.get('Icon', '').strip(),
                'time':   row.get('Time', '').strip(),
                'banner': row.get('Banner', '').strip(),
                'tasks':  [],
            }
            order.append(rid)
        task = row.get('Task', '').strip()
        if task:
            seen[rid]['tasks'].append(task)
    return [seen[rid] for rid in order]


def save_tasks_raw(routines):
    """Write routines list back to Violet Tasks.csv."""
    with open(TASKS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Violet Tasks'])
        writer.writerow(['Violet Tasks', '', '', '', '', ''])
        writer.writerow(['Routine', 'ID', 'Icon', 'Time', 'Banner', 'Task'])
        for r in routines:
            for task in r['tasks']:
                writer.writerow([r['name'], r['id'], r['icon'], r['time'], r['banner'], task])


@app.route('/admin/tasks')
def admin_tasks():
    routines = load_tasks_raw()
    return render_template('admin_tasks.html', routines_json=json.dumps(routines))


@app.route('/admin/tasks/save', methods=['POST'])
def admin_tasks_save():
    routines = request.get_json()
    save_tasks_raw(routines)
    return jsonify({'ok': True})


BADGES = [
    # ── Streak badges ──
    {'id': 'first-step',   'name': 'First Step',      'desc': 'Complete your first routine',  'emoji': '✨', 'bg': '#ede9fe', 'ring': '#9b87f5', 'type': 'streak',  'threshold': 1},
    {'id': 'spark',        'name': '3-Day Spark',      'desc': '3 days in a row',              'emoji': '🔥', 'bg': '#fef3c7', 'ring': '#f59e0b', 'type': 'streak',  'threshold': 3},
    {'id': 'week-warrior', 'name': 'Week Warrior',     'desc': '7-day streak',                 'emoji': '⭐', 'bg': '#d1fae5', 'ring': '#10b981', 'type': 'streak',  'threshold': 7},
    {'id': 'fortnight',    'name': 'Fortnight Hero',   'desc': '14 days in a row',             'emoji': '👑', 'bg': '#dbeafe', 'ring': '#3b82f6', 'type': 'streak',  'threshold': 14},
    {'id': '3-week',       'name': '3-Week Wonder',    'desc': '21 days in a row',             'emoji': '💜', 'bg': '#ede9fe', 'ring': '#7c3aed', 'type': 'streak',  'threshold': 21},
    {'id': 'month',        'name': 'Month Marvel',     'desc': '30-day streak',                'emoji': '🏆', 'bg': '#fce7f3', 'ring': '#ec4899', 'type': 'streak',  'threshold': 30},
    {'id': 'diamond',      'name': 'Diamond Legend',   'desc': '60-day streak',                'emoji': '💎', 'bg': '#cffafe', 'ring': '#06b6d4', 'type': 'streak',  'threshold': 60},
    # ── Routine badges ──
    {'id': 'morning-5',    'name': 'Morning Magic',    'desc': 'Morning routine ×5',           'emoji': '☁️', 'bg': '#fef9c3', 'ring': '#eab308', 'type': 'routine', 'routine': 'am', 'threshold': 5},
    {'id': 'morning-20',   'name': 'Rise & Shine',     'desc': 'Morning routine ×20',          'emoji': '🌅', 'bg': '#fef9c3', 'ring': '#f59e0b', 'type': 'routine', 'routine': 'am', 'threshold': 20},
    {'id': 'afternoon-5',  'name': 'Afternoon Ace',    'desc': 'Afternoon routine ×5',         'emoji': '🌸', 'bg': '#fce7f3', 'ring': '#ec4899', 'type': 'routine', 'routine': 'af', 'threshold': 5},
    {'id': 'evening-5',    'name': 'Bedtime Boss',     'desc': 'Evening routine ×5',           'emoji': '🖤', 'bg': '#ede9fe', 'ring': '#7c3aed', 'type': 'routine', 'routine': 'pm', 'threshold': 5},
    {'id': 'evening-20',   'name': 'Dream Keeper',     'desc': 'Evening routine ×20',          'emoji': '🌙', 'bg': '#ede9fe', 'ring': '#9b87f5', 'type': 'routine', 'routine': 'pm', 'threshold': 20},
    {'id': 'triple-crown', 'name': 'Triple Crown',     'desc': 'All 3 routines in one day',   'emoji': '👑', 'bg': '#fef3c7', 'ring': '#f59e0b', 'type': 'triple',  'threshold': 1},
    # ── Level Up badges ──
    {'id': 'levelup-1',    'name': 'Level Up!',        'desc': 'Log your first win',           'emoji': '⚡', 'bg': '#ede9fe', 'ring': '#7c3aed', 'type': 'levelup', 'threshold': 1},
    {'id': 'levelup-10',   'name': 'Win Collector',    'desc': '10 level-up wins',             'emoji': '💪', 'bg': '#fce7f3', 'ring': '#db2777', 'type': 'levelup', 'threshold': 10},
    {'id': 'levelup-25',   'name': 'Legend',           'desc': '25 level-up wins',             'emoji': '🌟', 'bg': '#fef3c7', 'ring': '#d97706', 'type': 'levelup', 'threshold': 25},
]


@app.route('/badges')
def badges():
    return render_template('badges.html', badges_json=json.dumps(BADGES))


@app.route('/dashboard')
def dashboard():
    routines     = load_routines()
    routine_meta = {r['id']: {'name': r['name'], 'icon': r['icon'], 'time': r['time']} for r in routines}
    milestones   = load_milestones()
    s            = compute_stats(load_log())
    lu_log       = load_levelup_log()

    # recent wins (last 10, newest first)
    recent_wins  = list(reversed(lu_log[-10:])) if lu_log else []
    lu_total     = len(lu_log)

    # next milestone
    streak = s['streak']
    milestones_sorted = sorted(milestones.items(), key=lambda x: int(x[0]))
    next_ms = next(((int(k), v) for k, v in milestones_sorted if int(k) > streak), None)
    prev_ms_streak = max((int(k) for k, v in milestones_sorted if int(k) <= streak), default=0)

    return render_template(
        'dashboard.html',
        stats=s,
        routine_meta=routine_meta,
        milestones=milestones,
        next_ms=next_ms,
        prev_ms_streak=prev_ms_streak,
        recent_wins=recent_wins,
        lu_total=lu_total,
        badges=BADGES,
        badges_json=json.dumps(BADGES),
        today_iso=date.today().isoformat(),
    )


@app.route('/stats')
def stats():
    routines = load_routines()
    routine_names = {r['id']: r['name'] for r in routines}
    s = compute_stats(load_log())
    return render_template('stats.html', stats=s, routine_names=routine_names,
                           routines=routines, today_iso=date.today().isoformat())


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port)
