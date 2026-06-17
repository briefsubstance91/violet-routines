import csv
import json
import os

from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

_BASE           = os.path.dirname(os.path.abspath(__file__))
TASKS_FILE      = os.path.join(_BASE, 'Violet Tasks.csv')
PHRASES_FILE    = os.path.join(_BASE, 'Violet Phrases.csv')
MILESTONES_FILE = os.path.join(_BASE, 'Violet Milestones.csv')
IMAGES_DIR      = os.path.join(_BASE, 'static', 'images')
IMG_EXTS        = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
LOG_FILE        = os.path.join(_BASE, 'Violet Log.csv')


def list_images():
    try:
        return [f'/static/images/{f}' for f in sorted(os.listdir(IMAGES_DIR))
                if os.path.splitext(f)[1].lower() in IMG_EXTS]
    except FileNotFoundError:
        return []


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
        streak  = row.get('Streak', '').strip()
        message = row.get('Message', '').strip()
        if streak and message:
            milestones[streak] = message
    return milestones


def save_log_entry(date, routine_id, completed, total):
    """Write (or overwrite) today's entry for a routine in the log CSV."""
    rows = []
    try:
        with open(LOG_FILE, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not (row['Date'] == date and row['Routine'] == routine_id):
                    rows.append(row)
    except FileNotFoundError:
        pass
    rows.append({'Date': date, 'Routine': routine_id, 'Completed': completed, 'Total': total})
    with open(LOG_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Date', 'Routine', 'Completed', 'Total'])
        writer.writeheader()
        writer.writerows(rows)


def load_log():
    """Return all log rows as list of dicts."""
    rows = []
    try:
        with open(LOG_FILE, newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                rows.append(row)
    except FileNotFoundError:
        pass
    return rows


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
    return render_template(
        'index.html',
        routines=routines,
        phrases_json=json.dumps(phrases),
        routines_json=json.dumps(routines_cfg),
        milestones_json=json.dumps(milestones),
        images_json=json.dumps(list_images()),
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port)
