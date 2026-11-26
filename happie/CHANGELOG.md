# Changelog

Alle veranderingen per versie, de nieuwste bovenaan. HAppie volgt [Semantic Versioning](https://semver.org/lang/nl/) (`MAJOR.MINOR.PATCH`):

- **PATCH** (0.9.**1**): alleen fouten hersteld; je hoeft niets te doen.
- **MINOR** (0.**10**.0): nieuwe functies of opties; alles wat je had blijft werken.
- **MAJOR** (**1**.0.0): veranderingen waarvoor je zelf iets moet aanpassen, zoals een andere entiteits-ID of een optie die verdwijnt. Zolang de versie met 0. begint, gebeurt zoiets in een MINOR-versie en staat het bovenaan die sectie.

## 0.12.2
- Uitgaven: bij kassabonnen telt nu de bonus mee, net als kortingsstickers, coupons, Air Miles en statiegeld. Daardoor waren de bedragen per artikel, per categorie en bij *Meest gekocht* te hoog; de totalen per week en maand klopten al.
- Op een kassabon zie je per artikel de prijs na bonus, met de oude prijs doorgestreept. Kortingen die niet bij één artikel horen en het statiegeld staan onderaan, met het betaalde bedrag.
- Kassabonnen die al opgehaald waren, haalt HAppie één keer opnieuw op.

## 0.12.1
- Uitgaven, *Per categorie*: een onbekende bonregel koppelen werkt nu ook als de voorgestelde categorie al klopt. Naast de keuzelijst staat een knop *Koppel* om de keuze te bevestigen.
- De keuzelijst sluit niet meer vanzelf terwijl HAppie op de achtergrond nog artikelen ophaalt.

## 0.12.0
- Nieuw: klik op een productfoto (in je lijst, bij zoeken, Ontdekken, Voorraad, bestellingen en uitgaven) om hem groter te zien.
- Nieuw: iets van je lijst weghalen gaat meteen, met *Ongedaan maken* in de melding onderin, in plaats van eerst een vraag.
- Rustiger bovenaan: alleen nog de bezorging, je uitgaven en (als er iets in de bonus is) de bonusitems. Wat je nog moet halen, de geschatte kosten, hoeveel er is afgevinkt en de laatste sync staan nu boven je lijst. Op een telefoon begint de lijst daardoor een stuk hoger.
- Zoeken: tijdens het typen staat er een knop *Toevoegen* in het zoekveld; die doet hetzelfde als Enter.
- Foutmeldingen zijn nu gewone zinnen met wat je kunt doen, in plaats van technische tekst van AH.
- Staat er een bezorgdatum die al voorbij is, dan haalt het paneel de bezorging opnieuw op.
- Uitgaven: de weeknavigatie staat naast de titel en *Bijwerken* is een klein ↻ naast "Bijgewerkt".
- Dunnere vinkjes en knoppen in de lijst, beter leesbare kleuren (ook in het donkere thema) en bedragen die netjes onder elkaar staan.
- Op een telefoon toont een regel alleen het totaalbedrag; producten zonder foto tonen hun eerste letter.
- Het profielmenu blijft zichtbaar als je naar beneden gescrold bent.

## 0.11.1
- Een optie die je op de configuratiepagina hebt veranderd, wordt niet meer teruggezet als je daarna in het paneel het sync-interval aanpast.
- Een sync-interval dat je op de configuratiepagina verandert, geldt binnen 5 minuten, ook zonder herstart. Een waarde onder 15 seconden wordt 15.
- Automatisch synchroniseren uitzetten start niet meer eerst nog een sync.
- Met automatisch synchroniseren uit wordt de bezorging weer elke 5 minuten bijgewerkt.
- Uitgaven: het gemiddelde per weekdag klopt nu ook als je HAppie nog maar kort gebruikt.
- Uitgaven: een aankoop openen gaat meteen, ook terwijl HAppie op de achtergrond nog artikelen ophaalt, en elk product wordt maar één keer opgezocht.

## 0.11.0
- Nieuw: in het profielmenu zet je **Automatisch** synchroniseren aan of uit. Staat het aan, dan kies je hoe vaak HAppie wijzigingen uit de AH-app ophaalt (van elke 15 seconden tot elk uur); staat het uit, dan gebruik je *Nu synchroniseren*. Je keuze wordt opgeslagen in de configuratie van de app.
- Staat het uit, dan gaan wijzigingen in Home Assistant en in het paneel nog wel meteen naar AH; wijzigingen in de AH-app haal je op met *Nu synchroniseren*. De sync-knop bovenaan toont dan "Sync handmatig" met een oranje stip, zonder tijd.
- `sync_interval` mag nu ook 0 zijn (alleen handmatig). Een nieuw interval geldt meteen, zonder herstart.
- De app vraagt nu toegang tot de Supervisor-API, om je instellingen in de configuratie van de app op te slaan.

## 0.10.1
- De agenda *HAppie Bezorging* (`calendar.happie_bezorging`) verschijnt nu ook echt; in Home Assistant 2026.11 werd hij door een fout niet toegevoegd. Na de update vraagt de app om één herstart.

## 0.10.0
- Nieuw: de agenda *HAppie Bezorging* (`calendar.happie_bezorging`) toont je volgende bezorging met het tijdvak, het aantal artikelen, het bedrag en tot wanneer je kunt wijzigen. Handig voor de agendakaart en voor automations zoals "een half uur van tevoren een melding". Na de update vraagt de app om één herstart.
- Nieuw: een melding als je met je lijst erbij boven je maandbudget (`month_budget`) komt, één keer per maand. De sensor *Uitgaven deze maand* heeft nu ook `budget` en `budget_remaining`.
- Je wordt niet meer onterecht uitgelogd als de app op meerdere plekken tegelijk je AH-sessie vernieuwt.
- Is AH of Home Assistant even niet bereikbaar, dan wacht de app steeds langer tussen de pogingen (tot 15 minuten) en staat dezelfde fout niet elke minuut opnieuw in het log.
- De documentatie over Voorraad is nu in het Nederlands.

## 0.9.1
- De HAppie-integratie heeft weer hetzelfde versienummer als de app; onder Apparaten & diensten stond nog 0.8.1. Na de update vraagt de app om één herstart.
- Het apparaat HAppie toont nu de huidige versie onder Apparaten & diensten.
- "Bezoeken" bij het apparaat HAppie opent nu de pagina van de app (log, configuratie) in plaats van het paneel.

## 0.9.0
- Nieuw: een eigen pagina Uitgaven (bovenaan naast Boodschappen en Voorraad, op een telefoon een vijfde tabblad). De tegel *Uitgegeven deze week* opent hem nu, in plaats van het venster van eerst.
- Per week of maand: grafiek met online en winkel, je gemiddelde, wat er op je lijst staat en je budget. Klik op een staaf of gebruik ‹ › om een eerdere periode te bekijken.
- Budget: hoeveel er nog over is met je lijst erbij, en per week of maand of je binnen je budget bleef. Nieuwe optie: een maandbudget (`month_budget`).
- Meest gekocht: wat je het vaakst koopt, online én in de winkel, hoe vaak, ongeveer om de hoeveel dagen en of het nu in de bonus is. Met "+ Lijst" zet je het meteen op je lijst.
- Per categorie: waar je geld naartoe gaat. Klik op een categorie voor de producten. Bonregels die HAppie niet herkent (statiegeld, tasjes) staan apart; met Koppel zet je ze zelf in een categorie.
- Aankopen: klik op een bezorging of kassabon voor de artikelen. Bij kassabonnen zie je wat je per artikel betaald hebt.
- Inzichten: prognose voor de maand, wat winkelbezoeken per week kosten, en op welke dag je het meest uitgeeft.
- De artikelen van je aankopen van het afgelopen jaar worden op de achtergrond opgehaald; de eerste keer duurt dat een paar minuten.

## 0.8.1
- De HAppie-integratie heeft nu een eigen icoon en logo (vanaf Home Assistant 2026.3), en heet overal "HAppie" in plaats van "happie". Na de update vraagt de app om nog één herstart.

## 0.8.0
- Nieuw: de HAppie-integratie. De app installeert die zelf in Home Assistant; na één herstart verschijnt HAppie onder Apparaten & diensten. Klik op Toevoegen.
- Met de integratie zijn de sensoren echte entiteiten op een apparaat "HAppie": je kunt ze hernoemen, in een ruimte zetten en ze blijven bestaan na een herstart van Home Assistant. De entiteits-ID's blijven hetzelfde, dus je automations blijven werken.
- Lange lijsten in de attributen (items, producten) komen niet meer in de geschiedenisdatabase.
- De app vraagt nu schrijftoegang tot de configuratiemap van Home Assistant, om de integratie te installeren.

## 0.7.3
- De +-knoppen bij Ontdekken zijn kleiner en het plusje staat precies in het midden.
- In de tegels bovenaan staan getal, tekst en voortgangsbalk niet meer zo dicht op elkaar.
- Uitgaven: de budgetlijn blijft zichtbaar over de staven heen; het budgetbedrag staat nu in de legenda.
- Uitgaven: onder de grafiek een overzichtelijke kaart per week (online, winkel, aantal aankopen) en een apart blok voor het weekbudget met balk.

## 0.7.2
- De zoekbalk valt bij het typen niet meer half onder de kop: de bovenrand blijft zichtbaar.
- Het barcodeknopje in de zoekbalk staat weer netjes gecentreerd en heeft weer de juiste kleur.

## 0.7.1
- De bezorgkaart is compacter en duidelijker. Staat er nog niets in je gereserveerde bezorgmoment, dan zie je "Vul aan tot € 45 vóór zo 18:00" in plaats van het lange bericht van AH. Zit je onder het minimumbedrag, dan zie je hoeveel er nog bij moet.
- De statusregel op de bezorgkaart blijft op één regel; de volledige tekst staat in de tooltip. De rij met tegels wordt daardoor niet meer onnodig hoog.
- Nieuw attribuut `min_order` op `sensor.happie_volgende_bezorging`: het minimumbedrag dat AH noemt voor een gereserveerd moment.
- Eigen kleuren: het paneel gebruikt nu de kleuren van het HAppie-icoon (petrol en koraal) in plaats van die van Albert Heijn.
- In het donkere thema hebben productfoto's geen fel witte achtergrond meer, maar een zacht grijs vlak.

## 0.7.0
- **Let op: dit verandert je installatie.** De interne naam van de app is nu `happie` in plaats van `appie`, omdat "Appie" een merk van Albert Heijn is. Home Assistant ziet HAppie daardoor als een nieuwe app:
  - Installeer HAppie opnieuw uit de App-winkel en verwijder daarna de oude versie. Neem je opties (to-do-lijst, weekbudget, meldingen) over.
  - Koppel je AH-account opnieuw. Je voorraad begint leeg en je uitgaven worden opnieuw opgehaald bij AH. De eerste sync voegt je lijst en je to-do-lijst samen zonder iets te verwijderen. Lopende bonusmeldingen kun je nog één keer krijgen.
  - De entiteiten heten nu `sensor.happie_*` en `binary_sensor.happie_*` (was `appie_*`). Pas je automations, scripts en dashboards daarop aan.
- In alle teksten heet de app van Albert Heijn nu "de AH-app".
- **Makkelijker inloggen, zonder F12**: sleep de bladwijzer *HAppie-koppelen* uit het paneel naar je bladwijzerbalk en klik erop op de AH-loginpagina voordat je inlogt. HAppie pakt de code dan zelf op en koppelt je account. De oude manier met de ontwikkelaarstools blijft beschikbaar.

## 0.6.2
- Eén image voor amd64 en aarch64 (`ghcr.io/emile-bodin/happie`), volgens de huidige richtlijnen van Home Assistant. HA kiest automatisch de juiste versie voor jouw processor.

## 0.6.1
- **Fix:** in de container kwam de omgeving van Home Assistant niet bij de app aan (onder andere de toegang tot HA). Daardoor werkten de sync met je to-do-lijst, de sensoren en meldingen niet in een echte installatie.
- Gebouwd volgens de nieuwe werkwijze van Home Assistant (Docker BuildKit) op een actuele basis (Alpine 3.24), met beveiligingsupdates.
- Eigen icoon en logo in de App-winkel.

## 0.6.0
- Te installeren via GitHub: voeg https://github.com/emile-bodin/HAppie toe als repository in de App-winkel. Kant-en-klare images voor amd64 en aarch64 worden automatisch gebouwd.
- Nieuwe naam: **HAppie**. In de zijbalk heet het paneel nu *HAppie*. Entiteiten (`sensor.appie_*`) en de slug blijven gelijk, dus je automations blijven werken.
- **Uitgavenoverzicht**: wat je per week en per maand bij AH uitgeeft, uit je online bestellingen én je kassabonnen uit de winkel.
  - Nieuwe tegel *Uitgegeven deze week* bovenaan. Klik erop voor een staafgrafiek (per week of per maand, online en winkel apart), kerncijfers en je laatste aankopen.
  - Sensoren `sensor.appie_uitgaven_week` en `sensor.appie_uitgaven_maand` (EUR, met online/winkel, vorige periode en weekgemiddelde als attributen). Ze tellen mee in de langetermijnstatistiek van HA.
- **Verwachte bezorgtijd**: is je bestelling onderweg, dan toont de bezorgtegel het nauwere venster dat AH doorgeeft (bijv. *Verwacht 20:40–21:40*). Op `sensor.appie_volgende_bezorging` staan `eta_window`, `eta_start`, `eta_end` en `eta_message`, handig voor een melding als de boodschappen bijna komen.
- **Je bestelling bekijken**: klik op de bezorgtegel voor alle artikelen van je volgende bezorging, per categorie met foto en aantal, en het totaal met korting. Producten die ook nog op je boodschappenlijst staan krijgen een markering. Met de tabbladen bekijk je ook eerdere bestellingen, en een bezorgde bestelling pak je hier direct uit naar je voorraad. `sensor.appie_volgende_bezorging` heeft nu ook de artikelen als attribuut `products`.
- **Weekbudget** (optie `week_budget`, 0 = uit): de tegel laat zien hoeveel je nog over hebt als je je lijst erbij optelt. Kom je erboven, dan zie je een waarschuwing in het paneel en krijg je één melding per week. Plus `binary_sensor.appie_boven_budget` voor automations.
- **Voorraadbeheer**: een nieuwe weergave *Voorraad* (een schakelaar in de bovenbalk; op een telefoon een 4e tabblad).
  - Voeg producten toe door te **zoeken** of de **barcode te scannen** (camera, foto of de code intypen).
  - Scanstanden: *Kiezen* (per scan +1, −1 of een aantal kiezen), *Inruimen +1* en *Verbruiken −1* om snel achter elkaar te scannen (live scannen start vanzelf opnieuw).
  - Onbekende barcodes (bijv. van producten die niet van AH zijn) koppel je één keer aan een naam of AH-product. Daarna worden ze herkend.
  - **Bestelling uitpakken**: zet alles uit een bezorgde bestelling in één keer in je voorraad (elke bestelling maar één keer).
  - Voorraad per categorie, met een filter, −/+, tik op een aantal om het te wijzigen, en een knop om een product op je boodschappenlijst te zetten. Is iets op, dan krijg je een melding met **Op de lijst**.
- Nieuwe sensor `sensor.appie_voorraad` (producten op voorraad; artikelen, totaal aantal stuks en lege producten als attributen).

## 0.5.1
- Bonusprijzen worden nu meegerekend, zowel per regel als in de geschatte kosten (dashboard en sensor). Ondersteund: "2 voor 3.99", "2 + 1 gratis", "2e halve prijs", "25% korting", "VOOR 1.99", "1 euro korting", en prijzen waar AH de korting al in verwerkt (bijv. "volume voordeel").
- Bonusvoordeel staat bij de geschatte kosten, en als `bonus_saving` op `sensor.appie_geschatte_kosten`.
- Een hint als je nog iets extra moet pakken voor de bonus, bijv. "nog 1 voor 2 voor 3.99".
- "✓ op lijst" in Ontdekken volgt nu je actuele lijst.

## 0.5.0
- Paneel "Ontdekken" met drie tabbladen: *Voor jou* (AH-suggesties), *Vaak gekocht* (uit je laatste 8 online bestellingen) en *Bonus* (persoonlijke bonus, plus eerder gekochte producten die nu in de bonus zijn).
- Barcode scannen: live met de camera, via een foto, of door de code in te typen.
- Sensoren: `sensor.appie_lijst_items`, `sensor.appie_geschatte_kosten`, `sensor.appie_bonus_items`.
- Melding in HA als je AH-sessie verloopt. Die verdwijnt weer zodra je opnieuw inlogt.
- Bonusmeldingen: één keer per aanbieding, voor items op je lijst en producten die je vaak koopt. Optioneel ook naar je telefoon via `notify_service`.
- Volgende bezorging werkt nu ook voor bevestigde bestellingen.

## 0.4.0
- Volgende bezorging in het dashboard: dag, tijdvak, tot wanneer je kunt wijzigen, aantal artikelen en totaalbedrag.
- Nieuwe sensor `sensor.appie_volgende_bezorging` in Home Assistant (tijdstempel van het begin van het tijdvak, met de details als attributen), te gebruiken in automations.
- Staat een bestelling open voor wijzigingen, dan vergrendelt AH de boodschappenlijst. De sync pauzeert dan zonder iets te verwijderen, en het dashboard legt uit waarom.

## 0.3.0
- Nieuw dashboard dat zich aanpast aan je scherm: drie kolommen op een computer, twee op een tablet, tabbladen op een telefoon.
- Bovenaan cijfers: te halen, geschatte kosten, bonusitems en hoeveel er al is afgevinkt.
- Je AH-accountnaam en inlogstatus in de bovenbalk, met een menu om te synchroniseren, uit te loggen of opnieuw in te loggen.

## 0.2.0
- "Suggesties voor jou": persoonlijke AH-suggesties in het paneel, met één klik op de lijst.

## 0.1.0
- Eerste versie: paneel met AH-productzoeker en lijstbeheer, tweewegsync met een HA-to-do-lijst.
