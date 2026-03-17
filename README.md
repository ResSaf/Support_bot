# Support_bot
Support picker bot
support_bot.py — Selektionslogiken. filen innehåller Slack User IDs under POOL. 
User ID väljs från medlemmar ur #suppory → "Kopiera member-ID".
support_bot.yml — GitHub Actions-workflow. Kör automatiskt varje måndag 09:00 UTC (= 09:00 vintertid, 10:00 sommartid). Sparar veckans val i last_week.json så att nästa vecka vet vilka som ska exkluderas.
