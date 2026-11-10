# Padel Watch – Bristol

Pings your phone when a padel court opens up near Bristol at around 7am or 7pm.

## 1. Get alerts on your phone
1. Install the free **ntfy** app (iPhone or Android).
2. Tap **+** and subscribe to a topic with a long random name, e.g. `sam-padel-x7k29q`.
   Keep it secret – anyone with the name can see your alerts.

## 2. Run it for free on GitHub (no computer needed)
1. Create a free GitHub account and a new **private** repo called `padel-watch`.
2. Upload `padel_watch.py`.
3. Create a file at `.github/workflows/padel-watch.yml` and paste in the contents of `padel-watch.yml`.
4. Go to **Settings → Secrets and variables → Actions → New secret**.
   Name: `NTFY_TOPIC`. Value: your topic name from step 1.
5. Go to **Actions → Padel watch → Run workflow** to test it.

It then checks every 10 minutes from about 5am to 10pm.

## Or run it on your laptop
```
pip install requests
export NTFY_TOPIC=sam-padel-x7k29q
python padel_watch.py --list      # see which clubs it found
python padel_watch.py --dry-run   # see matching slots, no alert
python padel_watch.py --loop      # keep watching
```

## Change the settings
At the top of `padel_watch.py`:
- `WINDOWS` – the start times you'd take (default 06:30–07:30 and 18:30–19:30)
- `DAYS_AHEAD` – how far ahead to look (default 7 days)
- `RADIUS_M` – how far from central Bristol (default 25 km)
- `MIN_DURATION` – shortest booking you'd want (default 60 min)

## Good to know
- It only sees clubs that take bookings on **Playtomic**. Clubs using other systems won't show up.
- It only sees slots that are open to the public, so member-only slots are left out.
- You get one alert per new slot. If a slot gets booked and then frees up again, you'll be told again.
- Keep it personal and low-frequency. This uses Playtomic's app data unofficially, so it could break or get blocked at any time.
