# HAppie

Beheer je Albert Heijn-boodschappenlijst vanuit Home Assistant. De add-on:

- voegt een **HAppie**-paneel toe aan de zijbalk, waarin je AH-producten zoekt (met foto, prijs en bonus) en je lijst beheert;
- heeft een paneel **Ontdekken** met suggesties van AH, wat je *vaak koopt* (uit je online bestellingen) en wat er deze week *voor jou in de bonus* is;
- kan **barcodes scannen**: live met de camera, via een foto, of door de code in te typen;
- toont je **volgende bezorging** en zet die, samen met je lijst, in **sensoren**;
- stuurt een **melding** als je AH-sessie verloopt, en als iets op je lijst of iets wat je vaak koopt in de bonus komt;
- houdt een **To-do-lijst in Home Assistant** in twee richtingen gelijk met de lijst in de **AH-app**. Daardoor werken Assist (*"zet melk op de boodschappenlijst"*), de standaard To-do-kaart en automations meteen.

> ⚠️ De add-on gebruikt de onofficiële API van de AH-app. AH kan die zonder aankondiging wijzigen.

## Installatie

1. Maak eerst een to-do-lijst aan: **Instellingen › Apparaten & diensten › Integratie toevoegen › Lokale to-do**, met de naam `Boodschappen` (dat wordt `todo.boodschappen`).
2. Installeer de add-on, kijk de configuratie na en start hem.
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

Daarna ververst de add-on de token zelf. Je wachtwoord wordt nooit opgeslagen.

## Configuratie

| Optie | Uitleg |
|---|---|
| `todo_entity` | De to-do-entiteit die gesynchroniseerd wordt. |
| `sync_interval` | Hoe vaak (in seconden) de AH-lijst opgehaald wordt. Wijzigingen in HA gaan meteen door. |
| `auto_match_products` | Iets wat je in HA toevoegt (bijv. via spraak) wordt als het best passende AH-product op de lijst gezet, niet als losse tekst. |
| `bonus_notifications` | Melding als iets op je lijst, of iets wat je vaak koopt, in de bonus komt. Je krijgt per aanbieding één melding. |
| `notify_service` | Optioneel, bijv. `notify.mobile_app_telefoon`. Dan gaan meldingen ook naar je telefoon. |
| `week_budget` | Optioneel weekbudget in euro (0 = uit). Je krijgt een waarschuwing als wat je deze week uitgaf plus je lijst erboven komt. |
| `log_level` | Hoeveel er gelogd wordt. |

## Sensoren

| Sensor | Waarde |
|---|---|
| `sensor.happie_volgende_bezorging` | Begin van het tijdvak; datum, tijdvak, wijzigtermijn, aantal artikelen, de artikelen zelf (`products`) en, als de bestelling onderweg is, het verwachte venster (`eta_window`, `eta_start`, `eta_end`, `eta_message`) als attributen |
| `sensor.happie_lijst_items` | Aantal open items; de items zelf als attribuut |
| `sensor.happie_geschatte_kosten` | Geschatte kosten van de open items (EUR) |
| `sensor.happie_bonus_items` | Aantal items op je lijst dat in de bonus is |
| `sensor.happie_voorraad` | Aantal producten op voorraad; items, totaal en wat op is als attributen |
| `sensor.happie_uitgaven_week` | Uitgegeven deze week (EUR, maandag t/m zondag); `online`, `winkel`, `previous`, `avg_week` en bij een budget `budget_remaining` als attributen |
| `sensor.happie_uitgaven_maand` | Uitgegeven deze maand (EUR); `online`, `winkel` en `previous` als attributen |
| `binary_sensor.happie_boven_budget` | `on` als uitgegeven deze week + je lijst boven `week_budget` komt (alleen met een budget) |

## Bestellingen

Klik op de bezorgtegel bovenaan voor je bestelling:

- alle artikelen per categorie, met foto, aantal en een indicatieprijs (AH geeft per artikel geen betaalde prijs, wel het totaal van de bestelling met korting);
- een markering **ook op lijst** bij producten die ook nog op je boodschappenlijst staan, zodat je niets dubbel koopt;
- met de tabbladen je komende bestellingen en je laatste bezorgde bestellingen. Een vaste bezorging die je nog niet gevuld hebt is leeg;
- bij een bezorgde bestelling: **Uitpakken naar voorraad**.

## Uitgaven

Bovenaan staat de tegel *Uitgegeven deze week*. Klik erop voor het overzicht: een staafgrafiek per week of per maand (online bestellingen en winkelaankopen apart), je gemiddelde per week en je laatste aankopen.

- **Bronnen**: afgeleverde online bestellingen (het betaalde totaal) en je kassabonnen uit de winkel, net als in de AH-app onder *Kassabonnen*. Daarvoor moet je bonuskaart aan je account gekoppeld zijn. Lukt het ophalen van kassabonnen niet, dan zie je alleen online bestellingen en staat dat in het overzicht.
- **Verversen**: elke 6 uur, direct nadat een bestelling is afgeleverd, en met ↻ in het overzicht. De add-on bewaart ruim een jaar aan aankopen.
- **Weekbudget**: zet `week_budget` in de configuratie. De tegel toont dan hoeveel je nog over hebt als je je lijst erbij optelt. Kom je erboven, dan zie je een waarschuwing in het paneel en krijg je één melding per week (ook op je telefoon met `notify_service`). De melding verdwijnt weer als je eronder zakt.

## Voorraad

Switch to **Voorraad** at the top (on a phone: the *Voorraad* tab) to keep track of what you have at home.

- **Adding**: search for a product, or press **Scannen**. A product without a barcode can be added as your own product.
- **Scan mode**:
  - *Kiezen*: after each scan you choose +1, −1 or a count.
  - *Inruimen +1* / *Verbruiken −1*: every scan updates the stock right away, and live scanning carries on by itself. Handy when unpacking or keeping count.
- **Unknown barcode**: give it a name, or pick the AH product. From then on the barcode is recognised.
- **Bestelling uitpakken**: after a delivery, use *Uitpakken* to add every product from that order. An order can't be counted twice.
- **Op**: when something reaches 0 you get a notice with **Op de lijst**. The 🛒 button on each row does the same.
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
- Toevoegen, afvinken en verwijderen gaat in beide richtingen. De add-on onthoudt de vorige stand, zodat hij weet aan welke kant iets veranderd is.
- Bij de eerste sync worden beide lijsten samengevoegd. Er wordt dan niets verwijderd.
- Getest op 19-11-2026 met een echt account: toevoegen (product en tekst), afvinken en verwijderen werken in beide richtingen.
- Werkt verwijderen bij AH ooit niet meer (de API is onofficieel), dan meldt het paneel dat. Haal het item dan weg in de AH-app.
