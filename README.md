# RomanBrickAnalysis

Lo script è stato progettato specificamente per supportare l'analisi quantitativa delle murature di età romana in opera laterizia, offrendo un approccio strutturato e automatizzato per l’analisi dimensionale e statistica dei laterizi utilizzati nelle murature secondo il modello proposto da Maura Medri e dalla sua equipe (https://pdfs.semanticscholar.org/373e/c1a3bf317c3216612f4c63d9802da5d67ce0.pdf).

Lo script utilizza gli strumenti di processing di QGIS per:
- Eseguire join spaziali.
- Calcolare il poligono minimo orientato per ciascun componente delle murature.
- Estrarre informazioni specifiche dai dati vettoriali.
- Generare statistiche relative alle dimensioni e alla distribuzione delle misure dei laterizi.
- Produrre risultati strutturati per supportare l'analisi quantitativa e comparativa.

Requisiti
- Versione di Python: lo script richiede Python 3.8 o successivo.
- Versione di QGIS: richiede QGIS 3.16 o successivo.
- QGIS: lo script deve essere eseguito all'interno degli strumenti di processing di QGIS.
- Plugin DataPlotly (https://plugins.qgis.org/plugins/DataPlotly/#plugin-about)
- Dati in un sistema di riferimento cartografico o locale; NON UTILIZZARE SISTEMI DI RIFERIMENTO GEOGRAFICI.

Dati:
 - Layer "campioni": rappresenta le superfici dei campioni di muratura, utili per il calcolo delle statistiche complessive.
 - Layer "rilievo": contiene le geometrie poligonali riferite ai laterizi contenuti in ciascun campione di muratura.

Input:
- layer_input: layer "rilievo".
- percorso stili: assegna il percorso ai rispettivi file qml all’interno della cartella “Stili”.

Output:
- Min_oriented_bbox: layer poligonale contenente i poligoni minimi orientati per ciascun componente allo scopo di verificare la bontà dell’analisi.
- Conteggio_width_bbox_range e Conteggio_height_bbox_range: statistiche raggruppate per range di lunghezza (2 mm) e spessore (1mm) dei laterizi.
- Analisi_campioni_table: tabella che riassume tutte le statistiche principali calcolate a partire dal numero e dalle dimensioni dei laterizi.
- Analisi_campioni: layer poligonale con tutti gli attributi calcolati e aggregati relativi ai campioni analizzati.

Sintesi dei processi:
1. Join spaziale:
   - Unisce attributi del layer "rilievo" al layer "campioni" sulla base dell'intersezione geometrica. Questo consente di associare informazioni dettagliate sui laterizi e sul campione di riferimento.
2. Calcolo poligono minimo orientato:
   - Genera il poligono minimo orientato calcolando le dimensioni (lunghezza e spessore) per ciascuna geometria contenuta nel layer_input
3. Unione attributi:
   - Combina attributi dal calcolo poligono minimo orientato con il layer originale per arricchire i dati con misure geometriche.
4. Estrazione e filtraggio:
   - Filtra i dati per tipologia (es. "laterizio"), superficie ("intera" o "parziale"), e altre proprietà, permettendo di isolare specifici elementi delle murature.
5. Calcolo statistiche:
   - Esegue statistiche (minimo, massimo, media, deviazione standard, ecc.) per attributi come area, lunghezza e spessore dei laterizi, supportando analisi comparative.
6. Calcolo di nuovi attributi:
   - Deriva nuovi campi come "rapporto laterizi/malta", "area totale laterizi", e altri indici utili per comprendere la composizione delle murature.
7. Riorganizzazione e formattazione:
   - Modifica i nomi e la struttura dei campi di output per renderli coerenti e ben organizzati.
8. Stilizzazione dei layers:
   - Applica stili predefiniti ai layers di output utilizzando file di stile QML, garantendo una rappresentazione grafica chiara dei risultati.

Esempio:
1.	Connettere a QGIS il geopackage “Analisi_campioni” all’interno della cartella “Data”.
2.	Aprire il progetto già predisposto “analisi_campioni”.
3.	Eseguire lo script dal pannello "Processing" di QGIS.
4.	Esaminare i layers di output.
5.	Aprire il gestore dei layout e caricare il modello “scheda_campione”.
6.	Attivare la modalità Atlante e utilizzare come layer di copertura “Analisi_campioni”.
7.	Aggiornare i grafici di DataPlotly con i file xml presenti nella cartella “Layout”
8.	Nel panello delle proprietà dei grafici utilizzare come layer rispettivamente le tabelle “Conteggio_width_bbox_range” e “Conteggio_height_bbox_range”.
9.	Impostare per il campo x rispettivamente i valori “width_bbox_range” e “height_bbox_range”, per il campo y il valore del campo “count”.
10.	Esporta scheda campione.


![scheda_campione](https://github.com/user-attachments/assets/c2e14c1c-e36f-4a7b-a713-884dba66ebe5)
