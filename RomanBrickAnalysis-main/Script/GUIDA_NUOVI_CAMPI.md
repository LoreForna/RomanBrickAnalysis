# Guida Rapida - Nuovi Nomi Campi v1.0

## 📋 Tabella di Conversione Nomi Campi

| Versione 0.9 | Versione 1.0 | Tipo | Descrizione |
|--------------|--------------|------|-------------|
| `width_piede` | `width_modulo` | Intero | Numero di moduli interi nella larghezza |
| `width_modulo` | `Δwidth_modulo` | Decimale (3 dec) | Resto della larghezza in metri |
| `height_piede` | `height_modulo` | Intero | Numero di moduli interi nell'altezza |
| `height_modulo` | `Δheight_modulo` | Decimale (3 dec) | Resto dell'altezza in metri |

## 🔤 Nomenclatura

### Perché "modulo"?
Il termine "modulo" è più appropriato del termine "piede" nel contesto architettonico e archeologico, in quanto rappresenta l'unità di misura base utilizzata per proporzionare gli elementi costruttivi.

### Perché il simbolo Δ (Delta)?
Il simbolo Δ (delta) è utilizzato in matematica e fisica per indicare una "variazione" o "differenza". Nel nostro caso:
- `Δwidth_modulo` = differenza/resto della larghezza dopo aver rimosso i moduli interi
- `Δheight_modulo` = differenza/resto dell'altezza dopo aver rimosso i moduli interi

Esempio pratico:
```
Se width_bbox = 0.658 m e valore_modulo = 0.296 m:
- width_modulo = 2 (floor(0.658 / 0.296) = floor(2.223) = 2)
- Δwidth_modulo = 0.066 (0.658 % 0.296 = 0.066)

Verifica: 2 × 0.296 + 0.066 = 0.592 + 0.066 = 0.658 ✓
```

## 🔧 Formule dei Campi

### width_modulo (intero)
```
floor(width_bbox / @modulo)
```
Calcola quanti moduli interi stanno nella larghezza del componente.

### Δwidth_modulo (decimale)
```
round(width_bbox % @modulo, 3)
```
Calcola il resto della larghezza dopo aver tolto i moduli interi, arrotondato a 3 decimali.

### height_modulo (intero)
```
floor(height_bbox / @modulo)
```
Calcola quanti moduli interi stanno nell'altezza del componente.

### Δheight_modulo (decimale)
```
round(height_bbox % @modulo, 3)
```
Calcola il resto dell'altezza dopo aver tolto i moduli interi, arrotondato a 3 decimali.

## 📊 Esempio Pratico

**Dati di input:**
- width_bbox = 0.890 m
- height_bbox = 0.450 m
- valore_modulo = 0.296 m (piede attico/romano)

**Output campi calcolati:**
- `width_modulo` = 3 (floor(0.890 / 0.296) = floor(3.007) = 3)
- `Δwidth_modulo` = 0.002 (0.890 % 0.296 = 0.002)
- `height_modulo` = 1 (floor(0.450 / 0.296) = floor(1.520) = 1)
- `Δheight_modulo` = 0.154 (0.450 % 0.296 = 0.154)

**Interpretazione:**
Il componente ha dimensioni pari a:
- Larghezza: 3 moduli + 2 mm
- Altezza: 1 modulo + 154 mm

## 🔄 Migrazione Script/Espressioni

### Se hai espressioni personalizzate in QGIS:

**Cerca e sostituisci:**
```
width_piede     →  width_modulo
width_modulo    →  Δwidth_modulo
height_piede    →  height_modulo
height_modulo   →  Δheight_modulo
@piede          →  @modulo
```

### Se hai script Python che usano questi campi:

**Prima (v0.9):**
```python
feat['width_piede']   # numero moduli larghezza
feat['width_modulo']  # resto larghezza
feat['height_piede']  # numero moduli altezza
feat['height_modulo'] # resto altezza
```

**Dopo (v1.0):**
```python
feat['width_modulo']    # numero moduli larghezza
feat['Δwidth_modulo']   # resto larghezza
feat['height_modulo']   # numero moduli altezza
feat['Δheight_modulo']  # resto altezza
```

## ⚠️ Note Importanti

1. **Tutti i campi sono NULL per superficie != 'intera'**
   - Solo i componenti con `superficie = 'intera'` hanno questi campi popolati
   - I componenti parziali avranno valore NULL

2. **La variabile di layer è cambiata**
   - Vecchia: `@piede`
   - Nuova: `@modulo`
   - Aggiorna tutte le espressioni che usano questa variabile

3. **Non c'è retrocompatibilità**
   - I layer prodotti con v0.9 hanno nomi campi diversi
   - È necessario rielaborare i layer con v1.0 per avere i nuovi nomi

4. **Carattere speciale Δ**
   - Il simbolo Δ (delta maiuscolo greco) è supportato in QGIS
   - Se hai problemi di visualizzazione, verifica le impostazioni di encoding UTF-8

## 📝 Convenzioni di Scrittura

Quando scrivi il simbolo Δ:
- **In QGIS**: copia e incolla: Δ
- **Unicode**: U+0394
- **HTML**: `&Delta;`
- **LaTeX**: `\Delta`
- **Python**: `'\u0394'`

---

**Versione documento**: 1.0  
**Data**: 16 Dicembre 2025  
**Compatibile con**: Script v1.0
