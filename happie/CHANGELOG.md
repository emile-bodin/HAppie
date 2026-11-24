# Changelog

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
