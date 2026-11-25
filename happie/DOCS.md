# HAppie

Beheer je Albert Heijn-boodschappenlijst vanuit Home Assistant. De app:

- voegt een **HAppie**-paneel toe aan de zijbalk, waarin je AH-producten zoekt (met foto, prijs en bonus) en je lijst beheert;
- heeft een paneel **Ontdekken** met suggesties van AH, wat je *vaak koopt* (uit je online bestellingen) en wat er deze week *voor jou in de bonus* is;
- kan **barcodes scannen**: live met de camera, via een foto, of door de code in te typen;
- toont je **volgende bezorging** en zet die, samen met je lijst, in **sensoren**;
- stuurt een **melding** als je AH-sessie verloopt, en als iets op je lijst of iets wat je vaak koopt in de bonus komt;
- houdt een **To-do-lijst in Home Assistant** in twee richtingen gelijk met de lijst in de **AH-app**. Daardoor werken Assist (*"zet melk op de boodschappenlijst"*), de standaard To-do-kaart en automations meteen.

> ⚠️ De app gebruikt de onofficiële API van de AH-app. AH kan die zonder aankondiging wijzigen.

## Installatie

1. Maak eerst een to-do-lijst aan: **Instellingen › Apparaten & diensten › Integratie toevoegen › Lokale to-do**, met de naam `Boodschappen` (dat wordt `todo.boodschappen`).
2. Installeer de app, kijk de configuratie na en start hem.
3. Open **HAppie** in de zijbalk en koppel je AH-account (zie hieronder).

## AH-account koppelen

AH stuurt na het inloggen door naar `appie://login-exit?code=…`. Die link werkt alleen in de app van AH. Een browser laat hem stilletjes vallen, en daarom heeft HAppie een eigen hulpje: de bladwijzer **HAppie-koppelen**. Die draait op de pagina van AH zelf, luistert mee tijdens het inloggen en geeft de code aan HAppie. Aan het formulier en de captcha van AH verandert niets. Je hoeft niets te installeren.

1. **Eenmalig:** sleep in het paneel de knop *HAppie-koppelen* naar je bladwijzerbalk (zie je geen balk, druk dan op `Ctrl+Shift+B`).
2. Klik in het paneel op **Open de AH-loginpagina**. De pagina opent in een nieuw tabblad. Log nog niet in.
3. Klik op de AH-pagina op **HAppie-koppelen** in je bladwijzerbalk. Bovenaan verschijnt een blauwe balk: *HAppie luistert mee*.
4. Log in. HAppie pakt de code zelf op en koppelt je account. Het AH-tabblad sluit, of gaat zelf door naar HAppie (de code staat dan even in de adresbalk achter `#`, wordt niet naar een server gestuurd en verdwijnt meteen).

Komt de code niet vanzelf aan, dan zie je hem in de blauwe balk met een knop **Kopieer code**. Plak hem in het paneel en klik op **Koppelen**. De code is maar kort geldig.

**Lukt het niet met de bladwijzer?** Dan vind je de code met de ontwikkelaarstools:

1. Open in een computerbrowser de ontwikkelaarstools (`F12`), tabblad **Netwerk**, en zet **Log behouden** aan.
2. Open in het paneel onder *Lukt het niet?* de AH-loginpagina in datzelfde tabblad en log in.
3. Zoek in het Netwerk-tabblad met `Ctrl+F` (zoekt ook in de antwoorden) naar `login-exit`. Die tekst staat in het antwoord van het verzoek `ingelogd`. Kopieer `appie://login-exit?code=…` en plak het in het paneel.

Daarna ververst de app de token zelf. Je wachtwoord wordt nooit opgeslagen.

## Configuratie

| Optie | Uitleg |
|---|---|
| `todo_entity` | De to-do-entiteit die gesynchroniseerd wordt. |
| `sync_interval` | Hoe vaak (in seconden, 15 tot 3600) de AH-lijst opgehaald wordt, of `0` voor alleen handmatig. Een waarde onder 15 wordt 15. Wijzigingen in HA gaan meteen door. Ook in te stellen in het profielmenu van het paneel (zie hieronder). |
| `auto_match_products` | Iets wat je in HA toevoegt (bijv. via spraak) wordt als het best passende AH-product op de lijst gezet, niet als losse tekst. |
| `bonus_notifications` | Melding als iets op je lijst, of iets wat je vaak koopt, in de bonus komt. Je krijgt per aanbieding één melding. |
| `notify_service` | Optioneel, bijv. `notify.mobile_app_telefoon`. Dan gaan meldingen ook naar je telefoon. |
| `week_budget` | Optioneel weekbudget in euro (0 = uit). Je krijgt een waarschuwing als wat je deze week uitgaf plus je lijst erboven komt. |
| `month_budget` | Optioneel maandbudget in euro (0 = uit). De pagina Uitgaven toont dan per maand hoeveel je nog over hebt, met je lijst erbij, en je krijgt een melding als je erboven komt. |
| `log_level` | Hoeveel er gelogd wordt. |

### Synchroniseren instellen in het paneel

