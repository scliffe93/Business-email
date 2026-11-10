#!/usr/bin/env bash
# Temporary: can GitHub's runners read ClubSpark court availability?
UA='User-Agent: court-watch personal script (low frequency)'
D=$(date -u -d tomorrow +%F)
for v in CanfordPark EastvillePark RedcatchPark StGeorgePark; do
  u="https://clubspark.lta.org.uk/v0/VenueBooking/$v/GetVenueSessions?resourceID=&startDate=$D&endDate=$D&roleId="
  echo "=== $u"; curl -sS -m 20 -H "$UA" -w '\n__HTTP %{http_code}\n' "$u" | head -c 1500; echo
done
u="https://clubspark.lta.org.uk/CanfordPark/Booking/BookByDate"
echo "=== $u"
curl -sS -m 20 -H "$UA" -w '\n__HTTP %{http_code}\n' "$u" > page.html; tail -1 page.html
grep -oiE '[^"'"'"' ]*(GetVenueSessions|VenueBooking|/v0/)[^"'"'"' ]*' page.html | sort -u | head -20
