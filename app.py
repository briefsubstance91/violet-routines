import csv
import json
import os
import re
import time
import uuid
import atexit
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import (Flask, render_template, request, jsonify, send_from_directory,
                   session, redirect, url_for)
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

_BASE           = os.path.dirname(os.path.abspath(__file__))
TASKS_SEED_FILE = os.path.join(_BASE, 'Violet Tasks.csv')
PHRASES_FILE    = os.path.join(_BASE, 'Violet Phrases.csv')   # read-only seed (never edited at runtime)
MILESTONES_SEED_FILE = os.path.join(_BASE, 'Violet Milestones.csv')
IMAGES_DIR      = os.path.join(_BASE, 'static', 'images')
CEL_DIR         = os.path.join(_BASE, 'static', 'celebration')
IMG_EXTS        = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
_DATA              = os.environ.get('DATA_DIR', _BASE)
LOG_FILE           = os.path.join(_DATA, 'Violet Log.csv')
LEVELUP_DATA_FILE  = os.path.join(_DATA, 'violet_data.json')
LEVELUP_SEED_FILE  = os.path.join(_BASE, 'violet_data.json')
LEVELUP_LOG_FILE   = os.path.join(_DATA, 'Violet Levelup Log.csv')
VAPID_FILE         = os.path.join(_DATA, 'vapid_keys.json')
PUSH_SUBS_FILE     = os.path.join(_DATA, 'push_subscriptions.json')
VAPID_CLAIMS       = {'sub': 'mailto:bgelineau@proton.me'}
_already_notified   = {}  # {routine_id:date → True}
CHARITIES_FILE      = os.path.join(_DATA, 'Violet Charities.csv')
CHARITIES_SEED_FILE = os.path.join(_BASE, 'Violet Charities.csv')
EVENTS_FILE         = os.path.join(_DATA, 'Violet Events.csv')
EVENTS_SEED_FILE    = os.path.join(_BASE, 'Violet Events.csv')
LEDGER_FILE         = os.path.join(_DATA, 'Violet Earnings.csv')
PAYOUTS_FILE        = os.path.join(_DATA, 'Violet Payouts.csv')
MONEY_MS_FILE       = os.path.join(_DATA, 'Violet Money Milestones.csv')
MONEY_MS_SEED_FILE  = os.path.join(_BASE, 'Violet Money Milestones.csv')
SETTINGS_FILE       = os.path.join(_DATA, 'violet_settings.json')
# Editable-at-runtime copies live on the volume; seeds in the repo are the fallback.
TASKS_FILE          = os.path.join(_DATA, 'Violet Tasks.csv')
MILESTONES_FILE     = os.path.join(_DATA, 'Violet Milestones.csv')
TOONIES_FILE        = os.path.join(_DATA, 'violet_toonies.json')
TOONIES_SEED_FILE   = os.path.join(_BASE, 'violet_toonies.json')
SURPRISES_FILE      = os.path.join(_DATA, 'violet_surprises.json')
PROGRESS_FILE       = os.path.join(_DATA, 'violet_progress.json')  # per-profile kid progress (synced)
SECRET_KEY_FILE     = os.path.join(_DATA, 'flask_secret.txt')      # persisted session signing key
DEFAULT_TZ          = 'America/Toronto'


# ── Sessions / parent login ─────────────────────────────────────────────
def _load_secret_key():
    """A stable secret so parent logins survive restarts. Prefer env, then a
    persisted key on the volume, otherwise generate and remember one."""
    key = os.environ.get('SECRET_KEY')
    if key:
        return key
    try:
        with open(SECRET_KEY_FILE, encoding='utf-8') as f:
            saved = f.read().strip()
        if saved:
            return saved
    except FileNotFoundError:
        pass
    key = uuid.uuid4().hex + uuid.uuid4().hex
    try:
        with open(SECRET_KEY_FILE, 'w', encoding='utf-8') as f:
            f.write(key)
    except OSError:
        pass
    return key


app.secret_key = _load_secret_key()
DEFAULT_ADMIN_PIN = '1234'


def admin_pin():
    """Current parent PIN. Settings override env, env overrides the default so a
    parent can change it in-app or via Railway without touching code."""
    pin = load_settings().get('admin_pin')
    if pin:
        return str(pin)
    return os.environ.get('ADMIN_PIN', DEFAULT_ADMIN_PIN)


def _admin_open(path):
    """Admin paths reachable without a session (the login flow itself)."""
    return path in ('/admin/login', '/admin/logout')


# ── Kid profiles ────────────────────────────────────────────────────────
# Single profile today; the store is keyed by id so more can be added later
# without a data migration.
PROFILES = {'violet': {'name': 'Violet'}}


@app.before_request
def _gate_admin():
    """Everything under /admin requires the parent PIN, except the login flow."""
    p = request.path
    if p.startswith('/admin') and not _admin_open(p):
        if not session.get('admin'):
            if request.method == 'GET':
                return redirect(url_for('admin_login', next=p))
            return jsonify({'error': 'unauthorized'}), 401
    return None


def current_profile():
    """The active kid profile. One profile for now; kept as a function so a
    profile picker can set session['profile'] in the future."""
    pid = session.get('profile', 'violet')
    return pid if pid in PROFILES else 'violet'


# Keys the kid client is allowed to persist server-side. Anything else is
# rejected so the endpoint can't be used as arbitrary storage.
PROGRESS_KEYS = {
    'violet-routines-v2', 'violet-days', 'violet-badges', 'violet-completions',
    'violet-lu-total', 'violet-triples', 'violet-last-triple', 'violet-extras-v1',
}


def _load_all_progress():
    try:
        with open(PROGRESS_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def load_progress(profile):
    """All synced progress for one kid profile (empty dict if none yet)."""
    return _load_all_progress().get(profile, {})


def save_progress_key(profile, key, value):
    all_p = _load_all_progress()
    all_p.setdefault(profile, {})[key] = value
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_p, f, indent=2)


def _data_or_seed(data_path, seed_path):
    """Prefer the volume copy (edited at runtime); fall back to the repo seed."""
    return data_path if os.path.exists(data_path) else seed_path


_MONTH_NUM = {m: i for i, m in enumerate(
    ['January','February','March','April','May','June',
     'July','August','September','October','November','December'], 1)}

_WEEKDAY_ABBR = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}

DEFAULT_TASK_VALUE = 2      # dollars earned per bonus task by default
GIVING_RATE        = 0.10   # default share of earnings routed to the giving pot


def load_settings():
    """Parent-tunable settings, with sensible defaults."""
    s = {'giving_rate': GIVING_RATE}
    try:
        with open(SETTINGS_FILE, encoding='utf-8') as f:
            s.update(json.load(f))
    except (FileNotFoundError, ValueError):
        pass
    return s


def save_settings(updates):
    s = load_settings()
    s.update(updates)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(s, f, indent=2)
    return s


def giving_rate():
    """Current giving rate as a fraction in [0, 1]."""
    try:
        r = float(load_settings().get('giving_rate', GIVING_RATE))
    except (TypeError, ValueError):
        r = GIVING_RATE
    return min(max(r, 0.0), 1.0)


