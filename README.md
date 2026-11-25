# HAppie: je AH-boodschappen in Home Assistant

Een Home Assistant-app waarmee je je **Albert Heijn-boodschappenlijst** vanuit HA beheert. Je lijst blijft in twee richtingen gelijk met de **AH-app** en met een **To-do-lijst in HA**.

> ⚠️ Gebruikt de onofficiële API van de AH-app. AH kan die zonder aankondiging wijzigen.

Huidige versie: **0.10.1**. Zie de [changelog](happie/CHANGELOG.md) en de [gebruikersdocumentatie](happie/DOCS.md).

## Functies

**Dashboard** (paneel *HAppie* in de zijbalk), dat zich aanpast aan je scherm: drie kolommen op een computer, twee op een tablet, tabbladen op een telefoon.
- **Bovenaan:** je volgende bezorging (dag, tijdvak, tot wanneer je kunt wijzigen) en cijfers: te halen, geschatte kosten mét bonus, bonusitems en hoeveel er is afgevinkt.
- **Zoeken:** in het AH-assortiment, met foto, prijs en bonus. Je kunt ook losse tekst toevoegen.
- **Barcode scannen:** live met de camera, via een foto, of door de code in te typen.
- **Mijn lijst:** gegroepeerd per categorie. Per regel zie je de bonusprijs ("2 voor 3.99" → ~~€ 5,98~~ € 3,99), en een hint als je nog iets extra moet pakken voor de bonus.
- **Ontdekken:** *Voor jou* (AH-suggesties), *Vaak gekocht* (uit je laatste 8 bestellingen) en *Bonus* (je persoonlijke bonus, plus eerder gekochte producten die nu in de bonus zijn).
- **Account:** je naam en inlogstatus. Is je sessie verlopen, dan zie je dat meteen.
- **Bestellingen:** klik op de bezorgtegel voor alle artikelen van je bestelling, ook van eerdere bezorgingen.
- **Uitgaven:** een eigen pagina met wat je per week of maand bij AH uitgeeft (online bestellingen en kassabonnen), je week- en maandbudget, wat je het meest koopt, uitgaven per categorie en de artikelen per aankoop.

**Voorraad** (bovenaan naast *Boodschappen*; op een telefoon een eigen tabblad)
- Toevoegen door te **zoeken** of te **scannen**, met de scanstanden *Kiezen* (per scan +1, −1 of een aantal), *Inruimen +1* en *Verbruiken −1* om snel achter elkaar te scannen.
- Onbekende barcodes (bijvoorbeeld van producten die niet van AH zijn) koppel je één keer aan een naam of een AH-product.
- **Bestelling uitpakken:** zet een hele bezorging met één klik in je voorraad (elke bestelling maar één keer).
- Voorraad per categorie met een filter, −/+, een aantal dat je kunt aantikken om het te wijzigen, en een 🛒-knop. Is iets op, dan zet **Op de lijst** het op je boodschappenlijst.

**Sync en Home Assistant**
- Tweewegsync met een HA-to-do-lijst. Daardoor werken Assist (*"zet melk op Boodschappen"*), de To-do-kaart en automations.
- Staat een bestelling open voor wijzigingen, dan vergrendelt AH de lijst. De sync pauzeert dan, zonder iets te verwijderen.
- Sensoren:

  | Sensor | Waarde |
  |---|---|
  | `sensor.happie_volgende_bezorging` | begin van het tijdvak, met de details als attributen |
  | `sensor.happie_lijst_items` | aantal open items |
  | `sensor.happie_geschatte_kosten` | geschatte kosten (EUR), inclusief bonus |
  | `sensor.happie_bonus_items` | aantal items op je lijst dat in de bonus is |
  | `sensor.happie_uitgaven_week` / `_maand` | uitgegeven deze week / maand (EUR) |
  | `binary_sensor.happie_boven_budget` | uitgegeven + lijst boven je weekbudget |
  | `sensor.happie_voorraad` | aantal producten op voorraad |
  | `calendar.happie_bezorging` | je volgende bezorging als afspraak in de agenda (met de integratie) |

  De app installeert zelf een kleine integratie in Home Assistant (`custom_components/happie`). Daarmee worden dit echte entiteiten op een apparaat *HAppie*, met dezelfde entiteits-ID's. Zonder die integratie zet de app ze zelf met `set_state`.

- Meldingen: als je AH-sessie verloopt, als iets op je lijst of iets wat je vaak koopt in de bonus komt (één keer per aanbieding), en als je boven je week- of maandbudget komt (één keer per week of maand). Met `notify_service` gaan ze ook naar je telefoon.

## Installeren

**Via GitHub (aanbevolen):** voeg `https://github.com/emile-bodin/HAppie` toe via **Instellingen › Apps › App-winkel › ⋮ › Repositories**. HAppie staat daarna in de winkel. Je HA downloadt een kant-en-klaar image voor jouw processor (amd64 of aarch64; 32-bit armv7 ondersteunt Home Assistant niet meer), dus installeren gaat snel.

