"""
SCRIPT ANALISI QUANTITATIVA COMPONENTI A SECCO - VERSIONE 1.0
"""

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsProcessingParameterBoolean,
    QgsProcessingException,
    QgsProcessingUtils,
    QgsVectorLayer,
    QgsExpressionContextUtils
)
import processing
from typing import Dict, List, Tuple, Optional, Any


# ============ COSTANTI ============
class FieldNames:
    """Nomi dei campi richiesti nei layer"""
    # Campi layer rilievo
    FID = 'fid'
    TIPO = 'tipo'
    SUPERFICIE = 'superficie'
    AREA_COMPONENTE = 'area_componente'
    NUM_COMPONENTE = 'num_componente'
    
    # Campi layer campioni
    CAMPIONE = 'campione'
    SITO = 'sito'
    AMBIENTE = 'ambiente'
    USM = 'usm'
    AREA_CAMPIONE = 'area_campione'
    
    # Campi bbox
    WIDTH_BBOX = 'width_bbox'
    HEIGHT_BBOX = 'height_bbox'
    ANGLE_BBOX = 'angle_bbox'
    PERIMETER_BBOX = 'perimeter_bbox'
    AREA_BBOX = 'area_bbox'


class SurfaceTypes:
    """Valori per il campo superficie"""
    INTERA = 'intera'
    PARZIALE = 'parziale'


class ProcessSteps:
    """Numero totale di step per il feedback"""
    TOTAL = 19


