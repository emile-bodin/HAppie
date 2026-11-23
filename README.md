# HAppie: je Appie-boodschappen in Home Assistant

Een Home Assistant-add-on waarmee je je **Albert Heijn-boodschappenlijst** vanuit HA beheert. Je lijst blijft in twee richtingen gelijk met de **Appie-app** en met een **To-do-lijst in HA**.

> ⚠️ Gebruikt de onofficiële API van de Appie-app. AH kan die zonder aankondiging wijzigen.

Huidige versie: **0.6.0**. Zie de [changelog](appie/CHANGELOG.md) en de [gebruikersdocumentatie](appie/DOCS.md).

## Functies

**Dashboard** (paneel *HAppie* in de zijbalk), dat zich aanpast aan je scherm: drie kolommen op een computer, twee op een tablet, tabbladen op een telefoon.
- **Bovenaan:** je volgende bezorging (dag, tijdvak, tot wanneer je kunt wijzigen) en cijfers: te halen, geschatte kosten mét bonus, bonusitems en hoeveel er is afgevinkt.
- **Zoeken:** in het AH-assortiment, met foto, prijs en bonus. Je kunt ook losse tekst toevoegen.
- **Barcode scannen:** live met de camera, via een foto, of door de code in te typen.
- **Mijn lijst:** gegroepeerd per categorie. Per regel zie je de bonusprijs ("2 voor 3.99" → ~~€ 5,98~~ € 3,99), en een hint als je nog iets extra moet pakken voor de bonus.
- **Ontdekken:** *Voor jou* (AH-suggesties), *Vaak gekocht* (uit je laatste 8 bestellingen) en *Bonus* (je persoonlijke bonus, plus eerder gekochte producten die nu in de bonus zijn).
- **Account:** je naam en inlogstatus. Is je sessie verlopen, dan zie je dat meteen.
- **Bestellingen:** klik op de bezorgtegel voor alle artikelen van je bestelling, ook van eerdere bezorgingen.
- **Uitgaven:** wat je per week of maand bij AH uitgeeft (online bestellingen en kassabonnen) als grafiek, met een optioneel weekbudget.

**Voorraad** (switch *Boodschappen | Voorraad* in the top bar; on phones a 4th tab)
- Add by **searching** or **scanning**, with scan modes *Kiezen* (+1 / −1 / set a count per scan), *Inruimen +1* and *Verbruiken −1* for scanning quickly in a row.
- Unknown barcodes (e.g. non-AH products) can be linked once to a name or AH product.
- **Bestelling uitpakken**: put a whole delivery into your stock with one click (each order only once).
- Stock per category with a filter, −/+, a count you can tap to change, and a 🛒 button. When something runs out: **Op de lijst**.

**Sync en Home Assistant**
- Tweewegsync met een HA-to-do-lijst. Daardoor werken Assist (*"zet melk op Boodschappen"*), de To-do-kaart en automations.
- Staat een bestelling open voor wijzigingen, dan vergrendelt AH de lijst. De sync pauzeert dan, zonder iets te verwijderen.
- Sensoren:

  | Sensor | Waarde |
  |---|---|
  | `sensor.appie_volgende_bezorging` | begin van het tijdvak, met de details als attributen |
  | `sensor.appie_lijst_items` | aantal open items |
  | `sensor.appie_geschatte_kosten` | geschatte kosten (EUR), inclusief bonus |
  | `sensor.appie_bonus_items` | aantal items op je lijst dat in de bonus is |
  | `sensor.appie_uitgaven_week` / `_maand` | uitgegeven deze week / maand (EUR) |
  | `binary_sensor.appie_boven_budget` | uitgegeven + lijst boven je weekbudget |
  | `sensor.appie_voorraad` | aantal producten op voorraad |

- Meldingen: als je AH-sessie verloopt, als iets op je lijst of iets wat je vaak koopt in de bonus komt (één keer per aanbieding), en als je boven je weekbudget komt (één keer per week). Met `notify_service` gaan ze ook naar je telefoon.

## Installeren

> Voorlopig wordt de add-on alleen op de lokale dev-HA getest (zie *Ontwikkelen*).

**Lokaal bouwen:** kopieer de map `appie/` naar `/addons/appie` op je HA-machine (via de Samba- of SSH-add-on). Kies dan in de Add-on-winkel **⋮ › Controleren op updates**. De add-on staat daarna onder *Lokale add-ons*. Haal dan wel de regel `image:` uit `config.yaml` weg, anders downloadt HA het image van GitHub in plaats van je lokale code te bouwen.

