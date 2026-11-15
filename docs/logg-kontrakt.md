# Loggkontrakt: slik skriver en agent til cyberos

Dashbordet viser bare det som står i vaulten. En agent som jobber, skriver én fil per kjøring i `Logg/`. Ingen fil, ingen lys. Dette er alt Hermes (eller en annen agent) trenger å vite. Lim gjerne hele fila inn i instruksjonene til agenten.

## Filnavn
`Logg/YYYY-MM-DD-HHMM-<agent>.md`, lokal tid, agentnavnet i små bokstaver. Eksempel: `Logg/2026-10-26-1432-coder.md`.

## Innhold
```
---
agent: Coder
status: ok
kostnad: 0.8
---
Én til tre setninger om hva som ble gjort, skrevet for et menneske.
```

- `agent`: navnet på agentfila i `Agenter/`, eller kallenavnet. Store og små bokstaver spiller ingen rolle. Dette er det som bestemmer hvem som lyser.
- `status`: `ok`, `pågår`, `varsel` eller `feil`. `varsel` er «gikk, men se på dette»: vises i blått i loggen, og Jarvis sier fra, men agenten lyser ikke rødt. `pågår` skrives når jobben starter og gir lys med én gang, i opptil en time. `ok` når den er ferdig. `feil` gir rødt lys på agenten, og et Discord-varsel om webhooken er satt.
- `kostnad`: valgfritt tall i kroner. Summeres per agent per måned og vises mot `budsjett_mnd` i agentfila.
- Teksten under: de første 160 tegnene vises i dashbordet. Skriv hva som skjedde, ikke at noe skjedde.

## Når
Skriv `pågår` når jobben starter, og `ok` eller `feil` når den er ferdig. En logg med `status: ok` yngre enn ti minutter, eller `pågår` yngre enn en time, betyr «jobber nå». En lang jobb kan logge underveis: én fil per delmål.

## Hermes som jobber for andre
Når Hermes gjør en jobb på vegne av en annen agent (for eksempel koder som Coder, eller sjekker tjenester som Drift), skriv `agent:` med den agentens navn, ikke Hermes. Da lyser riktig rom, og lyspakkene mellom agenter blir ekte.

## Jobber fra dashbordet
Dashbordet skriver én type fil: `Innboks/YYYY-MM-DD-HHMM-<agent>.md` med `til:` og `fra: dashbord` i frontmatter og jobben som tekst. Agenten som leser innboksen, tar jobber adressert til seg, gjør dem, og skriver en logg som over. Ferdige jobber flyttes til `Innboks/Ferdig/`, da telles de ikke lenger som åpne.

Hermes plukker dem opp med en cron-jobb hvert minutt: `hermes/innboks.sh` vekker ham bare når det ligger filer i `Innboks/` (tom innboks koster ingen tokens), og `hermes/innboks.md` er oppdraget han får. Svaret hans går til Discord-kanalen hans, og loggene vises i «Skjer nå». Oppsett:
```
cp ~/cyberos/hermes/innboks.sh ~/.hermes/scripts/ && chmod +x ~/.hermes/scripts/innboks.sh
hermes cron create "every 1m" "$(cat ~/cyberos/hermes/innboks.md)" --script innboks.sh --deliver discord --name cyberos-innboks
```
Endrer du oppdraget, fjern jobben (`hermes cron remove cyberos-innboks`) og lag den på nytt.

Frontmatter er ikke valgfritt: en logg uten `agent:` og `status:` vises som tom i dashbordet og teller ikke som arbeid. Dashbordet gjetter agenten fra filnavnet om feltet mangler, men ikke statusen.

## Oppgaver
`Oppgaver/<navn>.md` er sjekklister med `- [ ]` og `- [x]`. `tildelt:` i frontmatter sier hvilken agent som eier lista, og dashbordet viser åpne oppgaver per agent.

## Agentfila
```
---
rolle: Best på kode og alt rundt det
status: aktiv
verktoy: Claude Code, GitHub, shell
rom: Verksted
kallenavn: Coder
farge: #4FA8FF
drakt: programmerer
budsjett_mnd: 200
---
```
- `status`: `aktiv` (bygd og kan jobbe) eller `venter` (ikke bygd ennå, vises gjennomsiktig). `feil` settes av dashbordet fra siste logg.
- `rom`, `kallenavn`, `farge`, `drakt`, `budsjett_mnd` er valgfrie. `drakt` er en av: antenne, hatt, programmerer, frakk, slips, dollar, anonymous, hjelm, hodetelefoner, muskler, hvithatt, ironman, hermes. Uten `drakt` velges utseende etter navnet, ellers standardrobot.
- `Agenter/<navn>.png` med gjennomsiktig bakgrunn blir figuren i stasjonen, om du heller vil ha et bilde.
