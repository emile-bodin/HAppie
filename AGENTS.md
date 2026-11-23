# AGENTS.md

Instructies voor AI-agents (en mensen) die deze repo beheren, bouwen en bijwerken.

HAppie is een **Home Assistant-app** (vroeger "add-on"): een eigen container naast HA, beheerd door de Supervisor. Het synchroniseert je Albert Heijn-boodschappenlijst met een HA-to-do-lijst en heeft een paneel (ingress) met zoeken, ontdekken, bestellingen, voorraad en uitgaven. Het is **geen** HACS-integratie.

> De AH-API is onofficieel en reverse engineered uit de Appie-app. Velden en endpoints kunnen zonder aankondiging veranderen.

## Structuur

```
repository.yaml            app-repository voor de App-winkel
appie/                     de app (map en slug heten "appie", de naam is "HAppie")
  config.yaml              naam, versie, opties + schema, image, ingress
  build.yaml               base images per architectuur
  Dockerfile               Alpine + python3 + py3-aiohttp, verder niets
  CHANGELOG.md, DOCS.md    voor gebruikers (Nederlands)
  translations/nl.yaml, en.yaml   teksten bij de opties
  app/
    main.py                webserver + API voor het paneel, sensoren, meldingen, achtergrondtaken
    ah_client.py           AH-API (lijst, zoeken, bestellingen, bonus, kassabonnen, bonusberekening)
    ha_client.py           HA via de Supervisor-API (to-do, states, meldingen, websocket)
    sync.py                tweewegsync AH-lijst <-> HA-to-do
    spending.py            uitgaven per week/maand, weekbudget (pure functies)
    inventory.py           voorraad
    mock.py                nep-AH en nep-HA voor ontwikkeling
    static/index.html      het hele paneel: één bestand, zonder build-stap
tests/                     testscripts (gewone Python, geen pytest nodig)
dev/                       lokale HA in Docker + scripts
.github/workflows/build.yaml   CI: tests, linter, images
```

## Werkwijze en conventies

- **Taal:** alles wat een gebruiker ziet is Nederlands (paneel, meldingen, logs op info-niveau, DOCS, CHANGELOG, README). Code, identifiers en commentaar zijn Engels.
- **Geen nieuwe afhankelijkheden** zonder goede reden. Backend: alleen `aiohttp` (komt uit Alpine als `py3-aiohttp`). Frontend: vanilla JS in `index.html`, geen framework, geen build-stap. Alleen ZXing wordt op aanvraag geladen voor het scannen.
- **Werk chirurgisch:** herstel oorzaken en hergebruik bestaande helpers. Bijvoorbeeld `euro()`, `bonusLabel()`, `esc()`, `api()`, `srow()`, `productCard()` en de `.modal`-, `.stat`- en `ul.items`-stijlen in `index.html`; `line_for()`, `_set_state_if_changed()` en `_ensure_products()` in `main.py`; `parse_product()`, `bonus_line()` en `order_total()` in `ah_client.py`.
- **Stabiele namen:** verander nooit de `slug` (`appie`) of entiteits-ID's (`sensor.appie_*`, `binary_sensor.appie_*`), want dat breekt automations van gebruikers. Een weergavenaam veranderen mag wel.
- **Sensoren** worden gezet met `ha.set_state` via `_set_state_if_changed()`. Bedragen: `device_class: monetary`, `unit_of_measurement: EUR`, en bij periodetotalen `state_class: total` met `last_reset`.
- **Meldingen** gaan via `ha.notify(..., notification_id, notify_service)`, met een vaste `notification_id` zodat ze te vervangen en te sluiten zijn. Stuur ze niet herhaald: bewaar wat al gemeld is (zie `notified_bonus.json`, `notified_budget.json`).
- **Opties:** een nieuwe optie moet op vier plekken: `config.yaml` (`options` + `schema`), `load_options()` in `main.py` (standaardwaarde), `translations/nl.yaml` en `en.yaml`, en de tabel in `DOCS.md`.
- **Opties die gelijk zijn aan de standaard** (`boot`, `startup`, `ingress_port`, ...) horen niet in `config.yaml`; de linter in CI keurt ze af.
- **Architecturen:** alleen `amd64` en `aarch64`. armv7 wordt niet meer ondersteund door HA (sinds 2025.12); voeg het niet terug toe.
- **Merknaam:** "Appie" en "Albert Heijn" zijn merken van AH. Gebruik geen AH-logo's of huisstijl.

