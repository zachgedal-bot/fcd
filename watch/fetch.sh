#!/usr/bin/env bash
# Fetches public market and weather data on a GitHub-hosted runner and stores it under watch/latest.
# Research-only data collection for the daily-temperature market watch; no trading.
set -u
OUT=watch/latest
EVENT_SLUG=${EVENT_SLUG:-}; ICAO=${ICAO:-}; LAT=${LAT:-}; LON=${LON:-}; TZN=${TZN:-}; SG_DATE=${SG_DATE:-}; WU_DATE=${WU_DATE:-}
rm -rf "$OUT"; mkdir -p "$OUT/books" "$OUT/clobmkts"
UA="Mozilla/5.0 (X11; Linux x86_64) research-watch"
get() { curl -sS -L --max-time 40 -A "$UA" "$1" -o "$2" || echo "FAILED $1" >> "$OUT/errors.txt"; }
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$OUT/fetched_at_utc.txt"

SLUG="${EVENT_SLUG:-highest-temperature-in-singapore-on-october-5-2026}"
get "https://gamma-api.polymarket.com/events?slug=$SLUG" "$OUT/event.json"
get "https://gamma-api.polymarket.com/events?tag_slug=weather&active=true&closed=false&limit=200&order=endDate&ascending=true" "$OUT/weather_events.json"

# Order books + CLOB market metadata (fees) for every outcome in the event
if jq -e '.[0].markets' "$OUT/event.json" >/dev/null 2>&1; then
  jq -r '.[0].markets[] | [.groupItemTitle, .conditionId, (.clobTokenIds|fromjson|join(","))] | @tsv' "$OUT/event.json" | while IFS=$'\t' read -r title cond toks; do
    safe=$(echo "$title" | tr -c 'A-Za-z0-9' '_')
    yes=${toks%%,*}; no=${toks##*,}
    get "https://clob.polymarket.com/book?token_id=$yes" "$OUT/books/${safe}_YES.json"
    get "https://clob.polymarket.com/book?token_id=$no" "$OUT/books/${safe}_NO.json"
    get "https://clob.polymarket.com/markets/$cond" "$OUT/clobmkts/${safe}.json"
  done
fi

# Official / station observations
get "https://aviationweather.gov/api/data/metar?ids=${ICAO:-WSSS}&format=json&hours=30" "$OUT/metar.json"
get "https://aviationweather.gov/api/data/taf?ids=${ICAO:-WSSS}&format=json" "$OUT/taf.json"
get "https://api-open.data.gov.sg/v2/real-time/api/air-temperature" "$OUT/sg_airtemp_now.json"; sleep 3
get "https://api-open.data.gov.sg/v2/real-time/api/air-temperature?date=${SG_DATE:-2026-10-05}" "$OUT/sg_airtemp_day_p1.json"; sleep 3
tok=$(jq -r '.data.paginationToken // empty' "$OUT/sg_airtemp_day_p1.json" 2>/dev/null)
i=2; while [ -n "$tok" ] && [ $i -le 8 ]; do
  get "https://api-open.data.gov.sg/v2/real-time/api/air-temperature?date=${SG_DATE:-2026-10-05}&paginationToken=$tok" "$OUT/sg_airtemp_day_p$i.json"; sleep 3
  tok=$(jq -r '.data.paginationToken // empty' "$OUT/sg_airtemp_day_p$i.json" 2>/dev/null); i=$((i+1))
done
sleep 3; get "https://api-open.data.gov.sg/v2/real-time/api/two-hr-forecast" "$OUT/sg_2h.json"; sleep 3
get "https://api-open.data.gov.sg/v2/real-time/api/twenty-four-hr-forecast" "$OUT/sg_24h.json"; sleep 3
get "https://api-open.data.gov.sg/v2/real-time/api/rainfall" "$OUT/sg_rain.json"
get "https://www.ogimet.com/cgi-bin/gsynres?ind=48698&lang=en&decoded=yes&ndays=2" "$OUT/ogimet_48698.html"
# Weather Underground history (settlement-source proxy if rules cite WU); public site key
get "https://api.weather.com/v1/location/${ICAO:-WSSS}:9:SG/observations/historical.json?apiKey=e1f10a1e78da46f5b10a1e78da96f525&units=m&startDate=${WU_DATE:-20261005}&endDate=${WU_DATE:-20261005}" "$OUT/wu_history.json"

# Historical METAR archive (Iowa Environmental Mesonet) for analogue statistics, local time
if [ ! -f watch/hist/wsss_2025_sep_nov.csv ]; then mkdir -p watch/hist
  get "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=WSSS&data=tmpc&year1=2025&month1=9&day1=1&year2=2025&month2=11&day2=30&tz=Asia/Singapore&format=onlycomma&latlon=no&missing=M&trace=T&direct=no&report_type=3&report_type=4" watch/hist/wsss_2025_sep_nov.csv
  get "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=WSSS&data=tmpc&year1=2024&month1=9&day1=1&year2=2024&month2=11&day2=30&tz=Asia/Singapore&format=onlycomma&latlon=no&missing=M&trace=T&direct=no&report_type=3&report_type=4" watch/hist/wsss_2024_sep_nov.csv
  get "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=WSSS&data=tmpc&year1=2023&month1=9&day1=1&year2=2023&month2=11&day2=30&tz=Asia/Singapore&format=onlycomma&latlon=no&missing=M&trace=T&direct=no&report_type=3&report_type=4" watch/hist/wsss_2023_sep_nov.csv
fi
get "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=WSSS&data=tmpc&year1=2026&month1=9&day1=1&year2=2026&month2=10&day2=6&tz=Asia/Singapore&format=onlycomma&latlon=no&missing=M&trace=T&direct=no&report_type=3&report_type=4" "$OUT/wsss_2026_recent.csv"
# NWS timeseries page (settlement source; likely JS-rendered, kept for inspection)
get "https://www.weather.gov/wrh/timeseries?site=wsss" "$OUT/nws_timeseries.html"

# Polymarket fee documentation
get "https://docs.polymarket.com/polymarket-learn/trading/fees" "$OUT/pm_fees_learn.html"
get "https://docs.polymarket.com/developers/CLOB/fees" "$OUT/pm_fees_dev.html"
get "https://docs.polymarket.com/llms.txt" "$OUT/pm_llms.txt"
# Forecasts at the airport coordinates
LAT=${LAT:-1.3644}; LON=${LON:-103.9915}; TZ_=${TZN:-Asia/Singapore}
get "https://api.open-meteo.com/v1/forecast?latitude=$LAT&longitude=$LON&hourly=temperature_2m,cloud_cover,precipitation,wind_speed_10m,wind_direction_10m&daily=temperature_2m_max&models=ecmwf_ifs025,gfs_seamless,icon_seamless,ukmo_seamless,best_match&timezone=$TZ_&forecast_days=2" "$OUT/openmeteo_models.json"
get "https://ensemble-api.open-meteo.com/v1/ensemble?latitude=$LAT&longitude=$LON&hourly=temperature_2m&models=ecmwf_ifs025,gfs025&timezone=$TZ_&forecast_days=2" "$OUT/openmeteo_ensemble.json"
get "https://api.open-meteo.com/v1/forecast?latitude=$LAT&longitude=$LON&hourly=temperature_2m&past_days=1&forecast_days=1&timezone=$TZ_" "$OUT/openmeteo_recent.json"
ls -la "$OUT" "$OUT/books" | head -80
