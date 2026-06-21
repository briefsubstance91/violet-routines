# Violet's App — How It Works (DRAFT for current version)

> Working draft to get the wording set, then we'll roll it into the right pages
> (the **How It Works / FAQ** page first, plus the little help boxes on Admin
> pages and the Welcome Tour). **[CONFIRM]** tags = decisions for you.

---

## Part 0 — The Strategy & Methodology (the "why")

The app is built around a few core ideas. This is the framing we want every
page to reinforce:

1. **Routines, in their windows.** Three routines a day — Morning, Afternoon,
   Evening — each with a real time window. Doing the routine *in* its window is
   the goal, because that's when it actually helps the day run.
2. **Progress only adds up — it never resets.** "Days completed" is cumulative
   and permanent. A missed day costs nothing; you just pick back up. This is the
   heart of the whole thing: steady building, no punishment.
3. **Toonie tasks = extra earning, on top of routines.** Once a routine is done
   in its window, a shared daily list of 6 chores ($2 each) unlocks. They're a
   bonus, not a requirement.
4. **Weekdays are time-limited; weekends are flexible.** On school days the
   toonie window is tight (stay on the clock). On weekends it stays open until
   the next window, so there's more of the day to earn.
5. **Money has a purpose — including giving.** Earnings split automatically: a
   set percentage goes to a giving pot, the rest is Violet's to bank. Family
   Giving makes the generosity visible.
6. **Weekly rhythm: Sunday Planning.** Once a week the family sits down to look
   back (stats), log the week's Level-Up wins, pay out the bank, and plan next
   week's toonies.
7. **Celebrate everything.** Badges, milestones (days + money), surprises, and
   confetti are all there to make showing up feel good.

**The weekly loop, in one line:** *Do routines in their windows → finish them to
unlock toonie chores → earn money (some to giving, some to bank) → log wins,
cash out, and plan again at Sunday Planning.*

---

## Part 1 — For Violet (kid-facing)

### How do I do a routine?
Tap a routine card — **Morning, Afternoon, or Evening** — to open its checklist.
Tap each task as you finish it (some tasks open up into smaller steps). When
**every** task is checked, the routine celebrates automatically with confetti 🎉
— there's nothing else to press.

- ☁️ **Morning** — 6:00–9:00 AM
- 🌸 **Afternoon** — 3:30–5:00 PM
- 🖤 **Evening** — 5:00–7:00 PM

> **[CONFIRM]** Today the app needs **all** tasks checked for a routine to count.
> Keep it that way, or should a routine count once she's done *most* of it (say a
> threshold)? The current copy promising "you don't have to do every task" is
> wrong and I'll remove it either way.

### What's the "Now" tag and the greeting?
The app gently points you at the right routine for the time of day:
- **Now** — that routine's window is open right now. Jump in!
- **Time to finish…** — the window passed but it's not done yet; you can still
  catch up.
- **Next up…** — the window hasn't opened yet; here's what's coming.

### What are Toonie Tasks? 🪙
A list of **6 chores you can do for $2 each** — an extra way to earn on top of
your routines. They **unlock when you finish that time's routine** (e.g., finish
your Morning routine during the morning to open them up). It's the same list all
day, and ones you've already done stay checked. **Each one can be earned once a
day.**
- **School days:** the list is open only during the routine's window — be quick!
- **Weekends:** once it unlocks it stays open until the next window, so you have
  more time.

### What is Level Up ⚡?
Level Up is where your **wins** get celebrated — anything you did a little better
than before. You log them together each week at **Sunday Planning**, sorted into
categories:
🛁 Self-Care · 🧹 Cleaning & Organization · 🏃 Health & Fitness ·
📚 Education & Learning · 🎯 Goal Setting · 💛 Charity & Giving Back · 🎉 Fun.

### What's my Bank and the giving pot? 🏦
Money you earn from chores adds up in your Bank. A small slice automatically goes
to a **giving pot** to share with others, and the rest is yours to save and cash
out. You'll hit fun **money milestones** along the way.

### How do badges and milestones work?
- **Badges** 🏅 unlock automatically — for days completed, for repeating a
  routine, for "Triple Crown" days (all three in one day), and for logging
  Level-Up wins.