## Veiligheid en privacy (belangrijk)

- **Nooit committen:** `.devdata/` (AH-tokens, sync-stand, uitgaven), `dev/.env` (HA-token en -wachtwoord), persoonlijke gegevens of e-mailadressen. Ze staan in `.gitignore`. Controleer vóór elke commit met `git status` en zoek in wat je staget naar tokens (`git grep --cached -nIE "eyJ[A-Za-z0-9_-]{20,}|gh[op]_"`).
- **Test nooit schrijvende acties tegen het echte AH-account.** In het paneel zet Enter in de zoekbalk de zoekterm als losse tekst op de lijst, en `api/list/add`, `check`, `quantity` en `remove` veranderen de echte lijst (en via de sync ook HA). Gebruik voor alles met toevoegen of wijzigen de **mock** (zie hieronder). Tegen het echte account alleen lezen (GET).
- **Onderzoek naar de AH-API** (nieuwe velden of endpoints) mag met de echte tokens in `.devdata/real/tokens.json`, maar alleen lezend. Controleer eerst of het access token nog geldig is (`expires_at`), anders ververst `AHClient` het token. Dan wordt `tokens.json` herschreven en kan een draaiende app-instantie zijn sessie kwijtraken.
- **Een draaiende app-instantie** van iemand anders (bijvoorbeeld een andere sessie die `dev/run_addon.py` draait) stop je alleen na toestemming.

## Ontwikkelen

Vereist Python 3.12+ en `pip install aiohttp`.

```bash
# paneel met nep-AH en nep-HA (veilig om alles te testen); zoeken gebruikt wel de echte AH-API, anoniem
APPIE_MOCK=1 DATA_DIR=.devdata PORT=8100 python appie/app/main.py
```

In de Claude-app start je dit als preview `appie-mock` (zie `.claude/launch.json`). Draait poort 8099 al, dan kies je een andere poort.

Met de lokale HA (Docker in WSL, gewone HA Core zonder Supervisor en dus zonder App-winkel):

```bash
python dev/setup_ha.py             # eenmalig: testgebruiker, token, todo.boodschappen -> dev/.env
python dev/run_addon.py            # HA-container + app met het echte AH-account, paneel op :8099
python dev/run_addon.py --mock-ah  # zelfde, met een nep-AH-lijst (veilig)
```

- De app draait lokaal als gewoon Python-proces en praat via de API met HA op `localhost:8123`. Opties gaan lokaal via `<DATA_DIR>/options.json`, bijvoorbeeld `{"week_budget": 250}`.
- Wijzigingen in `static/index.html` zie je na een herlaadactie in de browser. Wijzigingen in Python vragen om een herstart van `main.py`.

### Verifiëren in de browser

Controleer elke wijziging aan het paneel in de draaiende app, zowel op **mobiel (390 px)** als op **desktop (~1280 px)**, en in licht en donker thema als je kleuren aanpast. Kijk daarbij naar consolefouten, horizontaal scrollen op mobiel en afgekapte teksten. Vaste controlepunten: lege lijst, zoeken op "melk", Ontdekken, lege voorraad, uitgaven per week en per maand, en de bestelmodal.

## Testen

```bash
for t in tests/test_*.py; do python "$t" || break; done   # alle tests; elk script print "all ... tests passed"
python dev/e2e_test.py                                     # end-to-end, naast: python dev/run_addon.py --mock-ah
```