def _parse_value(raw, etype):
    """Dollar value for an event row. Events earn nothing; tasks default to
    DEFAULT_TASK_VALUE when the Value cell is blank or unparseable."""
    if etype != 'task':
        return 0
    raw = (raw or '').strip().lstrip('$')
    try:
        return float(raw) if raw else DEFAULT_TASK_VALUE
    except ValueError:
        return DEFAULT_TASK_VALUE


def load_charities():
    path = CHARITIES_FILE if os.path.exists(CHARITIES_FILE) else CHARITIES_SEED_FILE
    rows = []
    try:
        with open(path, newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                if row.get('Charity', '').strip():
                    try:
                        amount = float(row.get('Amount') or 0)
                    except ValueError:
                        amount = 0.0
                    rows.append({
                        'month':   row['Month'].strip(),
                        'year':    int(row['Year'].strip() or 0),
                        'charity': row['Charity'].strip(),
                        'cause':   row.get('Cause', '').strip(),
                        'status':  row.get('Status', 'planned').strip(),
                        'notes':   row.get('Notes', '').strip(),
                        'amount':  amount,
                    })
    except FileNotFoundError:
        pass
    return rows


def save_charities(entries):
    with open(CHARITIES_FILE, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['Month','Year','Charity','Cause','Status','Notes','Amount'])
        w.writeheader()
        for e in entries:
            try:
                amount = float(e.get('amount') or 0)
            except (TypeError, ValueError):
                amount = 0.0
            w.writerow({'Month': e.get('month',''), 'Year': e.get('year',''),
                        'Charity': e.get('charity',''), 'Cause': e.get('cause',''),
                        'Status': e.get('status','planned'), 'Notes': e.get('notes',''),
                        'Amount': ('%g' % amount) if amount else ''})


def due_today(when, today):
    """Return True if a 'When' spec is due on `today` (a date).

    Recurring: daily | weekdays | weekends | monthly:N | a weekday list
    like "Mon,Wed,Fri". One-off: an ISO date like "2026-06-25".
    """
    w = (when or '').strip()
    if not w:
        return False
    wl = w.lower()
    if wl == 'daily':
        return True
    if wl == 'weekdays':
        return today.weekday() < 5
    if wl == 'weekends':
        return today.weekday() >= 5
    if wl.startswith('monthly:'):
        try:
            return today.day == int(wl.split(':', 1)[1])
        except ValueError:
            return False
    parts = [p.strip()[:3].lower() for p in w.split(',') if p.strip()]
    if parts and all(p in _WEEKDAY_ABBR for p in parts):
        return today.weekday() in {_WEEKDAY_ABBR[p] for p in parts}
    try:
        return date.fromisoformat(w) == today
    except ValueError:
        return False


def load_events():
    path = EVENTS_FILE if os.path.exists(EVENTS_FILE) else EVENTS_SEED_FILE
    rows = []
    try:
        with open(path, newline='', encoding='utf-8-sig') as f:
            for i, row in enumerate(csv.DictReader(f)):
                title = row.get('Title', '').strip()
                if title:
                    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-') or 'item'
                    etype = (row.get('Type', 'event').strip() or 'event').lower()
                    rows.append({
                        'key':    f'{slug}-{i}',
                        'title':  title,
                        'icon':   row.get('Icon', '').strip(),
                        'when':   row.get('When', '').strip(),
                        'time':   row.get('Time', '').strip(),
                        'type':   etype,
                        'value':  _parse_value(row.get('Value', ''), etype),
                        'banner': row.get('Banner', '').strip(),
                    })
    except FileNotFoundError:
        pass
    return rows


def events_due_today(today=None):
    today = today or date.today()
    return [e for e in load_events() if due_today(e['when'], today)]


def save_events(events):
    with open(EVENTS_FILE, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['Title', 'Icon', 'When', 'Time', 'Type', 'Value', 'Banner'])
        w.writeheader()
        for e in events:
            title = (e.get('title') or '').strip()
            if not title:
                continue
            etype = (e.get('type') or 'event').lower()
            value = _parse_value(e.get('value', ''), etype)
            w.writerow({
                'Title':  title,
                'Icon':   e.get('icon', ''),
                'When':   e.get('when', ''),
                'Time':   e.get('time', ''),
                'Type':   etype,
                'Value':  ('%g' % value) if etype == 'task' else '',
                'Banner': e.get('banner', ''),
            })


def archive_past_events(today=None):
    """Drop one-off (ISO-date) events whose date is in the past. Recurring
    events are always kept. Returns True if the file was rewritten."""
    today = today or date.today()
    kept, changed = [], False
    for e in load_events():
        try:
            d = date.fromisoformat(e['when'].strip())
        except ValueError:
            kept.append(e)          # recurring spec → keep
            continue
        if d < today:
            changed = True          # past one-off → archive (drop)
        else:
            kept.append(e)
    if changed:
        save_events(kept)
    return changed


def load_earnings():
    try:
        with open(LEDGER_FILE, newline='', encoding='utf-8-sig') as f:
            return list(csv.DictReader(f))
    except FileNotFoundError:
        return []


def set_earning(entry_date, key, title, amount, earned):
    """Upsert (earned=True) or remove (earned=False) one (date, key) row.
    Same-day reversible: unchecking a task pulls the money back out."""
    rows = [r for r in load_earnings()
            if not (r.get('Date') == entry_date and r.get('Key') == key)]
    if earned:
        try:
            amt = float(amount)
        except (TypeError, ValueError):
            amt = 0.0
        rows.append({'Date': entry_date, 'Key': key, 'Title': title, 'Amount': '%g' % amt})
    rows.sort(key=lambda r: r.get('Date', ''))
    with open(LEDGER_FILE, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['Date', 'Key', 'Title', 'Amount'])
        w.writeheader()
        w.writerows(rows)


def compute_bank():
    total = 0.0
    for r in load_earnings():
        try:
            total += float(r.get('Amount', 0))
        except ValueError:
            continue
    total = round(total, 2)
    given = round(total * giving_rate(), 2)
    spendable = round(total - given, 2)
    paid = total_paid_out()
    return {
        'earned': total,            # lifetime earned (drives milestones/stats)
        'given': given,             # lifetime giving-pot cut
        'spendable': spendable,     # lifetime spendable (earned - giving)
        'paid_out': paid,           # total cash already handed over
        'balance': round(spendable - paid, 2),   # what's still owed to Violet now
    }


def load_payouts():
    try:
        with open(PAYOUTS_FILE, newline='', encoding='utf-8-sig') as f:
            return list(csv.DictReader(f))
    except FileNotFoundError:
        return []


def total_paid_out():
    total = 0.0
    for r in load_payouts():
        try:
            total += float(r.get('Amount', 0))
        except (TypeError, ValueError):
            continue
    return round(total, 2)


def add_payout(amount, note=''):
    """Append a cash payout. Returns the recorded row, or None if amount <= 0."""
    try:
        amt = round(float(amount), 2)
    except (TypeError, ValueError):
        return None
    if amt <= 0:
        return None
    rows = load_payouts()
    row = {'Date': _now_local().date().isoformat(), 'Amount': '%g' % amt, 'Note': note or ''}
    rows.append(row)
    with open(PAYOUTS_FILE, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['Date', 'Amount', 'Note'])
        w.writeheader()
        w.writerows(rows)
    return row


def undo_last_payout():
    """Remove the most recent payout (for corrections). Returns True if removed."""
    rows = load_payouts()
    if not rows:
        return False
    rows = rows[:-1]
    with open(PAYOUTS_FILE, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['Date', 'Amount', 'Note'])
        w.writeheader()
        w.writerows(rows)
    return True


def load_money_milestones():
    """Money reward thresholds: {amount_str: {message, category}}."""
    path = MONEY_MS_FILE if os.path.exists(MONEY_MS_FILE) else MONEY_MS_SEED_FILE
    out = {}
    for row in scan_csv(path, 'Amount'):
        amount   = row.get('Amount', '').strip()
        message  = (row.get('Reward Message') or row.get('Message', '')).strip()
        category = (row.get('Category') or '').strip()
        if amount and message:
            out[amount] = {'message': message, 'category': category}
    return out


def save_money_milestones(items):
    """Write money milestones back to CSV, sorted by amount."""
    def amt(x):
        try:
            return float(x.get('amount', 0) or 0)
        except (TypeError, ValueError):
            return 0.0
    with open(MONEY_MS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Violet Money Milestones'])
        writer.writerow(['Amount', 'Reward Message', 'Category'])
        for item in sorted(items, key=amt):
            writer.writerow([('%g' % amt(item)), item.get('message', ''), item.get('category', '')])


def next_money_milestone(earned):
    """(next_amount, info) tuple above `earned`, and the previous threshold."""
    ms = sorted(((float(k), v) for k, v in load_money_milestones().items()),
                key=lambda x: x[0])
    nxt = next(((a, v) for a, v in ms if a > earned), None)
    prev = max((a for a, v in ms if a <= earned), default=0.0)
    return nxt, prev


# ── Toonie tasks (weekly-planned $2 earners, unlocked per routine window) ──
def load_toonies():
    """Per-window toonie-task config. Prefer the volume copy, fall back to seed."""
    for path in (TOONIES_FILE, TOONIES_SEED_FILE):
        if os.path.isfile(path):
            try:
                with open(path, encoding='utf-8') as f:
                    return json.load(f)
            except (OSError, ValueError):
                break
    return {'timezone': DEFAULT_TZ, 'windows': {}, 'tasks': {}}


def save_toonies(data):
    with open(TOONIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _fmt_clock(hhmm):
    """'06:00' → '6:00 AM', '15:30' → '3:30 PM'. Returns (label, meridiem)."""
    try:
        h, m = (int(x) for x in hhmm.split(':'))
    except (ValueError, AttributeError):
        return '', ''
    mer = 'AM' if h < 12 else 'PM'
    h12 = h % 12 or 12
    return f'{h12}:{m:02d} {mer}', mer


def window_time_label(win):
    """Human range for a window dict, e.g. {'start':'06:00','end':'09:00'} →
    '6:00–9:00 AM'. Drops the repeated meridiem when start and end share one."""
    start, smer = _fmt_clock((win or {}).get('start', ''))
    end,   emer = _fmt_clock((win or {}).get('end', ''))
    if not start or not end:
        return ''
    if smer == emer:
        return f"{start.rsplit(' ', 1)[0]}–{end}"   # '6:00–9:00 AM'
    return f"{start}–{end}"                           # '11:00 AM–1:00 PM'


def _now_local(cfg=None):
    """Current time in the configured timezone (falls back to naive local)."""
    tz_name = (cfg or load_toonies()).get('timezone') or DEFAULT_TZ
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        return datetime.now()


# ── Family calendar (read-only iCloud/iCal feed) ─────────────────────────
FAMILY_CAL_TTL = 1800   # seconds between feed refreshes
FAMILY_CAL_DAYS = 21    # how far ahead to expand recurring events
_family_cal = {'fetched': 0.0, 'events': [], 'error': None, 'url': None}


def family_calendar_url():
    """The subscribed feed URL — settings (set in Admin) override the env var."""
    return (load_settings().get('family_calendar_url')
            or os.environ.get('FAMILY_CALENDAR_URL', '')).strip()


def _local_tz():
    try:
        return ZoneInfo(load_toonies().get('timezone') or DEFAULT_TZ)
    except Exception:
        return ZoneInfo('UTC')


def refresh_family_calendar(force=False):
    """Fetch + parse the iCloud feed into the cache, respecting the TTL."""
    url = family_calendar_url()
    now = time.time()
    if not url:
        _family_cal.update(events=[], error=None, url=None, fetched=now)
        return
    if (not force and _family_cal['url'] == url
            and now - _family_cal['fetched'] < FAMILY_CAL_TTL):
        return
    try:
        import icalendar
        import recurring_ical_events
        fetch_url = url.replace('webcal://', 'https://', 1) if url.startswith('webcal://') else url
        req = urllib.request.Request(fetch_url, headers={'User-Agent': 'VioletApp/1.0'})
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read()
        cal = icalendar.Calendar.from_ical(raw)
        tz = _local_tz()
        today = _now_local().date()
        occ = recurring_ical_events.of(cal).between(today, today + timedelta(days=FAMILY_CAL_DAYS))
        events = []
        for e in occ:
            start = e.decoded('DTSTART')
            title = str(e.get('SUMMARY', '') or '').strip() or 'Event'
            location = str(e.get('LOCATION', '') or '').strip()
            if isinstance(start, datetime):
                sl = start.astimezone(tz) if start.tzinfo else start.replace(tzinfo=tz)
                d, all_day = sl.date(), False
                time_label = sl.strftime('%-I:%M %p')
                sort_t = sl.strftime('%H:%M')
            else:
                d, all_day, time_label, sort_t = start, True, 'All day', ''
            events.append({
                'title': title, 'location': location, 'all_day': all_day,
                'date': d.isoformat(), 'time_label': time_label,
                'day_label': d.strftime('%a, %b %-d'), 'sort': (d.isoformat(), sort_t),
            })
        events.sort(key=lambda x: x['sort'])
        _family_cal.update(events=events, error=None, url=url, fetched=now)
    except Exception as ex:
        _family_cal.update(error=str(ex), url=url, fetched=now)


def family_events_today():
    refresh_family_calendar()
    iso = _now_local().date().isoformat()
    return [e for e in _family_cal['events'] if e['date'] == iso]


def family_events_upcoming(days=14):
    refresh_family_calendar()
    today = _now_local().date()
    end = (today + timedelta(days=days)).isoformat()
    return [e for e in _family_cal['events'] if today.isoformat() <= e['date'] <= end]


def current_window(cfg=None):
    """Window id (am/af/pm) whose [start, end) clock range contains 'now', else None."""
    cfg = cfg or load_toonies()
    now = _now_local(cfg)
    mins = now.hour * 60 + now.minute
    for wid, w in cfg.get('windows', {}).items():
        try:
            sh, sm = (int(x) for x in w['start'].split(':'))
            eh, em = (int(x) for x in w['end'].split(':'))
        except (ValueError, KeyError, AttributeError):
            continue
        if sh * 60 + sm <= mins < eh * 60 + em:
            return wid
    return None


def routine_complete_today(routine_id, today=None):
    """True if today's log shows the given routine fully completed."""
    today = today or _now_local().date().isoformat()
    for r in load_log():
        if r.get('Date') == today and r.get('Routine') == routine_id:
            try:
                return int(r['Total']) > 0 and int(r['Completed']) == int(r['Total'])
            except (ValueError, KeyError):
                return False
    return False


def toonies_earned_today(today=None):
    """Ledger keys of toonie tasks already earned today (one per window+task)."""
    today = today or _now_local().date().isoformat()
    return [r.get('Key') for r in load_earnings()
            if r.get('Date') == today and (r.get('Key') or '').startswith('toonie:')]


# ── Surprise rewards (parent-loaded, hidden from Violet until they trigger) ──
def load_surprises():
    try:
        with open(SURPRISES_FILE, encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_surprises(items):
    with open(SURPRISES_FILE, 'w', encoding='utf-8') as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


def surprise_ready(s, today):
    """Ready to reveal: not yet delivered and its trigger condition is met.
    'now' fires when the parent flips it active; 'date' fires on/after its date."""
    if s.get('delivered'):
        return False
    trig = s.get('trigger', 'now')
    if trig == 'now':
        return bool(s.get('active'))
    if trig == 'date':
        d = (s.get('date') or '').strip()
        return bool(d) and today >= d
    return False


def pending_surprises(today=None):
    today = today or _now_local().date().isoformat()
    return [s for s in load_surprises() if surprise_ready(s, today)]


def notify_ready_surprises():
    """Push-notify any surprise that just became ready (once each)."""
    today = _now_local().date().isoformat()
    items = load_surprises()
    changed = False
    for s in items:
        if not s.get('notified') and surprise_ready(s, today):
            try:
                _push_to_all('🎁 A surprise is waiting!',
                             f"{s.get('icon', '🎁')} Open your app to see it, Violet! 💜")
            except Exception as exc:
                print(f'[push] surprise notify error: {exc}')
            s['notified'] = True
            changed = True
    if changed:
        save_surprises(items)


def get_vapid_keys():
    env_priv = os.environ.get('VAPID_PRIVATE_KEY')
    env_pub  = os.environ.get('VAPID_PUBLIC_KEY')
    if env_priv and env_pub:
        return {'private': env_priv.replace('\\n', '\n'), 'public': env_pub}
    if os.path.exists(VAPID_FILE):
        with open(VAPID_FILE) as f:
            return json.load(f)
    from py_vapid import Vapid
    import base64
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    vapid = Vapid()
    vapid.generate_keys()
    private_pem = vapid.private_pem().decode()
    pub_bytes = vapid._private_key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    pub_b64 = base64.urlsafe_b64encode(pub_bytes).rstrip(b'=').decode()
    keys = {'private': private_pem, 'public': pub_b64}
    with open(VAPID_FILE, 'w') as f:
        json.dump(keys, f)
    return keys


def load_push_subs():
    try:
        with open(PUSH_SUBS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_push_subs(subs):
    with open(PUSH_SUBS_FILE, 'w') as f:
        json.dump(subs, f, indent=2)


def _parse_time_hm(time_str):
    m = re.match(r'(\d{1,2}):(\d{2})\s*(AM|PM)', (time_str or '').strip(), re.IGNORECASE)
    if not m:
        return None, None
    h, mn, period = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    if period == 'PM' and h != 12:
        h += 12
    if period == 'AM' and h == 12:
        h = 0
    return h, mn


def _routine_for_time(time_str):
    """Which routine's part of the day a clock time falls in (am/af/pm), or
    None when there's no parseable time. Mirrors the client's time-of-day split."""
    h, _ = _parse_time_hm(time_str)
    if h is None:
        return None
    if h < 12:
        return 'am'
    if h < 18:
        return 'af'
    return 'pm'


def bucket_extras(extras):
    """Group today's extras by routine (am/af/pm) sorted by time, plus an
    'anytime' list for untimed ones, so they flow into the day as a schedule."""
    buckets = {'am': [], 'af': [], 'pm': []}
    anytime = []
    for e in extras:
        rid = _routine_for_time(e.get('time'))
        (buckets[rid] if rid else anytime).append(e)
    for rid in buckets:
        buckets[rid].sort(key=lambda e: _parse_time_hm(e.get('time')) or (0, 0))
    return buckets, anytime


_ROUTINE_MESSAGES = {
    'am': ('Morning Routine ☁️', "Hey Violet! Time for your morning routine. You've got this 💜"),
    'af': ('Afternoon Routine 🌸', "Afternoon check-in! Keep the momentum going, Violet 💜"),
    'pm': ('Evening Routine 🌙', "Almost done for the day! Time for your evening routine 💜"),
}


def _push_to_all(title, body, url='/routines'):
    from pywebpush import webpush, WebPushException
    payload = json.dumps({
        'title': title, 'body': body,
        'icon': '/icon.svg', 'badge': '/icon.svg',
        'data': {'url': url},
    })
    vapid = get_vapid_keys()
    subs = load_push_subs()
    dead = []
    for sub in subs:
        try:
            webpush(
                subscription_info={'endpoint': sub['endpoint'], 'keys': sub['keys']},
                data=payload,
                vapid_private_key=vapid['private'],
                vapid_claims=VAPID_CLAIMS,
            )
        except WebPushException as ex:
            if ex.response and ex.response.status_code in (404, 410):
                dead.append(sub['endpoint'])
            else:
                print(f'[push] send error: {ex}')
    if dead:
        save_push_subs([s for s in subs if s['endpoint'] not in dead])


def _send_push_for_routine(routine):
    rid = routine['id']
    title, body = _ROUTINE_MESSAGES.get(
        rid, (f"{routine.get('name', 'Routine')} time!", "Time for your routine, Violet! 💜")
    )
    _push_to_all(title, body)


def _send_push_for_event(e):
    icon = e.get('icon', '')
    title = f"{icon} {e['title']}".strip()
    if e.get('type') == 'task':
        body = "Don't forget — check it off when it's done! 💜"
    else:
        body = "Heads up — that's happening today! 💜"
    _push_to_all(title, body)


_last_archive_date = None


def _check_and_notify():
    global _last_archive_date
    try:
        subs = load_push_subs()
        tz_name = subs[0].get('timezone', 'America/Toronto') if subs else 'America/Toronto'
        now = datetime.now(ZoneInfo(tz_name))
        if _last_archive_date != now.date():
            _last_archive_date = now.date()
            archive_past_events(now.date())
        if not subs:
            return
        today_key = now.strftime('%Y-%m-%d')
        for r in load_tasks_raw():
            rh, rm = _parse_time_hm(r.get('time', ''))
            if rh is None:
                continue
            if now.hour == rh and now.minute == rm:
                key = f"{r['id']}:{today_key}"
                if key not in _already_notified:
                    _already_notified[key] = True
                    _send_push_for_routine(r)
        for e in events_due_today(now.date()):
            eh, em = _parse_time_hm(e.get('time', ''))
            if eh is None:
                continue
            if now.hour == eh and now.minute == em:
                key = f"event:{e['key']}:{today_key}"
                if key not in _already_notified:
                    _already_notified[key] = True
                    _send_push_for_event(e)
        notify_ready_surprises()   # date-based surprises that became ready
    except Exception as exc:
        print(f'[push] check_and_notify error: {exc}')


_scheduler = BackgroundScheduler()
_scheduler.add_job(_check_and_notify, IntervalTrigger(minutes=1), id='notify_check')
_scheduler.start()
atexit.register(lambda: _scheduler.shutdown(wait=False))


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
    rows = scan_csv(_data_or_seed(TASKS_FILE, TASKS_SEED_FILE), 'Routine')
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
            tags_raw = row.get('Tags', '').strip()
            tags = [tg.strip() for tg in tags_raw.split(',') if tg.strip()] if tags_raw else []
            t = {'label': label, 'subtasks': [], 'tags': tags}
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
    rows = scan_csv(_data_or_seed(MILESTONES_FILE, MILESTONES_SEED_FILE), 'Streak')
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


def completed_dates(log_rows):
    """ISO dates (sorted) on which at least one routine was fully completed.
    Used to seed/reconcile the client's cumulative 'days completed' list so it
    survives device changes and migrates users from the old streak data."""
    dates = set()
    for row in log_rows:
        if row.get('Routine') == 'extra':
            continue
        try:
            if int(row['Total']) and int(row['Completed']) == int(row['Total']):
                dates.add(row['Date'])
        except (ValueError, KeyError):
            continue
    return sorted(dates)


def compute_stats(log_rows):
    today = date.today()
    # 'extra' rows (recurring/one-off events) are logged separately and must
    # not affect the am/af/pm streak, calendar, or overall stats.
    log_rows = [r for r in log_rows if r.get('Routine') != 'extra']
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

    # Days completed — cumulative count of distinct days where Violet finished
    # at least one routine. Unlike a streak, this never resets: missing a day
    # just means you don't add to it, you never lose what you've earned.
    completed_days = {e['date'] for e in entries
                      if e['total'] and e['completed'] == e['total']}
    days_completed = len(completed_days)

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
        'days_completed': days_completed,
        'week':        week,
        'cal_days':    cal_days,
        'month_label': today.strftime('%B %Y'),
        'routine_pct': routine_pct,
        'total_days':  len(by_date),
        'overall_pct': round(total_c / total_t * 100) if total_t else 0,
    }


def load_levelup_data():
    data = None
    for path in (LEVELUP_DATA_FILE, LEVELUP_SEED_FILE):
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            break
    if data is None:
        return {'levelup_categories': []}
    # Reconcile the volume copy against the shipped seed (only relevant when a
    # customised copy lives on a separate volume).
    if LEVELUP_DATA_FILE != LEVELUP_SEED_FILE and os.path.isfile(LEVELUP_SEED_FILE):
        try:
            with open(LEVELUP_SEED_FILE, encoding='utf-8') as f:
                seed = json.load(f)
        except (OSError, ValueError):
            seed = None
        if seed is not None:
            if seed.get('categories_version', 0) > data.get('categories_version', 0):
                # A new category set shipped — replace the saved copy wholesale,
                # once, and remember the version so this never re-runs (and so it
                # won't clobber the parent's later Admin edits at the same version).
                data['levelup_categories'] = seed.get('levelup_categories', [])
                data['categories_version'] = seed.get('categories_version', 0)
                try:
                    save_levelup_data(data)
                except OSError:
                    pass
            else:
                # Same version: just add any seed categories the saved copy is
                # missing (matched by id). Existing categories are left untouched.
                existing_ids = {c.get('id') for c in data.get('levelup_categories', [])}
                for cat in seed.get('levelup_categories', []):
                    if cat.get('id') not in existing_ids:
                        data.setdefault('levelup_categories', []).append(cat)
    return data


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
    resp = send_from_directory(_BASE, 'sw.js', mimetype='application/javascript')
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


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


@app.route('/earn', methods=['POST'])
def earn():
    d = request.get_json()
    before = compute_bank()['earned']
    set_earning(d['date'], d['key'], d.get('title', ''), d.get('amount', 0), bool(d.get('earned')))
    bank_after = compute_bank()
    # Did this earning newly cross a money milestone? (only on the way up)
    hit = None
    if bank_after['earned'] > before:
        for k, v in load_money_milestones().items():
            try:
                amt = float(k)
            except ValueError:
                continue
            if before < amt <= bank_after['earned']:
                if hit is None or amt < hit['amount']:
                    hit = {'amount': amt, 'message': v['message'], 'category': v.get('category', '')}
    resp = dict(bank_after)
    resp['milestone'] = hit
    return jsonify(resp)


@app.route('/earn-toonie', methods=['POST'])
def earn_toonie():
    """Earn (or same-window reverse) one toonie task. Strictly gated server-side:
    must be inside the task's window AND that window's routine done today."""
    d = request.get_json() or {}
    task_id = d.get('task_id')
    want    = bool(d.get('earned', True))
    cfg = load_toonies()
    win = current_window(cfg)
    if not win:
        return jsonify({'ok': False, 'reason': 'closed'})
    task = next((t for t in cfg.get('tasks', {}).get(win, []) if t.get('id') == task_id), None)
    if not task:
        return jsonify({'ok': False, 'reason': 'unknown'})
    if want and not routine_complete_today(win):
        return jsonify({'ok': False, 'reason': 'routine'})
    today  = _now_local(cfg).date().isoformat()
    key    = 'toonie:%s:%s' % (win, task_id)
    before = compute_bank()['earned']
    set_earning(today, key, task.get('label', 'Toonie task'),
                task.get('value', DEFAULT_TASK_VALUE), want)
    bank_after = compute_bank()
    hit = None
    if bank_after['earned'] > before:
        for k, v in load_money_milestones().items():
            try:
                amt = float(k)
            except ValueError:
                continue
            if before < amt <= bank_after['earned']:
                if hit is None or amt < hit['amount']:
                    hit = {'amount': amt, 'message': v['message'], 'category': v.get('category', '')}
    resp = dict(bank_after)
    resp.update({'ok': True, 'key': key, 'window': win, 'milestone': hit})
    return jsonify(resp)


@app.route('/surprises/delivered', methods=['POST'])
def surprise_delivered():
    """Mark a surprise as seen by Violet so it only reveals once."""
    sid = (request.get_json() or {}).get('id')
    items = load_surprises()
    changed = False
    for s in items:
        if s.get('id') == sid and not s.get('delivered'):
            s['delivered'] = True
            s['delivered_at'] = _now_local().date().isoformat()
            changed = True
    if changed:
        save_surprises(items)
    return jsonify({'ok': True})


@app.route('/bank')
def bank():
    b = compute_bank()
    recent = list(reversed(load_earnings()))[:20]
    nxt, prev = next_money_milestone(b['earned'])
    money_ms = sorted(((float(k), v) for k, v in load_money_milestones().items()),
                      key=lambda x: x[0])
    return render_template('bank.html', bank=b, recent=recent,
                           giving_pct=int(round(giving_rate() * 100)),
                           next_ms=nxt, prev_amt=prev, money_ms=money_ms)


@app.route('/routines')
def index():
    routines   = load_routines()
    phrases    = load_phrases()
    milestones = load_milestones()
    # Show each routine's real window range as its time copy (single source of
    # truth = the toonie window config), falling back to the CSV's Time value.
    _windows = load_toonies().get('windows', {})
    for r in routines:
        label = window_time_label(_windows.get(r['id']))
        if label:
            r['time'] = label
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
    extras = events_due_today()
    extras_by_routine, extras_anytime = bucket_extras(extras)
    toonie_cfg = load_toonies()
    return render_template(
        'index.html',
        routines=routines,
        extras=extras,
        extras_by_routine=extras_by_routine,
        extras_anytime=extras_anytime,
        extras_tasks_json=json.dumps(
            [{'key': e['key'], 'value': e['value'], 'title': e['title']}
             for e in extras if e['type'] == 'task']),
        phrases_json=json.dumps(phrases),
        routines_json=json.dumps(routines_cfg),
        milestones_json=json.dumps(milestones),
        images_json=json.dumps(list_images()),
        cel_routines_json=json.dumps(cel_routines),
        cel_milestones_json=json.dumps(cel_milestones),
        levelup_categories_json=json.dumps(levelup_data.get('levelup_categories', [])),
        badges_json=json.dumps(BADGES),
        completed_dates_json=json.dumps(completed_dates(load_log())),
        toonie_config_json=json.dumps(toonie_cfg),
        toonie_earned_json=json.dumps(toonies_earned_today()),
        surprises_json=json.dumps(pending_surprises()),
        progress_json=json.dumps(load_progress(current_profile())),
        profile_name=PROFILES[current_profile()]['name'],
        levelup_total=len(load_levelup_log()),
        family_today=family_events_today(),
    )


@app.route('/')
def landing():
    return render_template('landing.html',
                           progress_json=json.dumps(load_progress(current_profile())))


@app.route('/welcome')
def welcome():
    return render_template('welcome.html')


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


def save_milestones(items):
    """Write milestones list back to Violet Milestones.csv."""
    with open(MILESTONES_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Violet Milestones'])
        writer.writerow(['Streak', 'Reward Message', 'Category'])
        for item in sorted(items, key=lambda x: int(x.get('streak', 0) or 0)):
            writer.writerow([item['streak'], item['message'], item.get('category', '')])


@app.route('/api/progress')
def api_progress_get():
    """Synced kid progress for the active profile."""
    return jsonify(load_progress(current_profile()))


@app.route('/api/progress', methods=['POST'])
def api_progress_set():
    """Persist a single progress key for the active profile."""
    data = request.get_json(silent=True) or {}
    key = data.get('key')
    if key not in PROGRESS_KEYS:
        return jsonify({'error': 'unknown key'}), 400
    save_progress_key(current_profile(), key, data.get('value'))
    return '', 204


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    nxt = request.args.get('next') or request.form.get('next') or '/admin'
    if not nxt.startswith('/admin'):
        nxt = '/admin'
    if request.method == 'POST':
        if request.form.get('pin', '').strip() == admin_pin():
            session['admin'] = True
            session.permanent = True
            return redirect(nxt)
        return render_template('admin_login.html', error=True, next=nxt), 401
    if session.get('admin'):
        return redirect(nxt)
    return render_template('admin_login.html', error=False, next=nxt)


@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('admin', None)
    return redirect('/')


@app.route('/admin/pin/save', methods=['POST'])
def admin_pin_save():
    new_pin = (request.get_json(silent=True) or {}).get('pin', '').strip()
    if not (4 <= len(new_pin) <= 64):
        return jsonify({'error': 'PIN must be 4–64 characters'}), 400
    save_settings({'admin_pin': new_pin})
    return '', 204


@app.route('/admin')
def admin():
    data      = load_levelup_data()
    routines  = load_tasks_raw()
    ms_dict   = load_milestones()
    milestones = [
        {'streak': k, 'message': v['message'], 'category': v.get('category', '')}
        for k, v in sorted(ms_dict.items(), key=lambda x: int(x[0]))
    ]
    money_ms = [
        {'amount': k, 'message': v['message'], 'category': v.get('category', '')}
        for k, v in sorted(load_money_milestones().items(), key=lambda x: float(x[0]))
    ]
    return render_template(
        'admin.html',
        data=data,
        routines_json=json.dumps(routines),
        milestones_json=json.dumps(milestones),
        money_milestones_json=json.dumps(money_ms),
        giving_pct=int(round(giving_rate() * 100)),
    )


@app.route('/admin/milestones/save', methods=['POST'])
def admin_milestones_save():
    items = request.get_json()
    save_milestones(items)
    return jsonify({'ok': True})


@app.route('/admin/money/save', methods=['POST'])
def admin_money_save():
    """Save the giving % and money-milestone rewards together."""
    payload = request.get_json() or {}
    if 'giving_pct' in payload:
        try:
            pct = float(payload['giving_pct'])
        except (TypeError, ValueError):
            pct = GIVING_RATE * 100
        save_settings({'giving_rate': min(max(pct, 0.0), 100.0) / 100.0})
    save_money_milestones(payload.get('milestones', []))
    return jsonify({'ok': True, 'giving_pct': int(round(giving_rate() * 100))})


@app.route('/admin/save', methods=['POST'])
def admin_save():
    data = request.get_json()
    save_levelup_data(data)
    return jsonify({'ok': True})


def load_tasks_raw():
    """Return routines as ordered list with metadata + task list (each task is {label, tags, subtasks})."""
    rows = scan_csv(_data_or_seed(TASKS_FILE, TASKS_SEED_FILE), 'Routine')
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
                '_map':   {},
            }
            order.append(rid)
        task_label = row.get('Task', '').strip()
        parent     = row.get('Parent', '').strip()
        if not task_label:
            continue
        tags_raw = row.get('Tags', '').strip()
        tags = [t.strip() for t in tags_raw.split(',') if t.strip()] if tags_raw else []
        r = seen[rid]
        if parent and parent in r['_map']:
            r['_map'][parent]['subtasks'].append({'label': task_label})
        else:
            task = {'label': task_label, 'tags': tags, 'subtasks': []}
            r['tasks'].append(task)
            r['_map'][task_label] = task
    result = []
    for rid in order:
        r = seen[rid]
        del r['_map']
        result.append(r)
    return result


def save_tasks_raw(routines):
    """Write routines list back to Violet Tasks.csv."""
    with open(TASKS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Violet Tasks'])
        writer.writerow(['Violet Tasks', '', '', '', '', '', '', ''])
        writer.writerow(['Routine', 'ID', 'Icon', 'Time', 'Banner', 'Task', 'Tags', 'Parent'])
        for r in routines:
            for task in r['tasks']:
                if isinstance(task, dict):
                    label    = task.get('label', '')
                    tags     = ','.join(task.get('tags', []))
                    subtasks = task.get('subtasks', [])
                else:
                    label    = str(task)
                    tags     = ''
                    subtasks = []
                writer.writerow([r['name'], r['id'], r['icon'], r['time'], r['banner'], label, tags, ''])
                for sub in subtasks:
                    sub_label = sub.get('label', '') if isinstance(sub, dict) else str(sub)
                    writer.writerow([r['name'], r['id'], r['icon'], r['time'], r['banner'], sub_label, '', label])


def compute_tag_breakdown(routines_raw):
    """Return {tag: count} sorted by count desc from tasks with tags."""
    counts = {}
    for r in routines_raw:
        for t in r['tasks']:
            for tag in (t.get('tags') or []):
                counts[tag] = counts.get(tag, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


@app.route('/admin/tasks')
def admin_tasks():
    routines = load_tasks_raw()
    return render_template('admin_tasks.html', routines_json=json.dumps(routines))


@app.route('/admin/tasks/save', methods=['POST'])
def admin_tasks_save():
    routines = request.get_json()
    save_tasks_raw(routines)
    return jsonify({'ok': True})


@app.route('/admin/routines/meta', methods=['POST'])
def admin_routines_meta_save():
    """Update only a routine's settings (name/icon/time). Tasks, tags and
    sub-tasks are loaded fresh and preserved, so saving routine settings from
    the Admin tab never clobbers task edits made on the Tasks page."""
    meta = {m.get('id'): m for m in (request.get_json() or []) if m.get('id')}
    routines = load_tasks_raw()
    for r in routines:
        m = meta.get(r['id'])
        if m:
            r['name'] = m.get('name', r['name'])
            r['icon'] = m.get('icon', r['icon'])
            r['time'] = m.get('time', r['time'])
    save_tasks_raw(routines)
    return jsonify({'ok': True})


@app.route('/admin/events')
def admin_events():
    return render_template('admin_events.html',
                           events_json=json.dumps(load_events()),
                           today_iso=date.today().isoformat())


@app.route('/admin/events/save', methods=['POST'])
def admin_events_save():
    save_events(request.get_json() or [])
    return jsonify({'ok': True})


@app.route('/calendar')
def family_calendar_page():
    """Family Calendar — upcoming events from the subscribed iCloud feed."""
    return render_template(
        'calendar.html',
        events=family_events_upcoming(14),
        configured=bool(family_calendar_url()),
        error=_family_cal.get('error'),
        is_admin=bool(session.get('admin')),
        feed_url=family_calendar_url() if session.get('admin') else '',
    )


@app.route('/admin/calendar/save', methods=['POST'])
def admin_calendar_save():
    """Set/replace the family calendar feed URL (parent-only)."""
    url = (request.get_json(silent=True) or {}).get('url', '').strip()
    save_settings({'family_calendar_url': url})
    refresh_family_calendar(force=True)
    return jsonify({'ok': True, 'error': _family_cal.get('error'),
                    'count': len(_family_cal.get('events', []))})


@app.route('/admin/toonies')
def admin_toonies():
    return render_template('admin_toonies.html',
                           toonies_json=json.dumps(load_toonies()))


@app.route('/admin/toonies/save', methods=['POST'])
def admin_toonies_save():
    data = request.get_json() or {}
    cfg = load_toonies()
    # Preserve window/timezone config; only the weekly task lists are editable here.
    cfg['tasks'] = data.get('tasks', {})
    save_toonies(cfg)
    return jsonify({'ok': True})


@app.route('/admin/surprises')
def admin_surprises():
    return render_template('admin_surprises.html',
                           surprises_json=json.dumps(load_surprises()),
                           today_iso=_now_local().date().isoformat())


@app.route('/admin/surprises/save', methods=['POST'])
def admin_surprises_save():
    incoming = request.get_json() or []
    existing = {s.get('id'): s for s in load_surprises()}
    out = []
    for s in incoming:
        sid = (s.get('id') or '').strip() or 's-' + uuid.uuid4().hex[:10]
        prev = existing.get(sid, {})
        # Server-owned flags survive editing; resetting 'active' off re-arms nothing.
        s['id']       = sid
        s['notified'] = prev.get('notified', False)
        s['delivered'] = prev.get('delivered', False)
        if prev.get('delivered_at'):
            s['delivered_at'] = prev['delivered_at']
        out.append(s)
    save_surprises(out)
    notify_ready_surprises()   # push immediately for any now-active / past-date surprise
    return jsonify({'ok': True})


@app.route('/admin/payout')
def admin_payout():
    return render_template('admin_payout.html',
                           bank=compute_bank(),
                           payouts=list(reversed(load_payouts())),
                           giving_pct=int(round(giving_rate() * 100)))


@app.route('/admin/payout/pay', methods=['POST'])
def admin_payout_pay():
    """Record a cash payout. Defaults to the current balance owed."""
    d = request.get_json() or {}
    bank = compute_bank()
    amount = d.get('amount', bank['balance'])
    note = (d.get('note') or '').strip()
    row = add_payout(amount, note)
    return jsonify({'ok': bool(row), 'row': row, 'bank': compute_bank()})


@app.route('/admin/payout/undo', methods=['POST'])
def admin_payout_undo():
    undone = undo_last_payout()
    return jsonify({'ok': undone, 'bank': compute_bank()})


@app.route('/admin/planning')
def admin_planning():
    """Sunday Planning — the weekly ritual hub: review the week, log Level Up
    wins together, pay out the Bank, then plan next week's Toonie Tasks."""
    today = date.today()
    week_start = (today - timedelta(days=6)).isoformat()
    week_wins = [r for r in reversed(load_levelup_log())
                 if r.get('Date', '') >= week_start]
    week_earned = 0.0
    for r in load_earnings():
        if r.get('Date', '') >= week_start:
            try:
                week_earned += float(r.get('Amount', 0))
            except (TypeError, ValueError):
                continue
    return render_template(
        'planning.html',
        stats=compute_stats(load_log()),
        bank=compute_bank(),
        giving_pct=int(round(giving_rate() * 100)),
        levelup_categories_json=json.dumps(load_levelup_data().get('levelup_categories', [])),
        week_wins=week_wins,
        week_earned=round(week_earned, 2),
        today_iso=today.isoformat(),
    )


BADGES = [
    # ── Days-completed badges (cumulative — never reset) ──
    {'id': 'first-step',   'name': 'First Step',      'desc': 'Complete your first routine',  'emoji': '✨', 'bg': '#ede9fe', 'ring': '#9b87f5', 'type': 'days',  'threshold': 1},
    {'id': 'spark',        'name': 'Getting Going',    'desc': '3 days completed',             'emoji': '🔥', 'bg': '#fef3c7', 'ring': '#f59e0b', 'type': 'days',  'threshold': 3},
    {'id': 'week-warrior', 'name': 'Week of Wins',     'desc': '7 days completed',             'emoji': '⭐', 'bg': '#d1fae5', 'ring': '#10b981', 'type': 'days',  'threshold': 7},
    {'id': 'fortnight',    'name': 'Fortnight Hero',   'desc': '14 days completed',            'emoji': '👑', 'bg': '#dbeafe', 'ring': '#3b82f6', 'type': 'days',  'threshold': 14},
    {'id': '3-week',       'name': '3-Week Wonder',    'desc': '21 days completed',            'emoji': '💜', 'bg': '#ede9fe', 'ring': '#7c3aed', 'type': 'days',  'threshold': 21},
    {'id': 'month',        'name': 'Month Marvel',     'desc': '30 days completed',            'emoji': '🏆', 'bg': '#fce7f3', 'ring': '#ec4899', 'type': 'days',  'threshold': 30},
    {'id': 'diamond',      'name': 'Diamond Legend',   'desc': '60 days completed',            'emoji': '💎', 'bg': '#cffafe', 'ring': '#06b6d4', 'type': 'days',  'threshold': 60},
    # ── Routine badges ──
    {'id': 'morning-5',    'name': 'Morning Magic',    'desc': 'Morning routine ×5',           'emoji': '☁️', 'bg': '#fef9c3', 'ring': '#eab308', 'type': 'routine', 'routine': 'am', 'threshold': 5},
    {'id': 'morning-20',   'name': 'Rise & Shine',     'desc': 'Morning routine ×20',          'emoji': '🌅', 'bg': '#fef9c3', 'ring': '#f59e0b', 'type': 'routine', 'routine': 'am', 'threshold': 20},
    {'id': 'afternoon-5',  'name': 'Afternoon Ace',    'desc': 'Afternoon routine ×5',         'emoji': '🌸', 'bg': '#fce7f3', 'ring': '#ec4899', 'type': 'routine', 'routine': 'af', 'threshold': 5},
    {'id': 'evening-5',    'name': 'Bedtime Boss',     'desc': 'Evening routine ×5',           'emoji': '🖤', 'bg': '#ede9fe', 'ring': '#7c3aed', 'type': 'routine', 'routine': 'pm', 'threshold': 5},
    {'id': 'evening-20',   'name': 'Dream Keeper',     'desc': 'Evening routine ×20',          'emoji': '🌙', 'bg': '#ede9fe', 'ring': '#9b87f5', 'type': 'routine', 'routine': 'pm', 'threshold': 20},
    {'id': 'triple-crown', 'name': 'Triple Crown',     'desc': 'All 3 routines in one day',   'emoji': '👑', 'bg': '#fef3c7', 'ring': '#f59e0b', 'type': 'triple',  'threshold': 1},
    {'id': 'triple-7',     'name': 'Triple Threat',    'desc': 'All 3 routines on 7 days',    'emoji': '🌟', 'bg': '#fef3c7', 'ring': '#f59e0b', 'type': 'triple',  'threshold': 7},
    {'id': 'triple-30',    'name': 'Perfect Day Pro',  'desc': 'All 3 routines on 30 days',   'emoji': '💯', 'bg': '#fce7f3', 'ring': '#ec4899', 'type': 'triple',  'threshold': 30},
    # ── Level Up badges ──
    {'id': 'levelup-1',    'name': 'Level Up!',        'desc': 'Log your first win',           'emoji': '⚡', 'bg': '#ede9fe', 'ring': '#7c3aed', 'type': 'levelup', 'threshold': 1},
    {'id': 'levelup-10',   'name': 'Win Collector',    'desc': '10 level-up wins',             'emoji': '💪', 'bg': '#fce7f3', 'ring': '#db2777', 'type': 'levelup', 'threshold': 10},
    {'id': 'levelup-25',   'name': 'Legend',           'desc': '25 level-up wins',             'emoji': '🌟', 'bg': '#fef3c7', 'ring': '#d97706', 'type': 'levelup', 'threshold': 25},
]


@app.route('/faq')
def faq():
    return render_template('faq.html')


@app.route('/badges')
def badges():
    return render_template('badges.html', badges_json=json.dumps(BADGES),
                           progress_json=json.dumps(load_progress(current_profile())))


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

    # next milestone — based on cumulative days completed
    done = s['days_completed']
    milestones_sorted = sorted(milestones.items(), key=lambda x: int(x[0]))
    next_ms = next(((int(k), v) for k, v in milestones_sorted if int(k) > done), None)
    prev_ms_streak = max((int(k) for k, v in milestones_sorted if int(k) <= done), default=0)

    routines_raw   = load_tasks_raw()
    tag_breakdown  = compute_tag_breakdown(routines_raw)

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
        tag_breakdown=tag_breakdown,
        progress_json=json.dumps(load_progress(current_profile())),
    )


@app.route('/stats')
def stats():
    routines = load_routines()
    routine_names = {r['id']: r['name'] for r in routines}
    s = compute_stats(load_log())
    return render_template('stats.html', stats=s, routine_names=routine_names,
                           routines=routines, today_iso=date.today().isoformat())


@app.route('/push/vapid-public-key')
def push_vapid_public_key():
    keys = get_vapid_keys()
    return jsonify({'key': keys['public']})


@app.route('/push/subscribe', methods=['POST'])
def push_subscribe():
    sub = request.get_json()
    subs = load_push_subs()
    if not any(s['endpoint'] == sub['endpoint'] for s in subs):
        subs.append(sub)
        save_push_subs(subs)
    return jsonify({'ok': True})


@app.route('/push/unsubscribe', methods=['POST'])
def push_unsubscribe():
    data = request.get_json()
    endpoint = data.get('endpoint', '')
    save_push_subs([s for s in load_push_subs() if s['endpoint'] != endpoint])
    return jsonify({'ok': True})


@app.route('/push/test', methods=['POST'])
def push_test():
    from pywebpush import webpush, WebPushException
    payload = json.dumps({
        'title': 'Test Notification ✦',
        'body': "Reminders are working! 💜",
        'icon': '/icon.svg',
        'data': {'url': '/routines'},
    })
    vapid = get_vapid_keys()
    subs = load_push_subs()
    if not subs:
        return jsonify({'ok': False, 'error': 'no subscriptions'})
    sent = 0
    for sub in subs:
        try:
            webpush(
                subscription_info={'endpoint': sub['endpoint'], 'keys': sub['keys']},
                data=payload,
                vapid_private_key=vapid['private'],
                vapid_claims=VAPID_CLAIMS,
            )
            sent += 1
        except WebPushException as ex:
            print(f'[push] test error: {ex}')
    return jsonify({'ok': sent > 0, 'sent': sent})


@app.route('/charities')
def charities():
    return render_template('charities.html',
                           charities_json=json.dumps(load_charities()),
                           bank=compute_bank(),
                           giving_pct=int(round(giving_rate() * 100)))


@app.route('/charities/save', methods=['POST'])
def charities_save():
    save_charities(request.get_json() or [])
    return jsonify({'ok': True})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port)
