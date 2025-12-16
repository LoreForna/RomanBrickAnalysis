# Changelog - Analisi Quantitativa v1.0

## Versione 1.0 (nuova)

Questo documento descrive le modifiche applicate a **entrambi** gli script di analisi quantitativa:
- **analisi_quantitativa_altri_componenti**
- **analisi_quantitativa_componenti_a_secco**

---

## 🎯 Modifiche Principali

**Valore del modulo configurabile + Rinominazione completa dei campi**

Il valore del modulo (piede romano), precedentemente fisso a 0.296 m, è ora un parametro personalizzabile dall'interfaccia dello script. Inoltre, tutti i nomi dei campi sono stati aggiornati per una nomenclatura più coerente con il simbolo matematico Δ (delta).

---

## 📝 Modifiche Dettagliate

### 1. Nuovo Parametro nell'Interfaccia

- **Nome parametro interno**: `valore_modulo` (nuovo in v1.0)
- **Etichetta interfaccia**: "Valore del modulo (m, default=piede attico/romano)"
- **Tipo**: Numero decimale (Double)
- **Valore predefinito**: 0.296 m (piede attico/romano)
- **Valore minimo**: 0.001 m
- **Posizione**: Dopo i parametri "Step range larghezza" e "Step range altezza" (ultimo parametro prima degli output)

### 2. Rinominazione Completa dei Campi

**Versione 0.9 → Versione 1.0:**

| Versione 0.9 | Versione 1.0 | Tipo | Descrizione |
|--------------|--------------|------|-------------|
| `width_piede` | `width_modulo` | Intero | Numero di moduli interi nella larghezza |
| `width_modulo` | `Δwidth_modulo` | Decimale (3 dec) | Resto della larghezza in metri |
| `height_piede` | `height_modulo` | Intero | Numero di moduli interi nell'altezza |
| `height_modulo` | `Δheight_modulo` | Decimale (3 dec) | Resto dell'altezza in metri |

### 3. Cambio Variabile di Layer

