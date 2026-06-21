# Violet's App — How It Works (DRAFT for current version)

> Working draft to get the wording set, then we'll roll it into the right pages:
> the **How It Works / FAQ** page, the help boxes on Admin pages, and the Welcome
> Tour. Decisions are now locked (see *Decisions — locked* at the bottom); the
> only things still open are the **parent PIN** and a 👍 on the **starter 1%
> ideas**.

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
6. **Get 1% better — the Compound Effect.** "Level Up" is how we make a routine
   task we've already gotten good at *a little* better — about **1%**. Small,
   almost-too-easy improvements that compound over time. The cycling line says
   it best: *"It doesn't get easier — you just get better."* The win isn't doing
   something hard; it's **never going back**. The 1% steps should feel easy on
   purpose.
7. **Weekly rhythm: Sunday Planning.** Once a week the family sits down to (a)
   review how the week went, (b) decide what we want to do next week, (c) figure
   out how to make next week **easier and more fun**, and (d) pick a few
   proficient tasks to **level up by 1%**. We also log the week's level-ups, pay
   out the bank, and plan next week's toonies.
8. **Celebrate everything.** Badges, milestones (days + money), surprises, and
   confetti are all there to make showing up feel good.

**The weekly loop, in one line:** *Do routines in their windows → finish them to
unlock toonie chores → earn money (some to giving, some to bank) → at Sunday
Planning, review, cash out, and level up a few tasks by 1% for next week.*

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

> **Decided:** a routine counts only when **all** tasks + subtasks are checked
> (that's what marks the day complete). The old "you don't have to do every task"
> line will be removed everywhere.

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
Level Up is how you make something you already do **1% better**. Pick a task
you've gotten good at and find a tiny way to push it forward — neater, faster,
or one notch more grown-up. Like in cycling: *"it doesn't get easier, you just
get better."* The goal isn't to do something hard — it's to **never go back**,
so a 1% step should feel easy. Those little steps add up (that's the Compound
Effect).

You log your level-ups together each week at **Sunday Planning**, sorted into
categories:
🛁 Self-Care · 🧹 Cleaning & Organization · 🏃 Health & Fitness ·
📚 Education & Learning · 🎯 Goal Setting · 💛 Charity & Giving Back · 🎉 Fun.

> Example: "Make my bed" → this week, also straighten the pillows. Next week,
> add the throw blanket. Each step is tiny; together they compound.

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

Everything below lives behind the **parent PIN** (Admin). **[NEEDS A VALUE]**
default is `1234` — tell me a 4-digit code and I'll set it.

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
- **Decided:** the list is **6 tasks** (you can still add/remove anytime).

### Level Up categories (the 1% / Compound-Effect tool)
- **What it's for:** taking tasks Violet is already proficient at and nudging
  them ~1% forward — small enough to feel easy, with the rule being "don't go
  back." It's the cycling mindset: *it doesn't get easier, you just get better.*
- Edit at **Admin → Level Up** (the main `/admin` page): add/rename categories,
  set icons, and optionally pre-load example level-ups.
- Level-ups are logged with Violet at **Sunday Planning**, where you also review
  the week and plan how to make next week easier, more fun, and 1% better.
- Current categories: Self-Care, Cleaning & Organization, Health & Fitness,
  Education & Learning, Goal Setting, Charity & Giving Back, Fun.
- **Decided:** pre-load a few starter **"1% level-up" ideas** per category (see
  the *Starter 1% level-up ideas* section below) — editable anytime.

### Money, giving & the bank
- **Giving %** and **money milestones**: Admin → main page (money section).
  Earnings auto-split: the giving % goes to the giving pot, the rest to Violet's
  spendable bank. **Decided:** giving rate stays **10%** (change anytime).
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
- Progress (day count, badges, streaks, wins, earnings) is saved on **a private
  server**, so it's the same on every device. Admin is PIN-protected. No
  third-party tracking and no analytics — it's just for your family. 💜

---

## Starter "1% level-up" ideas (for sign-off)
Proposed examples to pre-load per category — each is a *tiny* step up on
something she already does, in her own voice. Editable anytime. **[REVIEW]**

- **🛁 Self-Care:** "Brushed my teeth the full two minutes" · "Got ready without
  being reminded" · "Laid out my clothes the night before"
- **🧹 Cleaning & Organization:** "Made my bed a little neater" · "Put my clothes
  away instead of on the chair" · "Tidied one extra spot without being asked"
- **🏃 Health & Fitness:** "Moved my body 5 minutes longer" · "Chose water
  instead of juice" · "Did a quick stretch before bed"
- **📚 Education & Learning:** "Read a few minutes longer than usual" · "Checked
  my own work before saying I was done" · "Tried the tricky part before asking
  for help"
- **🎯 Goal Setting:** "Picked one small goal for the day" · "Broke a big job
  into smaller steps" · "Finished what I started before moving on"
- **💛 Charity & Giving Back:** "Helped someone without being asked" · "Said
  something kind on purpose" · "Set aside something to give"
- **🎉 Fun:** "Tried a new game or activity" · "Invited someone to join in" ·
  "Made something creative just for me"

---

## Decisions — locked ✅
1. **Routine completion:** all tasks required. (Remove old "best effort" copy.)
2. **Toonie count:** 6 (flexible to edit).
3. **Giving rate:** 10%.
4. **Level-Up starters:** add the 1% examples above, per category.
5. **Hosting wording:** generic ("a private server").
6. **Rollout:** update FAQ/How It Works, Admin help boxes, and Welcome Tour.

**Still needed from you:** a real 4-digit **parent PIN**, and a 👍 on the
starter 1% ideas above (tweak any you'd word differently).
