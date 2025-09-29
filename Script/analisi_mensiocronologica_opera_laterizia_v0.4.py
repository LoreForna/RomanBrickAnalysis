"""
SCRIPT ANALISI MENSIOCRONOLOGICA PER OPERA LATERIZIA - VERSIONE OTTIMIZZATA
"""

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFile,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsProcessingParameterBoolean,
    QgsProcessingException,
    QgsProcessingUtils
)
import processing
import os


class AnalisiFiltrata(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
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
            defaultValue=0.002,
            minValue=0.001
        ))
        
        self.addParameter(QgsProcessingParameterNumber(
            'height_range_step',
            'Step range altezza (m)',
            type=QgsProcessingParameterNumber.Double,
            defaultValue=0.001,
            minValue=0.001
        ))
        
        # Output layers
        self.addParameter(QgsProcessingParameterFeatureSink(
            'output_bbox',
            'Min oriented bbox',
            type=QgsProcessing.TypeVectorPolygon
        ))
        
        self.addParameter(QgsProcessingParameterFeatureSink(
            'output_rilievo',
            'Analisi rilievo',
            type=QgsProcessing.TypeVectorPolygon
        ))
        
        self.addParameter(QgsProcessingParameterFeatureSink(
            'output_campioni_table',
            'Analisi campioni (tabella)',
            type=QgsProcessing.TypeVectorAnyGeometry
        ))
        
        self.addParameter(QgsProcessingParameterFeatureSink(
            'output_campioni',
            'Analisi campioni (geografico)',
            type=QgsProcessing.TypeVectorAnyGeometry
        ))
        
        self.addParameter(QgsProcessingParameterFeatureSink(
            'output_width_range',
            'Conteggio range larghezza',
            type=QgsProcessing.TypeVectorAnyGeometry
        ))
        
        self.addParameter(QgsProcessingParameterFeatureSink(
            'output_height_range',
            'Conteggio range altezza',
            type=QgsProcessing.TypeVectorAnyGeometry
        ))

    def verifica_features(self, layer_id, context, feedback, step_name):
        """Conta e mostra le features a ogni step"""
        layer = QgsProcessingUtils.mapLayerFromString(layer_id, context)
        if layer and layer.isValid():
            count = layer.featureCount()
            feedback.pushInfo(f"  --> {step_name}: {count} features")
            
            # Conta per tipo se esiste il campo
            if 'tipo' in [f.name() for f in layer.fields()]:
                tipi = {}
                for feat in layer.getFeatures():
                    tipo = str(feat['tipo']) if feat['tipo'] else 'NULL'
                    tipi[tipo] = tipi.get(tipo, 0) + 1
                for tipo, cnt in sorted(tipi.items()):
                    feedback.pushInfo(f"      * {tipo}: {cnt}")
            return count
        return 0

    def processAlgorithm(self, parameters, context, model_feedback):
        feedback = QgsProcessingMultiStepFeedback(19, model_feedback)
        results = {}
        
        try:
            feedback.pushInfo("\n" + "="*70)
            feedback.pushInfo("ANALISI MENSIOCRONOLOGICA - VERSIONE OTTIMIZZATA")
            feedback.pushInfo("="*70)
            
            # ============ FASE 1: PARAMETRI E VALIDAZIONE ============
            layer_rilievo = self.parameterAsSource(parameters, 'layer_rilievo', context)
            layer_campioni = self.parameterAsSource(parameters, 'layer_campioni', context)
            tipo_input = self.parameterAsString(parameters, 'tipo_materiale', context).strip()
            includi_null = self.parameterAsBool(parameters, 'includi_non_classificati', context)
            width_step = self.parameterAsDouble(parameters, 'width_range_step', context)
            height_step = self.parameterAsDouble(parameters, 'height_range_step', context)
            
            # Validazione parametri
            if layer_rilievo.featureCount() == 0:
                raise QgsProcessingException("Il layer rilievo e' vuoto!")
            if layer_campioni.featureCount() == 0:
                raise QgsProcessingException("Il layer campioni e' vuoto!")
            if width_step <= 0:
                raise QgsProcessingException("Lo step larghezza deve essere maggiore di 0!")
            if height_step <= 0:
                raise QgsProcessingException("Lo step altezza deve essere maggiore di 0!")
            
            feedback.pushInfo(f"\nLayer rilievo: {layer_rilievo.featureCount()} features")
            feedback.pushInfo(f"Layer campioni: {layer_campioni.featureCount()} features")
            
            # Parse tipi materiale
            if tipo_input:
                tipi = [t.strip() for t in tipo_input.split(',') if t.strip()]
                applica_filtro = True
                feedback.pushInfo(f"Filtro materiali: {', '.join(tipi)}")
                if includi_null:
                    feedback.pushInfo("  (+ elementi non classificati)")
            else:
                tipi = []
                applica_filtro = False
                feedback.pushInfo("Filtro materiali: NESSUNO (tutti i tipi)")
            
            feedback.setCurrentStep(1)
            
            # ============ FASE 2: SPATIAL JOIN ============
            feedback.pushInfo("\n--- SPATIAL JOIN ---")
            
            joined = processing.run('native:joinattributesbylocation', {
                'INPUT': parameters['layer_rilievo'],
                'JOIN': parameters['layer_campioni'],
                'JOIN_FIELDS': ['campione', 'ambiente', 'usm', 'sito'],
                'PREDICATE': [0],
                'METHOD': 0,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            self.verifica_features(joined['OUTPUT'], context, feedback, "Dopo spatial join")
            feedback.setCurrentStep(2)
            
            # ============ FASE 3: FILTRO MATERIALI ============
            if applica_filtro:
                feedback.pushInfo("\n--- APPLICAZIONE FILTRO ---")
                
                # Costruisci espressione
                if len(tipi) == 1:
                    expr = f'"tipo" = \'{tipi[0]}\''
                else:
                    tipi_quoted = "','".join(tipi)
                    expr = f'"tipo" IN (\'{tipi_quoted}\')'
                
                # Aggiungi NULL se richiesto
                if includi_null:
                    expr = f'({expr}) OR "tipo" IS NULL OR "tipo" = \'NULL\''
                
                feedback.pushInfo(f"Espressione filtro: {expr}")
                
                filtrato = processing.run('native:extractbyexpression', {
                    'EXPRESSION': expr,
                    'INPUT': joined['OUTPUT'],
                    'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
                }, context=context, feedback=feedback, is_child_algorithm=True)
                
                count_filtrato = self.verifica_features(filtrato['OUTPUT'], context, feedback, "Dopo filtro")
                
                if count_filtrato == 0:
                    raise QgsProcessingException(f"Il filtro ha prodotto 0 risultati! Verifica i valori: {', '.join(tipi)}")
                
                layer_base = filtrato['OUTPUT']
            else:
                feedback.pushInfo("\n--- NESSUN FILTRO APPLICATO ---")
                layer_base = joined['OUTPUT']
            
            feedback.setCurrentStep(3)
            
            # ============ FASE 4: BOUNDING BOX ============
            feedback.pushInfo("\n--- CALCOLO BOUNDING BOX ---")
            
            bbox = processing.run('qgis:minimumboundinggeometry', {
                'INPUT': layer_base,
                'FIELD': 'fid',
                'TYPE': 1,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            self.verifica_features(bbox['OUTPUT'], context, feedback, "Bounding box creati")
            feedback.setCurrentStep(4)
            
            # Join bbox con attributi originali
            bbox_full = processing.run('native:joinattributestable', {
                'INPUT': bbox['OUTPUT'],
                'INPUT_2': layer_base,
                'FIELD': 'fid',
                'FIELD_2': 'fid',
                'METHOD': 1,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            feedback.setCurrentStep(5)
            
            # Riorganizza campi bbox
            bbox_final = processing.run('native:refactorfields', {
                'INPUT': bbox_full['OUTPUT'],
                'FIELDS_MAPPING': [
                    {'expression': '"fid"', 'name': 'fid', 'type': 4, 'length': 0, 'precision': 0},
                    {'expression': '"sito"', 'name': 'sito', 'type': 10, 'length': 0, 'precision': 0},
                    {'expression': '"ambiente"', 'name': 'ambiente', 'type': 10, 'length': 0, 'precision': 0},
                    {'expression': '"usm"', 'name': 'usm', 'type': 10, 'length': 0, 'precision': 0},
                    {'expression': '"campione"', 'name': 'campione', 'type': 10, 'length': 0, 'precision': 0},
                    {'expression': '"num_componente"', 'name': 'num_componente', 'type': 4, 'length': 0, 'precision': 0},
                    {'expression': '"tipo"', 'name': 'tipo', 'type': 10, 'length': 0, 'precision': 0},
                    {'expression': '"superficie"', 'name': 'superficie', 'type': 10, 'length': 0, 'precision': 0},
                    {'expression': '"area_componente"', 'name': 'area_componente', 'type': 6, 'length': 6, 'precision': 4},
                    {'expression': '"height"', 'name': 'width_bbox', 'type': 6, 'length': 6, 'precision': 4},
                    {'expression': '"width"', 'name': 'height_bbox', 'type': 6, 'length': 6, 'precision': 4},
                    {'expression': '"angle"', 'name': 'angle_bbox', 'type': 6, 'length': 6, 'precision': 4},
                    {'expression': '"perimeter"', 'name': 'perimeter_bbox', 'type': 6, 'length': 6, 'precision': 4},
                    {'expression': '"area"', 'name': 'area_bbox', 'type': 6, 'length': 6, 'precision': 4}
                ],
                'OUTPUT': parameters['output_bbox']
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            results['output_bbox'] = bbox_final['OUTPUT']
            context.layerToLoadOnCompletionDetails(results['output_bbox']).name = "min_oriented_bbox"
            self.verifica_features(results['output_bbox'], context, feedback, "Min oriented bbox FINALE")
            feedback.setCurrentStep(6)
            
            # ============ FASE 5: SEPARAZIONE INTERI/PARZIALI ============
            feedback.pushInfo("\n--- SEPARAZIONE INTERI/PARZIALI ---")
            
            interi = processing.run('native:extractbyattribute', {
                'INPUT': bbox_final['OUTPUT'],
                'FIELD': 'superficie',
                'OPERATOR': 0,
                'VALUE': 'intera',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            parziali = processing.run('native:extractbyattribute', {
                'INPUT': bbox_final['OUTPUT'],
                'FIELD': 'superficie',
                'OPERATOR': 0,
                'VALUE': 'parziale',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            count_interi = self.verifica_features(interi['OUTPUT'], context, feedback, "Componenti interi")
            count_parziali = self.verifica_features(parziali['OUTPUT'], context, feedback, "Componenti parziali")
            
            # Avviso se non ci sono componenti interi (problema per le statistiche)
            if count_interi == 0:
                feedback.pushWarning("ATTENZIONE: Nessun componente intero trovato! Le statistiche potrebbero essere incomplete.")
            
            # Avviso se ci sono solo interi o solo parziali
            if count_parziali == 0:
                feedback.pushInfo("INFO: Nessun componente parziale trovato.")
            
            feedback.setCurrentStep(7)
            
            # ============ FASE 6: CALCOLO RANGE ============
            feedback.pushInfo("\n--- CALCOLO RANGE ---")
            
            # Range width (formula semplificata e piu' robusta)
            with_width_range = processing.run('native:fieldcalculator', {
                'INPUT': interi['OUTPUT'],
                'FIELD_NAME': 'width_bbox_range',
                'FIELD_TYPE': 2,
                'FORMULA': f'''CASE 
    WHEN "width_bbox" IS NULL THEN 'N/A'
    ELSE concat(
        round(floor("width_bbox"/{width_step})*{width_step}, 4),
        ' - ',
        round((floor("width_bbox"/{width_step})+1)*{width_step}, 4)
    )
END''',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            # Range height (formula semplificata e piu' robusta)
            with_both_ranges = processing.run('native:fieldcalculator', {
                'INPUT': with_width_range['OUTPUT'],
                'FIELD_NAME': 'height_bbox_range',
                'FIELD_TYPE': 2,
                'FORMULA': f'''CASE 
    WHEN "height_bbox" IS NULL THEN 'N/A'
    ELSE concat(
        round(floor("height_bbox"/{height_step})*{height_step}, 4),
        ' - ',
        round((floor("height_bbox"/{height_step})+1)*{height_step}, 4)
    )
END''',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            feedback.setCurrentStep(8)
            
            # ============ FASE 7: STATISTICHE ============
            feedback.pushInfo("\n--- STATISTICHE ---")
            
            # Statistiche per campione
            stat_area_int = processing.run('qgis:statisticsbycategories', {
                'INPUT': interi['OUTPUT'],
                'CATEGORIES_FIELD_NAME': ['campione'],
                'VALUES_FIELD_NAME': 'area_componente',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            stat_area_parz = processing.run('qgis:statisticsbycategories', {
                'INPUT': parziali['OUTPUT'],
                'CATEGORIES_FIELD_NAME': ['campione'],
                'VALUES_FIELD_NAME': 'area_componente',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            stat_width = processing.run('qgis:statisticsbycategories', {
                'INPUT': interi['OUTPUT'],
                'CATEGORIES_FIELD_NAME': ['campione'],
                'VALUES_FIELD_NAME': 'width_bbox',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            stat_height = processing.run('qgis:statisticsbycategories', {
                'INPUT': interi['OUTPUT'],
                'CATEGORIES_FIELD_NAME': ['campione'],
                'VALUES_FIELD_NAME': 'height_bbox',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            feedback.setCurrentStep(9)
            
            # Conteggi per range
            count_width = processing.run('qgis:statisticsbycategories', {
                'INPUT': with_both_ranges['OUTPUT'],
                'CATEGORIES_FIELD_NAME': ['campione', 'width_bbox_range'],
                'VALUES_FIELD_NAME': '',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            count_height = processing.run('qgis:statisticsbycategories', {
                'INPUT': with_both_ranges['OUTPUT'],
                'CATEGORIES_FIELD_NAME': ['campione', 'height_bbox_range'],
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
            context.layerToLoadOnCompletionDetails(results['output_width_range']).name = "conteggio_range_larghezza"
            
            sorted_height = processing.run('native:orderbyexpression', {
                'INPUT': count_height['OUTPUT'],
                'EXPRESSION': 'height_bbox_range',
                'ASCENDING': True,
                'OUTPUT': parameters['output_height_range']
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            results['output_height_range'] = sorted_height['OUTPUT']
            context.layerToLoadOnCompletionDetails(results['output_height_range']).name = "conteggio_range_altezza"
            feedback.setCurrentStep(10)
            
            # ============ FASE 8: ANALISI RILIEVO ============
            feedback.pushInfo("\n--- ANALISI RILIEVO ---")
            
            # Join rilievo con bbox
            rilievo_bbox_temp = processing.run('native:joinattributestable', {
                'INPUT': layer_base,
                'INPUT_2': bbox_final['OUTPUT'],
                'FIELD': 'fid',
                'FIELD_2': 'fid',
                'FIELDS_TO_COPY': ['width_bbox', 'height_bbox', 'angle_bbox', 'perimeter_bbox', 'area_bbox'],
                'DISCARD_NONMATCHING': True,
                'METHOD': 1,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            # Riorganizza campi come min_oriented_bbox
            rilievo_bbox = processing.run('native:refactorfields', {
                'INPUT': rilievo_bbox_temp['OUTPUT'],
                'FIELDS_MAPPING': [
                    {'expression': '"fid"', 'name': 'fid', 'type': 4, 'length': 0, 'precision': 0},
                    {'expression': '"sito"', 'name': 'sito', 'type': 10, 'length': 0, 'precision': 0},
                    {'expression': '"ambiente"', 'name': 'ambiente', 'type': 10, 'length': 0, 'precision': 0},
                    {'expression': '"usm"', 'name': 'usm', 'type': 10, 'length': 0, 'precision': 0},
                    {'expression': '"campione"', 'name': 'campione', 'type': 10, 'length': 0, 'precision': 0},
                    {'expression': '"num_componente"', 'name': 'num_componente', 'type': 4, 'length': 0, 'precision': 0},
                    {'expression': '"tipo"', 'name': 'tipo', 'type': 10, 'length': 0, 'precision': 0},
                    {'expression': '"superficie"', 'name': 'superficie', 'type': 10, 'length': 0, 'precision': 0},
                    {'expression': '"area_componente"', 'name': 'area_componente', 'type': 6, 'length': 6, 'precision': 4},
                    {'expression': '"width_bbox"', 'name': 'width_bbox', 'type': 6, 'length': 6, 'precision': 4},
                    {'expression': '"height_bbox"', 'name': 'height_bbox', 'type': 6, 'length': 6, 'precision': 4},
                    {'expression': '"angle_bbox"', 'name': 'angle_bbox', 'type': 6, 'length': 6, 'precision': 4},
                    {'expression': '"perimeter_bbox"', 'name': 'perimeter_bbox', 'type': 6, 'length': 6, 'precision': 4},
                    {'expression': '"area_bbox"', 'name': 'area_bbox', 'type': 6, 'length': 6, 'precision': 4}
                ],
                'OUTPUT': parameters['output_rilievo']
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            results['output_rilievo'] = rilievo_bbox['OUTPUT']
            context.layerToLoadOnCompletionDetails(results['output_rilievo']).name = "analisi_rilievo"
            self.verifica_features(results['output_rilievo'], context, feedback, "Analisi rilievo FINALE")
            feedback.setCurrentStep(11)
            
            # ============ FASE 9: AGGREGAZIONE STATISTICHE CON CAMPIONI ============
            feedback.pushInfo("\n--- AGGREGAZIONE STATISTICHE CAMPIONI ---")
            
            # Rinomina layer per merge
            stat_area_int_renamed = processing.run('native:renamelayer', {
                'INPUT': stat_area_int['OUTPUT'],
                'NAME': 'stat_area_int'
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            stat_area_parz_renamed = processing.run('native:renamelayer', {
                'INPUT': stat_area_parz['OUTPUT'],
                'NAME': 'stat_area_parz'
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            stat_width_renamed = processing.run('native:renamelayer', {
                'INPUT': stat_width['OUTPUT'],
                'NAME': 'stat_width_bbox'
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            stat_height_renamed = processing.run('native:renamelayer', {
                'INPUT': stat_height['OUTPUT'],
                'NAME': 'stat_height_bbox'
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            # Merge tutte le statistiche
            merged_stats = processing.run('native:mergevectorlayers', {
                'LAYERS': [
                    stat_area_int_renamed['OUTPUT'],
                    stat_area_parz_renamed['OUTPUT'],
                    stat_width_renamed['OUTPUT'],
                    stat_height_renamed['OUTPUT']
                ],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            # Riorganizza merged stats
            stats_reorganized = processing.run('native:refactorfields', {
                'INPUT': merged_stats['OUTPUT'],
                'FIELDS_MAPPING': [
                    {'expression': '"campione"', 'name': 'campione', 'type': 10},
                    {'expression': '"layer"', 'name': 'stat_type', 'type': 10},
                    {'expression': '"count"', 'name': 'count', 'type': 2},
                    {'expression': '"min"', 'name': 'min', 'type': 6},
                    {'expression': '"max"', 'name': 'max', 'type': 6},
                    {'expression': '"range"', 'name': 'range', 'type': 6},
                    {'expression': '"sum"', 'name': 'sum', 'type': 6},
                    {'expression': '"mean"', 'name': 'mean', 'type': 6},
                    {'expression': '"stddev"', 'name': 'stddev', 'type': 6}
                ],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            feedback.setCurrentStep(12)
            
            # ============ FASE 10: JOIN SEQUENZIALE OTTIMIZZATO ============
            feedback.pushInfo("\n--- JOIN STATISTICHE (OTTIMIZZATO) ---")
            
            # Strategia: partire da campioni e aggiungere progressivamente le statistiche
            # Questo elimina ridondanze: 4 join sequenziali + 1 refactor invece di 11 operazioni
            
            # Estrai e prepara ogni tipo di statistica
            stat_area_parz = processing.run('native:extractbyexpression', {
                'INPUT': stats_reorganized['OUTPUT'],
                'EXPRESSION': '"stat_type" = \'stat_area_parz\'',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            stat_area_int = processing.run('native:extractbyexpression', {
                'INPUT': stats_reorganized['OUTPUT'],
                'EXPRESSION': '"stat_type" = \'stat_area_int\'',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            stat_width = processing.run('native:extractbyexpression', {
                'INPUT': stats_reorganized['OUTPUT'],
                'EXPRESSION': '"stat_type" = \'stat_width_bbox\'',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            stat_height = processing.run('native:extractbyexpression', {
                'INPUT': stats_reorganized['OUTPUT'],
                'EXPRESSION': '"stat_type" = \'stat_height_bbox\'',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            # Join sequenziale: campioni + parz + int + width + height
            campioni_parz = processing.run('native:joinattributestable', {
                'INPUT': parameters['layer_campioni'],
                'INPUT_2': stat_area_parz['OUTPUT'],
                'FIELD': 'campione',
                'FIELD_2': 'campione',
                'FIELDS_TO_COPY': ['count', 'sum'],
                'PREFIX': 'parz_',
                'METHOD': 1,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            campioni_parz_int = processing.run('native:joinattributestable', {
                'INPUT': campioni_parz['OUTPUT'],
                'INPUT_2': stat_area_int['OUTPUT'],
                'FIELD': 'campione',
                'FIELD_2': 'campione',
                'FIELDS_TO_COPY': ['count', 'sum', 'mean'],
                'PREFIX': 'int_',
                'METHOD': 1,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            campioni_parz_int_width = processing.run('native:joinattributestable', {
                'INPUT': campioni_parz_int['OUTPUT'],
                'INPUT_2': stat_width['OUTPUT'],
                'FIELD': 'campione',
                'FIELD_2': 'campione',
                'FIELDS_TO_COPY': ['min', 'max', 'range', 'mean', 'stddev'],
                'PREFIX': 'width_',
                'METHOD': 1,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            all_stats = processing.run('native:joinattributestable', {
                'INPUT': campioni_parz_int_width['OUTPUT'],
                'INPUT_2': stat_height['OUTPUT'],
                'FIELD': 'campione',
                'FIELD_2': 'campione',
                'FIELDS_TO_COPY': ['min', 'max', 'range', 'mean', 'stddev'],
                'PREFIX': 'height_',
                'METHOD': 1,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            feedback.setCurrentStep(13)
            
            # Un unico refactor con tutti i campi (conversioni di tipo incluse)
            all_stats_final = processing.run('native:refactorfields', {
                'INPUT': all_stats['OUTPUT'],
                'FIELDS_MAPPING': [
                    {'expression': '"sito"', 'name': 'sito', 'type': 10, 'length': 0, 'precision': 0},
                    {'expression': '"ambiente"', 'name': 'ambiente', 'type': 10, 'length': 0, 'precision': 0},
                    {'expression': '"usm"', 'name': 'usm', 'type': 10, 'length': 0, 'precision': 0},
                    {'expression': '"campione"', 'name': 'campione', 'type': 10, 'length': 0, 'precision': 0},
                    {'expression': 'to_real("area_campione")', 'name': 'area campione', 'type': 6, 'length': 0, 'precision': 4},
                    {'expression': 'to_int("parz_count")', 'name': 'num. laterizi parziali', 'type': 2, 'length': 0, 'precision': 0},
                    {'expression': 'to_real("parz_sum")', 'name': 'totale area laterizi parziali', 'type': 6, 'length': 0, 'precision': 4},
                    {'expression': 'to_int("int_count")', 'name': 'num. laterizi interi', 'type': 2, 'length': 0, 'precision': 0},
                    {'expression': 'to_real("int_sum")', 'name': 'totale area laterizi interi', 'type': 6, 'length': 0, 'precision': 4},
                    {'expression': 'to_real("int_mean")', 'name': 'media area laterizi interi', 'type': 6, 'length': 0, 'precision': 4},
                    {'expression': 'to_real("width_min")', 'name': 'width_min', 'type': 6, 'length': 0, 'precision': 4},
                    {'expression': 'to_real("width_max")', 'name': 'width_max', 'type': 6, 'length': 0, 'precision': 4},
                    {'expression': 'to_real("width_range")', 'name': 'width_range', 'type': 6, 'length': 0, 'precision': 4},
                    {'expression': 'to_real("width_mean")', 'name': 'width_mean', 'type': 6, 'length': 0, 'precision': 4},
                    {'expression': 'to_real("width_stddev")', 'name': 'width_stddev', 'type': 6, 'length': 0, 'precision': 4},
                    {'expression': 'to_real("height_min")', 'name': 'height_min', 'type': 6, 'length': 0, 'precision': 4},
                    {'expression': 'to_real("height_max")', 'name': 'height_max', 'type': 6, 'length': 0, 'precision': 4},
                    {'expression': 'to_real("height_range")', 'name': 'height_range', 'type': 6, 'length': 0, 'precision': 4},
                    {'expression': 'to_real("height_mean")', 'name': 'height_mean', 'type': 6, 'length': 0, 'precision': 4},
                    {'expression': 'to_real("height_stddev")', 'name': 'height_stddev', 'type': 6, 'length': 0, 'precision': 4}
                ],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            feedback.setCurrentStep(14)
            
            # ============ FASE 11: CALCOLI FINALI ============
            feedback.pushInfo("\n--- CALCOLI FINALI ---")
            
            # Calcolo num. laterizi interi calcolati (con gestione NULL robusta)
            calc1 = processing.run('native:fieldcalculator', {
                'INPUT': all_stats_final['OUTPUT'],
                'FIELD_NAME': 'num. laterizi interi calcolati',
                'FIELD_TYPE': 0,
                'FORMULA': '''CASE 
    WHEN "media area laterizi interi" IS NULL OR "media area laterizi interi" = 0 THEN 0
    WHEN "totale area laterizi parziali" IS NULL THEN 0
    ELSE round("totale area laterizi parziali" / "media area laterizi interi", 0)
END''',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            # Calcolo totale laterizi interi calcolati
            calc2 = processing.run('native:fieldcalculator', {
                'INPUT': calc1['OUTPUT'],
                'FIELD_NAME': 'totale laterizi interi calcolati',
                'FIELD_TYPE': 0,
                'FORMULA': 'round(COALESCE("num. laterizi interi", 0) + COALESCE("num. laterizi interi calcolati", 0), 0)',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            # Calcolo totale area laterizi (somma interi + parziali)
            calc3 = processing.run('native:fieldcalculator', {
                'INPUT': calc2['OUTPUT'],
                'FIELD_NAME': 'totale area laterizi',
                'FIELD_TYPE': 0,
                'FORMULA': 'round(COALESCE("totale area laterizi interi", 0) + COALESCE("totale area laterizi parziali", 0), 4)',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            # Calcolo totale area malta
            calc4 = processing.run('native:fieldcalculator', {
                'INPUT': calc3['OUTPUT'],
                'FIELD_NAME': 'totale area malta',
                'FIELD_TYPE': 0,
                'FORMULA': 'round(COALESCE("area campione", 0) - COALESCE("totale area laterizi", 0), 4)',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            # Calcolo rapporto laterizi/malta (con gestione divisione per zero)
            calc5 = processing.run('native:fieldcalculator', {
                'INPUT': calc4['OUTPUT'],
                'FIELD_NAME': 'rapporto laterizi/malta',
                'FIELD_TYPE': 2,
                'FORMULA': '''CASE 
    WHEN "totale area malta" IS NULL OR "totale area malta" <= 0 THEN NULL
    WHEN "totale area laterizi" IS NULL THEN NULL
    ELSE round("totale area laterizi" / "totale area malta", 2)
END''',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            feedback.setCurrentStep(15)
            
            # ============ FASE 12: OUTPUT TABELLA COMPLETA ============
            feedback.pushInfo("\n--- CREAZIONE TABELLA ANALISI CAMPIONI ---")
            
            # Riorganizza campi finali per tabella
            table_refactored = processing.run('native:refactorfields', {
                'INPUT': calc5['OUTPUT'],
                'FIELDS_MAPPING': [
                    {'expression': '"sito"', 'name': 'sito', 'type': 10},
                    {'expression': '"ambiente"', 'name': 'ambiente', 'type': 10},
                    {'expression': '"usm"', 'name': 'usm', 'type': 10},
                    {'expression': '"campione"', 'name': 'campione', 'type': 10},
                    {'expression': '"area campione"', 'name': 'area_campione', 'type': 6, 'precision': 4},
                    {'expression': '"num. laterizi interi"', 'name': 'num_laterizi_interi', 'type': 2},
                    {'expression': '"totale area laterizi interi"', 'name': 'totale_area_laterizi_interi', 'type': 6, 'precision': 4},
                    {'expression': '"media area laterizi interi"', 'name': 'media_area_laterizi_interi', 'type': 6, 'precision': 4},
                    {'expression': '"num. laterizi parziali"', 'name': 'num_laterizi_parziali', 'type': 2},
                    {'expression': '"totale area laterizi parziali"', 'name': 'totale_area_laterizi_parziali', 'type': 6, 'precision': 4},
                    {'expression': '"num. laterizi interi calcolati"', 'name': 'num_laterizi_interi_calcolati', 'type': 2},
                    {'expression': '"totale laterizi interi calcolati"', 'name': 'totale_laterizi_interi_calcolati', 'type': 2},
                    {'expression': '"totale area laterizi"', 'name': 'totale_area_laterizi', 'type': 6, 'precision': 4},
                    {'expression': '"totale area malta"', 'name': 'totale_area_malta', 'type': 6, 'precision': 4},
                    {'expression': '"rapporto laterizi/malta"', 'name': 'rapporto_laterizi/malta', 'type': 6, 'precision': 2},
                    {'expression': '"width_min"', 'name': 'width_min', 'type': 6, 'precision': 4},
                    {'expression': '"width_max"', 'name': 'width_max', 'type': 6, 'precision': 4},
                    {'expression': '"width_range"', 'name': 'width_range', 'type': 6, 'precision': 4},
                    {'expression': '"width_mean"', 'name': 'width_mean', 'type': 6, 'precision': 4},
                    {'expression': '"width_stddev"', 'name': 'width_stddev', 'type': 6, 'precision': 4},
                    {'expression': '"height_min"', 'name': 'height_min', 'type': 6, 'precision': 4},
                    {'expression': '"height_max"', 'name': 'height_max', 'type': 6, 'precision': 4},
                    {'expression': '"height_range"', 'name': 'height_range', 'type': 6, 'precision': 4},
                    {'expression': '"height_mean"', 'name': 'height_mean', 'type': 6, 'precision': 4},
                    {'expression': '"height_stddev"', 'name': 'height_stddev', 'type': 6, 'precision': 4}
                ],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            # Rimuovi geometrie per creare una tabella pura
            table_final = processing.run('native:dropgeometries', {
                'INPUT': table_refactored['OUTPUT'],
                'OUTPUT': parameters['output_campioni_table']
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            results['output_campioni_table'] = table_final['OUTPUT']
            context.layerToLoadOnCompletionDetails(results['output_campioni_table']).name = "analisi_campioni_table"
            self.verifica_features(results['output_campioni_table'], context, feedback, "Tabella analisi campioni")
            feedback.setCurrentStep(16)
            
            # ============ FASE 13: OUTPUT CAMPIONI GEOGRAFICO ============
            feedback.pushInfo("\n--- CREAZIONE LAYER CAMPIONI GEOGRAFICO ---")
            
            # Join tabella completa con layer campioni
            campioni_geo = processing.run('native:joinattributestable', {
                'INPUT': parameters['layer_campioni'],
                'INPUT_2': table_final['OUTPUT'],
                'FIELD': 'campione',
                'FIELD_2': 'campione',
                'FIELDS_TO_COPY': [
                    'num_laterizi_interi', 'totale_area_laterizi_interi', 'media_area_laterizi_interi',
                    'num_laterizi_parziali', 'totale_area_laterizi_parziali', 'num_laterizi_interi_calcolati',
                    'totale_laterizi_interi_calcolati', 'totale_area_laterizi', 'totale_area_malta',
                    'rapporto_laterizi/malta', 'width_min', 'width_max', 'width_range', 'width_mean',
                    'width_stddev', 'height_min', 'height_max', 'height_range', 'height_mean', 'height_stddev'
                ],
                'DISCARD_NONMATCHING': True,
                'METHOD': 1,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            # Riorganizza campi campioni geografico
            campioni_final = processing.run('native:refactorfields', {
                'INPUT': campioni_geo['OUTPUT'],
                'FIELDS_MAPPING': [
                    {'expression': '"fid"', 'name': 'fid', 'type': 4},
                    {'expression': '"sito"', 'name': 'sito', 'type': 10},
                    {'expression': '"usm"', 'name': 'usm', 'type': 10},
                    {'expression': '"ambiente"', 'name': 'ambiente', 'type': 10},
                    {'expression': '"campione"', 'name': 'campione', 'type': 10},
                    {'expression': '"area_campione"', 'name': 'area_campione', 'type': 6, 'precision': 4},
                    {'expression': '"num_laterizi_parziali"', 'name': 'num_laterizi_parziali', 'type': 2},
                    {'expression': '"totale_area_laterizi_parziali"', 'name': 'totale_area_laterizi_parziali', 'type': 6, 'precision': 4},
                    {'expression': '"num_laterizi_interi"', 'name': 'num_laterizi_interi', 'type': 2},
                    {'expression': '"totale_area_laterizi_interi"', 'name': 'totale_area_laterizi_interi', 'type': 6, 'precision': 4},
                    {'expression': '"media_area_laterizi_interi"', 'name': 'media_area_laterizi_interi', 'type': 6, 'precision': 4},
                    {'expression': '"num_laterizi_interi_calcolati"', 'name': 'num_laterizi_interi_calcolati', 'type': 2},
                    {'expression': '"totale_laterizi_interi_calcolati"', 'name': 'totale_laterizi_interi_calcolati', 'type': 2},
                    {'expression': '"totale_area_laterizi"', 'name': 'totale_area_laterizi', 'type': 6, 'precision': 4},
                    {'expression': '"totale_area_malta"', 'name': 'totale_area_malta', 'type': 6, 'precision': 4},
                    {'expression': '"rapporto_laterizi/malta"', 'name': 'rapporto_laterizi/malta', 'type': 6, 'precision': 2},
                    {'expression': '"width_min"', 'name': 'width_min', 'type': 6, 'precision': 4},
                    {'expression': '"width_max"', 'name': 'width_max', 'type': 6, 'precision': 4},
                    {'expression': '"width_range"', 'name': 'width_range', 'type': 6, 'precision': 4},
                    {'expression': '"width_mean"', 'name': 'width_mean', 'type': 6, 'precision': 4},
                    {'expression': '"width_stddev"', 'name': 'width_stddev', 'type': 6, 'precision': 4},
                    {'expression': '"height_min"', 'name': 'height_min', 'type': 6, 'precision': 4},
                    {'expression': '"height_max"', 'name': 'height_max', 'type': 6, 'precision': 4},
                    {'expression': '"height_range"', 'name': 'height_range', 'type': 6, 'precision': 4},
                    {'expression': '"height_mean"', 'name': 'height_mean', 'type': 6, 'precision': 4},
                    {'expression': '"height_stddev"', 'name': 'height_stddev', 'type': 6, 'precision': 4}
                ],
                'OUTPUT': parameters['output_campioni']
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            results['output_campioni'] = campioni_final['OUTPUT']
            context.layerToLoadOnCompletionDetails(results['output_campioni']).name = "analisi_campioni"
            self.verifica_features(results['output_campioni'], context, feedback, "Analisi campioni geografico")
            feedback.setCurrentStep(17)
            
            # ============ RIEPILOGO ============
            feedback.pushInfo("\n" + "="*70)
            feedback.pushInfo("ELABORAZIONE COMPLETATA CON SUCCESSO")
            feedback.pushInfo("="*70)
            
            feedback.pushInfo("\n[RIEPILOGO ELABORAZIONE]")
            feedback.pushInfo(f"Componenti totali analizzati: {count_interi + count_parziali}")
            feedback.pushInfo(f"  - Componenti interi: {count_interi}")
            feedback.pushInfo(f"  - Componenti parziali: {count_parziali}")
            
            if applica_filtro:
                feedback.pushInfo(f"\n[FILTRO APPLICATO]")
                feedback.pushInfo(f"Tipi materiale: {', '.join(tipi)}")
                if includi_null:
                    feedback.pushInfo("Include non classificati: SI")
            else:
                feedback.pushInfo("\n[NESSUN FILTRO] - Tutti i materiali inclusi")
            
            feedback.pushInfo("\n[PARAMETRI RANGE]")
            feedback.pushInfo(f"Step larghezza: {width_step} m")
            feedback.pushInfo(f"Step altezza: {height_step} m")
            
            feedback.pushInfo("\n[OUTPUT GENERATI]")
            for name in results.keys():
                layer = QgsProcessingUtils.mapLayerFromString(results[name], context)
                if layer:
                    feedback.pushInfo(f"  * {layer.name()}: {layer.featureCount()} features")
            
            feedback.pushInfo("\n" + "="*70)
            
            return results
            
        except Exception as e:
            feedback.reportError(f"\nERRORE: {str(e)}")
            import traceback
            feedback.reportError(traceback.format_exc())
            raise

    def name(self):
        return 'analisi_filtrata_ottimizzato'

    def displayName(self):
        return 'Opera laterizia'

    def group(self):
        return 'Analisi'

    def groupId(self):
        return 'analisi'

    def createInstance(self):
        return AnalisiFiltrata()

    def shortHelpString(self):
        return """
        
        <p>Questo script analizza geometrie di componenti murari in opera laterizia calcolando statistiche su dimensioni, aree e distribuzioni dei materiali.</p>
        
        <h4>Parametri di Input:</h4>
        <ul>
            <li><b>Layer rilievo:</b> Layer poligonale con i componenti murari</li>
            <li><b>Layer campioni:</b> Layer con i campioni di muratura</li>
            <li><b>Tipo di materiale:</b> Lista separata da virgole (es: "laterizio,blocco") o vuoto per includere tutti i tipi</li>
            <li><b>Includi non classificati:</b> Se attivo, include elementi con tipo NULL</li>
            <li><b>Step range larghezza/altezza:</b> Incremento per il calcolo dei range (in metri)</li>
        </ul>
        
        <h4>Output Generati:</h4>
        <ul>
            <li><b>min_oriented_bbox:</b> Rettangoli orientati minimi per ogni componente</li>
            <li><b>analisi_rilievo:</b> Layer rilievo arricchito con metriche bbox</li>
            <li><b>analisi_campioni_table:</b> Tabella statistiche per campione (senza geometria)</li>
            <li><b>analisi_campioni:</b> Layer campioni con statistiche aggregate</li>
            <li><b>conteggio_range_larghezza:</b> Distribuzione componenti per range larghezza</li>
            <li><b>conteggio_range_altezza:</b> Distribuzione componenti per range altezza</li>
        </ul>
        
        <h4>Note Importanti:</h4>
        <ul>
            <li>Il layer rilievo deve contenere i campi: fid, tipo, superficie, area_componente, num_componente</li>
            <li>Il layer campioni deve contenere i campi: campione, sito, ambiente, usm, area_campione</li>
            <li>I componenti vengono separati in "interi" e "parziali" in base al campo "superficie"</li>
            <li>Le statistiche vengono calcolate solo sui componenti interi</li>
            <li>Il filtro materiali e' case-sensitive</li>
        </ul>
        
        <h4>Versione: 0.4 (Ottimizzata)</h4>
        """
