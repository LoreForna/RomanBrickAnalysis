import os
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterFeatureSource
from qgis.core import QgsProcessingParameterFeatureSink
from qgis.core import QgsProcessingParameterFile
from qgis.core import QgsProcessingParameterNumber
from qgis.core import QgsProcessingParameterString
import processing


class Analisi_campioni(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        # Parametri di input originali
        self.addParameter(QgsProcessingParameterFeatureSource('layer_input', 'layer_input', types=[QgsProcessing.TypeVectorPolygon], defaultValue='rilievo'))
        
        # NUOVI PARAMETRI CONFIGURABILI
        # Parametri per il calcolo dei range width_bbox
        self.addParameter(
            QgsProcessingParameterNumber(
                'width_range_step',
                'Incremento range larghezza (valore in m)',
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.002,
                minValue=0.001,
                maxValue=1.000
            )
        )
        
        # Parametri per il calcolo dei range height_bbox
        self.addParameter(
            QgsProcessingParameterNumber(
                'height_range_step',
                'Incremento range altezza (valore in m)',
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.001,
                minValue=0.001,
                maxValue=1.000
            )
        )
        
        # Parametro per i tipi di materiale da analizzare (multipli separati da virgola)
        self.addParameter(
            QgsProcessingParameterString(
                'tipo_materiale',
                'Tipi di materiale da analizzare (separati da virgola)',
                defaultValue='laterizio'
            )
        )
        
        # Layer campioni (menu a tendina con tutti i layer disponibili)
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                'nome_layer_campioni',
                'Layer per join analisi campioni',
                types=[QgsProcessing.TypeVectorAnyGeometry],
                defaultValue='campioni'
            )
        )
        
        # Layer rilievo (menu a tendina con tutti i layer disponibili)
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                'nome_layer_rilievo',
                'Layer per join analisi componenti',
                types=[QgsProcessing.TypeVectorAnyGeometry],
                defaultValue='rilievo'
            )
        )
        
        # Parametri di output (invariati)
        self.addParameter(QgsProcessingParameterFeatureSink('Conteggio_width_bbox_range', 'conteggio_width_bbox_range', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue=''))
        self.addParameter(QgsProcessingParameterFeatureSink('Conteggio_height_bbox_range', 'conteggio_height_bbox_range', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue=''))
        self.addParameter(QgsProcessingParameterFeatureSink('Min_oriented_bbox', 'min_oriented_bbox', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, supportsAppend=True, defaultValue=''))
        self.addParameter(QgsProcessingParameterFeatureSink('Analisi_campioni_table', 'analisi_campioni_table', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, supportsAppend=True, defaultValue=''))
        self.addParameter(QgsProcessingParameterFeatureSink('Analisi_campioni', 'analisi_campioni', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, supportsAppend=True, defaultValue=''))
        self.addParameter(QgsProcessingParameterFeatureSink('Analisi_rilievo', 'analisi_rilievo', type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, supportsAppend=True, defaultValue=''))
        
        # Parametri opzionali per gli stili (se non specificati, usa stile default)
        self.addParameter(QgsProcessingParameterFile('stile_analisi_campioni_table', 'Percorso stile analisi_campioni_table', behavior=QgsProcessingParameterFile.File, fileFilter='File QML (*.qml);;Tutti i File (*.*)', defaultValue=None, optional=True))
        self.addParameter(QgsProcessingParameterFile('stile_analisi_campioni', 'Percorso stile analisi_campioni', behavior=QgsProcessingParameterFile.File, fileFilter='File QML (*.qml);;Tutti i File (*.*)', defaultValue=None, optional=True))
        self.addParameter(QgsProcessingParameterFile('stile_min_oriented_bbox', 'Percorso stile min_oriented_bbox', behavior=QgsProcessingParameterFile.File, fileFilter='File QML (*.qml);;Tutti i File (*.*)', defaultValue=None, optional=True))
        self.addParameter(QgsProcessingParameterFile('stile_analisi_rilievo', 'Percorso stile analisi_rilievo', behavior=QgsProcessingParameterFile.File, fileFilter='File QML (*.qml);;Tutti i File (*.*)', defaultValue=None, optional=True))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Ottieni i valori dei parametri configurabili
        width_range_step = self.parameterAsDouble(parameters, 'width_range_step', context)
        height_range_step = self.parameterAsDouble(parameters, 'height_range_step', context)
        tipi_materiale_input = self.parameterAsString(parameters, 'tipo_materiale', context)
        layer_campioni = self.parameterAsSource(parameters, 'nome_layer_campioni', context)
        layer_rilievo = self.parameterAsSource(parameters, 'nome_layer_rilievo', context)
        
        # Processa i tipi di materiale (separa per virgola e rimuovi spazi)
        tipi_materiale = [tipo.strip() for tipo in tipi_materiale_input.split(',') if tipo.strip()]
        
        # Ottieni i percorsi degli stili (opzionali)
        stile_min_oriented_bbox = self.parameterAsFile(parameters, 'stile_min_oriented_bbox', context)
        stile_analisi_rilievo = self.parameterAsFile(parameters, 'stile_analisi_rilievo', context)
        stile_analisi_campioni_table = self.parameterAsFile(parameters, 'stile_analisi_campioni_table', context)
        stile_analisi_campioni = self.parameterAsFile(parameters, 'stile_analisi_campioni', context)
        
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(52, model_feedback)
        results = {}
        outputs = {}

        # Mostra i parametri configurabili nel feedback
        feedback.pushInfo(f"Parametri configurati:")
        feedback.pushInfo(f"- Incremento range larghezza: {width_range_step}")
        feedback.pushInfo(f"- Incremento range altezza: {height_range_step}")
        feedback.pushInfo(f"- Tipi di materiale: {', '.join(tipi_materiale)}")
        feedback.pushInfo(f"- Layer campioni: {layer_campioni.sourceName()}")
        feedback.pushInfo(f"- Layer rilievo: {layer_rilievo.sourceName()}")

        # spatial join rilievo su campioni
        alg_params = {
            'DISCARD_NONMATCHING': False,
            'INPUT': parameters['layer_input'],
            'JOIN': parameters['nome_layer_campioni'],
            'JOIN_FIELDS': ['campione','ambiente','usm','sito'],
            'METHOD': 0,  # Crea elementi separati per ciascun elemento corrispondente (uno-a-molti)
            'PREDICATE': [0],  # interseca
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['SpatialJoinRilievoSuCampioni'] = processing.run('native:joinattributesbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # minimum bounding geometry
        alg_params = {
            'FIELD': 'fid',
            'INPUT': outputs['SpatialJoinRilievoSuCampioni']['OUTPUT'],
            'TYPE': 1,  # Rettangolo Orientato Minimo
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['MinimumBoundingGeometry'] = processing.run('qgis:minimumboundinggeometry', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # join campi tra min oriented bbox e rilievo 
        alg_params = {
            'DISCARD_NONMATCHING': False,
            'FIELD': 'fid',
            'FIELDS_TO_COPY': [''],
            'FIELD_2': 'fid',
            'INPUT': outputs['MinimumBoundingGeometry']['OUTPUT'],
            'INPUT_2': outputs['SpatialJoinRilievoSuCampioni']['OUTPUT'],
            'METHOD': 1,  # Prendi solamente gli attributi del primo elemento corrispondente (uno-a-uno)
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['JoinCampiTraMinOrientedBboxERilievo'] = processing.run('native:joinattributestable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # riorganizza campi min oriented bbox
        alg_params = {
            'FIELDS_MAPPING': [{'expression': '"fid"','length': 0,'name': 'fid','precision': 0,'sub_type': 0,'type': 4,'type_name': 'int8'},{'expression': '"sito"','length': 0,'name': 'sito','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"ambiente"','length': 0,'name': 'ambiente','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"usm"','length': 0,'name': 'usm','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"campione"','length': 0,'name': 'campione','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"num_componente"','length': 0,'name': 'num_componente','precision': 0,'sub_type': 0,'type': 4,'type_name': 'int8'},{'expression': '"tipo"','length': 0,'name': 'tipo','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"superficie"','length': 0,'name': 'superficie','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"area_componente"','length': 6,'name': 'area_componente','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"height"','length': 6,'name': 'width_bbox','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"width"','length': 6,'name': 'height_bbox','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"angle"','length': 6,'name': 'angle_bbox','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"perimeter"','length': 6,'name': 'perimeter_bbox','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"area"','length': 6,'name': 'area_bbox','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'}],
            'INPUT': outputs['JoinCampiTraMinOrientedBboxERilievo']['OUTPUT'],
            'OUTPUT': parameters['Min_oriented_bbox']
        }
        outputs['RiorganizzaCampiMinOrientedBbox'] = processing.run('native:refactorfields', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Min_oriented_bbox'] = outputs['RiorganizzaCampiMinOrientedBbox']['OUTPUT']
        context.layerToLoadOnCompletionDetails(results['Min_oriented_bbox']).name = "Min_oriented_bbox"

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}

        # assegna stile min_oriented_bbox (se specificato)
        if stile_min_oriented_bbox:
            alg_params = {
                'INPUT': outputs['RiorganizzaCampiMinOrientedBbox']['OUTPUT'],
                'STYLE': stile_min_oriented_bbox
            }
            outputs['AssegnaStileMin_oriented_bbox'] = processing.run('native:setlayerstyle', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            feedback.pushInfo("Stile min_oriented_bbox applicato")
        else:
            feedback.pushInfo("Nessuno stile specificato per min_oriented_bbox, uso stile default")

        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}

        # join campi tra rilievo e min_oriented_bbox
        alg_params = {
            'DISCARD_NONMATCHING': True,
            'FIELD': 'fid',
            'FIELDS_TO_COPY': ['sito','ambiente','usm','width_bbox','height_bbox','angle_bbox','perimeter_bbox','area_bbox'],
            'FIELD_2': 'fid',
            'INPUT': parameters['nome_layer_rilievo'],
            'INPUT_2': outputs['RiorganizzaCampiMinOrientedBbox']['OUTPUT'],
            'METHOD': 1,  # Prendi solamente gli attributi del primo elemento corrispondente (uno-a-uno)
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['JoinCampiTraRilievoEMin_oriented_bbox'] = processing.run('native:joinattributestable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        # estrai per tipi di materiale (usa parametri configurabili multipli)
        if len(tipi_materiale) == 1:
            # Se c'è un solo tipo, usa l'estrazione semplice
            alg_params = {
                'FIELD': 'tipo',
                'INPUT': outputs['RiorganizzaCampiMinOrientedBbox']['OUTPUT'],
                'OPERATOR': 0,  # =
                'VALUE': tipi_materiale[0],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['EstraiPerTipoLaterizio'] = processing.run('native:extractbyattribute', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        else:
            # Se ci sono più tipi, usa un'espressione per includerli tutti
            tipi_quoted = [f"'{tipo}'" for tipo in tipi_materiale]
            expression = f'"tipo" IN ({",".join(tipi_quoted)})'
            
            alg_params = {
                'EXPRESSION': expression,
                'INPUT': outputs['RiorganizzaCampiMinOrientedBbox']['OUTPUT'],
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }
            outputs['EstraiPerTipoLaterizio'] = processing.run('native:extractbyexpression', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        
        feedback.pushInfo(f"Estratti elementi per i tipi: {', '.join(tipi_materiale)}")

        feedback.setCurrentStep(7)
        if feedback.isCanceled():
            return {}

        # estrai componenti interi
        alg_params = {
            'FIELD': 'superficie',
            'INPUT': outputs['EstraiPerTipoLaterizio']['OUTPUT'],
            'OPERATOR': 0,  # =
            'VALUE': 'intera',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['EstraiComponentiInteri'] = processing.run('native:extractbyattribute', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(8)
        if feedback.isCanceled():
            return {}

        # riorganizza campi analisi_rilievo
        alg_params = {
            'FIELDS_MAPPING': [{'expression': '"fid"','length': 0,'name': 'fid','precision': 0,'sub_type': 0,'type': 4,'type_name': 'int8'},{'expression': '"sito"','length': 0,'name': 'sito','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"ambiente"','length': 0,'name': 'ambiente','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"usm"','length': 0,'name': 'usm','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"campione"','length': 0,'name': 'campione','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"num_componente"','length': 0,'name': 'num_componente','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"tipo"','length': 0,'name': 'tipo','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"superficie"','length': 0,'name': 'superficie','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"area_componente"','length': 6,'name': 'area_componente','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"width_bbox"','length': 6,'name': 'width_bbox','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"height_bbox"','length': 6,'name': 'height_bbox','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"angle_bbox"','length': 6,'name': 'angle_bbox','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"perimeter_bbox"','length': 6,'name': 'perimeter_bbox','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"area_bbox"','length': 6,'name': 'area_bbox','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'}],
            'INPUT': outputs['JoinCampiTraRilievoEMin_oriented_bbox']['OUTPUT'],
            'OUTPUT': parameters['Analisi_rilievo']
        }
        outputs['RiorganizzaCampiAnalisi_rilievo'] = processing.run('native:refactorfields', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Analisi_rilievo'] = outputs['RiorganizzaCampiAnalisi_rilievo']['OUTPUT']
        context.layerToLoadOnCompletionDetails(results['Analisi_rilievo']).name = "Analisi_rilievo"

        feedback.setCurrentStep(9)
        if feedback.isCanceled():
            return {}

        # estrai componenti parziali
        alg_params = {
            'FIELD': 'superficie',
            'INPUT': outputs['EstraiPerTipoLaterizio']['OUTPUT'],
            'OPERATOR': 0,  # =
            'VALUE': 'parziale',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['EstraiComponentiParziali'] = processing.run('native:extractbyattribute', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(10)
        if feedback.isCanceled():
            return {}

        # statistiche area_int
        alg_params = {
            'CATEGORIES_FIELD_NAME': ['campione'],
            'INPUT': outputs['EstraiComponentiInteri']['OUTPUT'],
            'VALUES_FIELD_NAME': 'area_componente',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['StatisticheArea_int'] = processing.run('qgis:statisticsbycategories', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(11)
        if feedback.isCanceled():
            return {}

        # calcola range width_bbox (usa parametro configurabile)
        formula_width = f'''concat (
round(to_string(floor("width_bbox"/{width_range_step})*{width_range_step}),4),
  ' - ',
  round(to_string((floor("width_bbox"/{width_range_step})+1)*{width_range_step}),4)
)'''
        
        alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'width_bbox_range',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 2,  # Testo (stringa)
            'FORMULA': formula_width,
            'INPUT': outputs['EstraiComponentiInteri']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['CalcolaRangeWidth_bbox'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(12)
        if feedback.isCanceled():
            return {}

        # calcola range height_bbox (usa parametro configurabile)
        formula_height = f'''concat (
round(to_string(floor("height_bbox"/{height_range_step})*{height_range_step}),4),
  ' - ',
  round(to_string((floor("height_bbox"/{height_range_step})+1)*{height_range_step}),4)
)'''
        
        alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'height_bbox_range',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 2,  # Testo (stringa)
            'FORMULA': formula_height,
            'INPUT': outputs['CalcolaRangeWidth_bbox']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['CalcolaRangeHeight_bbox'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(13)
        if feedback.isCanceled():
            return {}

        # statistiche width_bbox
        alg_params = {
            'CATEGORIES_FIELD_NAME': ['campione'],
            'INPUT': outputs['EstraiComponentiInteri']['OUTPUT'],
            'VALUES_FIELD_NAME': 'width_bbox',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['StatisticheWidth_bbox'] = processing.run('qgis:statisticsbycategories', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(14)
        if feedback.isCanceled():
            return {}

        # statistiche height_bbox
        alg_params = {
            'CATEGORIES_FIELD_NAME': ['campione'],
            'INPUT': outputs['EstraiComponentiInteri']['OUTPUT'],
            'VALUES_FIELD_NAME': 'height_bbox',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['StatisticheHeight_bbox'] = processing.run('qgis:statisticsbycategories', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(15)
        if feedback.isCanceled():
            return {}

        # conteggia per range heigth_bbox
        alg_params = {
            'CATEGORIES_FIELD_NAME': ['campione','height_bbox_range'],
            'INPUT': outputs['CalcolaRangeHeight_bbox']['OUTPUT'],
            'VALUES_FIELD_NAME': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ConteggiaPerRangeHeigth_bbox'] = processing.run('qgis:statisticsbycategories', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(16)
        if feedback.isCanceled():
            return {}

        # assegna stile analisi_rilievo (se specificato)
        if stile_analisi_rilievo:
            alg_params = {
                'INPUT': outputs['RiorganizzaCampiAnalisi_rilievo']['OUTPUT'],
                'STYLE': stile_analisi_rilievo
            }
            outputs['AssegnaStileAnalisi_rilievo'] = processing.run('native:setlayerstyle', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            feedback.pushInfo("Stile analisi_rilievo applicato")
        else:
            feedback.pushInfo("Nessuno stile specificato per analisi_rilievo, uso stile default")

        feedback.setCurrentStep(17)
        if feedback.isCanceled():
            return {}

        # rinomina layer stat_area_int
        alg_params = {
            'INPUT': outputs['StatisticheArea_int']['OUTPUT'],
            'NAME': 'stat_area_int'
        }
        outputs['RinominaLayerStat_area_int'] = processing.run('native:renamelayer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(18)
        if feedback.isCanceled():
            return {}

        # statistiche area_parz
        alg_params = {
            'CATEGORIES_FIELD_NAME': ['campione'],
            'INPUT': outputs['EstraiComponentiParziali']['OUTPUT'],
            'VALUES_FIELD_NAME': 'area_componente',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['StatisticheArea_parz'] = processing.run('qgis:statisticsbycategories', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(19)
        if feedback.isCanceled():
            return {}

        # rinomina layer stat_width_bbox
        alg_params = {
            'INPUT': outputs['StatisticheWidth_bbox']['OUTPUT'],
            'NAME': 'stat_width_bbox'
        }
        outputs['RinominaLayerStat_width_bbox'] = processing.run('native:renamelayer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(20)
        if feedback.isCanceled():
            return {}

        # conteggia per range width_bbox
        alg_params = {
            'CATEGORIES_FIELD_NAME': ['campione','width_bbox_range'],
            'INPUT': outputs['CalcolaRangeWidth_bbox']['OUTPUT'],
            'VALUES_FIELD_NAME': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ConteggiaPerRangeWidth_bbox'] = processing.run('qgis:statisticsbycategories', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(21)
        if feedback.isCanceled():
            return {}

        # rinomina layer stat_height_bbox
        alg_params = {
            'INPUT': outputs['StatisticheHeight_bbox']['OUTPUT'],
            'NAME': 'stat_height_bbox'
        }
        outputs['RinominaLayerStat_height_bbox'] = processing.run('native:renamelayer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(22)
        if feedback.isCanceled():
            return {}

        # ordina colonna range heigth_bbox
        alg_params = {
            'ASCENDING': True,
            'EXPRESSION': 'height_bbox_range',
            'INPUT': outputs['ConteggiaPerRangeHeigth_bbox']['OUTPUT'],
            'NULLS_FIRST': False,
            'OUTPUT': parameters['Conteggio_height_bbox_range']
        }
        outputs['OrdinaColonnaRangeHeigth_bbox'] = processing.run('native:orderbyexpression', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Conteggio_height_bbox_range'] = outputs['OrdinaColonnaRangeHeigth_bbox']['OUTPUT']
        context.layerToLoadOnCompletionDetails(results['Conteggio_height_bbox_range']).name = "Conteggio_height_bbox_range"

        feedback.setCurrentStep(23)
        if feedback.isCanceled():
            return {}

        # rinomina layer stat_area_parz
        alg_params = {
            'INPUT': outputs['StatisticheArea_parz']['OUTPUT'],
            'NAME': 'stat_area_parz'
        }
        outputs['RinominaLayerStat_area_parz'] = processing.run('native:renamelayer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(24)
        if feedback.isCanceled():
            return {}

        # unisci layer
        alg_params = {
            'CRS': None,
            'LAYERS': [outputs['RinominaLayerStat_width_bbox']['OUTPUT'],outputs['RinominaLayerStat_height_bbox']['OUTPUT'],outputs['RinominaLayerStat_area_int']['OUTPUT'],outputs['RinominaLayerStat_area_parz']['OUTPUT']],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['UnisciLayer'] = processing.run('native:mergevectorlayers', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(25)
        if feedback.isCanceled():
            return {}

        # riorganizza campi stat_table
        alg_params = {
            'FIELDS_MAPPING': [{'expression': '"campione"','length': 0,'name': 'campione','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"layer"','length': 0,'name': 'stat_type','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"count"','length': 0,'name': 'count','precision': 0,'sub_type': 0,'type': 2,'type_name': 'integer'},{'expression': '"min"','length': 0,'name': 'min','precision': 0,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"max"','length': 0,'name': 'max','precision': 0,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"range"','length': 0,'name': 'range','precision': 0,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"sum"','length': 0,'name': 'sum','precision': 0,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"mean"','length': 0,'name': 'mean','precision': 0,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"stddev"','length': 0,'name': 'stddev','precision': 0,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"minority"','length': 0,'name': 'minority','precision': 0,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"majority"','length': 0,'name': 'majority','precision': 0,'sub_type': 0,'type': 6,'type_name': 'double precision'}],
            'INPUT': outputs['UnisciLayer']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RiorganizzaCampiStat_table'] = processing.run('native:refactorfields', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(26)
        if feedback.isCanceled():
            return {}

        # ordina colonna range width_bbox
        alg_params = {
            'ASCENDING': True,
            'EXPRESSION': 'width_bbox_range',
            'INPUT': outputs['ConteggiaPerRangeWidth_bbox']['OUTPUT'],
            'NULLS_FIRST': False,
            'OUTPUT': parameters['Conteggio_width_bbox_range']
        }
        outputs['OrdinaColonnaRangeWidth_bbox'] = processing.run('native:orderbyexpression', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Conteggio_width_bbox_range'] = outputs['OrdinaColonnaRangeWidth_bbox']['OUTPUT']
        context.layerToLoadOnCompletionDetails(results['Conteggio_width_bbox_range']).name = "Conteggio_width_bbox_range"

        feedback.setCurrentStep(27)
        if feedback.isCanceled():
            return {}

        # estrai elementi stat_area_parz
        alg_params = {
            'FIELD': 'stat_type',
            'INPUT': outputs['RiorganizzaCampiStat_table']['OUTPUT'],
            'OPERATOR': 0,  # =
            'VALUE': 'stat_area_parz',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['EstraiElementiStat_area_parz'] = processing.run('native:extractbyattribute', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(28)
        if feedback.isCanceled():
            return {}

        # estrai elementi stat_width_bbox
        alg_params = {
            'FIELD': 'stat_type',
            'INPUT': outputs['RiorganizzaCampiStat_table']['OUTPUT'],
            'OPERATOR': 0,  # =
            'VALUE': 'stat_width_bbox',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['EstraiElementiStat_width_bbox'] = processing.run('native:extractbyattribute', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(29)
        if feedback.isCanceled():
            return {}

        # estrai elementi stat_height_bbox
        alg_params = {
            'FIELD': 'stat_type',
            'INPUT': outputs['RiorganizzaCampiStat_table']['OUTPUT'],
            'OPERATOR': 0,  # =
            'VALUE': 'stat_height_bbox',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['EstraiElementiStat_height_bbox'] = processing.run('native:extractbyattribute', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(30)
        if feedback.isCanceled():
            return {}

        # join campi tra stat_area_parz e campioni (usa parametro configurabile)
        alg_params = {
            'DISCARD_NONMATCHING': True,
            'FIELD': 'campione',
            'FIELDS_TO_COPY': [''],
            'FIELD_2': 'campione',
            'INPUT': outputs['EstraiElementiStat_area_parz']['OUTPUT'],
            'INPUT_2': parameters['nome_layer_campioni'],
            'METHOD': 1,
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['JoinCampiTraStat_area_parzECampioni'] = processing.run('native:joinattributestable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(31)
        if feedback.isCanceled():
            return {}

        # estrai elementi stat_area_int
        alg_params = {
            'FIELD': 'stat_type',
            'INPUT': outputs['RiorganizzaCampiStat_table']['OUTPUT'],
            'OPERATOR': 0,  # =
            'VALUE': 'stat_area_int',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['EstraiElementiStat_area_int'] = processing.run('native:extractbyattribute', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(32)
        if feedback.isCanceled():
            return {}

        # join campi tra stat_area_int e campioni (usa parametro configurabile)
        alg_params = {
            'DISCARD_NONMATCHING': True,
            'FIELD': 'campione',
            'FIELDS_TO_COPY': [''],
            'FIELD_2': 'campione',
            'INPUT': outputs['EstraiElementiStat_area_int']['OUTPUT'],
            'INPUT_2': parameters['nome_layer_campioni'],
            'METHOD': 1,
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['JoinCampiTraStat_area_intECampioni'] = processing.run('native:joinattributestable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(33)
        if feedback.isCanceled():
            return {}

        # join campi tra stat_width_bbox e campioni (usa parametro configurabile)
        alg_params = {
            'DISCARD_NONMATCHING': True,
            'FIELD': 'campione',
            'FIELDS_TO_COPY': [''],
            'FIELD_2': 'campione',
            'INPUT': outputs['EstraiElementiStat_width_bbox']['OUTPUT'],
            'INPUT_2': parameters['nome_layer_campioni'],
            'METHOD': 1,
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['JoinCampiTraStat_width_bboxECampioni'] = processing.run('native:joinattributestable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(34)
        if feedback.isCanceled():
            return {}

        # riorganizza campi stat_area_parz
        alg_params = {
            'FIELDS_MAPPING': [{'expression': '"sito"','length': 0,'name': 'sito','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"ambiente"','length': 0,'name': 'ambiente','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"usm"','length': 0,'name': 'usm','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"campione"','length': 0,'name': 'campione','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"area_campione"','length': 6,'name': 'area campione','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"count"','length': 0,'name': 'num. laterizi parziali','precision': 0,'sub_type': 0,'type': 2,'type_name': 'integer'},{'expression': '"sum"','length': 6,'name': 'totale area laterizi parziali','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'}],
            'INPUT': outputs['JoinCampiTraStat_area_parzECampioni']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RiorganizzaCampiStat_area_parz'] = processing.run('native:refactorfields', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(35)
        if feedback.isCanceled():
            return {}

        # join campi tra stat_height_bbox e campioni (usa parametro configurabile)
        alg_params = {
            'DISCARD_NONMATCHING': True,
            'FIELD': 'campione',
            'FIELDS_TO_COPY': [''],
            'FIELD_2': 'campione',
            'INPUT': outputs['EstraiElementiStat_height_bbox']['OUTPUT'],
            'INPUT_2': parameters['nome_layer_campioni'],
            'METHOD': 1,
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['JoinCampiTraStat_height_bboxECampioni'] = processing.run('native:joinattributestable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(36)
        if feedback.isCanceled():
            return {}

        # riorganizza campi stat_area_int
        alg_params = {
            'FIELDS_MAPPING': [{'expression': '"sito"','length': 0,'name': 'sito','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"ambiente"','length': 0,'name': 'ambiente','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"usm"','length': 0,'name': 'usm','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"campione"','length': 0,'name': 'campione','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"area"','length': 6,'name': 'area campione','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"count"','length': 0,'name': 'num. laterizi interi','precision': 0,'sub_type': 0,'type': 2,'type_name': 'integer'},{'expression': '"sum"','length': 6,'name': 'totale area laterizi interi','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"mean"','length': 6,'name': 'media area laterizi interi','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'}],
            'INPUT': outputs['JoinCampiTraStat_area_intECampioni']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RiorganizzaCampiStat_area_int'] = processing.run('native:refactorfields', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(37)
        if feedback.isCanceled():
            return {}

        # riorganizza campi stat_width_bbox
        alg_params = {
            'FIELDS_MAPPING': [{'expression': '"sito"','length': 0,'name': 'sito','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"ambiente"','length': 0,'name': 'ambiente','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"usm"','length': 0,'name': 'usm','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"campione"','length': 0,'name': 'campione','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"area"','length': 6,'name': 'area campione','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"count"','length': 0,'name': 'num. laterizi interi','precision': 0,'sub_type': 0,'type': 2,'type_name': 'integer'},{'expression': '"min"','length': 6,'name': 'width_min','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"max"','length': 6,'name': 'width_max','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"range"','length': 6,'name': 'width_range','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"mean"','length': 6,'name': 'width_mean','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"stddev"','length': 6,'name': 'width_stddev','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'}],
            'INPUT': outputs['JoinCampiTraStat_width_bboxECampioni']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RiorganizzaCampiStat_width_bbox'] = processing.run('native:refactorfields', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(38)
        if feedback.isCanceled():
            return {}

        # riorganizza campi stat_height_bbox
        alg_params = {
            'FIELDS_MAPPING': [{'expression': '"sito"','length': 0,'name': 'sito','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"ambiente"','length': 0,'name': 'ambiente','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"usm"','length': 0,'name': 'usm','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"campione"','length': 0,'name': 'campione','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"area"','length': 6,'name': 'area campione','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"count"','length': 0,'name': 'num. laterizi interi','precision': 0,'sub_type': 0,'type': 2,'type_name': 'integer'},{'expression': '"min"','length': 6,'name': 'height_min','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"max"','length': 6,'name': 'height_max','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"range"','length': 6,'name': 'height_range','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"mean"','length': 6,'name': 'height_mean','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"stddev"','length': 6,'name': 'height_stddev','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'}],
            'INPUT': outputs['JoinCampiTraStat_height_bboxECampioni']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RiorganizzaCampiStat_height_bbox'] = processing.run('native:refactorfields', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(39)
        if feedback.isCanceled():
            return {}

        # join campi tra stat_area_parz e stat_area_int
        alg_params = {
            'DISCARD_NONMATCHING': False,
            'FIELD': 'campione',
            'FIELDS_TO_COPY': ['num. laterizi interi','totale area laterizi interi','media area laterizi interi'],
            'FIELD_2': 'campione',
            'INPUT': outputs['RiorganizzaCampiStat_area_parz']['OUTPUT'],
            'INPUT_2': outputs['RiorganizzaCampiStat_area_int']['OUTPUT'],
            'METHOD': 1,
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['JoinCampiTraStat_area_parzEStat_area_int'] = processing.run('native:joinattributestable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(40)
        if feedback.isCanceled():
            return {}

        # join campi tra stat_area e stat_width_bbox
        alg_params = {
            'DISCARD_NONMATCHING': False,
            'FIELD': 'campione',
            'FIELDS_TO_COPY': ['width_min','width_max','width_range','width_mean','width_stddev'],
            'FIELD_2': 'campione',
            'INPUT': outputs['JoinCampiTraStat_area_parzEStat_area_int']['OUTPUT'],
            'INPUT_2': outputs['RiorganizzaCampiStat_width_bbox']['OUTPUT'],
            'METHOD': 1,
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['JoinCampiTraStat_areaEStat_width_bbox'] = processing.run('native:joinattributestable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(41)
        if feedback.isCanceled():
            return {}

        # join campi tra stat_area e stat_height_bbox
        alg_params = {
            'DISCARD_NONMATCHING': False,
            'FIELD': 'campione',
            'FIELDS_TO_COPY': ['height_min','height_max','height_range','height_mean','height_stddev'],
            'FIELD_2': 'campione',
            'INPUT': outputs['JoinCampiTraStat_areaEStat_width_bbox']['OUTPUT'],
            'INPUT_2': outputs['RiorganizzaCampiStat_height_bbox']['OUTPUT'],
            'METHOD': 1,
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['JoinCampiTraStat_areaEStat_height_bbox'] = processing.run('native:joinattributestable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(42)
        if feedback.isCanceled():
            return {}

        # calcolo num. laterizi interi calcolati
        alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'num. laterizi interi calcolati',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 0,
            'FORMULA': "(attribute('totale area laterizi parziali') / attribute('media area laterizi interi'))",
            'INPUT': outputs['JoinCampiTraStat_areaEStat_height_bbox']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['CalcoloNumLateriziInteriCalcolati'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(43)
        if feedback.isCanceled():
            return {}

        # calcolo totale laterizi interi calcolati
        alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'totale laterizi interi calcolati',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 0,
            'FORMULA': "attribute('num. laterizi interi') + attribute('num. laterizi interi calcolati')",
            'INPUT': outputs['CalcoloNumLateriziInteriCalcolati']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['CalcoloTotaleLateriziInteriCalcolati'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(44)
        if feedback.isCanceled():
            return {}

        # calcolo totale area laterizi (usa parametro configurabile per il layer rilievo)
        nome_layer_rilievo_str = layer_rilievo.sourceName()
        alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'totale area laterizi',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 0,
            'FORMULA': f'aggregate(\'{nome_layer_rilievo_str}\', \'sum\', "area_componente", "campione" = attribute(@parent, \'campione\'))',
            'INPUT': outputs['CalcoloTotaleLateriziInteriCalcolati']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['CalcoloTotaleAreaLaterizi'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(45)
        if feedback.isCanceled():
            return {}

        # calcolo totale area malta
        alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'totale area malta',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 0,
            'FORMULA': "attribute('area campione') - attribute('totale area laterizi')",
            'INPUT': outputs['CalcoloTotaleAreaLaterizi']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['CalcoloTotaleAreaMalta'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(46)
        if feedback.isCanceled():
            return {}

        # calcolo rapporto laterizi/malta
        alg_params = {
            'FIELD_LENGTH': 0,
            'FIELD_NAME': 'rapporto laterizi/malta',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 2,
            'FORMULA': "attribute('totale area laterizi') / attribute('totale area malta')",
            'INPUT': outputs['CalcoloTotaleAreaMalta']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['CalcoloRapportoLaterizimalta'] = processing.run('native:fieldcalculator', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(47)
        if feedback.isCanceled():
            return {}

        # riorganizza campi analisi_table
        alg_params = {
            'FIELDS_MAPPING': [{'expression': '"sito"','length': 0,'name': 'sito','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"ambiente"','length': 0,'name': 'ambiente','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"usm"','length': 0,'name': 'usm','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"campione"','length': 0,'name': 'campione','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"area campione"','length': 6,'name': 'area_campione','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"num. laterizi interi"','length': 3,'name': 'num_laterizi_interi','precision': 0,'sub_type': 0,'type': 2,'type_name': 'integer'},{'expression': '"totale area laterizi interi"','length': 6,'name': 'totale_area_laterizi_interi','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"media area laterizi interi"','length': 6,'name': 'media_area_laterizi_interi','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"num. laterizi parziali"','length': 3,'name': 'num_laterizi_parziali','precision': 0,'sub_type': 0,'type': 2,'type_name': 'integer'},{'expression': '"totale area laterizi parziali"','length': 6,'name': 'totale_area_laterizi_parziali','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"num. laterizi interi calcolati"','length': 3,'name': 'num_laterizi_interi_calcolati','precision': 0,'sub_type': 0,'type': 2,'type_name': 'integer'},{'expression': '"totale laterizi interi calcolati"','length': 3,'name': 'totale_laterizi_interi_calcolati','precision': 0,'sub_type': 0,'type': 2,'type_name': 'integer'},{'expression': '"totale area laterizi"','length': 6,'name': 'totale_area_laterizi','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"totale area malta"','length': 6,'name': 'totale_area_malta','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"rapporto laterizi/malta"','length': 4,'name': 'rapporto_laterizi/malta','precision': 2,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"width_min"','length': 6,'name': 'width_min','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"width_max"','length': 6,'name': 'width_max','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"width_range"','length': 6,'name': 'width_range','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"width_mean"','length': 6,'name': 'width_mean','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"width_stddev"','length': 6,'name': 'width_stddev','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"height_min"','length': 6,'name': 'height_min','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"height_max"','length': 6,'name': 'height_max','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"height_range"','length': 6,'name': 'height_range','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"height_mean"','length': 6,'name': 'height_mean','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"height_stddev"','length': 6,'name': 'height_stddev','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'}],
            'INPUT': outputs['CalcoloRapportoLaterizimalta']['OUTPUT'],
            'OUTPUT': parameters['Analisi_campioni_table']
        }
        outputs['RiorganizzaCampiAnalisi_table'] = processing.run('native:refactorfields', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Analisi_campioni_table'] = outputs['RiorganizzaCampiAnalisi_table']['OUTPUT']
        context.layerToLoadOnCompletionDetails(results['Analisi_campioni_table']).name = "Analisi_campioni_table"

        feedback.setCurrentStep(48)
        if feedback.isCanceled():
            return {}

        # assegna stile analisi_table (se specificato)
        if stile_analisi_campioni_table:
            alg_params = {
                'INPUT': outputs['RiorganizzaCampiAnalisi_table']['OUTPUT'],
                'STYLE': stile_analisi_campioni_table
            }
            outputs['AssegnaStileAnalisi_table'] = processing.run('native:setlayerstyle', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            feedback.pushInfo("Stile analisi_campioni_table applicato")
        else:
            feedback.pushInfo("Nessuno stile specificato per analisi_campioni_table, uso stile default")

        feedback.setCurrentStep(49)
        if feedback.isCanceled():
            return {}

        # join campi tra analisi_table e campioni (usa parametro configurabile)
        alg_params = {
            'DISCARD_NONMATCHING': True,
            'FIELD': 'campione',
            'FIELDS_TO_COPY': ['num_laterizi_interi','totale_area_laterizi_interi','media_area_laterizi_interi','num_laterizi_parziali','totale_area_laterizi_parziali','num_laterizi_interi_calcolati','totale_laterizi_interi_calcolati','totale_area_laterizi','totale_area_malta','rapporto_laterizi/malta','width_min','width_max','width_range','width_mean','width_stddev','height_min','height_max','height_range','height_mean','height_stddev'],
            'FIELD_2': 'campione',
            'INPUT': parameters['nome_layer_campioni'],
            'INPUT_2': outputs['AssegnaStileAnalisi_table']['OUTPUT'] if stile_analisi_campioni_table else outputs['RiorganizzaCampiAnalisi_table']['OUTPUT'],
            'METHOD': 1,
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['JoinCampiTraAnalisi_tableECampioni'] = processing.run('native:joinattributestable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(50)
        if feedback.isCanceled():
            return {}

        # riorganizza campi analisi_campioni
        alg_params = {
            'FIELDS_MAPPING': [{'expression': '"fid"','length': 0,'name': 'fid','precision': 0,'sub_type': 0,'type': 4,'type_name': 'int8'},{'expression': '"sito"','length': 0,'name': 'sito','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"usm"','length': 0,'name': 'usm','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"ambiente"','length': 0,'name': 'ambiente','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"campione"','length': 0,'name': 'campione','precision': 0,'sub_type': 0,'type': 10,'type_name': 'text'},{'expression': '"area_campione"','length': 6,'name': 'area_campione','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"num_laterizi_parziali"','length': 3,'name': 'num_laterizi_parziali','precision': 0,'sub_type': 0,'type': 2,'type_name': 'integer'},{'expression': '"totale_area_laterizi_parziali"','length': 6,'name': 'totale_area_laterizi_parziali','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"num_laterizi_interi"','length': 3,'name': 'num_laterizi_interi','precision': 0,'sub_type': 0,'type': 2,'type_name': 'integer'},{'expression': '"totale_area_laterizi_interi"','length': 6,'name': 'totale_area_laterizi_interi','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"media_area_laterizi_interi"','length': 6,'name': 'media_area_laterizi_interi','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"num_laterizi_interi_calcolati"','length': 3,'name': 'num_laterizi_interi_calcolati','precision': 0,'sub_type': 0,'type': 2,'type_name': 'integer'},{'expression': '"totale_laterizi_interi_calcolati"','length': 3,'name': 'totale_laterizi_interi_calcolati','precision': 0,'sub_type': 0,'type': 2,'type_name': 'integer'},{'expression': '"totale_area_laterizi"','length': 6,'name': 'totale_area_laterizi','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"totale_area_malta"','length': 6,'name': 'totale_area_malta','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"rapporto_laterizi/malta"','length': 4,'name': 'rapporto_laterizi/malta','precision': 2,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"width_min"','length': 6,'name': 'width_min','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"width_max"','length': 6,'name': 'width_max','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"width_range"','length': 6,'name': 'width_range','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"width_mean"','length': 6,'name': 'width_mean','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"width_stddev"','length': 6,'name': 'width_stddev','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"height_min"','length': 6,'name': 'height_min','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"height_max"','length': 6,'name': 'height_max','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"height_range"','length': 6,'name': 'height_range','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"height_mean"','length': 6,'name': 'height_mean','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'},{'expression': '"height_stddev"','length': 6,'name': 'height_stddev','precision': 4,'sub_type': 0,'type': 6,'type_name': 'double precision'}],
            'INPUT': outputs['JoinCampiTraAnalisi_tableECampioni']['OUTPUT'],
            'OUTPUT': parameters['Analisi_campioni']
        }
        outputs['RiorganizzaCampiAnalisi_campioni'] = processing.run('native:refactorfields', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['Analisi_campioni'] = outputs['RiorganizzaCampiAnalisi_campioni']['OUTPUT']
        context.layerToLoadOnCompletionDetails(results['Analisi_campioni']).name = "Analisi_campioni"

        feedback.setCurrentStep(51)
        if feedback.isCanceled():
            return {}

        # assegna stile analisi_campioni (se specificato)
        if stile_analisi_campioni:
            alg_params = {
                'INPUT': outputs['RiorganizzaCampiAnalisi_campioni']['OUTPUT'],
                'STYLE': stile_analisi_campioni
            }
            outputs['AssegnaStileAnalisi_campioni'] = processing.run('native:setlayerstyle', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
            feedback.pushInfo("Stile analisi_campioni applicato")
        else:
            feedback.pushInfo("Nessuno stile specificato per analisi_campioni, uso stile default")

        feedback.setCurrentStep(52)
        if feedback.isCanceled():
            return {}

        return results

    def name(self):
        return 'Opera laterizia'

    def displayName(self):
        return 'Opera laterizia'

    def group(self):
        return 'Analisi mensiocronologica'

    def groupId(self):
        return 'analisi_mensiocronologica'

    def createInstance(self):
        return Analisi_campioni()

    def shortHelpString(self):
        return """
        Script per l'analisi mensiocronologica.
        
        Lo script analizza geometrie dei componenti della muratura calcolando statistiche su dimensioni, aree e distribuzioni dei materiali.
        Per analizzare più tipi di materiale, inserire i nomi separati da virgola nel campo "Tipi di materiale".
        
        Parametri configurabili:
        - Incremento range larghezza: step per il calcolo dei range di width_bbox
        - Incremento range altezza: step per il calcolo dei range di height_bbox  
        - Tipi di materiale: tipi di materiale da analizzare, separati da virgola (esempi: "laterizio" oppure "laterizio,mattone,ceramica")
        - Layer di riferimento per join spaziali
        - Stili (opzionali): percorsi ai file .qml per personalizzare la visualizzazione
        """