**Via GitHub (aanbevolen):** voeg `https://github.com/emile-bodin/HAppie` toe via **Instellingen › Apps › App-winkel › ⋮ › Repositories**. HAppie staat daarna in de winkel. Je HA downloadt een kant-en-klaar image voor jouw processor (amd64 of aarch64; 32-bit armv7 ondersteunt Home Assistant niet meer), dus installeren gaat snel.

**Automatische builds:** bij elke push naar `main` draait GitHub Actions de tests, controleert de app-configuratie en bouwt de images (amd64 en aarch64) naar `ghcr.io/emile-bodin/{arch}-happie` met het versienummer uit `appie/config.yaml`. Een nieuwe versie uitbrengen = het versienummer in `config.yaml` ophogen (plus een regel in de changelog) en pushen; HA meldt de update dan vanzelf.

Na de installatie:
1. Maak een to-do-lijst aan: **Instellingen › Apparaten & diensten › Integratie toevoegen › Lokale to-do** → `Boodschappen` (wordt `todo.boodschappen`).
2. Start de add-on en open **HAppie** in de zijbalk.
3. Koppel je AH-account. De stappen staan in het paneel en in [DOCS.md](appie/DOCS.md#ah-account-koppelen).

## Projectstructuur

```
repository.yaml          add-on-repository voor HA
appie/
  config.yaml            add-on: opties, ingress, versie
  Dockerfile, build.yaml container (Alpine + Python + aiohttp)
  DOCS.md, CHANGELOG.md  gebruikersdocumentatie
  translations/          teksten bij de opties (nl/en)
  app/
    main.py              webserver, API voor het paneel, sensoren, meldingen
    ah_client.py         client voor de AH-API (lijst, zoeken, bestellingen, bonus, barcode, bonusberekening)
    ha_client.py         HA via de Supervisor (to-do, states, meldingen, websocket)
    sync.py              tweewegsync: AH-lijst ↔ HA-to-do-lijst
    spending.py          uitgaven per week/maand en weekbudget
    inventory.py         voorraad (JSON in /data): aantallen, barcodekoppelingen, uitgepakte bestellingen
    mock.py              nep-AH en nep-HA voor ontwikkeling
    static/index.html    het dashboard (één bestand, zonder build-stap)
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
APPIE_MOCK=1 DATA_DIR=.devdata python appie/app/main.py   # dashboard met nep-AH en nep-HA op http://localhost:8099
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
- WSL zet zichzelf uit als er niets meer draait, en dan stopt HA ook. `run_addon.py` houdt WSL actief zolang de add-on draait.
- Gegevens van de add-on (tokens, sync-stand) staan in `.devdata/`.

### Tests

```bash
python tests/test_sync.py           # sync: toevoegen, afvinken, verwijderen, eerste samenvoeging, vergrendelde lijst
python tests/test_bonus.py          # bonusberekening ("2 voor", "+ gratis", %, vaste prijs, ...)
python tests/test_inventory.py      # voorraad: +/−, tellen, barcodes koppelen, bestelling uitpakken
python tests/test_notifications.py  # sensoren, melding bij verlopen sessie, bonusmeldingen
python tests/test_orders.py         # bestellingen: overzicht, artikelen, ook-op-lijst, sensorattribuut
python tests/test_spending.py       # uitgaven per week/maand, weekbudget, budgetmelding
python dev/e2e_test.py              # end-to-end tegen de lokale HA (naast run_addon.py --mock-ah)
```

## Bekende beperkingen

- De AH-API is onofficieel. Wat met een echt account getest is, staat in de changelog.
- Inloggen gaat nog met de hand: je kopieert de code via F12 uit het netwerkverkeer.
- Zolang een bestelling openstaat voor wijzigingen, kan de add-on de lijst niet lezen of wijzigen.
- Live barcode scannen werkt alleen via https. **Foto maken** werkt altijd.

## Ideeën voor later

- Producten direct aan een openstaande bestelling toevoegen.
- Makkelijker inloggen, zonder F12.

## Credits

AH documenteert de API van de Appie-app niet. Hoe die werkt (inloggen, endpoints, velden) hebben we uit deze open-sourceprojecten gehaald. Bedankt aan de makers:

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

Deze add-on is gevibecoded met [Claude Code](https://claude.com/claude-code) van Anthropic. Claude schreef het grootste deel van de code, de tests en de documentatie, en zocht uit hoe de AH-API werkt. De richting, het testen met een echt AH-account en de keuzes kwamen van mij. Controleer de code dus zelf voordat je erop vertrouwt.