- Tests zijn gewone scripts met fakes (`FakeHA`, nep-`order_summaries`, ...). Ze zetten zelf een tijdelijke `DATA_DIR` en hebben geen netwerk nodig.
- Een nieuwe functie krijgt een test in de stijl van de bestaande, bijvoorbeeld `tests/test_spending.py` of `tests/test_orders.py`, en een regel in de testlijst van `README.md`.
- Voor het paneel zijn er geen geautomatiseerde tests: verifieer in de browser (zie hierboven) en controleer of het script nog parseert.

## Bouwen en CI

`.github/workflows/build.yaml` draait bij elke push naar `main`, bij pull requests en met de hand (`workflow_dispatch`):

1. **Tests:** alle `tests/test_*.py` op Python 3.12.
2. **App-configuratie controleren:** `frenck/action-addon-linter` op `appie/`.
3. **Images:** `home-assistant/builder` bouwt per architectuur `ghcr.io/emile-bodin/{arch}-happie:<versie>` (de versie komt uit `config.yaml`). Bij pull requests wordt alleen gebouwd (`--test`), niet gepubliceerd.

```bash
gh run list --limit 3                    # laatste runs
gh run view <id> --log-failed            # waarom een run faalde
gh run watch <id> --exit-status          # wachten tot een run klaar is
```

De images moeten publiek zijn, anders kan HA ze niet downloaden. Controle zonder inloggen:

```bash
T=$(curl -s "https://ghcr.io/token?scope=repository:emile-bodin/amd64-happie:pull" | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $T" -H "Accept: application/vnd.oci.image.index.v1+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json" https://ghcr.io/v2/emile-bodin/amd64-happie/manifests/<versie>
```

Lokaal een image bouwen zonder CI kan door `appie/` naar `/addons/appie` op een HA OS-machine te kopiëren. Haal dan de regel `image:` uit `config.yaml`, anders downloadt HA het image van GitHub.

## Een nieuwe versie uitbrengen

1. Werk de code bij en laat alle tests slagen.
2. Verhoog `version` in `appie/config.yaml` (semver: patch voor fixes, minor voor nieuwe functies).
3. Voeg bovenaan `appie/CHANGELOG.md` een sectie `## <versie>` toe: korte Nederlandse regels, geschreven voor gebruikers.
4. Werk `README.md` en `appie/DOCS.md` bij als er functies, opties of sensoren bijkomen.
5. Commit en push naar `main`. CI bouwt en publiceert de images, en HA meldt de update vanzelf.
6. Controleer dat de run groen is en dat de nieuwe images publiek te downloaden zijn.

Push je zonder het versienummer te verhogen, dan wordt het image van dezelfde versie overschreven en ziet HA géén update. Verhoog dus altijd de versie als gebruikers de wijziging moeten krijgen.

## Git

- Branch: `main`; remote: `https://github.com/emile-bodin/HAppie`.
- Commitberichten in het Nederlands: een korte titel en daaronder waarom. Commit of push alleen als daarom gevraagd is.
- Grotere of riskante wijzigingen gaan via een branch en een pull request. CI test en bouwt die dan zonder te publiceren.

## Nuttige AH-API-kennis

- Bestellingen: `GET /mobile-services/order/v1/summaries` (met `orderTotalPrice.priceTotalPayable`, `trackTraceInfo.message` met het verwachte bezorgvenster, `slotInfo`) en `GET /mobile-services/order/v1/{id}/details-grouped-by-taxonomy` voor de artikelen. Per artikel staat er geen betaalde prijs in, alleen aantallen.
- Kassabonnen: GraphQL `posReceiptsPage(pagination: {offset, limit}) { posReceipts { id dateTime totalAmount { amount } } }`. De oude REST-endpoints `/receipts` geven 404.
- GraphQL (`POST /graphql`) heeft introspectie uitgeschakeld; velden vind je door ze te proberen ("Cannot query field" betekent dat het veld niet bestaat). `order(id: Int)` geeft onder andere `delivery { status slot startTime endTime method }`. Het aantal stops vóór je adres is niet gevonden.
- Bronnen: zie "Bronnen" in `README.md` (onder andere `gwillem/appie-go`).