Klik rechtsboven op je profiel. Met de schakelaar **Automatisch** zet je het automatisch synchroniseren aan of uit. Staat hij aan, dan kies je bij **Interval** hoe vaak HAppie wijzigingen uit de AH-app ophaalt, van elke 15 seconden tot elk uur. Staat hij uit, dan synchroniseer je met de knop **Nu synchroniseren**. Je keuze wordt meteen opgeslagen in de configuratie van de app, dus je ziet hem ook hierboven bij `sync_interval`.

Staat *Automatisch* uit, dan gaan wijzigingen in je lijst in Home Assistant (bijvoorbeeld via Assist) en in het paneel nog steeds meteen naar AH. Wat je in de AH-app verandert, komt binnen als je op **Nu synchroniseren** drukt, of bij de volgende sync na een wijziging. De bezorging, de uitgaven en de sensoren worden gewoon bijgewerkt, net als anders.

## Sensoren

| Sensor | Waarde |
|---|---|
| `sensor.happie_volgende_bezorging` | Begin van het tijdvak; datum, tijdvak, wijzigtermijn, aantal artikelen, de artikelen zelf (`products`) en, als de bestelling onderweg is, het verwachte venster (`eta_window`, `eta_start`, `eta_end`, `eta_message`) als attributen. Bij een gereserveerd moment dat nog (bijna) leeg is ook het minimumbedrag (`min_order`) |
| `sensor.happie_lijst_items` | Aantal open items; de items zelf als attribuut |
| `sensor.happie_geschatte_kosten` | Geschatte kosten van de open items (EUR) |
| `sensor.happie_bonus_items` | Aantal items op je lijst dat in de bonus is |
| `sensor.happie_voorraad` | Aantal producten op voorraad; items, totaal en wat op is als attributen |
| `sensor.happie_uitgaven_week` | Uitgegeven deze week (EUR, maandag t/m zondag); `online`, `winkel`, `previous`, `avg_week` en bij een budget `budget_remaining` als attributen |
| `sensor.happie_uitgaven_maand` | Uitgegeven deze maand (EUR); `online`, `winkel`, `previous` en bij een maandbudget `budget_remaining` als attributen |
| `binary_sensor.happie_boven_budget` | `on` als uitgegeven deze week + je lijst boven `week_budget` komt (alleen met een budget) |
| `calendar.happie_bezorging` | Agenda met je volgende bezorging: het tijdvak als afspraak, met aantal artikelen, bedrag en wijzigtermijn in de beschrijving. Alleen de komende bezorging, en alleen met de HAppie-integratie |

## Integratie

De app installeert bij het starten de **HAppie-integratie** in Home Assistant (in `custom_components/happie`). Daarvoor heeft hij schrijftoegang tot de configuratiemap. Je hoeft niets te downloaden of via HACS te installeren.

1. Na de eerste start krijg je een melding: **herstart Home Assistant** (Instellingen › Systeem › Herstarten).
2. Daarna staat HAppie onder **Instellingen › Apparaten & diensten** als gevonden. Klik op **Toevoegen**.

Wat het oplevert: dezelfde sensoren als hierboven, met dezelfde entiteits-ID's, maar nu als echte entiteiten op een apparaat *HAppie*. Je kunt ze hernoemen en in een ruimte zetten, en ze blijven bestaan als Home Assistant herstart. Zonder de integratie maakt de app de sensoren zelf, zoals voorheen.

- Bij een update van de app wordt de integratie ook bijgewerkt; je krijgt dan opnieuw een melding om te herstarten.
- Verschijnt HAppie niet vanzelf, voeg dan de integratie *HAppie* zelf toe en vul het adres van de app in: `http://<slug>-happie:8099`, waarbij `<slug>` de code is die in de adresbalk staat op de pagina van de app (`.../hassio/addon/<slug>_happie`). Bij een app uit een eigen map is het `http://local-happie:8099`.
- Weghalen: verwijder de integratie onder Apparaten & diensten. Na vijf minuten maakt de app de sensoren weer zelf. Verwijder je de app, haal dan ook de map `custom_components/happie` weg en herstart.

## Bestellingen

Klik op de bezorgtegel bovenaan voor je bestelling:

- alle artikelen per categorie, met foto, aantal en een indicatieprijs (AH geeft per artikel geen betaalde prijs, wel het totaal van de bestelling met korting);
- een markering **ook op lijst** bij producten die ook nog op je boodschappenlijst staan, zodat je niets dubbel koopt;
- met de tabbladen je komende bestellingen en je laatste bezorgde bestellingen. Een vaste bezorging die je nog niet gevuld hebt is leeg;
- bij een bezorgde bestelling: **Uitpakken naar voorraad**.

## Uitgaven

Kies bovenaan **Uitgaven** (op een telefoon het tabblad *Uitgaven*), of klik op de tegel *Uitgegeven deze week*. Je ziet:

