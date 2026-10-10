# Repeater-Firmware flashen — Anleitung

*🇬🇧 [English version](./flashing-repeater.md) · ⚙️ [Forward-Filter-Handbuch](./forward-filter.de.md)*

Diese Anleitung beschreibt, wie du die ACETyr-Repeater-Firmware
(`repeater-v1.17.0.fwdfilterN`) auf ein Gerät bekommst — mit dem Webflasher, per esptool und über
Funk (OTA).

Der **[MeshCore-Webflasher](https://flasher.meshcore.io)** ist der empfohlene Weg, so wie bei der
offiziellen Firmware auch. In der Geräteliste steht er nicht — diese Firmware wird nicht über den
Flasher *verteilt* — aber er kann sie flashen: über den Eintrag **„Custom Firmware“** ganz unten in der
Geräteliste lädst du die Datei aus den
[Releases dieses Forks](https://github.com/ACETyr/MeshCore/releases) direkt von deinem Rechner.

---

## Schritt 1 — Die richtige Datei herunterladen

Immer die **neueste** Release-Version nehmen ([Releases](https://github.com/ACETyr/MeshCore/releases)),
ältere enthalten behobene Fehler. Welche der Dateien du brauchst, hängt vom Board ab —
und davon, ob du **updaten** oder **neu aufsetzen** willst:

| Board | Update (Konfiguration bleibt) | Erstflash / komplett neu | OTA über Funk |
|---|---|---|---|
| **RAK4631** (nRF52840) | `…​.zip` | `…​.zip` | `…​.zip` |
| **Heltec V3** (ESP32-S3) | `…​.bin` (**ohne** `merged`) | `…​-merged.bin` | `…​.bin` (**ohne** `merged`) |
| **SenseCAP Solar Node P1** (nRF52840) | `…​.zip` | `…​.zip` | `…​.zip` |
| **Seeed XIAO nRF52840 + Wio-SX1262** | `…​.zip` | `…​.zip` | `…​.zip` |

Bei den nRF52-Boards ist es immer dieselbe `.zip` — ein DFU-Paket, das nur die Anwendung ersetzt und
Konfiguration wie Identität in Ruhe lässt. Die zusätzlich beiliegende `.uf2` ist eine Alternative für
den Drag-and-Drop-Weg ohne Flasher (siehe [Weg C](#weg-c--rak4631--sensecap-p1-per-uf2-drag-and-drop)),
der Webflasher nimmt sie **nicht** an.

Bei Heltec V3 hängt alles an dieser einen Unterscheidung:

> ⚠️ **`-merged.bin` löscht den gesamten Flash — inklusive Geräteidentität.**
> Sie enthält Bootloader, Partitionstabelle und Anwendung, wird an Adresse `0x0` geschrieben, und der
> Webflasher führt dabei einen vollständigen Chip-Erase durch (er warnt dich auch selbst davor). Danach
> hat der Knoten einen **neuen Pubkey** und muss überall neu eingetragen werden.
>
> **Zum Aktualisieren eines laufenden Knotens die einfache `.bin` ohne `merged` im Namen nehmen.** Sie
> ersetzt nur die Anwendung; Name, Passwort, Funk- und Regionseinstellungen sowie die Identität bleiben
> erhalten. Dieselbe Datei wird auch für OTA verwendet.

> ℹ️ Beim **SenseCAP Solar Node P1** ist bisher nur geprüft, dass er sich **fehlerfrei bauen lässt —
> auf echter Hardware getestet ist er nicht**, es stand kein Gerät zur Verfügung. Der Filter-Code ist
> boardunabhängig und übersetzt sauber, aber behandle diese Binaries als ungeprüft. Rückmeldungen von
> P1-Betreibern sind ausdrücklich willkommen.

> ℹ️ Die **XIAO-Firmware** ist auf dem Kit aus XIAO nRF52840 und aufgestecktem **Wio-SX1262**
> getestet (Seeed-Artikel 102010710) und setzt genau dessen Pinbelegung voraus. Ein XIAO mit anderem
> LoRa-Modul — etwa einem E22 oder der Wio-SX1262-Variante mit 30-poligem Board-to-Board-Stecker —
> funktioniert mit diesem Image nicht.

---

## Schritt 2 — Flashen

### Weg A — Webflasher (empfohlen)

Browser: **Chrome oder Edge**. Firefox und Safari können kein WebSerial und funktionieren nicht.

1. <https://flasher.meshcore.io> öffnen.
   *(Der Flasher der österreichischen Community unter <https://flasher.meshcore-austria.at> ist ein Fork
   davon und verhält sich identisch — beide funktionieren.)*
2. In der Geräteliste **nicht** dein Board auswählen, sondern ganz unten **„Custom Firmware“**
   anklicken und die heruntergeladene Datei aus Schritt 1 auswählen. Der Flasher erkennt am Dateityp
   selbst, worum es sich handelt: `.zip` → nRF52, `.bin` → ESP32.
3. Gerät per USB anstecken.
4. **Nur bei den nRF52-Boards (RAK4631, SenseCAP P1, XIAO):** das Gerät in den DFU-Modus bringen —
   entweder mit der Schaltfläche **„Enter DFU mode“** im Flasher, oder von Hand durch **zweimaliges
   kurzes Drücken der Reset-Taste**. Der XIAO meldet sich im DFU-Modus unter einem **anderen
   seriellen Port** an als im Betrieb — im nächsten Schritt also den neu aufgetauchten Port wählen.
5. Flashen starten, seriellen Port auswählen, warten.

Wählst du eine `-merged.bin`, zeigt der Flasher eine Warnung, dass der Flash gelöscht wird — das ist
korrekt und gewollt, siehe oben. Beim Update willst du diese Warnung *nicht* sehen.

### Weg B — Heltec V3 mit esptool (Kommandozeile)

Für Skripte und Massenflash. `pip install esptool`, dann:

```bash
# Update eines laufenden Knotens — Konfiguration bleibt erhalten
esptool.py --chip esp32s3 --port COM5 --baud 921600 write_flash 0x10000 Heltec_v3_repeater-v1.17.0.fwdfilter8-<sha>.bin

# Erstflash / komplett neu aufsetzen — löscht die Identität
esptool.py --chip esp32s3 --port COM5 --baud 921600 write_flash 0x0 Heltec_v3_repeater-v1.17.0.fwdfilter8-<sha>-merged.bin
```

`<sha>` ist der Commit-Kurzhash im Namen der heruntergeladenen Datei — einfach den tatsächlichen
Dateinamen aus dem Release einsetzen.

Unter Linux/macOS statt `COM5` den passenden Port angeben (`/dev/ttyUSB0`, `/dev/cu.usbserial-…`).
Bei Verbindungsproblemen die Baudrate auf `115200` senken.

### Weg C — RAK4631 / SenseCAP P1 per UF2 (Drag and Drop)

Ohne jedes Werkzeug, nur Dateimanager. Kann den Knoten nicht unbrauchbar machen.

1. Gerät per USB anstecken.
2. **Reset-Taste zweimal kurz hintereinander drücken.** Es erscheint ein USB-Laufwerk
   (beim RAK4631 heißt es `RAK4631`, beim XIAO je nach Bootloader `XIAO-SENSE` oder `XIAO-BOOT`).
3. Die `.uf2`-Datei auf dieses Laufwerk kopieren.
4. Das Laufwerk verschwindet von selbst, das Gerät startet neu. Fertig.

Die `.uf2` ersetzt nur die Anwendung, Konfiguration und Identität bleiben erhalten.

Klappt der Doppel-Reset nicht: langsamer probieren (zwei getrennte Klicks, nicht ein Doppelklick),
anderes USB-Kabel testen — viele Kabel können nur laden, nicht Daten übertragen.

### Weg D — Über Funk, nRF52-Boards (RAK4631, SenseCAP P1, XIAO)

Für Knoten, an die du nicht mehr physisch herankommst. Du brauchst BLE-Reichweite zum Gerät und
Admin-Zugang über Funk.

1. Die **`.zip`** des Releases auf das Telefon laden — dieselbe Datei wie beim Webflasher.
2. App **nRF Device Firmware Update** installieren (iOS App Store / Google Play, Suchbegriff `nrf dfu`).
3. In der MeshCore-App per Remote-Administration am Repeater als Admin anmelden, im Command-Line-Tab
   `start ota` eingeben. Antwort `OK` bedeutet: Gerät ist im OTA-Modus.
4. In der DFU-App unter `Settings` die **Packet receipt notifications** aktivieren und
   **Number of Packets** auf `10` setzen (RAK4631; `8` funktioniert ebenfalls und ist für den T114 der
   richtige Wert). Ohne diese Einstellung brechen Uploads häufig ab.
5. Die ZIP-Datei auswählen, das Gerät aus der Liste wählen, `Upload` starten. Der Vorgang dauert
   einige Minuten.

Taucht das Gerät nicht in der Liste auf: `Force Scanning` in der DFU-App aktivieren, und `start ota`
noch einmal absetzen — der OTA-Modus läuft nach einiger Zeit ab.

> 💡 **Dringende Empfehlung für alles, was an einem Mast hängt:** vorher den
> [OTAFIX-Bootloader](https://github.com/oltaco/Adafruit_nRF52_Bootloader_OTAFIX) installieren. Er
> erkennt eine ungültige Anwendungs-Firmware und fällt selbsttätig in den OTA-DFU-Modus zurück, statt
> den Knoten tot am Mast zu lassen. Ein abgebrochener OTA-Flash ist damit kein Kletter-Einsatz mehr.
> Hintergrund: <https://blog.meshcore.io/2026/04/06/otafix-bootloader>
>
> Für den **XIAO** gibt es zwei OTAFIX-Varianten, `xiao_nrf52840_ble` und `xiao_nrf52840_ble_sense`.
> Welche passt, steht in der Datei `INFO_UF2.TXT` auf dem USB-Laufwerk (doppelter Reset): enthält
> die Zeile `Board-ID` das Wort `Sense`, die `_sense`-Variante nehmen, sonst die andere. Das Update
> über Funk ist beim XIAO bisher nicht erprobt, nur der Weg über USB.

### Weg E — Über Funk, Heltec V3

1. Die **nicht**-`merged` `.bin` des Releases bereithalten.
2. Per Remote-Administration als Admin anmelden und `start ota` absetzen.
3. Auf ESP32-Geräten öffnet das einen WLAN-Hotspot namens **`MeshCore OTA`**. Mit Telefon oder Laptop
   verbinden.
4. Im Browser <http://192.168.4.1/update> aufrufen und die `.bin` hochladen.

Das setzt voraus, dass du in WLAN-Reichweite des Knotens bist — für einen Mast also meist nichts,
was vom Boden aus funktioniert.

---

## Schritt 3 — Prüfen, dass es geklappt hat

An der CLI:

```
ver
> v1.17.0.fwdfilter8-<sha> (Build: …)
```

Stimmt die Versionsnummer mit dem Release überein, hat das Gerät die richtige Firmware. Gegenprobe,
dass die Fork-Funktionen tatsächlich da sind:

```
get fwd.hashfilter
> off prob=100
```

Antwortet der Knoten hier mit einem Fehler statt mit dem Status, läuft Mainline-Firmware ohne
Forward-Filter.

---

## Duty Cycle prüfen

Bevor der Knoten dauerhaft sendet: **prüfe den Duty Cycle und stelle ihn auf das ein, was an deinem
Standort zulässig ist.**

```
get dutycycle
set dutycycle <wert>      # 1-100, in Prozent
```

> ⚠️ **Der Auslieferungswert ist kein zulässiger Wert.** Die Firmware startet mit einem
> Airtime-Faktor von 1.0, das entspricht **50 %** Duty Cycle. In den meisten Funkbändern, in denen
> MeshCore betrieben wird, liegt das weit über dem erlaubten Anteil. Der Standardwert ist eine
> technische Vorgabe der Mainline-Firmware und keine Aussage darüber, was du senden darfst.

Welcher Wert korrekt ist, hängt vom Band, vom Kanal und von der Rechtslage an deinem Standort ab. Das
zu kennen und einzuhalten **liegt allein beim Betreiber des Knotens** — diese Firmware wird
international verteilt und kann dir keine Zahl nennen. Frage im Zweifel deine nationale
Regulierungsbehörde oder den zuständigen Amateurfunkverband.

Der Wert wirkt auf mehr als nur die Legalität: die Airtime-Reserve aus
[Stufe 4](./forward-filter.de.md#stufe-4--airtime-reserve-für-scoped-traffic) leitet ihre
Fensterzuteilung direkt aus dem Duty Cycle ab. Ein falsch gesetzter Duty Cycle verstellt damit auch
das Filterverhalten.

> ℹ️ **`set af` ist der alte Weg** und rechnet mit dem Kehrwert (`af = 100 / Duty Cycle − 1`). Seit
> MeshCore 1.15 gibt es `set dutycycle`, das direkt in Prozent arbeitet. Nimm `dutycycle`; `af` bleibt
> nur aus Kompatibilitätsgründen erhalten. Ältere Knoten, die auf `get dutycycle` mit `??` antworten,
> laufen mit Firmware vor 1.15 und müssen über `af` gesetzt werden.

---

## Zugang zur CLI

Drei Wege, alle gleichwertig — die Forward-Filter-Befehle funktionieren auf jedem davon:

**Per USB, im Browser.** <https://config.meshcore.io> in Chrome oder Edge öffnen, Gerät per USB
verbinden, seriellen Port auswählen. Bequemster Weg für die Erstkonfiguration. (Der Webflasher hat
unter „Serial console“ dieselbe Funktion eingebaut.)

**Über Funk, aus der MeshCore-App.** Repeater als Admin hinzufügen (Remote Management), dann den
Command-Line-Tab benutzen. Das ist der Weg für Knoten im Feld — und der Grund, warum die Whitelist
Adverts und `ANON_REQ` grundsätzlich durchlässt: damit dieser Zugang auch bei fehlerhafter
Filterkonfiguration erhalten bleibt.

**Per Kommandozeile.** [`meshcore-cli`](https://github.com/fdlamotte/meshcore-cli) — für
Skripte, Massenkonfiguration und alles, was reproduzierbar sein soll.

Nach dem Flashen weiter im [Forward-Filter-Handbuch](./forward-filter.de.md).

---

## Was beim Flashen erhalten bleibt

Ein **Update** — `.zip`, `.uf2` oder die nicht-`merged` `.bin`, egal auf welchem Weg — lässt das
Dateisystem und damit die Konfiguration unangetastet: Node-Name, Admin-Passwort, Funk- und
Regionseinstellungen sowie die Geräteidentität (der Pubkey) bleiben erhalten. Der Knoten ist nach dem
Neustart derselbe Knoten.

Zwei Ausnahmen:

- **Ein `-merged.bin`-Flash oder ein Flash-Erase löscht alles**, auch die Identität. Danach hat der
  Knoten einen neuen Pubkey und muss überall neu eingetragen werden — in Whitelists anderer Betreiber
  ebenso wie in deiner eigenen Dokumentation. Nur machen, wenn du genau das willst.
- **Beim Update von `fwdfilter3` auf `fwdfilter4` oder neuer** wird die Filterkonfiguration einmalig
  zurückgesetzt (Umstellung auf die eigene `/fwd_prefs`-Datei). Whitelist- und Blacklist-Einträge
  danach neu setzen — am besten vorher `get fwd.whitelist` und `get fwd.block` abfragen und die
  Ausgabe aufheben. Alles andere bleibt erhalten.

---

## Downgrade nach einem Update auf fwdfilter8

`fwdfilter8` setzt auf MeshCore 1.17 auf, und 1.17 hat das Format der Einstellungsdatei gewechselt:
statt des alten Blobs `/com_prefs` wird jetzt `/prefs.json` geschrieben.

Beim ersten Start nach dem Update liest die Firmware die vorhandene `/com_prefs` noch einmal ein und
schreibt von da an ausschließlich `/prefs.json`. Für dich ändert sich dabei nichts: alle
Einstellungen wandern automatisch mit, es ist nichts zu tun.

> ⚠️ **Die alte `/com_prefs` bleibt liegen und wird ab diesem Zeitpunkt nicht mehr aktualisiert.**
> Sie friert auf dem Stand ein, den der Knoten unmittelbar vor dem Update hatte.
>
> Flasht du später wieder eine Version vor `fwdfilter8`, kennt diese `/prefs.json` nicht und liest die
> eingefrorene `/com_prefs`. **Alle Änderungen, die du seit dem Update auf fwdfilter8 gemacht hast,
> sind damit stillschweigend weg** — ohne Fehlermeldung, der Knoten läuft einfach mit der alten
> Konfiguration weiter. Betroffen sind Funk-, Regions- und Node-Einstellungen.

Die Filterkonfiguration in `/fwd_prefs` ist davon **nicht** betroffen: sie liegt in einer eigenen
Datei und übersteht den Wechsel in beide Richtungen.

Wenn du ein Downgrade planst, notiere dir vorher den Stand — `get radio`, `get name`,
`get dutycycle` und was du sonst verstellt hast — und setze ihn danach neu.

---

## Zurück auf Mainline

Die offizielle Repeater-Firmware im Webflasher auswählen — diesmal ganz normal über die Geräteliste —
und flashen. Auch hier gilt die Unterscheidung: die Update-Variante behält die Identität, die
Wipe-Variante nicht.

Die Filterkonfiguration in `/fwd_prefs` bleibt als verwaiste Datei liegen und wird von der
Mainline-Firmware ignoriert; die Filter sind damit wirkungslos. Flasht du später wieder eine
fwdfilter-Version, ist die alte Konfiguration wieder da.

---

## Wenn etwas nicht klappt

| Problem | Ursache / Abhilfe |
|---|---|
| Browser sieht das Gerät nicht | WebSerial gibt es nur in Chrome und Edge, nicht in Firefox oder Safari |
| Webflasher nimmt die Datei nicht an | Der Dateiauswahldialog akzeptiert nur `.zip` und `.bin`. Für nRF52 die `.zip` nehmen, nicht die `.uf2` |
| RAK4631: Flasher meldet einen DFU-Fehler | Gerät war nicht im DFU-Modus. „Enter DFU mode“ im Flasher benutzen oder zweimal Reset drücken |
| Kein USB-Laufwerk nach Doppel-Reset | Zwei getrennte Klicks statt Doppelklick; anderes USB-Kabel (viele sind reine Ladekabel) |
| esptool findet den Port nicht | USB-Treiber (CP210x/CH340) fehlt; unter Linux fehlt die Berechtigung — Benutzer in Gruppe `dialout` |
| Heltec startet nach dem Flash nicht mehr | Vermutlich die nicht-`merged` `.bin` an Adresse `0x0` geschrieben. Die `-merged.bin` an `0x0` nachflashen |
| Knoten hat nach dem Flash einen neuen Pubkey | Es war ein `-merged.bin`-Flash. Zum Aktualisieren die nicht-`merged` `.bin` verwenden |
| OTA bricht mittendrin ab | `Packet receipt notifications` aktivieren, `Number of Packets` auf 10; Bluetooth am Telefon aus- und einschalten; Gerät in den Bluetooth-Einstellungen entfernen und neu koppeln |
| Gerät erscheint nicht in der DFU-App | `start ota` erneut absetzen (der Modus läuft ab), `Force Scanning` aktivieren |
| Knoten nach OTA-Abbruch tot | Ohne OTAFIX-Bootloader hilft nur USB vor Ort. Genau deshalb OTAFIX **vorher** installieren |

Bleibt es dabei: [Issue aufmachen](https://github.com/ACETyr/MeshCore/issues) — mit Board, Release,
Flash-Weg und der genauen Fehlermeldung.