# ============ CLASSE PRINCIPALE ============
class Analisi(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        """Inizializza i parametri dell'algoritmo"""
        # Input layers
        self.addParameter(QgsProcessingParameterFeatureSource(
            'layer_rilievo',
            'Layer rilievo (poligoni componenti muratura)',
            types=[QgsProcessing.TypeVectorPolygon],
            defaultValue='rilievo'
        ))
        
        self.addParameter(QgsProcessingParameterFeatureSource(
            'layer_campioni',
            'Layer campioni (poligoni aree campioni)',
            types=[QgsProcessing.TypeVectorPolygon],
            defaultValue='campioni'
        ))
        
        # Parametri filtro
        self.addParameter(QgsProcessingParameterString(
            'tipo_materiale',
            'Tipo di materiale (separati da virgola, vuoto=tutti)',
            defaultValue='',
            optional=True
        ))
        
        self.addParameter(QgsProcessingParameterBoolean(
            'includi_non_classificati',
            'Includi elementi non classificati (NULL)',
            defaultValue=False
        ))
        
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
        
        # Parametro valore modulo
        self.addParameter(QgsProcessingParameterNumber(
            'valore_modulo',
            'Valore del modulo (m, default=piede attico/romano)',
            type=QgsProcessingParameterNumber.Double,
            defaultValue=0.296,
            minValue=0.001
        ))
        
        # Output layers
        self._add_output_parameters()

    def _add_output_parameters(self):
        """Aggiunge i parametri di output"""
        outputs = [
            ('output_bbox', 'Min oriented bbox', QgsProcessing.TypeVectorPolygon),
            ('output_rilievo', 'Analisi rilievo', QgsProcessing.TypeVectorPolygon),
            ('output_campioni_table', 'Analisi campioni (tabella)', QgsProcessing.TypeVectorAnyGeometry),
            ('output_campioni', 'Analisi campioni (layer poligonale)', QgsProcessing.TypeVectorAnyGeometry),
            ('output_width_range', 'Conteggio range larghezza', QgsProcessing.TypeVectorAnyGeometry),
            ('output_height_range', 'Conteggio range altezza', QgsProcessing.TypeVectorAnyGeometry)
        ]
        
        for param_name, description, geom_type in outputs:
            self.addParameter(QgsProcessingParameterFeatureSink(
                param_name, description, type=geom_type
            ))

    def validate_layer_fields(self, layer, required_fields: List[str], layer_name: str, feedback) -> bool:
        """
        Valida che un layer contenga tutti i campi richiesti
        
        Args:
            layer: Layer da validare
            required_fields: Lista dei nomi dei campi richiesti
            layer_name: Nome del layer (per messaggi di errore)
            feedback: Oggetto feedback per logging
            
        Returns:
            True se tutti i campi esistono, False altrimenti
            
        Raises:
            QgsProcessingException: Se mancano campi obbligatori
        """
        if not layer:
            raise QgsProcessingException(f"Layer {layer_name} non valido!")
        
        existing_fields = [f.name() for f in layer.fields()]
        missing_fields = [f for f in required_fields if f not in existing_fields]
        
        if missing_fields:
            feedback.reportError(f"Campi mancanti in {layer_name}: {', '.join(missing_fields)}")
            feedback.reportError(f"Campi disponibili: {', '.join(existing_fields)}")
            raise QgsProcessingException(
                f"Il layer '{layer_name}' non contiene i campi obbligatori: {', '.join(missing_fields)}"
            )
        
        feedback.pushInfo(f"✓ Validazione campi {layer_name} completata")
        return True

    def count_features_by_field(self, layer, field_name: str, feedback) -> Dict[str, int]:
        """
        Conta le features raggruppate per valore di un campo
        
        Args:
            layer: Layer da analizzare
            field_name: Nome del campo per il raggruppamento
            feedback: Oggetto feedback per logging
            
        Returns:
            Dizionario {valore: conteggio}
        """
        counts = {}
        if field_name not in [f.name() for f in layer.fields()]:
            return counts
        
        try:
            for feat in layer.getFeatures():
                value = str(feat[field_name]) if feat[field_name] is not None else 'NULL'
                counts[value] = counts.get(value, 0) + 1
        except Exception as e:
            feedback.pushWarning(f"Errore nel conteggio per campo {field_name}: {str(e)}")
        
        return counts

    def verifica_features(self, layer_id: str, context, feedback, step_name: str) -> int:
        """
        Conta e mostra le features a ogni step con dettagli per tipo
        
        Args:
            layer_id: ID del layer da verificare
            context: Contesto di processing
            feedback: Oggetto feedback per logging
            step_name: Nome dello step per il log
            
        Returns:
            Numero di features nel layer
        """
        layer = QgsProcessingUtils.mapLayerFromString(layer_id, context)
        if not layer or not layer.isValid():
            feedback.pushWarning(f"Layer non valido per step: {step_name}")
            return 0
        
        count = layer.featureCount()
        feedback.pushInfo(f"  --> {step_name}: {count} features")
        
        # Dettagli per tipo se il campo esiste
        tipo_counts = self.count_features_by_field(layer, FieldNames.TIPO, feedback)
        if tipo_counts:
            for tipo, cnt in sorted(tipo_counts.items()):
                feedback.pushInfo(f"      * {tipo}: {cnt}")
        
        return count

    def build_filter_expression(self, tipi: List[str], includi_null: bool) -> str:
        """
        Costruisce l'espressione di filtro per i materiali
        
        Args:
            tipi: Lista dei tipi di materiale da filtrare
            includi_null: Se includere valori NULL
            
        Returns:
            Espressione SQL per il filtro
        """
        if not tipi:
            return ""
        
        # Escape delle virgolette nei valori
        tipi_escaped = [t.replace("'", "''") for t in tipi]
        
        if len(tipi_escaped) == 1:
            expr = f'"{FieldNames.TIPO}" = \'{tipi_escaped[0]}\''
        else:
            tipi_quoted = "','".join(tipi_escaped)
            expr = f'"{FieldNames.TIPO}" IN (\'{tipi_quoted}\')'
        
        # Aggiungi condizione per NULL se richiesto
        if includi_null:
            expr = f'({expr}) OR "{FieldNames.TIPO}" IS NULL'
        
        return expr

    def create_field_mapping(self, field_configs: List[Tuple[str, str, int, int, int]]) -> List[Dict]:
        """
        Crea la configurazione dei campi per refactorfields
        
        Args:
            field_configs: Lista di tuple (expression, name, type, length, precision)
            
        Returns:
            Lista di dizionari per FIELDS_MAPPING
        """
        return [
            {
                'expression': expr,
                'name': name,
                'type': field_type,
                'length': length,
                'precision': precision
            }
            for expr, name, field_type, length, precision in field_configs
        ]

    def processAlgorithm(self, parameters: Dict, context, model_feedback) -> Dict[str, Any]:
        """
        Algoritmo principale di elaborazione
        
        Args:
            parameters: Dizionario dei parametri di input
            context: Contesto di processing
            model_feedback: Oggetto feedback del modello
            
        Returns:
            Dizionario con i risultati dell'elaborazione
            
        Raises:
            QgsProcessingException: In caso di errori durante l'elaborazione
        """
        feedback = QgsProcessingMultiStepFeedback(ProcessSteps.TOTAL, model_feedback)
        results = {}
        
        try:
            self._log_header(feedback)
            
            # ============ FASE 1: CARICAMENTO E VALIDAZIONE ============
            params = self._load_and_validate_parameters(parameters, context, feedback)
            feedback.setCurrentStep(1)
            
            # ============ FASE 2: SPATIAL JOIN ============
            joined = self._spatial_join(parameters, context, feedback)
            feedback.setCurrentStep(2)
            
            # ============ FASE 3: FILTRO MATERIALI ============
            layer_base = self._apply_material_filter(
                joined['OUTPUT'], params, context, feedback
            )
            feedback.setCurrentStep(3)
            
            # ============ FASE 4-6: BOUNDING BOX ============
            bbox_final = self._compute_bounding_boxes(
                layer_base, parameters, context, feedback, results
            )
            feedback.setCurrentStep(6)
            
            # ============ FASE 7: SEPARAZIONE INTERI/PARZIALI ============
            interi, parziali, count_interi, count_parziali = self._separate_complete_partial(
                bbox_final['OUTPUT'], context, feedback
            )
            feedback.setCurrentStep(7)
            
            # ============ FASE 8-9: RANGE E STATISTICHE ============
            with_ranges = self._compute_ranges(
                interi['OUTPUT'], params['width_step'], params['height_step'],
                context, feedback
            )
            feedback.setCurrentStep(8)
            
            stats = self._compute_statistics(
                interi['OUTPUT'], parziali['OUTPUT'], with_ranges['OUTPUT'],
                parameters, context, feedback, results
            )
            feedback.setCurrentStep(10)
            
            # ============ FASE 10-11: ANALISI RILIEVO ============
            self._create_rilievo_analysis(
                layer_base, bbox_final['OUTPUT'], parameters, params['valore_modulo'],
                context, feedback, results
            )
            feedback.setCurrentStep(11)
            
            # ============ FASE 12-17: ANALISI CAMPIONI ============
            self._create_campioni_analysis(
                parameters, stats, context, feedback, results
            )
            feedback.setCurrentStep(17)
            
            # ============ RIEPILOGO ============
            self._log_summary(
                count_interi, count_parziali, params, results, context, feedback
            )
            
            return results
            
        except QgsProcessingException:
            raise
        except Exception as e:
            feedback.reportError(f"\nERRORE IMPREVISTO: {str(e)}")
            import traceback
            feedback.reportError(traceback.format_exc())
            raise QgsProcessingException(f"Errore durante l'elaborazione: {str(e)}")

    def _log_header(self, feedback):
        """Stampa l'intestazione del log"""
        feedback.pushInfo("\n" + "="*70)
        feedback.pushInfo("ANALISI QUANTITATIVA COMPONENTI A SECCO - VERSIONE 1.0")
        feedback.pushInfo("="*70)

    def _load_and_validate_parameters(self, parameters: Dict, context, feedback) -> Dict:
        """Carica e valida tutti i parametri di input"""
        feedback.pushInfo("\n--- CARICAMENTO E VALIDAZIONE PARAMETRI ---")
        
        # Carica layer
        layer_rilievo = self.parameterAsSource(parameters, 'layer_rilievo', context)
        layer_campioni = self.parameterAsSource(parameters, 'layer_campioni', context)
        
        # Valida feature count
        if layer_rilievo.featureCount() == 0:
            raise QgsProcessingException("Il layer rilievo è vuoto!")
        if layer_campioni.featureCount() == 0:
            raise QgsProcessingException("Il layer campioni è vuoto!")
        
        feedback.pushInfo(f"Layer rilievo: {layer_rilievo.featureCount()} features")
        feedback.pushInfo(f"Layer campioni: {layer_campioni.featureCount()} features")
        
        # Valida campi obbligatori
        required_rilievo = [
            FieldNames.FID, FieldNames.TIPO, FieldNames.SUPERFICIE,
            FieldNames.AREA_COMPONENTE, FieldNames.NUM_COMPONENTE
        ]
        required_campioni = [
            FieldNames.CAMPIONE, FieldNames.SITO, FieldNames.AMBIENTE,
            FieldNames.USM, FieldNames.AREA_CAMPIONE
        ]
        
        self.validate_layer_fields(layer_rilievo, required_rilievo, "rilievo", feedback)
        self.validate_layer_fields(layer_campioni, required_campioni, "campioni", feedback)
        
        # Carica altri parametri
        tipo_input = self.parameterAsString(parameters, 'tipo_materiale', context).strip()
        includi_null = self.parameterAsBool(parameters, 'includi_non_classificati', context)
        width_step = self.parameterAsDouble(parameters, 'width_range_step', context)
        height_step = self.parameterAsDouble(parameters, 'height_range_step', context)
        valore_modulo = self.parameterAsDouble(parameters, 'valore_modulo', context)
        
        # Valida step
        if width_step <= 0:
            raise QgsProcessingException("Lo step larghezza deve essere maggiore di 0!")
        if height_step <= 0:
            raise QgsProcessingException("Lo step altezza deve essere maggiore di 0!")
        if valore_modulo <= 0:
            raise QgsProcessingException("Il valore del modulo deve essere maggiore di 0!")
        
        feedback.pushInfo(f"Valore del modulo: {valore_modulo} m")
        
        # Parse tipi materiale
        tipi = []
        applica_filtro = False
        
        if tipo_input:
            tipi = [t.strip() for t in tipo_input.split(',') if t.strip()]
            applica_filtro = True
            feedback.pushInfo(f"Filtro materiali: {', '.join(tipi)}")
            if includi_null:
                feedback.pushInfo("  (+ elementi non classificati)")
        else:
            feedback.pushInfo("Filtro materiali: NESSUNO (tutti i tipi)")
        
        return {
            'layer_rilievo': layer_rilievo,
            'layer_campioni': layer_campioni,
            'tipi': tipi,
            'includi_null': includi_null,
            'applica_filtro': applica_filtro,
            'width_step': width_step,
            'height_step': height_step,
            'valore_modulo': valore_modulo
        }

    def _spatial_join(self, parameters: Dict, context, feedback) -> Dict:
        """Esegue lo spatial join tra rilievo e campioni"""
        feedback.pushInfo("\n--- SPATIAL JOIN ---")
        
        joined = processing.run('native:joinattributesbylocation', {
            'INPUT': parameters['layer_rilievo'],
            'JOIN': parameters['layer_campioni'],
            'JOIN_FIELDS': [FieldNames.CAMPIONE, FieldNames.AMBIENTE, 
                           FieldNames.USM, FieldNames.SITO],
            'PREDICATE': [0],  # intersects
            'METHOD': 0,  # one-to-one
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        self.verifica_features(joined['OUTPUT'], context, feedback, "Dopo spatial join")
        return joined

    def _apply_material_filter(self, input_layer: str, params: Dict, 
                               context, feedback) -> str:
        """Applica il filtro sui materiali se necessario"""
        if not params['applica_filtro']:
            feedback.pushInfo("\n--- NESSUN FILTRO APPLICATO ---")
            return input_layer
        
        feedback.pushInfo("\n--- APPLICAZIONE FILTRO ---")
        
        expr = self.build_filter_expression(params['tipi'], params['includi_null'])
        feedback.pushInfo(f"Espressione filtro: {expr}")
        
        filtrato = processing.run('native:extractbyexpression', {
            'EXPRESSION': expr,
            'INPUT': input_layer,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        count = self.verifica_features(filtrato['OUTPUT'], context, feedback, "Dopo filtro")
        
        if count == 0:
            raise QgsProcessingException(
                f"Il filtro ha prodotto 0 risultati! Verifica i valori: {', '.join(params['tipi'])}"
            )
        
        return filtrato['OUTPUT']

    def _compute_bounding_boxes(self, layer_base: str, parameters: Dict,
                                context, feedback, results: Dict) -> Dict:
        """Calcola i bounding box orientati e li arricchisce con attributi"""
        feedback.pushInfo("\n--- CALCOLO BOUNDING BOX ---")
        
        # Calcola bbox
        bbox = processing.run('qgis:minimumboundinggeometry', {
            'INPUT': layer_base,
            'FIELD': FieldNames.FID,
            'TYPE': 1,  # oriented rectangle
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        self.verifica_features(bbox['OUTPUT'], context, feedback, "Bounding box creati")
        feedback.setCurrentStep(4)
        
        # Join con attributi originali
        bbox_full = processing.run('native:joinattributestable', {
            'INPUT': bbox['OUTPUT'],
            'INPUT_2': layer_base,
            'FIELD': FieldNames.FID,
            'FIELD_2': FieldNames.FID,
            'METHOD': 1,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        feedback.setCurrentStep(5)
        
        # Riorganizza campi
        field_mapping = self.create_field_mapping([
            (f'"{FieldNames.FID}"', FieldNames.FID, 4, 0, 0),
            (f'"{FieldNames.SITO}"', FieldNames.SITO, 10, 0, 0),
            (f'"{FieldNames.AMBIENTE}"', FieldNames.AMBIENTE, 10, 0, 0),
            (f'"{FieldNames.USM}"', FieldNames.USM, 10, 0, 0),
            (f'"{FieldNames.CAMPIONE}"', FieldNames.CAMPIONE, 10, 0, 0),
            (f'"{FieldNames.NUM_COMPONENTE}"', FieldNames.NUM_COMPONENTE, 4, 0, 0),
            (f'"{FieldNames.TIPO}"', FieldNames.TIPO, 10, 0, 0),
            (f'"{FieldNames.SUPERFICIE}"', FieldNames.SUPERFICIE, 10, 0, 0),
            (f'"{FieldNames.AREA_COMPONENTE}"', FieldNames.AREA_COMPONENTE, 6, 6, 3),
            ('"height"', FieldNames.WIDTH_BBOX, 6, 6, 3),
            ('"width"', FieldNames.HEIGHT_BBOX, 6, 6, 3),
            ('"angle"', FieldNames.ANGLE_BBOX, 6, 6, 3),
            ('"perimeter"', FieldNames.PERIMETER_BBOX, 6, 6, 3),
            ('"area"', FieldNames.AREA_BBOX, 6, 6, 3)
        ])
        
        bbox_final = processing.run('native:refactorfields', {
            'INPUT': bbox_full['OUTPUT'],
            'FIELDS_MAPPING': field_mapping,
            'OUTPUT': parameters['output_bbox']
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        results['output_bbox'] = bbox_final['OUTPUT']
        context.layerToLoadOnCompletionDetails(results['output_bbox']).name = "min_oriented_bbox_componenti_a_secco"
        self.verifica_features(results['output_bbox'], context, feedback, "Min oriented bbox FINALE")
        
        return bbox_final

    def _separate_complete_partial(self, bbox_layer: str, context, feedback) -> Tuple:
        """Separa i componenti interi da quelli parziali"""
        feedback.pushInfo("\n--- SEPARAZIONE INTERI/PARZIALI ---")
        
        interi = processing.run('native:extractbyattribute', {
            'INPUT': bbox_layer,
            'FIELD': FieldNames.SUPERFICIE,
            'OPERATOR': 0,  # =
            'VALUE': SurfaceTypes.INTERA,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        parziali = processing.run('native:extractbyattribute', {
            'INPUT': bbox_layer,
            'FIELD': FieldNames.SUPERFICIE,
            'OPERATOR': 0,
            'VALUE': SurfaceTypes.PARZIALE,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        count_interi = self.verifica_features(interi['OUTPUT'], context, feedback, "Componenti interi")
        count_parziali = self.verifica_features(parziali['OUTPUT'], context, feedback, "Componenti parziali")
        
        if count_interi == 0:
            feedback.pushWarning("ATTENZIONE: Nessun componente intero trovato! Le statistiche potrebbero essere incomplete.")
        if count_parziali == 0:
            feedback.pushInfo("INFO: Nessun componente parziale trovato.")
        
        return interi, parziali, count_interi, count_parziali

    def _compute_ranges(self, interi_layer: str, width_step: float, height_step: float,
                       context, feedback) -> Dict:
        """Calcola i range di larghezza e altezza"""
        feedback.pushInfo("\n--- CALCOLO RANGE ---")
        
        # Formula per range larghezza
        width_formula = f'''CASE 
    WHEN "{FieldNames.WIDTH_BBOX}" IS NULL THEN 'N/A'
    ELSE concat(
        round(floor("{FieldNames.WIDTH_BBOX}"/{width_step})*{width_step}, 3),
        ' - ',
        round((floor("{FieldNames.WIDTH_BBOX}"/{width_step})+1)*{width_step}, 3)
    )
END'''
        
        with_width_range = processing.run('native:fieldcalculator', {
            'INPUT': interi_layer,
            'FIELD_NAME': 'width_bbox_range',
            'FIELD_TYPE': 2,  # string
            'FORMULA': width_formula,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        # Formula per range altezza
        height_formula = f'''CASE 
    WHEN "{FieldNames.HEIGHT_BBOX}" IS NULL THEN 'N/A'
    ELSE concat(
        round(floor("{FieldNames.HEIGHT_BBOX}"/{height_step})*{height_step}, 3),
        ' - ',
        round((floor("{FieldNames.HEIGHT_BBOX}"/{height_step})+1)*{height_step}, 3)
    )
END'''
        
        with_both_ranges = processing.run('native:fieldcalculator', {
            'INPUT': with_width_range['OUTPUT'],
            'FIELD_NAME': 'height_bbox_range',
            'FIELD_TYPE': 2,
            'FORMULA': height_formula,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        return with_both_ranges

    def _compute_statistics(self, interi_layer: str, parziali_layer: str,
                           ranges_layer: str, parameters: Dict,
                           context, feedback, results: Dict) -> Dict:
        """Calcola tutte le statistiche necessarie"""
        feedback.pushInfo("\n--- STATISTICHE ---")
        
        # Statistiche per campione
        stats = {}
        stats['area_int'] = processing.run('qgis:statisticsbycategories', {
            'INPUT': interi_layer,
            'CATEGORIES_FIELD_NAME': [FieldNames.CAMPIONE],
            'VALUES_FIELD_NAME': FieldNames.AREA_COMPONENTE,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        stats['area_parz'] = processing.run('qgis:statisticsbycategories', {
            'INPUT': parziali_layer,
            'CATEGORIES_FIELD_NAME': [FieldNames.CAMPIONE],
            'VALUES_FIELD_NAME': FieldNames.AREA_COMPONENTE,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        stats['width'] = processing.run('qgis:statisticsbycategories', {
            'INPUT': interi_layer,
            'CATEGORIES_FIELD_NAME': [FieldNames.CAMPIONE],
            'VALUES_FIELD_NAME': FieldNames.WIDTH_BBOX,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        stats['height'] = processing.run('qgis:statisticsbycategories', {
            'INPUT': interi_layer,
            'CATEGORIES_FIELD_NAME': [FieldNames.CAMPIONE],
            'VALUES_FIELD_NAME': FieldNames.HEIGHT_BBOX,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        feedback.setCurrentStep(9)
        
        # Conteggi per range
        count_width = processing.run('qgis:statisticsbycategories', {
            'INPUT': ranges_layer,
            'CATEGORIES_FIELD_NAME': [FieldNames.CAMPIONE, 'width_bbox_range'],
            'VALUES_FIELD_NAME': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        count_height = processing.run('qgis:statisticsbycategories', {
            'INPUT': ranges_layer,
            'CATEGORIES_FIELD_NAME': [FieldNames.CAMPIONE, 'height_bbox_range'],
            'VALUES_FIELD_NAME': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        # Ordina e salva
        sorted_width = processing.run('native:orderbyexpression', {
            'INPUT': count_width['OUTPUT'],
            'EXPRESSION': 'width_bbox_range',
            'ASCENDING': True,
            'OUTPUT': parameters['output_width_range']
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        results['output_width_range'] = sorted_width['OUTPUT']
        context.layerToLoadOnCompletionDetails(results['output_width_range']).name = "conteggio_range_larghezza_componenti_a_secco"
        
        sorted_height = processing.run('native:orderbyexpression', {
            'INPUT': count_height['OUTPUT'],
            'EXPRESSION': 'height_bbox_range',
            'ASCENDING': True,
            'OUTPUT': parameters['output_height_range']
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        results['output_height_range'] = sorted_height['OUTPUT']
        context.layerToLoadOnCompletionDetails(results['output_height_range']).name = "conteggio_range_altezza_componenti_a_secco"
        
        return stats

    def _create_rilievo_analysis(self, layer_base: str, bbox_layer: str,
                                 parameters: Dict, valore_modulo: float, context, feedback, results: Dict):
        """Crea il layer di analisi del rilievo con campi calcolati"""
        feedback.pushInfo("\n--- ANALISI RILIEVO ---")
        
        # Join rilievo con bbox
        rilievo_bbox_temp = processing.run('native:joinattributestable', {
            'INPUT': layer_base,
            'INPUT_2': bbox_layer,
            'FIELD': FieldNames.FID,
            'FIELD_2': FieldNames.FID,
            'FIELDS_TO_COPY': [FieldNames.WIDTH_BBOX, FieldNames.HEIGHT_BBOX,
                             FieldNames.ANGLE_BBOX, FieldNames.PERIMETER_BBOX,
                             FieldNames.AREA_BBOX],
            'DISCARD_NONMATCHING': True,
            'METHOD': 1,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        # Riorganizza campi
        field_mapping = self.create_field_mapping([
            (f'"{FieldNames.FID}"', FieldNames.FID, 4, 0, 0),
            (f'"{FieldNames.SITO}"', FieldNames.SITO, 10, 0, 0),
            (f'"{FieldNames.AMBIENTE}"', FieldNames.AMBIENTE, 10, 0, 0),
            (f'"{FieldNames.USM}"', FieldNames.USM, 10, 0, 0),
            (f'"{FieldNames.CAMPIONE}"', FieldNames.CAMPIONE, 10, 0, 0),
            (f'"{FieldNames.NUM_COMPONENTE}"', FieldNames.NUM_COMPONENTE, 4, 0, 0),
            (f'"{FieldNames.TIPO}"', FieldNames.TIPO, 10, 0, 0),
            (f'"{FieldNames.SUPERFICIE}"', FieldNames.SUPERFICIE, 10, 0, 0),
            (f'"{FieldNames.AREA_COMPONENTE}"', FieldNames.AREA_COMPONENTE, 6, 6, 3),
            (f'"{FieldNames.WIDTH_BBOX}"', FieldNames.WIDTH_BBOX, 6, 6, 3),
            (f'"{FieldNames.HEIGHT_BBOX}"', FieldNames.HEIGHT_BBOX, 6, 6, 3),
            (f'"{FieldNames.ANGLE_BBOX}"', FieldNames.ANGLE_BBOX, 6, 6, 3),
            (f'"{FieldNames.PERIMETER_BBOX}"', FieldNames.PERIMETER_BBOX, 6, 6, 3),
            (f'"{FieldNames.AREA_BBOX}"', FieldNames.AREA_BBOX, 6, 6, 3)
        ])
        
        rilievo_bbox = processing.run('native:refactorfields', {
            'INPUT': rilievo_bbox_temp['OUTPUT'],
            'FIELDS_MAPPING': field_mapping,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        rilievo_refactored = processing.run('native:refactorfields', {
            'INPUT': rilievo_bbox['OUTPUT'],
            'FIELDS_MAPPING': field_mapping,
            'OUTPUT': parameters['output_rilievo']
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        results['output_rilievo'] = rilievo_refactored['OUTPUT']
        context.layerToLoadOnCompletionDetails(results['output_rilievo']).name = "analisi_rilievo_componenti_a_secco"
        
        # ========== AGGIUNTA CAMPI VIRTUALI (SOLO PER SUPERFICIE='INTERA') ==========
        feedback.pushInfo("\n--- AGGIUNTA CAMPI VIRTUALI ---")
        layer = QgsProcessingUtils.mapLayerFromString(results['output_rilievo'], context)
        if layer:
            # Aggiungi variabile modulo al layer
            QgsExpressionContextUtils.setLayerVariable(layer, 'modulo', valore_modulo)
            feedback.pushInfo(f"Variabile 'modulo' aggiunta al layer (valore: {valore_modulo})")
            
            # Aggiungi campi virtuali
            from qgis.PyQt.QtCore import QVariant
            from qgis.core import QgsField
            
            # Campo 1: width_modulo (solo per superficie = 'intera')
            width_modulo_expr = '''CASE 
        WHEN "superficie" = 'intera' THEN floor("width_bbox" / @modulo)
        ELSE NULL
    END'''
            layer.addExpressionField(width_modulo_expr, QgsField('width_modulo', QVariant.Int))
            feedback.pushInfo("Campo virtuale 'width_modulo' aggiunto (solo per superficie='intera')")
            
            # Campo 2: Δwidth_modulo (solo per superficie = 'intera')
            delta_width_modulo_expr = '''CASE 
        WHEN "superficie" = 'intera' THEN round("width_bbox" % @modulo, 3)
        ELSE NULL
    END'''
            layer.addExpressionField(delta_width_modulo_expr, QgsField('Δwidth_modulo', QVariant.Double))
            feedback.pushInfo("Campo virtuale 'Δwidth_modulo' aggiunto (solo per superficie='intera')")
            
            # Campo 3: height_modulo (solo per superficie = 'intera')
            height_modulo_expr = '''CASE 
        WHEN "superficie" = 'intera' THEN floor("height_bbox" / @modulo)
        ELSE NULL
    END'''
            layer.addExpressionField(height_modulo_expr, QgsField('height_modulo', QVariant.Int))
            feedback.pushInfo("Campo virtuale 'height_modulo' aggiunto (solo per superficie='intera')")
            
            # Campo 4: Δheight_modulo (solo per superficie = 'intera')
            delta_height_modulo_expr = '''CASE 
        WHEN "superficie" = 'intera' THEN round("height_bbox" % @modulo, 3)
        ELSE NULL
    END'''
            layer.addExpressionField(delta_height_modulo_expr, QgsField('Δheight_modulo', QVariant.Double))
            feedback.pushInfo("Campo virtuale 'Δheight_modulo' aggiunto (solo per superficie='intera')")
            
        self.verifica_features(results['output_rilievo'], context, feedback, "Analisi rilievo FINALE")

    def _create_campioni_analysis(self, parameters: Dict, stats: Dict,
                                  context, feedback, results: Dict):
        """Crea i layer di analisi dei campioni (tabella e layer poligonale)"""
        feedback.pushInfo("\n--- AGGREGAZIONE STATISTICHE CAMPIONI ---")
        
        # Rinomina layer per identificazione
        stat_layers = {}
        for key, stat_type in [('area_int', 'stat_area_int'), ('area_parz', 'stat_area_parz'),
                               ('width', 'stat_width_bbox'), ('height', 'stat_height_bbox')]:
            stat_layers[key] = processing.run('native:renamelayer', {
                'INPUT': stats[key]['OUTPUT'],
                'NAME': stat_type
            }, context=context, feedback=feedback, is_child_algorithm=True)
        
        # Merge statistiche
        merged_stats = processing.run('native:mergevectorlayers', {
            'LAYERS': [layer['OUTPUT'] for layer in stat_layers.values()],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        # Riorganizza
        stats_reorganized = processing.run('native:refactorfields', {
            'INPUT': merged_stats['OUTPUT'],
            'FIELDS_MAPPING': self.create_field_mapping([
                (f'"{FieldNames.CAMPIONE}"', FieldNames.CAMPIONE, 10, 0, 0),
                ('"layer"', 'stat_type', 10, 0, 0),
                ('"count"', 'count', 2, 0, 0),
                ('"min"', 'min', 6, 0, 3),
                ('"max"', 'max', 6, 0, 3),
                ('"range"', 'range', 6, 0, 3),
                ('"sum"', 'sum', 6, 0, 3),
                ('"mean"', 'mean', 6, 0, 3),
                ('"stddev"', 'stddev', 6, 0, 3)
            ]),
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        feedback.setCurrentStep(12)
        
        # Estrai ogni tipo di statistica
        stat_types = ['stat_area_parz', 'stat_area_int', 'stat_width_bbox', 'stat_height_bbox']
        extracted_stats = {}
        
        for stat_type in stat_types:
            extracted_stats[stat_type] = processing.run('native:extractbyexpression', {
                'INPUT': stats_reorganized['OUTPUT'],
                'EXPRESSION': f'"stat_type" = \'{stat_type}\'',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
        
        # Join sequenziale
        current_layer = parameters['layer_campioni']
        
        # Join parziali
        current_layer = processing.run('native:joinattributestable', {
            'INPUT': current_layer,
            'INPUT_2': extracted_stats['stat_area_parz']['OUTPUT'],
            'FIELD': FieldNames.CAMPIONE,
            'FIELD_2': FieldNames.CAMPIONE,
            'FIELDS_TO_COPY': ['count', 'sum'],
            'PREFIX': 'parz_',
            'METHOD': 1,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']
        
        # Join interi
        current_layer = processing.run('native:joinattributestable', {
            'INPUT': current_layer,
            'INPUT_2': extracted_stats['stat_area_int']['OUTPUT'],
            'FIELD': FieldNames.CAMPIONE,
            'FIELD_2': FieldNames.CAMPIONE,
            'FIELDS_TO_COPY': ['count', 'sum', 'mean'],
            'PREFIX': 'int_',
            'METHOD': 1,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']
        
        # Join width
        current_layer = processing.run('native:joinattributestable', {
            'INPUT': current_layer,
            'INPUT_2': extracted_stats['stat_width_bbox']['OUTPUT'],
            'FIELD': FieldNames.CAMPIONE,
            'FIELD_2': FieldNames.CAMPIONE,
            'FIELDS_TO_COPY': ['min', 'max', 'range', 'mean', 'stddev'],
            'PREFIX': 'width_',
            'METHOD': 1,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)['OUTPUT']
        
        # Join height
        all_stats = processing.run('native:joinattributestable', {
            'INPUT': current_layer,
            'INPUT_2': extracted_stats['stat_height_bbox']['OUTPUT'],
            'FIELD': FieldNames.CAMPIONE,
            'FIELD_2': FieldNames.CAMPIONE,
            'FIELDS_TO_COPY': ['min', 'max', 'range', 'mean', 'stddev'],
            'PREFIX': 'height_',
            'METHOD': 1,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        feedback.setCurrentStep(13)
        
        # Refactor con conversioni tipo
        all_stats_final = self._create_final_stats_table(all_stats['OUTPUT'], context, feedback)
        feedback.setCurrentStep(14)
        
        # Calcoli finali
        final_calcs = self._compute_final_calculations(all_stats_final['OUTPUT'], context, feedback)
        feedback.setCurrentStep(15)
        
        # Crea tabella e layer poligonale
        self._create_output_tables(final_calcs, parameters, context, feedback, results)
        feedback.setCurrentStep(16)

    def _create_final_stats_table(self, input_layer: str, context, feedback) -> Dict:
        """Crea la tabella delle statistiche finali con tutti i campi"""
        field_mapping = self.create_field_mapping([
            (f'"{FieldNames.SITO}"', FieldNames.SITO, 10, 0, 0),
            (f'"{FieldNames.AMBIENTE}"', FieldNames.AMBIENTE, 10, 0, 0),
            (f'"{FieldNames.USM}"', FieldNames.USM, 10, 0, 0),
            (f'"{FieldNames.CAMPIONE}"', FieldNames.CAMPIONE, 10, 0, 0),
            (f'to_real("{FieldNames.AREA_CAMPIONE}")', 'area campione', 6, 0, 3),
            ('to_int("parz_count")', 'num. componenti parziali', 2, 0, 0),
            ('to_real("parz_sum")', 'totale area componenti parziali', 6, 0, 3),
            ('to_int("int_count")', 'num. componenti interi', 2, 0, 0),
            ('to_real("int_sum")', 'totale area componenti interi', 6, 0, 3),
            ('to_real("int_mean")', 'media area componenti interi', 6, 0, 3),
            ('to_real("width_min")', 'width_min', 6, 0, 3),
            ('to_real("width_max")', 'width_max', 6, 0, 3),
            ('to_real("width_range")', 'width_range', 6, 0, 3),
            ('to_real("width_mean")', 'width_mean', 6, 0, 3),
            ('to_real("width_stddev")', 'width_stddev', 6, 0, 3),
            ('to_real("height_min")', 'height_min', 6, 0, 3),
            ('to_real("height_max")', 'height_max', 6, 0, 3),
            ('to_real("height_range")', 'height_range', 6, 0, 3),
            ('to_real("height_mean")', 'height_mean', 6, 0, 3),
            ('to_real("height_stddev")', 'height_stddev', 6, 0, 3)
        ])
        
        return processing.run('native:refactorfields', {
            'INPUT': input_layer,
            'FIELDS_MAPPING': field_mapping,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)

    def _compute_final_calculations(self, input_layer: str, context, feedback) -> str:
        """Esegue i calcoli finali (solo totale area componenti)"""
        feedback.pushInfo("\n--- CALCOLI FINALI ---")
        
        # Calcola solo totale area componenti
        calc1 = processing.run('native:fieldcalculator', {
            'INPUT': input_layer,
            'FIELD_NAME': 'totale area componenti',
            'FIELD_TYPE': 0,
            'FORMULA': 'round(COALESCE("totale area componenti interi", 0) + COALESCE("totale area componenti parziali", 0), 3)',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        return calc1['OUTPUT']

    def _create_output_tables(self, input_layer: str, parameters: Dict,
                             context, feedback, results: Dict):
        """Crea le tabelle di output (tabellare e layer poligonale)"""
        feedback.pushInfo("\n--- CREAZIONE TABELLA ANALISI CAMPIONI ---")
        
        # Mapping campi finali per tabella (RIMOSSI totale_area_malta e rapporto_componenti/malta)
        table_fields = self.create_field_mapping([
            (f'"{FieldNames.SITO}"', FieldNames.SITO, 10, 0, 0),
            (f'"{FieldNames.AMBIENTE}"', FieldNames.AMBIENTE, 10, 0, 0),
            (f'"{FieldNames.USM}"', FieldNames.USM, 10, 0, 0),
            (f'"{FieldNames.CAMPIONE}"', FieldNames.CAMPIONE, 10, 0, 0),
            ('"area campione"', 'area_campione', 6, 0, 3),
            ('"num. componenti interi"', 'num_componenti_interi', 2, 0, 0),
            ('"totale area componenti interi"', 'totale_area_componenti_interi', 6, 0, 3),
            ('"media area componenti interi"', 'media_area_componenti_interi', 6, 0, 3),
            ('"num. componenti parziali"', 'num_componenti_parziali', 2, 0, 0),
            ('"totale area componenti parziali"', 'totale_area_componenti_parziali', 6, 0, 3),
            ('"totale area componenti"', 'totale_area_componenti', 6, 0, 3),
            ('"width_min"', 'width_min', 6, 0, 3),
            ('"width_max"', 'width_max', 6, 0, 3),
            ('"width_range"', 'width_range', 6, 0, 3),
            ('"width_mean"', 'width_mean', 6, 0, 3),
            ('"width_stddev"', 'width_stddev', 6, 0, 3),
            ('"height_min"', 'height_min', 6, 0, 3),
            ('"height_max"', 'height_max', 6, 0, 3),
            ('"height_range"', 'height_range', 6, 0, 3),
            ('"height_mean"', 'height_mean', 6, 0, 3),
            ('"height_stddev"', 'height_stddev', 6, 0, 3)
        ])
        
        table_refactored = processing.run('native:refactorfields', {
            'INPUT': input_layer,
            'FIELDS_MAPPING': table_fields,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        # Rimuovi geometrie per tabella pura
        table_final = processing.run('native:dropgeometries', {
            'INPUT': table_refactored['OUTPUT'],
            'OUTPUT': parameters['output_campioni_table']
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        results['output_campioni_table'] = table_final['OUTPUT']
        context.layerToLoadOnCompletionDetails(results['output_campioni_table']).name = "analisi_campioni_table_componenti_a_secco"
        self.verifica_features(results['output_campioni_table'], context, feedback, "Tabella analisi campioni")
        
        # Layer poligonale
        feedback.pushInfo("\n--- CREAZIONE LAYER POLIGONALE CAMPIONI---")
        
        # Join con layer campioni originale (RIMOSSI totale_area_malta e rapporto_componenti/malta)
        campioni_geo = processing.run('native:joinattributestable', {
            'INPUT': parameters['layer_campioni'],
            'INPUT_2': table_final['OUTPUT'],
            'FIELD': FieldNames.CAMPIONE,
            'FIELD_2': FieldNames.CAMPIONE,
            'FIELDS_TO_COPY': [
                'num_componenti_interi', 'totale_area_componenti_interi', 'media_area_componenti_interi',
                'num_componenti_parziali', 'totale_area_componenti_parziali',
                'totale_area_componenti',
                'width_min', 'width_max', 'width_range', 'width_mean',
                'width_stddev', 'height_min', 'height_max', 'height_range', 'height_mean', 'height_stddev'
            ],
            'DISCARD_NONMATCHING': True,
            'METHOD': 1,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        # Riorganizza campi layer poligonale (RIMOSSI totale_area_malta e rapporto_componenti/malta)
        geo_fields = self.create_field_mapping([
            ('"fid"', 'fid', 4, 0, 0),
            (f'"{FieldNames.SITO}"', FieldNames.SITO, 10, 0, 0),
            (f'"{FieldNames.USM}"', FieldNames.USM, 10, 0, 0),
            (f'"{FieldNames.AMBIENTE}"', FieldNames.AMBIENTE, 10, 0, 0),
            (f'"{FieldNames.CAMPIONE}"', FieldNames.CAMPIONE, 10, 0, 0),
            (f'"{FieldNames.AREA_CAMPIONE}"', 'area_campione', 6, 0, 3),
            ('"num_componenti_parziali"', 'num_componenti_parziali', 2, 0, 0),
            ('"totale_area_componenti_parziali"', 'totale_area_componenti_parziali', 6, 0, 3),
            ('"num_componenti_interi"', 'num_componenti_interi', 2, 0, 0),
            ('"totale_area_componenti_interi"', 'totale_area_componenti_interi', 6, 0, 3),
            ('"media_area_componenti_interi"', 'media_area_componenti_interi', 6, 0, 3),
            ('"totale_area_componenti"', 'totale_area_componenti', 6, 0, 3),
            ('"width_min"', 'width_min', 6, 0, 3),
            ('"width_max"', 'width_max', 6, 0, 3),
            ('"width_range"', 'width_range', 6, 0, 3),
            ('"width_mean"', 'width_mean', 6, 0, 3),
            ('"width_stddev"', 'width_stddev', 6, 0, 3),
            ('"height_min"', 'height_min', 6, 0, 3),
            ('"height_max"', 'height_max', 6, 0, 3),
            ('"height_range"', 'height_range', 6, 0, 3),
            ('"height_mean"', 'height_mean', 6, 0, 3),
            ('"height_stddev"', 'height_stddev', 6, 0, 3)
        ])
        
        campioni_final = processing.run('native:refactorfields', {
            'INPUT': campioni_geo['OUTPUT'],
            'FIELDS_MAPPING': geo_fields,
            'OUTPUT': parameters['output_campioni']
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        results['output_campioni'] = campioni_final['OUTPUT']
        context.layerToLoadOnCompletionDetails(results['output_campioni']).name = "analisi_campioni_componenti_a_secco"
        self.verifica_features(results['output_campioni'], context, feedback, "Analisi campioni layer poligonale")

    def _log_summary(self, count_interi: int, count_parziali: int, params: Dict,
                    results: Dict, context, feedback):
        """Stampa il riepilogo finale dell'elaborazione"""
        feedback.pushInfo("\n" + "="*70)
        feedback.pushInfo("ELABORAZIONE COMPLETATA CON SUCCESSO")
        feedback.pushInfo("="*70)
        
        feedback.pushInfo("\n[RIEPILOGO ELABORAZIONE]")
        feedback.pushInfo(f"Componenti totali analizzati: {count_interi + count_parziali}")
        feedback.pushInfo(f"  - Componenti interi: {count_interi}")
        feedback.pushInfo(f"  - Componenti parziali: {count_parziali}")
        
        if params['applica_filtro']:
            feedback.pushInfo(f"\n[FILTRO APPLICATO]")
            feedback.pushInfo(f"Tipi materiale: {', '.join(params['tipi'])}")
            if params['includi_null']:
                feedback.pushInfo("Include non classificati: SI")
        else:
            feedback.pushInfo("\n[NESSUN FILTRO] - Tutti i materiali inclusi")
        
        feedback.pushInfo("\n[PARAMETRI RANGE]")
        feedback.pushInfo(f"Step larghezza: {params['width_step']} m")
        feedback.pushInfo(f"Step altezza: {params['height_step']} m")
        
        feedback.pushInfo("\n[PARAMETRI UNITÀ DI MISURA]")
        feedback.pushInfo(f"Valore del modulo: {params['valore_modulo']} m")
        
        feedback.pushInfo("\n[OUTPUT GENERATI]")
        for name in results.keys():
            layer = QgsProcessingUtils.mapLayerFromString(results[name], context)
            if layer:
                feedback.pushInfo(f"  * {layer.name()}: {layer.featureCount()} features")
        
        feedback.pushInfo("\n[CAMPI AGGIUNTI AL LAYER RILIEVO]")
        feedback.pushInfo("  * width_modulo (intero) - Numero di moduli interi nella larghezza - SOLO per superficie='intera'")
        feedback.pushInfo("  * Δwidth_modulo (decimale, 3 decimali) - Resto della larghezza - SOLO per superficie='intera'")
        feedback.pushInfo("  * height_modulo (intero) - Numero di moduli interi nell'altezza - SOLO per superficie='intera'")
        feedback.pushInfo("  * Δheight_modulo (decimale, 3 decimali) - Resto dell'altezza - SOLO per superficie='intera'")
        feedback.pushInfo("  * Valore NULL per tutti i componenti con superficie != 'intera'")
        
        feedback.pushInfo("\n" + "="*70)

    def name(self) -> str:
        return 'analisi_componenti_a_secco'

    def displayName(self) -> str:
        return 'Componenti a secco'

    def group(self) -> str:
        return 'Analisi quantitative'

    def groupId(self) -> str:
        return 'analisi'

    def createInstance(self):
        return Analisi()

    def shortHelpString(self) -> str:
        return """
        <h3>Analisi Quantitativa Componenti a Secco - Versione 1.0</h3>
        
        <p>Analizza le geometrie dei componenti in una muratura calcolando statistiche dettagliate su dimensioni, aree e distribuzioni dei materiali.</p>
        
        <h4>Parametri di Input:</h4>
        <ul>
            <li><b>Layer rilievo:</b> Poligoni dei componenti murari (richiede: fid, tipo, superficie, area_componente, num_componente)</li>
            <li><b>Layer campioni:</b> Poligoni dei campioni di muratura (richiede: campione, sito, ambiente, usm, area_campione)</li>
            <li><b>Tipo di materiale:</b> Lista separata da virgole o vuoto per tutti</li>
            <li><b>Includi non classificati:</b> Include elementi con tipo NULL</li>
            <li><b>Step range larghezza:</b> Incremento per calcolo dei range di larghezza (metri)</li>
            <li><b>Step range altezza:</b> Incremento per calcolo dei range di altezza (metri)</li>
            <li><b>Valore del modulo:</b> Unità di misura per calcoli metrici (default: 0.296 m per piede attico/romano)</li>
        </ul>
        
        <h4>Output Generati:</h4>
        <ul>
            <li><b>min_oriented_bbox:</b> Rettangoli orientati minimi</li>
            <li><b>analisi_rilievo:</b> Rilievo arricchito con metriche bbox e campi calcolati (width_modulo, Δwidth_modulo, height_modulo, Δheight_modulo)</li>
            <li><b>analisi_campioni_table:</b> Statistiche per campione (tabella)</li>
            <li><b>analisi_campioni:</b> Campioni con statistiche (layer poligonale)</li>
            <li><b>conteggio_range_larghezza/altezza:</b> Distribuzioni per range</li>
        </ul>
        
        <h4>Campi Calcolati nel Layer Rilievo:</h4>
        <p><b>IMPORTANTE: I seguenti campi vengono calcolati SOLO per gli elementi con superficie = 'intera'. Per tutti gli altri elementi (superficie = 'parziale' o altro) i campi avranno valore NULL.</b></p>
        <ul>
            <li><b>width_modulo:</b> Numero di moduli interi nella larghezza (floor(width_bbox / valore_modulo))</li>
            <li><b>Δwidth_modulo:</b> Resto della larghezza in metri (width_bbox % valore_modulo, arrotondato a 3 decimali)</li>
            <li><b>height_modulo:</b> Numero di moduli interi nell'altezza (floor(height_bbox / valore_modulo))</li>
            <li><b>Δheight_modulo:</b> Resto dell'altezza in metri (height_bbox % valore_modulo, arrotondato a 3 decimali)</li>
        </ul>
        
        <h4>Note Importanti:</h4>
        <ul>
            <li>Il layer rilievo deve contenere i campi: fid, tipo, superficie, area_componente, num_componente</li>
            <li>Il layer campioni deve contenere i campi: campione, sito, ambiente, usm, area_campione</li>
            <li>I componenti vengono separati in "interi" e "parziali" in base al campo "superficie"</li>
            <li>Le statistiche vengono calcolate solo sui componenti interi</li>
            <li>I campi width_modulo, Δwidth_modulo, height_modulo e Δheight_modulo sono NULL per i componenti parziali</li>
            <li>Il filtro materiali è case-sensitive</li>
            <li>Al layer analisi_rilievo viene aggiunta la variabile 'modulo' con il valore del modulo impostato dall'utente</li>
            <li>Il valore del modulo può essere personalizzato (default 0.296 m per piede attico/romano)</li>
        </ul>
        
        <p><b>Versione:</b> 1.0</p>
        """