- **v0.9**: `@piede` (valore fisso 0.296 m, non modificabile)
- **v1.0**: `@modulo` (valore configurabile dall'utente, default 0.296 m)

### 4. Modifiche al Codice

#### Funzione `initAlgorithm`

```python
# Parametri filtro
...

# Parametri range
self.addParameter(QgsProcessingParameterNumber(
    'width_range_step',
    'Step range larghezza (m)',
    type=QgsProcessingParameterNumber.Double,
    defaultValue=0.01,
    minValue=0.001
))

self.addParameter(QgsProcessingParameterNumber(
    'height_range_step',
    'Step range altezza (m)',
    type=QgsProcessingParameterNumber.Double,
    defaultValue=0.01,
    minValue=0.001
))

# Parametro valore modulo (DOPO gli step range)
self.addParameter(QgsProcessingParameterNumber(
    'valore_modulo',
    'Valore del modulo (m, default=piede attico/romano)',
    type=QgsProcessingParameterNumber.Double,
    defaultValue=0.296,
    minValue=0.001
))
```

#### Funzione `_load_and_validate_parameters`

**Modifiche:**
- Aggiunta estrazione del parametro `valore_modulo`
- Aggiunta validazione: `if valore_modulo <= 0: raise QgsProcessingException(...)`
- Aggiunto log: `feedback.pushInfo(f"Valore del modulo: {valore_modulo} m")`
- Parametro incluso nel dizionario restituito: `'valore_modulo': valore_modulo`

```python
# Carica altri parametri
...
valore_modulo = self.parameterAsDouble(parameters, 'valore_modulo', context)

# Valida step
...
if valore_modulo <= 0:
    raise QgsProcessingException("Il valore del modulo deve essere maggiore di 0!")

feedback.pushInfo(f"Valore del modulo: {valore_modulo} m")
```

#### Funzione `_create_rilievo_analysis`

**Modifiche:**
- Firma modificata per accettare `valore_modulo: float`
- Variabile di layer: `QgsExpressionContextUtils.setLayerVariable(layer, 'modulo', valore_modulo)`
- Tutte le espressioni usano `@modulo` invece di `@piede`
- Nomi campi completamente aggiornati

```python
def _create_rilievo_analysis(self, layer_base: str, bbox_layer: str,
                             parameters: Dict, valore_modulo: float, 
                             context, feedback, results: Dict):
    ...
    # Aggiungi variabile modulo al layer
    QgsExpressionContextUtils.setLayerVariable(layer, 'modulo', valore_modulo)
    feedback.pushInfo(f"Variabile 'modulo' aggiunta al layer (valore: {valore_modulo})")
    
    # Campo 1: width_modulo
    width_modulo_expr = '''CASE 
        WHEN "superficie" = 'intera' THEN floor("width_bbox" / @modulo)
        ELSE NULL
    END'''
    layer.addExpressionField(width_modulo_expr, QgsField('width_modulo', QVariant.Int))
    
    # Campo 2: Δwidth_modulo
    delta_width_modulo_expr = '''CASE 
        WHEN "superficie" = 'intera' THEN round("width_bbox" % @modulo, 3)
        ELSE NULL
    END'''
    layer.addExpressionField(delta_width_modulo_expr, QgsField('Δwidth_modulo', QVariant.Double))
    
    # Campo 3: height_modulo
    height_modulo_expr = '''CASE 
        WHEN "superficie" = 'intera' THEN floor("height_bbox" / @modulo)
        ELSE NULL
    END'''
    layer.addExpressionField(height_modulo_expr, QgsField('height_modulo', QVariant.Int))
    
    # Campo 4: Δheight_modulo
    delta_height_modulo_expr = '''CASE 
        WHEN "superficie" = 'intera' THEN round("height_bbox" % @modulo, 3)
        ELSE NULL
    END'''
    layer.addExpressionField(delta_height_modulo_expr, QgsField('Δheight_modulo', QVariant.Double))
```

#### Funzione `processAlgorithm`

**Modifica alla chiamata:**

```python
self._create_rilievo_analysis(
    layer_base, bbox_final['OUTPUT'], parameters, params['valore_modulo'],
    context, feedback, results
)
```

#### Funzione `_log_summary`

**Aggiunte:**
- Nuova sezione "PARAMETRI UNITÀ DI MISURA"
- Mostra il valore del modulo utilizzato
- Nomi campi aggiornati nel riepilogo

```python
feedback.pushInfo("\n[PARAMETRI UNITÀ DI MISURA]")
feedback.pushInfo(f"Valore del modulo: {params['valore_modulo']} m")

feedback.pushInfo("\n[CAMPI AGGIUNTI AL LAYER RILIEVO]")
feedback.pushInfo("  * width_modulo (intero) - Numero di moduli interi nella larghezza")
feedback.pushInfo("  * Δwidth_modulo (decimale, 3 decimali) - Resto della larghezza")
feedback.pushInfo("  * height_modulo (intero) - Numero di moduli interi nell'altezza")
feedback.pushInfo("  * Δheight_modulo (decimale, 3 decimali) - Resto dell'altezza")
```

#### Funzione `_log_header`

**Modifica:**
```python
feedback.pushInfo("ANALISI QUANTITATIVA [NOME SCRIPT] - VERSIONE 1.0")
```

#### Funzione `shortHelpString`

**Modifiche complete:**
- Versione aggiornata a 1.0
- Parametri aggiornati con "Valore del modulo"
- Nomi campi aggiornati nella documentazione
- Note sulla personalizzazione del valore e nuova nomenclatura

---

## 🔧 Comportamento

### Prima (v0.9)
- **Valore**: FISSO a 0.296 m (hard-coded nel codice)
- **Variabile**: `@piede`
- **Campi**: `width_piede`, `width_modulo`, `height_piede`, `height_modulo`
- **Modifica**: necessario editare il codice sorgente

### Ora (v1.0)
- **Valore**: CONFIGURABILE dall'interfaccia (default 0.296 m)
- **Variabile**: `@modulo`
- **Campi**: `width_modulo`, `Δwidth_modulo`, `height_modulo`, `Δheight_modulo`
- **Modifica**: tramite parametro nell'interfaccia QGIS

---

## 💡 Esempi di Utilizzo

### Valori Comuni per Diverse Culture

| Tipo di piede | Valore (m) | Regione/Periodo |
|---------------|------------|-----------------|
| **Piede attico/romano** | **0.296** | Roma antica, Grecia classica (DEFAULT) |
| Piede greco | 0.308 | Grecia antica |
| Piede dorico | 0.326 | Ordine dorico greco |
| Piede osco-italico | 0.275 | Italia preromana |
| Piede ionico | 0.294 | Asia Minore greca |

### Esempio Pratico di Calcolo

**Dati di input:**
- `width_bbox` = 0.890 m
- `height_bbox` = 0.450 m
- `valore_modulo` = 0.296 m (piede attico/romano)

**Output campi calcolati:**
- `width_modulo` = 3 (floor(0.890 / 0.296) = floor(3.007) = 3)
- `Δwidth_modulo` = 0.002 (0.890 % 0.296 = 0.002)
- `height_modulo` = 1 (floor(0.450 / 0.296) = floor(1.520) = 1)
- `Δheight_modulo` = 0.154 (0.450 % 0.296 = 0.154)

**Interpretazione:**
Il componente ha dimensioni pari a:
- **Larghezza**: 3 moduli + 2 mm
- **Altezza**: 1 modulo + 154 mm

---

## 🔤 Nomenclatura e Simboli

### Perché "modulo"?
Il termine "modulo" è più appropriato nel contesto architettonico e archeologico, rappresentando l'unità di misura base utilizzata per proporzionare gli elementi costruttivi.

### Perché il simbolo Δ (Delta)?
Il simbolo Δ (delta maiuscolo greco) è utilizzato in matematica e fisica per indicare una "variazione" o "differenza". Nel nostro caso:
- `Δwidth_modulo` = differenza/resto della larghezza dopo aver rimosso i moduli interi
- `Δheight_modulo` = differenza/resto dell'altezza dopo aver rimosso i moduli interi

Questo segue la convenzione matematica standard e rende immediatamente chiaro che si tratta di un valore residuale.

### Scrivere il simbolo Δ
- **In QGIS**: copia e incolla: Δ
- **Unicode**: U+0394
- **HTML**: `&Delta;`
- **LaTeX**: `\Delta`
- **Python**: `'\u0394'`

---

## ✅ Vantaggi della v1.0

- ✓ **Flessibilità**: maggiore adattabilità per studi comparativi
- ✓ **Multiculturale**: possibilità di analizzare murature di epoche/culture diverse
- ✓ **User-friendly**: nessuna necessità di modificare il codice
- ✓ **Trasparenza**: valore sempre visibile nel riepilogo finale
- ✓ **Validazione**: controllo automatico del valore inserito (> 0)
- ✓ **Nomenclatura**: più coerente e matematicamente corretta
- ✓ **Documentazione**: etichetta auto-esplicativa nell'interfaccia

---

## 📋 Note Tecniche

- Il valore viene salvato come **variabile di layer** (`@modulo`)
- I **campi virtuali** utilizzano automaticamente il valore tramite `@modulo`
- La **validazione** impedisce valori <= 0
- Il simbolo **Δ (delta)** è pienamente supportato in QGIS
- **Encoding UTF-8** garantisce la corretta visualizzazione del simbolo delta
- I **campi virtuali** vengono calcolati dinamicamente, non salvati nel file

---

## ⚠️ Retrocompatibilità

### IMPORTANTE: NON retrocompatibile con v0.9

Lo script **NON è retrocompatibile** con la versione 0.9 a causa dei cambiamenti sostanziali nella nomenclatura.

### ⛔ Cosa NON funziona più

- ❌ Variabile `@piede` sostituita con `@modulo`
- ❌ Campo `width_piede` rinominato in `width_modulo`
- ❌ Campo `width_modulo` rinominato in `Δwidth_modulo`
- ❌ Campo `height_piede` rinominato in `height_modulo`
- ❌ Campo `height_modulo` rinominato in `Δheight_modulo`
- ❌ Layer esistenti prodotti dalla v0.9 hanno nomi campi diversi
- ❌ Espressioni personalizzate con riferimento a `@piede` o vecchi nomi campi
- ❌ Script Python che usano i vecchi nomi campi
- ❌ Modelli QGIS che richiamano questo algoritmo con parametri vecchi

### ✅ Cosa funziona

- ✅ I **layer della v0.9** possono essere **riprocessati** con la v1.0 (genereranno nuovi nomi campi)
- ✅ Il **valore predefinito** rimane 0.296 m (stessi risultati numerici)
- ✅ La **logica di calcolo** è identica (solo i nomi sono cambiati)

---

## 🔄 Guida alla Migrazione (v0.9 → v1.0)

### Passo 1: Backup
```
✓ Salva una copia dei tuoi progetti QGIS attuali
✓ Esporta i layer esistenti se necessario
✓ Documenta le espressioni personalizzate che usi
```

### Passo 2: Rielaborazione Layer
```
✓ Rielabora tutti i layer con la v1.0 per ottenere i nuovi nomi campi
✓ I nuovi layer avranno: width_modulo, Δwidth_modulo, height_modulo, Δheight_modulo
✓ Verifica che i valori numerici siano identici ai precedenti
```

### Passo 3: Aggiornamento Espressioni

**Trova e sostituisci** in tutte le espressioni QGIS:

| Vecchio | Nuovo |
|---------|-------|
| `@piede` | `@modulo` |
| `"width_piede"` | `"width_modulo"` |
| `"width_modulo"` | `"Δwidth_modulo"` |
| `"height_piede"` | `"height_modulo"` |
| `"height_modulo"` | `"Δheight_modulo"` |

### Passo 4: Aggiornamento Script Python

**Esempio di migrazione script:**

```python
# PRIMA (v0.9)
feat['width_piede']   # numero moduli larghezza
feat['width_modulo']  # resto larghezza
feat['height_piede']  # numero moduli altezza
feat['height_modulo'] # resto altezza

# DOPO (v1.0)
feat['width_modulo']    # numero moduli larghezza
feat['Δwidth_modulo']   # resto larghezza
feat['height_modulo']   # numero moduli altezza
feat['Δheight_modulo']  # resto altezza
```

### Passo 5: Test e Validazione
```
✓ Testa tutti i workflow con i nuovi nomi campi
✓ Verifica che le statistiche siano corrette
✓ Controlla che le espressioni custom funzionino
✓ Valida i risultati finali confrontandoli con la v0.9
```

### Passo 6: Documentazione
```
✓ Aggiorna la documentazione interna del progetto
✓ Informa il team dei cambiamenti
✓ Aggiungi note sulla migrazione al sistema di versioning
```

---

## 📊 Tabella Riassuntiva Modifiche

| Elemento | v0.9 | v1.0 | Note |
|----------|------|------|------|
| **Script** | analisi_..._v0_9.py | analisi_..._v1_0.py | Nuova versione |
| **Parametro modulo** | *(assente)* | `valore_modulo` | Nuovo parametro |
| **Default modulo** | 0.296 (hard-coded) | 0.296 (configurabile) | Stessi valori |
| **Variabile layer** | `@piede` | `@modulo` | Rinominata |
| **Campo 1** | `width_piede` | `width_modulo` | Rinominato |
| **Campo 2** | `width_modulo` | `Δwidth_modulo` | Rinominato + Δ |
| **Campo 3** | `height_piede` | `height_modulo` | Rinominato |
| **Campo 4** | `height_modulo` | `Δheight_modulo` | Rinominato + Δ |
| **Posizione parametro** | N/A | Dopo step range | Nuova posizione |
| **Etichetta interfaccia** | N/A | Con default esplicito | Più chiara |
| **Documentazione** | Help base | Help esteso | Migliorata |
| **Retrocompatibilità** | N/A | ❌ Non compatibile | Breaking change |

---

## 📚 Formule dei Campi

### width_modulo (intero)
```python
CASE 
    WHEN "superficie" = 'intera' THEN floor("width_bbox" / @modulo)
    ELSE NULL
END
```
Calcola quanti moduli interi stanno nella larghezza del componente.

### Δwidth_modulo (decimale, 3 decimali)
```python
CASE 
    WHEN "superficie" = 'intera' THEN round("width_bbox" % @modulo, 3)
    ELSE NULL
END
```
Calcola il resto della larghezza dopo aver tolto i moduli interi.

### height_modulo (intero)
```python
CASE 
    WHEN "superficie" = 'intera' THEN floor("height_bbox" / @modulo)
    ELSE NULL
END
```
Calcola quanti moduli interi stanno nell'altezza del componente.

### Δheight_modulo (decimale, 3 decimali)
```python
CASE 
    WHEN "superficie" = 'intera' THEN round("height_bbox" % @modulo, 3)
    ELSE NULL
END
```
Calcola il resto dell'altezza dopo aver tolto i moduli interi.

---

## 🎓 Best Practices

### Quando Usare Valori Diversi dal Default

1. **Studi comparativi** tra diverse culture architettoniche
2. **Analisi diacroniche** (evoluzione nel tempo)
3. **Verifiche metrologiche** su edifici con metrologia nota
4. **Ricerca di pattern** dimensionali in contesti specifici

### Come Documentare il Valore Usato

Sempre registrare nei metadati del progetto:
- Valore del modulo utilizzato (es. 0.296 m)
- Tipo di piede/modulo (es. attico/romano)
- Fonte/riferimento bibliografico
- Motivazione della scelta

### Gestione dei Risultati

- Esportare sempre i layer finali con metadati completi
- Includere il valore del modulo nel nome del file output
- Documentare eventuali modifiche al valore durante l'analisi
- Mantenere tracciabilità tra input e output

---

## 📞 Supporto e Feedback

Per problemi, domande o suggerimenti:
- Verificare prima la documentazione completa
- Consultare la GUIDA_NUOVI_CAMPI.md per esempi pratici
- Controllare che tutti i layer di input abbiano i campi richiesti
- Validare che i valori inseriti siano nel range corretto (> 0)

---

## 📅 Informazioni Versione

**Data rilascio**: 16 Dicembre 2025  
**Autore modifiche**: Claude (Anthropic)  
**Versione precedente**: 0.9  
**Versione attuale**: 1.0  
**Tipo di release**: Major version (breaking changes)

**Script interessati**:
- `analisi_quantitativa_altri_componenti_v1_0.py`
- `analisi_quantitativa_componenti_a_secco_v1_0.py`

**File di supporto**:
- `CHANGELOG_v1_0.md` (questo documento)
- `GUIDA_NUOVI_CAMPI.md` (guida rapida con esempi)

---

## ✨ Prossimi Sviluppi Possibili

Idee per future versioni (non implementate in v1.0):

- [ ] Supporto per altri sistemi metrologici (cubiti, braccia, ecc.)
- [ ] Preset predefiniti per culture/periodi comuni
- [ ] Esportazione automatica metadati metrologici
- [ ] Calcolo automatico del "best fit" del modulo
- [ ] Visualizzazione grafica delle distribuzioni modulari
- [ ] Integrazione con database metrologici online

---

**Fine del documento**