- **Milestones** are real-life rewards your family set for reaching certain
  day-counts (and dollar amounts). Because your day count never resets, you're
  always building toward the next one.

### What if I miss a day?
Nothing is lost — your "days completed" never goes backwards. Just pick up again
whenever you're ready. 💜

### Surprises 🎁
Sometimes a surprise from your family pops up in the app. Tap it to reveal it!

---

## Part 2 — For Parents (setup & management)

Everything below lives behind the **parent PIN** (Admin). **[CONFIRM]** default
PIN is `1234` unless you've changed it — we should set a real one.

### The routines themselves
- **Edit tasks:** Admin → **Edit Routines** (`/admin/tasks`) — task names, icons,
  subtasks, tags, order.
- **Window times** (when each routine/toonie window opens) live with the toonie
  config (`/admin/toonies`). The routine cards display these exact times.

### Toonie tasks (the daily $2 list)
- Edit at **Admin → Toonie Tasks** (`/admin/toonies`): one shared list of tasks,
  each with an icon, label, and $ value (default $2).
- Rules: unlocks when the window's routine is done; **once per task per day**;
  weekday = window-only, weekend = open until the next window.
- **[CONFIRM]** Keep exactly **6** tasks, or is the count flexible?

### Level Up categories
- Edit at **Admin → Level Up** (the main `/admin` page): add/rename categories,
  set icons, and optionally pre-load example "wins."
- Wins themselves are logged with Violet at **Sunday Planning**.
- Current categories: Self-Care, Cleaning & Organization, Health & Fitness,
  Education & Learning, Goal Setting, Charity & Giving Back, Fun. (Currently no
  example wins are pre-loaded — they're typed in at planning. **[CONFIRM]** add
  starter wins?)

### Money, giving & the bank
- **Giving %** and **money milestones**: Admin → main page (money section).
  Earnings auto-split: the giving % goes to the giving pot, the rest to Violet's
  spendable bank. **[CONFIRM]** giving rate is **10%** today — keep it?
- **Pay out** cash at **Sunday Planning** (or `/admin/payout`); there's an undo.
- **Family Giving** (`/charities`) shows where the giving pot goes; parents
  allocate it to causes month by month.

### Streak (day) milestones
- Real-life rewards tied to **days completed** (e.g., 3, 7, 14, 21, 30, 60).
  Edit at Admin → Milestones. These never reset, so they're "build toward" goals.

### Family Calendar
- Connect an iCloud/iCal share link at `/calendar` (parent settings) — paste the
  `webcal://`/`https://` public link.
- Views: **List · Day · Week · Month** (Day is a timed hour grid).

### Surprises
- Create at **Admin → Surprises** (`/admin/surprises`): title, icon, message,
  optional image, and a trigger — **"now"** (flip it on) or **on a date**. It
  reveals once in Violet's app (and can send a push notification).

### One-off & recurring events
- **Admin → Events** (`/admin/events`): dated or recurring extras (e.g., dentist,
  soccer Tue/Thu, "tidy your room" daily). Mark as a **task** (earns $) or an
  **event** (just a heads-up). They surface on the routines page on their day.

### Where to watch progress
- **Parent Dashboard** (`/dashboard`): days completed, completion %, total wins,
  per-routine breakdown, this week's chart, recent wins, next milestone.
- **Stats** (`/stats`): monthly calendar view and more detail.

### Data & privacy
- Progress (day count, badges, streaks, wins, earnings) is saved on the server,
  so it's the same on every device. Admin is PIN-protected. No third-party
  tracking. **[CONFIRM]** hosting wording — the old copy says "Railway"; want me
  to keep, change, or make it generic ("a private server")?

---

## Open decisions to lock before we update pages
1. **Routine completion:** all tasks required (current) vs a "done enough"
   threshold.
2. **Toonie count:** fixed 6 vs flexible.
3. **Giving rate:** keep 10%?
4. **Level-Up starter wins:** add example wins per category, or keep type-your-own?
5. **PIN:** set a real parent PIN.
6. **Hosting/privacy wording.**
7. **Where this content goes:** FAQ page is the main target — also refresh the
   Admin help boxes and the Welcome Tour to match? (recommended)