- **Grafiek** per week of per maand, met online bestellingen en winkelaankopen apart, je gemiddelde, je budget en wat er nu op je lijst staat. Klik op een staaf of gebruik ‹ › om de cijfers van een eerdere periode te zien.
- **Budget**: hoeveel je nog over hebt met je lijst erbij, en voor de laatste 8 weken of maanden of je binnen je budget bleef.
- **Meest gekocht** in de laatste 3 of 12 maanden, online en in de winkel samen: hoe vaak, ongeveer om de hoeveel dagen, of het in de bonus is en of het misschien bijna op is. Met **+ Lijst** zet je het op je lijst.
- **Per categorie**: waar je geld naartoe gaat. Klik op een categorie voor de producten. Bonregels die niet bij een AH-product horen (statiegeld, tasjes, "bakkerij div") staan onder *Niet herkend*. Met **Koppel** kies je zelf een categorie; HAppie onthoudt dat voor dezelfde bonregel.
- **Aankopen**: al je bezorgingen en kassabonnen. Klik erop voor de artikelen.
- **Inzichten**: een prognose voor de maand, wat winkelbezoeken per week kosten, wat een bezorging gemiddeld kost en op welke dag je het meest uitgeeft.

Bedragen per artikel: op een kassabon staat wat je per artikel betaald hebt. Bij een online bestelling geeft AH alleen het totaal, dus daar is het bedrag per artikel een schatting met de huidige prijs (met ± ervoor).

- **Bronnen**: afgeleverde online bestellingen (het betaalde totaal) en je kassabonnen uit de winkel, net als in de AH-app onder *Kassabonnen*. Daarvoor moet je bonuskaart aan je account gekoppeld zijn. Lukt het ophalen van kassabonnen niet, dan zie je alleen online bestellingen en staat dat in het overzicht.
- **Verversen**: elke 6 uur, direct nadat een bestelling is afgeleverd, en met *Bijwerken* op de pagina. De app bewaart ruim een jaar aan aankopen. De artikelen van die aankopen haalt hij op de achtergrond op, elke aankoop één keer; de eerste keer duurt dat een paar minuten.
- **Maandbudget**: zet `month_budget` in de configuratie. De pagina Uitgaven toont het bij *Per maand*. Kom je er met je lijst erbij boven, dan krijg je één melding per maand, net als bij het weekbudget.
- **Weekbudget**: zet `week_budget` in de configuratie. De tegel toont dan hoeveel je nog over hebt als je je lijst erbij optelt. Kom je erboven, dan zie je een waarschuwing in het paneel en krijg je één melding per week (ook op je telefoon met `notify_service`). De melding verdwijnt weer als je eronder zakt.

## Voorraad

Ga bovenaan naar **Voorraad** (op een telefoon: het tabblad *Voorraad*) om bij te houden wat je in huis hebt.

- **Toevoegen**: zoek een product, of druk op **Scannen**. Een product zonder barcode voeg je toe als eigen product.
- **Scanstand**:
  - *Kiezen*: na elke scan kies je +1, −1 of een aantal.
  - *Inruimen +1* / *Verbruiken −1*: elke scan past de voorraad meteen aan, en live scannen gaat vanzelf door. Handig bij het uitpakken of tellen.
- **Onbekende barcode**: geef hem een naam, of kies het AH-product. Daarna wordt de barcode herkend.
- **Bestelling uitpakken**: zet na een bezorging met *Uitpakken* alle producten van die bestelling in je voorraad. Een bestelling telt maar één keer.
- **Op**: staat iets op 0, dan zie je een melding met **Op de lijst**. De 🛒-knop bij elke regel doet hetzelfde.
- In HA: `sensor.happie_voorraad`.

## Barcode scannen

Live scannen met de camera werkt alleen als je Home Assistant via **https** opent (bijv. via Nabu Casa) en je browser camera-toegang geeft. Gaat dat niet, gebruik dan **Foto maken**; dat werkt altijd, ook in de HA-app. Je kunt de barcode ook intypen.

## Voorbeelden

Spraak werkt standaard via Assist: *"Voeg eieren toe aan Boodschappen"*.

Automation, bijvoorbeeld als de wc-papiervoorraad op is:

```yaml
action: todo.add_item
target:
  entity_id: todo.boodschappen
data:
  item: Wc-papier
```

Melding op de bezorgdag, met de sensor `sensor.happie_volgende_bezorging`:

```yaml
triggers:
  - trigger: time
    at: "08:00:00"
conditions:
  - condition: template
    value_template: "{{ state_attr('sensor.happie_volgende_bezorging', 'date') == now().date() | string }}"
actions:
  - action: notify.notify
    data:
      message: "AH bezorgt vandaag tussen {{ state_attr('sensor.happie_volgende_bezorging', 'window') }}"
```

## Hoe de sync werkt

- Items worden gekoppeld op naam (hoofdletters maken niet uit).
- Toevoegen, afvinken en verwijderen gaat in beide richtingen. De app onthoudt de vorige stand, zodat hij weet aan welke kant iets veranderd is.
- Bij de eerste sync worden beide lijsten samengevoegd. Er wordt dan niets verwijderd.
- Getest op 19-11-2026 met een echt account: toevoegen (product en tekst), afvinken en verwijderen werken in beide richtingen.
- Werkt verwijderen bij AH ooit niet meer (de API is onofficieel), dan meldt het paneel dat. Haal het item dan weg in de AH-app.
