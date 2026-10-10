# Forward-Filter für Repeater — Handbuch

*🇬🇧 [English version](./forward-filter.md) · 📻 [Flash-Anleitung](./flashing-repeater.de.md)*

Dieses Handbuch beschreibt **alle** Forward-Filter-Funktionen der ACETyr-Repeater-Firmware
(`repeater-v1.17.1.fwdfilterN`) an einer Stelle. Es ersetzt die über die einzelnen Releases verteilten
Beschreibungen — die Release-Notes dokumentieren ab jetzt nur noch, *was sich geändert hat*, dieses
Dokument beschreibt, *was das Gerät kann*.

---

## Das Wichtigste zuerst

**Alle Filter sind ab Werk ausgeschaltet.** Ein frisch geflashter Knoten verhält sich exakt wie ein
Standard-MeshCore-1.17.1-Repeater. Es passiert nichts, solange du nicht selbst etwas einschaltest.

Die Filter greifen ausschließlich **lokal auf diesem einen Knoten** — es gibt keine Protokolländerung,
keine Absprache mit anderen Knoten. Ein Netz aus gemischter Firmware ist unproblematisch, ein einzelner
gefilterter Knoten in einem sonst unveränderten Netz genauso.

Bedient wird alles über die **Admin-CLI**: lokal per USB oder aus der Ferne über Funk
(Remote-Administration in der MeshCore-App, Admin-Login erforderlich). Siehe
[Zugang zur CLI](./flashing-repeater.de.md#zugang-zur-cli).

---

## Alle Befehle auf einen Blick

| Befehl | Werte | Standard | Wirkung |
|---|---|---|---|
| `set fwd.hashfilter` | `off` · `advert` · `all` | `off` | Weiterleitung von Paketen mit 1-Byte-Path-Hash unterbinden |
| `set fwd.hashfilter.prob` | `0`–`100` | `100` | Mit welcher Wahrscheinlichkeit ein Treffer tatsächlich verworfen wird |
| `set fwd.block.add` | `<64-hex> [prune\|advert\|both]` | Aktion `prune` | Knoten in die Policy-Tabelle aufnehmen (max. 16) |
| `set fwd.block.del` | `<hex-Präfix>` | — | Einträge mit passendem Präfix entfernen |
| `set fwd.block.clear` | — | — | Policy-Tabelle leeren |
| `set fwd.whitelist` | `on` · `off` | `off` | Last-Hop-Whitelist scharf schalten |
| `set fwd.whitelist.0hop` | `allow` · `drop` | `allow` | Umgang mit Floods, die noch keinen Hop hinter sich haben |
| `set fwd.whitelist.add` | `<64-hex>` | — | Knoten in die Whitelist aufnehmen (max. 16) |
| `set fwd.whitelist.del` | `<hex-Präfix>` | — | Einträge mit passendem Präfix entfernen |
| `set fwd.whitelist.clear` | — | — | Whitelist leeren |
| `set fwd.scoped.reserve` | `0`–`100` | `0` | Prozent der Airtime-Zuteilung (60-s-Fenster) für Scoped-Traffic freihalten |
| `set fwd.chan.block` | `#name` · `Public` · `<32\|64-hex>` `[Label]` | — | Kanal in die Blockliste aufnehmen (max. 16) |
| `set fwd.chan.unblock` | `#name` · `Public` · `<32\|64-hex>` · `<Index>` | — | Einen Eintrag entfernen |
| `set fwd.chan.clear` | — | — | Blockliste leeren |
| `set flood.max.request` | `0`–`64` | `64` | Hop-Limit für geflutete REQUEST-Pakete |
| `set flood.max.anon.request` | `0`–`64` | `64` | Hop-Limit für geflutete ANON_REQUEST-Pakete |
| `set flood.max.response` | `0`–`64` | `64` | Hop-Limit für geflutete RESPONSE-Pakete |

Zu jedem `set` gibt es ein passendes `get`:

| Befehl | Beispielausgabe |
|---|---|
| `get fwd.hashfilter` | `> advert prob=75` |
| `get fwd.hashfilter.prob` | `> 75` |
| `get fwd.block` | `> 2 entries \| a1b2c3d4e5f6 P \| 9988776655ff PA` |
| `get fwd.whitelist` | `> on 0hop=allow 3 entries \| a1b2c3d4e5f6 \| …` |
| `get fwd.scoped.reserve` | `> 40` |
| `get fwd.scoped.stats` | `> reserve=40% fwd_scoped=812 fwd_unscoped=95 drop_unscoped=1043 saved_air=214500ms air=1180/6000ms/60s` |
| `get fwd.chan` | `> 3 entries \| 2F B2 9C` |
| `get fwd.chan <Index>` | `> 1: #slovakia (B2)` |
| `get fwd.chan.stats` | `> blocked=1832 saved_air=856000ms` |
| `get flood.max.request` | `> 64` |

In den Listenausgaben steht pro Eintrag nur das **6-Byte-Präfix** des Pubkey; bei `get fwd.block`
bedeutet `P` = *prune*, `A` = *advert*. Lange Listen werden in der Anzeige nach rund 140 Zeichen
abgeschnitten — die Einträge selbst bleiben natürlich aktiv, nur die Ausgabe ist gekürzt.

---

## Warum das Ganze

Zwei Probleme, die im laufenden Betrieb großer Netze auftreten:

**1-Byte-Path-Hashes.** Der Path-Hash ist ein Präfix des Node-Pubkey. Bei einem Byte bleiben nur 256
mögliche Werte — in einem Netz mit mehr als ein paar Dutzend Knoten kollidieren die zwangsläufig. Ein
solcher Hop lässt sich keinem Knoten mehr eindeutig zuordnen, und das Direct-Route-Matching kann
mehrdeutig auflösen. Ergebnis: Relay-Traffic, den niemand mehr zurückverfolgen kann, und Pfade, die
falsch abbiegen.

**Unscoped Floods.** Ein nicht konfigurierter Knoten sendet immer ohne Region-Code — das ist das
Standard- und Legacy-Verhalten und aus Kompatibilitätsgründen so gewollt. In der Praxis stellt dieser
Traffic in gewachsenen Netzen aber die Mehrheit und verdrängt die Zustellung zwischen korrekt
konfigurierten Repeatern aus dem Airtime-Budget.

Die Filter geben dem Betreiber Werkzeuge gegen beides — ohne eine Protokolländerung, die alle
mitmachen müssten.

---

## Stufe 1 — Hash-Size-Filter

Verwirft Pakete, deren Path-Hash nur ein Byte breit ist.

```
set fwd.hashfilter off      # aus (Standard)
set fwd.hashfilter advert   # nur Adverts mit 1-Byte-Hash nicht weiterleiten
set fwd.hashfilter all      # jeglichen 1-Byte-Flood- und Direct-Traffic nicht weiterleiten
```

`advert` ist der sanfte Einstieg: Adverts sind der Traffic, der die Routing-Tabellen im Netz mit
mehrdeutigen Einträgen füllt. `all` erfasst zusätzlich Nutzdaten.

Mit der Wahrscheinlichkeit lässt sich das Ganze dosieren statt hart zu schalten:

```
set fwd.hashfilter.prob 100   # jeder Treffer wird verworfen (Standard)
set fwd.hashfilter.prob 75    # drei von vier Treffern werden verworfen
set fwd.hashfilter.prob 0     # kein Treffer wird verworfen (Filter faktisch wirkungslos)
```

Die Wahrscheinlichkeit wirkt auf **alle** Treffer des eingestellten Modus, also im Modus `advert` auch
auf die Adverts. Ein Wert unter 100 ist sinnvoll, wenn du den Druck auf betroffene Nachbarn erhöhen
willst, ohne sie vollständig abzuklemmen — ihre Pakete kommen dann noch durch, nur unzuverlässiger.

---

## Stufe 2 — Policy-Tabelle pro Pubkey

Eine Liste mit bis zu 16 Knoten und jeweils einer von drei Aktionen.

```
set fwd.block.add <64-stelliger-hex-pubkey> prune    # Pfad-Prune (Standard, wenn nichts angegeben)
set fwd.block.add <64-stelliger-hex-pubkey> advert   # Adverts dieses Knotens nicht weiterleiten
set fwd.block.add <64-stelliger-hex-pubkey> both     # beides
```

**`prune`** verwirft Flood-Kopien, deren Pfad über den genannten Knoten gelaufen ist. Der Test läuft
**vor** der Duplikat-Unterdrückung — eine Kopie desselben Pakets, die über einen anderen Pfad
eintrifft, kann also noch gewinnen. Damit steuert man Pfade, statt Pakete zu vernichten: „nimm nicht
den Weg über X, nimm den anderen“. Zuverlässig ist das nur bei Mehrbyte-Hashgrößen, weil der Pfad-Hop
sonst mehrdeutig ist.

**`advert`** unterbindet die Weiterleitung von Adverts, die dieser Knoten selbst ausgesendet hat. Hier
wird der vollständige Pubkey exakt verglichen, das funktioniert daher bei jeder Hashgröße.

Entfernen und prüfen:

```
set fwd.block.del a1b2c3d4      # Präfix genügt, entfernt alle passenden Einträge -> "OK (1 removed)"
set fwd.block.clear             # Tabelle leeren
get fwd.block                   # Inhalt anzeigen
```

Das Hinzufügen eines bereits vorhandenen Pubkey ersetzt dessen Aktion, es entsteht kein Doppeleintrag.

---

## Stufe 3 — Last-Hop-Whitelist

Der schärfste Filter: ein Flood wird nur noch weitergeleitet, wenn sein **unmittelbarer Absender** —
der letzte Hop im Pfad — auf der Erlaubnisliste steht. Alles andere wird verworfen.

```
set fwd.whitelist.add <64-stelliger-hex-pubkey>   # Backbone-Nachbarn eintragen (max. 16)
set fwd.whitelist.del a1b2c3d4                    # Präfix genügt
set fwd.whitelist.clear
get fwd.whitelist
set fwd.whitelist on|off                          # Durchsetzung (Standard: off)
set fwd.whitelist.0hop allow|drop                 # Standard: allow
```

`0hop` betrifft Floods, die noch keinen Hop hinter sich haben, also direkt vom Absender kommen. Da es
hier keinen „letzten Hop“ gibt, den man prüfen könnte, braucht es eine eigene Regel. Standard ist
`allow`, damit direkt gehörte Knoten weiterhin durchkommen.

**Damit du dich nicht selbst aussperrst**, sind drei Paketarten grundsätzlich von der Whitelist
ausgenommen und passieren immer: Adverts, `ANON_REQ` und Floods, die an diesen Knoten selbst adressiert
sind. Der Admin-Login über Funk funktioniert also auch bei falsch gesetzter Whitelist noch.

Der Last-Hop wird auf der Hashgröße des Pakets verglichen. Bei einem 1-Byte-Hash heißt das: 256
mögliche Werte, und jeder fremde Knoten mit demselben Präfix passiert die Whitelist ebenfalls.
**Deshalb `fwd.hashfilter all` zuerst einschalten** — dann greift die Whitelist auf Mehrbyte-Ebene und
der Vergleich ist aussagekräftig.

---

## Stufe 4 — Airtime-Reserve für Scoped-Traffic

```
set fwd.scoped.reserve 0     # aus (Standard)
set fwd.scoped.reserve 40    # 40 % der Airtime-Zuteilung für Scoped-Traffic freihalten
```

Hält den angegebenen Prozentsatz der **Sende-Airtime dieses Knotens** für **scoped** (region-codierten)
Flood-Traffic frei. Reicht die verbleibende Zuteilung nicht mehr für ein weiteres unscoped Paket, ohne
die Reserve anzugreifen, wird dieses Paket verworfen; scoped Floods und sämtlicher Direct-Traffic
laufen unabhängig davon immer durch.

**Bezugsgröße ist ein 60-Sekunden-Fenster, nicht das Stundenbudget.** Die Zuteilung pro Fenster ergibt
sich direkt aus dem eingestellten Duty Cycle:

```
Zuteilung pro Fenster = 60 s × Duty Cycle
```

Bei `set dutycycle 10` sind das 6000 ms je Fenster, also rund zwölf Pakete im SF8-Preset. Eine Reserve
von 40 % hält davon 2400 ms frei: unscoped Floods werden verworfen, sobald dieser Knoten im laufenden
Fenster so viel gesendet hat, dass der Rest für ein weiteres unscoped Paket nicht mehr reicht.

> **Warum nicht das Duty-Cycle-Budget selbst?** Weil sich damit nichts messen lässt. Der Token-Bucket
> im Dispatcher läuft über eine ganze Stunde und hat bei legalen 10 % rund 360 000 ms Spielraum. Ein
> Flood-Sturm aus zwanzig Weiterleitungen kostet ~10 000 ms und verschwindet darin spurlos. Auf dem
> Prüfstand gemessen: Bucket bei 359 325/360 000 ms (99,8 % voll), während der Knoten den Verkehr
> eines belebten Netzes weitergeleitet hat — bei 0,995 % tatsächlichem Duty Cycle und einem Limit von
> 10 %. Eine prozentuale Schwelle über einem dauerhaft vollen Bucket kann nur bei 100 % auslösen. Bis
> einschließlich `fwdfilter7` war die Einstellung deshalb faktisch ein Schalter: 0 = aus, 100 = alle
> unscoped Floods verwerfen, alles dazwischen wirkungslos. Das kurze Fenster ist der eigentliche Fix
> — nicht ein anderer Schwellwert.

Freigehalten wird ausschließlich das **Sendebudget dieses Knotens**, nicht der Funkkanal.

> **Seit Mainline 1.17.1 gehen weniger Antworten unscoped hinaus.** Kann ein Server den Scope einer
> Anfrage nicht auflösen — etwa bei einer Direct-Anfrage, die keinen Transportcode mitbringt —, sendet
> er die Antwort seit 1.17.1 auf seinem eigenen Standard-Scope statt unscoped. Vorher ging sie unscoped
> hinaus und war damit auf jedem Repeater mit gesetzter Reserve ein Kandidat fürs Verwerfen. Login- und
> Admin-Antworten trifft die Reserve dadurch seltener. Darauf verlassen sollte man sich nicht: es wirkt
> nur, wenn der *antwortende* Knoten bereits auf 1.17.1 läuft und eine Standard-Region gesetzt hat —
> ältere Knoten und solche ohne Standard-Region antworten weiterhin unscoped.

### Gemessenes Verhalten

Zwei Durchläufe mit identischer Last (je 93 Flood-Adverts, `dutycycle 10`, also 6000 ms Zuteilung je
Fenster):

| Reserve | weitergeleitet | verworfen | Airtime-Spitze im Fenster |
|---|---|---|---|
| `0` | 93 | 0 | **7733** / 6000 ms — 129 % |
| `50` | 24 | 69 | 2579 / 6000 ms — 43 % |

Ohne Reserve überzieht diese Last die Fensterzuteilung um 29 %. Mit 50 % Reserve leitet der Knoten die
ersten Pakete weiter und hält die Airtime danach flach bei 2577–2579 ms, über alle sieben Messpunkte
hinweg.

Die Reserve **schaltet also nicht ab, sie regelt sich ein.** Am Haltepunkt standen noch 3423 ms zur
Verfügung, gegen eine Schwelle von 2400 ms Reserve plus rund 500 ms für das nächste Paket — der Knoten
lässt gegen eine 50-%-Reserve rund 57 % der Zuteilung frei, statt an einer festen Grenze umzukippen.
Wie viel tatsächlich durchkommt, hängt damit an der Last und nicht am eingestellten Wert allein.

> **Bei sehr niedrigem Duty Cycle vorsichtig einstellen.** Die Zuteilung schrumpft mit, ein einzelnes
> Paket bleibt aber ~500 ms groß. Bei `set dutycycle 1` stehen nur 600 ms je Fenster zur Verfügung —
> ein einziges Paket füllt die Zuteilung fast vollständig aus, und dann verwirft jede Reserve über 0
> praktisch jeden unscoped Flood, unabhängig von der Last. Rechnerisch korrekt, aber selten gewollt.

Wirkung kontrollieren:

```
get fwd.scoped.stats
> reserve=40% fwd_scoped=812 fwd_unscoped=95 drop_unscoped=1043 saved_air=214500ms air=1180/6000ms/60s
```

- `fwd_scoped` / `fwd_unscoped` — weitergeleitete Floods, nach Scope getrennt
- `drop_unscoped` — von der Reserve verworfene Floods
- `saved_air` — dadurch eingesparte Airtime in Millisekunden
- `air` — im laufenden Fenster verbrauchte Sende-Airtime / Zuteilung / Fensterlänge. Das ist die
  Größe, auf die die Reserve schaut: liegt der erste Wert weit unter dem zweiten, greift sie nicht,
  ganz gleich was eingestellt ist

Die Zähler zählen die **Weiterleitungs-Entscheidung**, nicht das bestätigte Senden. Sie liegen im RAM
und **werden bei jedem Neustart auf 0 gesetzt** — das ist Absicht, ein Zähler pro Paket im Flash würde
den nRF52 verschleißen. Für Langzeitstatistik den Wert regelmäßig extern abholen und aufsummieren; ein
Reboot sieht dann einfach wie ein Zähler-Reset aus.

---

## Stufe 5 — Kanal-Blockliste

```
set fwd.chan.block #austria       # Kanal über seinen Namen sperren
set fwd.chan.block Public         # der eingebaute Standardkanal
set fwd.chan.block <32|64-hex>    # Kanal über seinen Schlüssel sperren
set fwd.chan.unblock #austria     # rückgängig — auch über Index oder Schlüssel
set fwd.chan.clear                # Blockliste leeren
```

Verwirft geflutete **Gruppennachrichten** (`GRP_TXT`, `GRP_DATA`), die zu einem der eingetragenen
Kanäle gehören. Alles andere bleibt unberührt: Direktnachrichten, Adverts, Anfragen, und
Gruppennachrichten aller nicht eingetragenen Kanäle.

In den Zahlen unten liegt **21 % der Flood-Airtime** auf Gruppennachrichten — nach den Adverts der
zweitgrößte Posten.

> **Woher die Zahlen stammen, und was sie nicht sind.** Grundlage aller Messwerte in diesem Abschnitt
> ist eine Tagesmessung (2026-08-17) über die Beobachtungsknoten von logger-at, die überwiegend in
> Österreich stehen und Verkehr aus dem mitteleuropäischen Raum mitschneiden. Das ist ein
> **Ausschnitt zu einem Zeitpunkt**, keine Eigenschaft des Netzes: eine andere Woche, eine andere
> Region oder ein anderer Standort ergeben andere Werte. Die Zahlen zeigen die Größenordnung und
> begründen, warum es diese Stufe gibt — was an **deinem** Standort tatsächlich läuft, sagt dir erst
> `get fwd.chan.stats`, nachdem du etwas eingetragen hast.

### Warum nicht einfach über das Hash-Byte

Ein Gruppenpaket trägt seinen Kanal nur als **ein einziges Byte** mit sich, den gekürzten Hash des
Kanalschlüssels. Im mitgeschnittenen Verkehr waren davon **244 von 256 Werten belegt**. Wer auf dieses
Byte filtert, trifft zwangsläufig fremde Kanäle mit, und das Protokoll bietet nichts Längeres an.

Wie stark, hängt vom Byte ab und ist nicht vorhersehbar. Im selben Mitschnitt:

| Byte | gehört wirklich zum gesuchten Kanal |
|---|---|
| `0xD9` (`#test`) | 96 % |
| `0xDD` (`#vienna`) | 77 % |
| `0xB3` (`#hamradio`) | 43 % |
| `0x98` (`#yo`) | 1 % |

Bei `#yo` würde ein Filter auf das Hash-Byte **99 % fremden Verkehr** verwerfen und 1 % Zielverkehr.
Ohne den Schlüssel lassen sich die beiden Fälle nicht auseinanderhalten — genau deshalb arbeitet diese
Stufe anders.

### Der Knoten erkennt den Kanal, ohne ihn lesen zu können

Statt das Hash-Byte zu vergleichen, hinterlegst du den **Kanalschlüssel**. Jedes Gruppenpaket führt
einen 2 Byte langen Authentifizierungscode (MAC) mit sich, der unter genau diesem Schlüssel über den
verschlüsselten Text gebildet wurde. Stimmt er, gehört das Paket zu diesem Kanal — nicht
wahrscheinlich, sondern nachweislich.

Der Filter prüft diesen Code **und hört dann auf**. Er entschlüsselt nichts. Im Empfangspfad der
Firmware folgt auf dieselbe Prüfung ein `decrypt()`; auf dem Filterpfad steht dieser Aufruf nicht, und
zwar nachprüfbar im Quelltext (`src/helpers/ChannelFilter.h`). Ein Repeater kann damit benennen,
welchen Kanal er verwirft, und trotzdem keine einzige Nachricht mitlesen.

Am mitgeschnittenen Verkehr nachgerechnet: auf dem Byte `0xD9` lagen 2130 Pakete, davon 2048 aus
`#test` und 82 aus anderen Kanälen. Der `#test`-Schlüssel erkannte alle 2048 und ließ alle 82 durch.
Ein Filter auf das Hash-Byte hätte alle 2130 verworfen.

Über Funk auf dem Prüfstand gegengeprüft, mit zwei eigens dafür gebauten Kanälen auf demselben
Hash-Byte: der gesperrte wurde verworfen, der andere in derselben Sekunde weitergeleitet.

### Kanäle eintragen

**Über den Namen** — für die öffentlichen Hashtag-Kanäle, die die Apps anbieten:

```
set fwd.chan.block #austria
> OK (hash FB)
```

Der Knoten leitet den Schlüssel aus dem Namen ab, genau wie die Clients es tun. Der Name wird
**buchstabengetreu** genommen: `#ping` trifft, `ping`, `#Ping` und `#PING` treffen nichts. Das 
gehört dazu.

**Der Standardkanal** heißt schlicht `Public`. Er hat keinen `#…`-Namen, sondern einen festen
Schlüssel; dafür gibt es den eingebauten Namen, damit niemand ihn abtippen muss:

```
set fwd.chan.block Public
> OK (hash 11)
```

**Über den Schlüssel** — für alles Übrige, 32 oder 64 Hex-Zeichen, mit optionaler Beschriftung:

```
set fwd.chan.block 4f2b… MeinKanal
> OK (hash 7A)
```

**Anzeigen.** Die Liste zeigt nur die Hash-Bytes, damit sie auch bei voller Tabelle vollständig über
Funk passt; Einzelheiten holst du dir pro Eintrag:

```
get fwd.chan
> 3 entries | 2F B2 9C

get fwd.chan 1
> 1: #slovakia (B2)
```

**Entfernen** geht über Namen, Schlüssel oder Index:

```
set fwd.chan.unblock 1
> OK (1 removed)
```

### Was steckt hinter einem Hash-Byte?

Diese Frage lässt sich auf dem Knoten nicht beantworten — ein Hash ist nicht umkehrbar, und der Knoten
kennt nur die Kanäle, die du selbst eingetragen hast. Sie muss auch nur einmal beantwortet werden,
nämlich bevor du entscheidest, was du sperrst.

Am eigenen Standort weißt du in aller Regel, welche Kanäle laufen: Namen eintragen, `get fwd.chan`
lesen, fertig. Wo das nicht reicht, geht es am Rechner: Kandidatennamen sammeln, aus jedem den
Schlüssel ableiten und ihn gegen echte Pakete per MAC prüfen. Das ist Gewissheit statt Raten unter 256
Möglichkeiten — dasselbe Verfahren, das der Filter selbst benutzt. Ein fertiges Werkzeug dafür liegt
im Projekt unter `reference/corescope_channel_profile.py --identify`.

### Der naheliegendste Fall: Kanäle ohne Bezug zur Region

Im Mitschnitt tauchen **zehn Kanäle** auf, deren Namen auf eine andere Gegend zeigen — `#hungary`,
`#slovakia`, `#kosice`, `#switzerland`, `#polska`, `#turiec`, `#poland`, `#yo`, `#australia` und
`#slovenia`, zusammen **4,8 % der Gruppen-Airtime**. Ihre Pakete waren also auf dem Funk und wurden
weitergereicht.

Ob an **deinem** Standort jemand auf einem davon mitliest, weißt nur du. Genau das ist der Punkt: bei
diesen Kanälen lässt sich die Frage in aller Regel klar beantworten, bei einem belebten lokalen Kanal
nicht — ihn zu sperren ist eine Betreiberentscheidung, die andere Nutzer desselben Repeaters trifft.
Die Firmware nimmt sie dir nicht ab und trifft von sich aus keine.

### Wirkung kontrollieren

```
get fwd.chan.stats
> blocked=1832 saved_air=856000ms
```

- `blocked` — verworfene Gruppenpakete
- `saved_air` — die dadurch eingesparte Airtime in Millisekunden

Wie die anderen Zähler liegen beide im RAM und **stehen nach einem Neustart wieder auf 0**.

### Rechenaufwand

Die Prüfung kostet Rechenzeit, aber nur für Pakete, deren Hash-Byte überhaupt zu einem Eintrag passt —
alle anderen sind nach einem Byte-Vergleich erledigt. Gemessen, ein Treffer:

| | pro Prüfung |
|---|---|
| RAK4631 (nRF52840, Krypto-Hardware) | **210 µs** |
| Heltec V3 (ESP32-S3, Software) | **482 µs** |

Gegen die rund 470 ms, die dasselbe Paket auf dem Funk belegt, sind das **0,1 %**. Ist die Blockliste
leer, entfällt die Prüfung vollständig.

### Was der Knoten dabei speichert

**Ein Repeater speichert keine Kanalschlüssel — außer denen, die du selbst einträgst.** Ein
Standard-Repeater ist keinem Kanal beigetreten und hält keinen einzigen. Erst `set fwd.chan.block`
legt einen Schlüssel in `/fwd_prefs` ab.

Und zwar den **vollständigen** Schlüssel — auch bei der Eingabe über `#name`, wo der Knoten ihn sich
aus dem Namen selbst ausrechnet. Einen halben Schlüssel gibt es nicht: derselbe Schlüssel, der den MAC
prüft, entschlüsselt auch (`Utils::MACThenDecrypt` reicht ihn an beide Schritte weiter). Wer
verifizieren kann, kann grundsätzlich mitlesen — dass *diese* Firmware es nicht tut, ist eine
Eigenschaft des Codes, keine des Schlüssels.

Die Frage ist deshalb nie, *ob* ein ganzer Schlüssel auf dem Gerät liegt, sondern **ob dieser
Schlüssel ein Geheimnis ist.**

Bei den beiden üblichen Fällen ist das folgenlos:

- **`#name`-Kanäle** — der Schlüssel ist der Hash des Namens. Jeder, der den Namen kennt, kann ihn
  ausrechnen. Der Knoten trägt nichts, was ein Angreifer nicht ohnehin hätte.
- **Der `Public`-Kanal** — sein PSK steht im Quelltext der Firmware und in [der FAQ](./faq.md), und
  jedes Companion-Gerät im Netz bringt ihn mit. Ebenfalls kein Geheimnis.

Nur wenn du den PSK eines **wirklich privaten** Kanals einträgst, liegt danach ein echtes Geheimnis
auf dem Gerät — und ein Gerät auf einem Mast lässt sich abbauen und auslesen. Der Schlüssel wäre
derselbe, mit dem sich der Kanal auch mitlesen ließe; dass *diese Firmware* nicht entschlüsselt,
schützt den Schlüssel nicht vor jemandem, der das Gerät in der Hand hält.

Dieser Fall ist selten und meist gar nicht gewollt: einen privaten Kanal kannst du nur sperren, wenn
du selbst Mitglied bist — und dann willst du seinen Verkehr in aller Regel eher weiterleiten als
verwerfen. **Empfehlung: diese Stufe für öffentliche Kanäle verwenden**, und einen privaten Schlüssel
nur nach bewusster Abwägung über ein konkretes Gerät an einem konkreten Ort.

---

## Hop-Limits für geflutete Pakete

```
set flood.max.request 64        # REQUEST      (Standard 64)
set flood.max.anon.request 64   # ANON_REQUEST (Standard 64)
set flood.max.response 64       # RESPONSE     (Standard 64)
```

Begrenzt, wie weit geflutete Pakete dieser Typen laufen dürfen. Der Standard 64 entspricht dem
Maximum und ist damit wirkungslos. Gedacht sind die Limits gegen fehlkonfigurierten
Automatisierungs-Traffic, der das ganze Netz durchquert, obwohl er lokal bleiben sollte.

> ⚠️ **An Backbone-Hochstandorten bei 64 belassen.** Der RF-Admin-Login läuft über
> `ANON_REQUEST`/`RESPONSE`. Wer diese Werte an einem entfernten Knoten zu niedrig setzt, kappt genau
> den Traffic, mit dem er den Knoten wieder erreichen wollte.

(Diese drei Einstellungen stammen aus Mainline-PR #2797 und sind nicht Teil des Forward-Filters im
engeren Sinn, werden aber im selben `/fwd_prefs` gespeichert und über dieselbe CLI bedient.)

---

## Typische Konfigurationen

**„Ich will erst mal nur beobachten.“**
Nichts tun. Der Auslieferungszustand filtert nicht. Regelmäßig `get fwd.scoped.stats` abfragen liefert
dir schon ohne aktiven Filter die Aufteilung scoped/unscoped an deinem Standort.

**„Die 1-Byte-Adverts sollen aufhören.“**
```
set fwd.hashfilter advert
```
Der übliche erste Schritt. Wirkt nur auf Adverts, Nutzdaten bleiben unangetastet.

**„Ein bestimmter Knoten flutet mich zu.“**
```
set fwd.block.add <pubkey> both
get fwd.block
```

**„Der Weg über Knoten X ist schlecht, ich will den anderen Pfad.“**
```
set fwd.block.add <pubkey-von-X> prune
```
Kein Datenverlust — Kopien über andere Pfade gewinnen weiterhin.

**„Mein Backbone-Knoten soll nur noch für den Backbone relayen.“**
Siehe [Sichere Inbetriebnahme](#sichere-inbetriebnahme) — das ist der Fall, bei dem die Reihenfolge
zählt.

**„Unscoped Traffic frisst meine Airtime.“**
```
set fwd.scoped.reserve 40
```
Nach ein paar Stunden `get fwd.scoped.stats` prüfen und den Wert nachziehen. 100 verwirft unscoped
Floods, sobald überhaupt Budgetdruck herrscht.

**„Ich leite Kanäle weiter, die hier niemand hört.“**
```
set fwd.chan.block #hungary
set fwd.chan.block #polska
get fwd.chan
```
Der unstrittige Fall. Vorher aufschreiben, welche Kanäle an deinem Standort tatsächlich gelesen
werden — der Rest ist die Kandidatenliste. Nach einem Tag `get fwd.chan.stats` prüfen: bleibt
`blocked` bei 0, war der Kanal hier ohnehin nicht unterwegs, und der Eintrag kann wieder weg.

---

## Sichere Inbetriebnahme

Für die Whitelist (Stufe 3) — der einzige Filter, mit dem man einen Knoten funktional aus dem Netz
nehmen kann. **Bis Schritt 4 greift nichts ein**, die Schritte 1–3 befüllen und prüfen nur und sind
daher gefahrlos an einem laufenden Knoten durchführbar.

1. **Die echten Backbone-Nachbarn ermitteln** — aus aktiver Relay-Adjazenz bzw. TRACE, **nicht** aus
   der Nachbartabelle des Geräts. Die listet Knoten, die du *hörst*, nicht die, die deinen Traffic
   tatsächlich weiterleiten. Das ist der häufigste Fehler an dieser Stelle.

2. **Bei weiterhin ausgeschalteter Whitelist** jeden bestätigten Pubkey eintragen:
   ```
   set fwd.whitelist.add <64hex>
   ```
   Das befüllt nur die Tabelle, an der Weiterleitung ändert sich nichts.

3. **Tabelle prüfen** — `get fwd.whitelist`. Steht dort genau das, was du erwartest?

4. **Erst jetzt scharf schalten**, und in dieser Reihenfolge:
   ```
   set fwd.hashfilter all
   set fwd.whitelist on
   ```
   Der Hashfilter zuerst, damit die Whitelist auf Mehrbyte-Ebene vergleicht statt auf
   kollisionsanfälligem 1-Byte. `0hop allow` (Standard) belassen, bis bestätigt ist, dass der Backbone
   weiterhin über diesen Knoten läuft.

**Rückweg — jederzeit:**
```
set fwd.whitelist off
set fwd.hashfilter off
```

> ⚠️ **Vorsicht bei entfernten Knoten und Masten.** Mit aktiver Whitelist relayt der Knoten für keinen
> nicht gelisteten Last-Hop mehr. Der Admin-*Login* funktioniert weiterhin (Adverts und `ANON_REQ` sind
> grundsätzlich ausgenommen), aber Mehr-Hop-Pfade **durch** diesen Knoten zu dahinterliegenden Knoten
> brechen ab, wenn die Whitelist unvollständig ist. Vor Schritt 4 an einem Standort ohne Backhaul einen
> Rückweg sicherstellen: lokal über USB/BLE erreichbar, oder ein Knoten, über den du noch hinkommst.

---

## Wo die Einstellungen liegen

Alle `fwd.*`- und `flood.max.*`-Einstellungen werden in einer eigenen Datei **`/fwd_prefs`** im
Dateisystem des Knotens gespeichert, in einem selbstbeschreibenden TLV-Format. Die
Mainline-Einstellungen liegen davon vollständig getrennt in ihrer eigenen Datei — seit 1.17 ist das
`/prefs.json`, davor war es der Blob `/com_prefs`.

Das ist keine Kosmetik: Würden die Filter-Felder in der Mainline-Datei mitgeschrieben, könnte ein
Mainline-Merge, der dort ein Feld einfügt, die Positionen verschieben — und dann werden Funk- oder
Regionseinstellungen still gegen Filterwerte verrechnet. Durch die Trennung kann das
konstruktionsbedingt nicht passieren. Der Wechsel des Mainline-Formats von `/com_prefs` auf
`/prefs.json` in 1.17 ist genau dieser Fall: `/fwd_prefs` war davon nicht betroffen.

Praktische Folgen:

- **Wechsel zwischen Fork und Mainline-Firmware** verliert nur die Filterkonfiguration. Funk-, Regions-
  und Identitätseinstellungen bleiben erhalten.
- **Ältere Firmware liest neuere `/fwd_prefs`** und ignoriert unbekannte Felder. Fehlt ein Feld, gilt
  der Standardwert — also „aus“.
- **Beim Update von fwdfilter3 auf fwdfilter4 oder neuer** wird die Filterkonfiguration einmalig auf
  Standardwerte zurückgesetzt (Umstellung von `/com_prefs` auf `/fwd_prefs`). Whitelist- und
  Blacklist-Einträge danach neu setzen. Funk- und Regionseinstellungen bleiben erhalten. Zwischen
  fwdfilter4 und allen neueren Versionen bleibt die Konfiguration erhalten.
- **Beim Update auf fwdfilter8** wandern die *Mainline*-Einstellungen einmalig von `/com_prefs` nach
  `/prefs.json`. Die Filterkonfiguration ist davon nicht betroffen, ein Rückschritt auf ältere Firmware
  hat aber Folgen — siehe
  [Downgrade nach einem Update auf fwdfilter8](./flashing-repeater.de.md#downgrade-nach-einem-update-auf-fwdfilter8).

---

## Versionsverlauf

| Version | Datum | Was dazukam |
|---|---|---|
| `fwdfilter1` | 2026-06-16 | Stufe 1 (Hash-Size-Filter) + Stufe 2 (Policy-Tabelle) |
| `fwdfilter2` | 2026-06-17 | Stufe 3 (Last-Hop-Whitelist) — **überholt, nicht verwenden** |
| `fwdfilter3` | 2026-06-17 | Fix: Puffer-Überlauf bei `get fwd.whitelist`/`fwd.block` über Funk |
| `fwdfilter4` | 2026-06-20 | Eigene `/fwd_prefs`-Datei · Neuaufsetzen auf Mainline · `flood.max.*` · `get fwd.hashfilter.prob` |
| `fwdfilter5` | 2026-06-21 | Neues Build-Ziel SenseCAP Solar Node P1 (keine Funktionsänderung) |
| `fwdfilter6` | 2026-07-10 | Stufe 4 (`fwd.scoped.reserve`) + `get fwd.scoped.stats` |
| `fwdfilter7` | 2026-07-13 | Fix: Airtime-Schätzung gegen Fehlercodes abgesichert · Version mit führendem `v` |
| `fwdfilter8` | 2026-08-10 | Basis auf MeshCore 1.17.0 · Fix: Stufe 4 misst über ein 60-s-Fenster statt über den Stundenbucket (1–99 war zuvor wirkungslos) · Fix: Schätzung des Grundrauschens klemmte auf −120 fest · Fix: abgesicherte Airtime-Schätzung brach laufende Sendungen ab |
| `fwdfilter9` | 2026-08-16 | Basis auf MeshCore 1.17.1 · mitgetragene Korrektur der Grundrauschen-Schätzung auf den aktuellen Stand gebracht (keine Änderung an den `fwd.*`-Kommandos) |
| `fwdfilter10` | 2026-08-17 | Stufe 5 (`fwd.chan.block`) + `get fwd.chan` / `get fwd.chan.stats` · am 2026-10-10 Build-Ziel Seeed XIAO nRF52840 + Wio-SX1262 nachgereicht (dieselbe Firmware, keine neue Version) |

**Empfehlung: immer die neueste Version.** Alle älteren enthalten mindestens einen der oben
behobenen Fehler.

---

## Grenzen und offene Punkte

- **Je 16 Einträge** in Whitelist, Policy-Tabelle und Kanal-Blockliste. Das reicht für
  Backbone-Nachbarschaften und für die Kanäle einer Region, nicht für netzweite Listen.
- **Listenausgaben werden gekürzt.** `get fwd.whitelist`/`get fwd.block` zeigen bei voller Tabelle
  nicht alle Einträge an. Die Einträge sind trotzdem aktiv.
- **Statistikzähler sind flüchtig** (siehe Stufe 4) und zählen die Weiterleitungs-Entscheidung, nicht
  das bestätigte Senden.
- **Das Airtime-Fenster ist ein fester 60-Sekunden-Wert**, keine Einstellung. Die Länge ist eine
  Abwägung: kurz genug, dass ein Flood-Sturm sichtbar wird, lang genug, dass einzelne Pakete das
  Ergebnis nicht dominieren. Ein gemessenes Optimum ist sie nicht.
- **Das Fenster ist rollend, nicht gleitend.** Ein Burst, der kurz nach einem Fensterwechsel eintrifft,
  bekommt die volle Zuteilung — die Reserve dämpft anhaltende Last, nicht jede einzelne Spitze.
- **Die Lastmessung oben wurde mit Flood-Adverts gefahren.** Bei gemischtem Realverkehr — größere
  Nutzlasten, andere Airtime pro Paket — ist das Verhalten hergeleitet, nicht gemessen.
- **Die Kanal-Blockliste wirkt nur auf geflutete Gruppenpakete.** Gruppenverkehr, der als Direktpaket
  läuft, geht durch. In der Messung waren das 3 von 13 820 Paketen; die Ausnahme kostet also praktisch
  nichts und hält den Eingriff eng.
- **Ein Kanal, dessen Schlüssel du nicht hast, lässt sich nicht gezielt sperren.** Das ist kein
  Versehen, sondern der Punkt: ohne Schlüssel gibt es nur das Hash-Byte, und das trifft fremde Kanäle
  mit.
- **Ein Fehltreffer ist rechnerisch möglich**, mit rund 1 zu 65 536 je eingetragenem Kanal und Paket —
  der Code ist 2 Byte lang. Bei einer Handvoll Einträgen ist das ohne praktische Bedeutung und
  jedenfalls um Größenordnungen besser als ein Filter auf ein einzelnes Hash-Byte.
- **Path-Prune ist bei 1-Byte-Hashes unzuverlässig**, weil der Pfad-Hop mehrdeutig ist. Bei
  Mehrbyte-Hashes zuverlässig.

Fehler und Rückmeldungen bitte als
[Issue](https://github.com/ACETyr/MeshCore/issues) melden.