**Lokaal bouwen:** kopieer de map `happie/` naar `/addons/happie` op je HA-machine (via de Samba- of SSH-app). Kies dan in de App-winkel **⋮ › Controleren op updates**. De app staat daarna onder *Lokale apps*. Haal dan wel de regel `image:` uit `config.yaml` weg, anders downloadt HA het image van GitHub in plaats van je lokale code te bouwen. Lokaal testen kan ook met `docker build happie/` (BuildKit).

**Automatische builds** (volgens het officiële [apps-example](https://github.com/home-assistant/apps-example)):
- *Builder*: bij elke push en pull request naar `main` draaien de tests. Is er iets veranderd in `happie/config.yaml`, de `Dockerfile` of `happie/app/`, dan bouwt GitHub Actions de images voor amd64 en aarch64. Op `main` worden ze gepubliceerd als `ghcr.io/emile-bodin/happie:<versie>` (één multi-arch image) en wordt een GitHub Release `v<versie>` gemaakt met de tekst uit de changelog.
- Een image van een bestaande versie wordt nooit overschreven. Wijzig je de app zonder het versienummer op te hogen, dan wordt er alleen als test gebouwd.
- *Lint*: controleert de app-configuratie, ook dagelijks.
- Dependabot houdt de actions en de base image bij.

**Een nieuwe versie uitbrengen:** versienummers volgen [Semantic Versioning](https://semver.org/): PATCH voor foutherstel, MINOR voor nieuwe functies, MAJOR voor veranderingen waarvoor gebruikers zelf iets moeten aanpassen (zolang de versie 0.x is, wordt dat een MINOR-versie). Verhoog `version` in `happie/config.yaml` en in `custom_components/happie/manifest.json`, zet een sectie `## <versie>` bovenaan `happie/CHANGELOG.md` en push naar `main`. HA meldt de update dan vanzelf.

Na de installatie:
1. Maak een to-do-lijst aan: **Instellingen › Apparaten & diensten › Integratie toevoegen › Lokale to-do** → `Boodschappen` (wordt `todo.boodschappen`).
2. Start de app en open **HAppie** in de zijbalk.
3. Koppel je AH-account. De stappen staan in het paneel en in [DOCS.md](happie/DOCS.md#ah-account-koppelen).

## Projectstructuur

```
repository.yaml          app-repository voor HA
happie/
  config.yaml            app: opties, ingress, versie
  Dockerfile             container (HA-base met Alpine + Python + aiohttp)
  README.md, icon.png, logo.png   beschrijving en afbeeldingen in de App-winkel
  DOCS.md, CHANGELOG.md  gebruikersdocumentatie
  translations/          teksten bij de opties (nl/en)
  app/
    main.py              opstarten: webserver en achtergrondtaken
    config.py            paden, entiteits-ID's, intervallen, opties
    ah/                  client voor de AH-API: inloggen, lijst, bestellingen, aankopen, producten, bonusberekening
    ha/                  HA via de Supervisor (to-do, states, meldingen, websocket)
    services/            sync (AH-lijst ↔ HA-to-do), uitgaven en weekbudget, voorraad
    server/              API voor het paneel, sensoren en meldingen, per onderwerp
    custom_components/happie/   de HAppie-integratie; de app installeert die in HA en geeft de sensoren eraan over
    mock.py              nep-AH en nep-HA voor ontwikkeling
    static/              het dashboard: index.html, css/ en js/ (zonder build-stap)
dev/                     lokale HA in Docker + scripts
tests/                   automatische tests
```

## Ontwikkelen

Vereist Python 3.12+ met `aiohttp`, en Docker in WSL voor de lokale HA.

```bash
pip install aiohttp
```

### Zonder Home Assistant

```bash
HAPPIE_MOCK=1 DATA_DIR=.devdata python happie/app/main.py   # dashboard met nep-AH en nep-HA op http://localhost:8099
```

Zoeken gebruikt ook in mock-modus de echte AH-API, met een anonieme token.

### Met een lokale Home Assistant (Docker in WSL)

```bash
python dev/setup_ha.py             # eenmalig, met de container al draaiend: testgebruiker, token en todo.boodschappen -> dev/.env
python dev/run_addon.py            # start de HA-container + add-on met je echte AH-account (inloggen via het paneel)
python dev/run_addon.py --mock-ah  # zelfde, maar met een nep-AH-lijst
```

- HA: http://localhost:8123 (inloggegevens staan in `dev/.env`, dat niet in git komt)
- Dashboard: http://localhost:8099
- De eerste keer start je de container met `docker compose -f dev/docker-compose.yml up -d` in WSL. Daarna doet `run_addon.py` dat zelf.
- WSL zet zichzelf uit als er niets meer draait, en dan stopt HA ook. `run_addon.py` houdt WSL actief zolang de app draait.
- Gegevens van de app (tokens, sync-stand) staan in `.devdata/`.

### Tests

```bash
python tests/test_sync.py           # sync: toevoegen, afvinken, verwijderen, eerste samenvoeging, vergrendelde lijst, langer wachten na fouten
python tests/test_auth.py           # inloggen: token maar één keer tegelijk vernieuwen
python tests/test_bonus.py          # bonusberekening ("2 voor", "+ gratis", %, vaste prijs, ...)
python tests/test_inventory.py      # voorraad: +/−, tellen, barcodes koppelen, bestelling uitpakken
python tests/test_notifications.py  # sensoren, melding bij verlopen sessie, bonusmeldingen
python tests/test_orders.py         # bestellingen: overzicht, artikelen, ook-op-lijst, sensorattribuut
python tests/test_spending.py       # uitgaven per week/maand, week- en maandbudget, budgetmeldingen
python tests/test_purchase_items.py # artikelen per aankoop: meest gekocht, categorieën, bonregels koppelen
python tests/test_integration.py    # integratie: installeren, herstartmelding, sensoren overdragen, versie gelijk aan de app
python dev/e2e_test.py              # end-to-end tegen de lokale HA (naast run_addon.py --mock-ah)
```

## Bekende beperkingen

- De AH-API is onofficieel. Wat met een echt account getest is, staat in de changelog.
- Inloggen vraagt eenmalig een bladwijzer (*HAppie-koppelen*) in een computerbrowser; lukt dat niet, dan kopieer je de code via de ontwikkelaarstools (F12).
- Zolang een bestelling openstaat voor wijzigingen, kan de app de lijst niet lezen of wijzigen.
- Live barcode scannen werkt alleen via https. **Foto maken** werkt altijd.

## Ideeën voor later

- Producten direct aan een openstaande bestelling toevoegen.
- Acties in de HAppie-integratie, zoals `happie.add_product` (op zoekterm of barcode) en `happie.sync_now`, zodat automations en scripts echte producten op de lijst kunnen zetten.
- Producten automatisch op de lijst zetten als de voorraad onder een ingesteld minimum komt.

## Credits

AH documenteert de API van de AH-app niet. Hoe die werkt (inloggen, endpoints, velden) hebben we uit deze open-sourceprojecten gehaald. Bedankt aan de makers:

- [gwillem/appie-go](https://github.com/gwillem/appie-go): Go-library en CLI voor de AH-API, plus [API-documentatie](https://github.com/gwillem/appie-go/blob/main/doc/albertheijn_api.md). Onze belangrijkste bron voor inloggen, de boodschappenlijst, zoeken, producten en bestellingen.
- [KixAss/home-assistant-appie](https://github.com/KixAss/home-assistant-appie): HA-integratie met tweewegsync. Hier hebben we gekeken hoe je items afvinkt en verwijdert in de lijst-API (`shoppinglist/v2`).
- [whazor/ah-mcp](https://github.com/whazor/ah-mcp): MCP-server voor AH, voor *vaak gekocht* en suggesties.
- [jabbink's gist](https://gist.github.com/jabbink/8bfa44bdfc535d696b340c46d228fdd1) over de AH-app-API, voor de zoekparameters en voorbeeldantwoorden.
- [digital-IMEI/home-assistant-ah-shopping](https://github.com/digital-IMEI/home-assistant-ah-shopping): HA-integratie, voor het formaat van het antwoord van `shoppinglist/v2`.

Verder gebruiken we:

- [ZXing (`@zxing/library`)](https://github.com/zxing-js/library) voor het scannen van barcodes in browsers zonder `BarcodeDetector`.
- [aiohttp](https://github.com/aio-libs/aiohttp) voor de webserver en de HTTP-client.
- De [base images van Home Assistant](https://github.com/home-assistant/docker-base) voor de container.

## Gemaakt met Claude

HAppie is gebouwd met [Claude Code](https://claude.com/claude-code) van Anthropic. Claude schreef het grootste deel van de code, de tests en de documentatie, en zocht uit hoe de AH-API werkt. Wat de app moet doen, de keuzes en het testen met een echt AH-account en in dagelijks gebruik kwamen van mij.

Wat dat voor jou betekent:
- De kern (sync, uitgaven, bonusberekening, voorraad, meldingen) heeft automatische tests die bij elke wijziging in GitHub Actions draaien. Het paneel test ik met de hand.
- HAppie gebruikt een onofficiële AH-API en heeft toegang tot je AH-account. Kijk dus gerust zelf in de code voordat je de app installeert.
- Zie je iets geks? Meld het via [Issues](https://github.com/emile-bodin/HAppie/issues).
