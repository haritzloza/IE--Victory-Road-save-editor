"""UI translations. Spanish is the source language; ``tr`` returns the text in
the active language (English otherwise), filling ``{placeholders}``.

The language is picked once at import: the ``ui_language`` setting, else the
system locale (Spanish for ``es*``, English for anything else).
"""
import locale
import os

from . import config

LANGUAGES = {'es': 'Español', 'en': 'English'}


def _detect():
    lang = config.get('ui_language')
    if lang in LANGUAGES:
        return lang
    loc = (locale.getlocale()[0] or os.environ.get('LANG', '') or '').lower()
    return 'es' if loc.startswith('es') else 'en'


LANG = _detect()


def tr(text: str, **kw) -> str:
    out = EN.get(text, text) if LANG == 'en' else text
    return out.format(**kw) if kw else out


EN = {
    # ------------------------------------------------------------- navigation / window
    '🏠  Resumen': '🏠  Overview', '⚽  Jugadores': '⚽  Players', '🎒  Objetos': '🎒  Items',
    '🔥  Técnicas': '🔥  Techniques', '✨  Espíritus': '✨  Spirits', '📜  Crónica': '📜  Chronicle',
    '👤  Partida': '👤  Save',
    '↶ Deshacer': '↶ Undo', '↷ Rehacer': '↷ Redo',
    '💾  Guardar cambios': '💾  Save changes', '📂  Abrir otra partida…': '📂  Open another save…',
    'Deshacer: {label}': 'Undo: {label}', 'Rehacer: {label}': 'Redo: {label}',
    'Deshecho': 'Undone', 'Rehecho': 'Redone',
    'Abrir guardado': 'Open save', 'Guardado ({name});;Todos (*)': 'Save ({name});;All files (*)',
    'Error': 'Error', 'No se pudo abrir el guardado:\n{error}': 'Could not open the save:\n{error}',
    'No se pudo guardar:\n{error}': 'Could not save:\n{error}',
    'Juego abierto': 'Game running',
    'INAZUMA ELEVEN Victory Road está en ejecución.\nCiérralo antes de guardar, o sobrescribirá los cambios.':
        'INAZUMA ELEVEN Victory Road is running.\nClose it before saving, or it will overwrite your changes.',
    '✔  Guardado · copia del anterior en {path}': '✔  Saved · previous save backed up to {path}',
    'Cambios sin guardar': 'Unsaved changes',
    '¿Descartar los cambios sin guardar?': 'Discard unsaved changes?',
    'Guardar cambios': 'Save changes', 'Se van a guardar {n} cambio(s)': '{n} change(s) will be saved',
    'Antes se hará una copia de seguridad de la partida actual.': 'The current save will be backed up first.',
    '… y {n} más': '… and {n} more', '💾  Guardar': '💾  Save', 'Cancelar': 'Cancel',
    '(se han deshecho cambios ya guardados)': '(changes that were already saved have been undone)',
    'Leyendo los datos del juego…': 'Reading game data…',
    'Versión del juego más nueva': 'Newer game version',
    'VERSION_WARNING': (
        'This save comes from game version {major}.{minor} (format {fmt}), newer than the last one tested with '
        'the editor ({tmajor}.{tminor}, format {tfmt}).\n\nIt may work, but if the game changed the format the '
        'edits might not apply correctly. A backup is made when saving; check it in the game and look for a new '
        'version of the editor.'),
    'Hay una versión nueva del editor: {version}': 'A new version of the editor is available: {version}',
    'Descargar': 'Download',
    # ------------------------------------------------------------- app start
    'Juego no encontrado': 'Game not found',
    'GAME_NOT_FOUND': ('INAZUMA ELEVEN Victory Road was not found in your Steam libraries.\n\nSelect the game '
                       'folder (the one with «nie.exe» and the «data» folder), usually:\n'
                       '…/steamapps/common/INAZUMA ELEVEN Victory Road'),
    'Carpeta de INAZUMA ELEVEN Victory Road': 'INAZUMA ELEVEN Victory Road folder',
    'Carpeta incorrecta': 'Wrong folder',
    '«{path}» no parece la carpeta del juego (falta data/cpk_list.cfg.bin).':
        '«{path}» does not look like the game folder (data/cpk_list.cfg.bin is missing).',
    'Elegir partida': 'Choose save', 'Hay varias cuentas de Steam con partida:': 'Several Steam accounts have a save:',
    'Error leyendo el juego': 'Error reading the game',
    'GAME_READ_ERROR': ('The game data could not be read in:\n{path}\n\n{error}\n\n'
                        'If the game was updated recently, the editor may need an update.'),
    # ------------------------------------------------------------- shared
    'Todos': 'All', 'Tengo': 'Owned', 'No tengo': 'Missing', '— vacío —': '— empty —',
    '🔍  Buscar por nombre…   (Ctrl+F)': '🔍  Search by name…   (Ctrl+F)',
    '{shown} de {total}': '{shown} of {total}', 'sí': 'yes', 'no': 'no',
    'Verde': 'Green', 'Azul': 'Blue', 'Morado': 'Purple', 'Amarillo': 'Yellow', 'Leyenda': 'Legend',
    'Ídolo rojo': 'Red idol', 'Ídolo gris': 'Grey idol', 'Ídolo rosa': 'Pink idol', 'Diamante': 'Diamond',
    'Normal': 'Normal', 'Héroe': 'Hero', 'Basara': 'Basara',
    'Viento': 'Wind', 'Bosque': 'Forest', 'Fuego': 'Fire', 'Montaña': 'Mountain', 'Neutro': 'Neutral',
    'PR': 'GK', 'DL': 'FW', 'MC': 'MF', 'DF': 'DF',
    'Crónica': 'Chronicle', 'Desbloqueo': 'Route unlock', 'Obj. inusuales': 'Rare items', 'Heroica': 'Heroic',
    'Heroica+': 'Heroic+', 'Legendaria': 'Legendary',
    'Batalla de crónica': 'Chronicle battle', 'Batalla de desbloqueo de ruta': 'Route unlock battle',
    'Batalla de objetos inusuales': 'Rare items battle', 'Batalla heroica': 'Heroic battle',
    'Batalla heroica+': 'Heroic battle+', 'Batalla legendaria': 'Legendary battle',
    # item / technique kinds (catalog keys)
    'Consumibles': 'Consumables', 'Botas': 'Boots', 'Pulseras': 'Bracelets', 'Accesorios': 'Accessories',
    'Especiales': 'Specials', 'Ropa': 'Clothes', 'Equipaciones': 'Kits', 'Emblemas': 'Emblems',
    'Tácticas especiales': 'Special tactics', 'Banderas de sinergia': 'Synergy flags',
    'Objetos de construcción': 'Building objects', 'Animales': 'Animals', 'Títulos': 'Titles',
    'Vínculos': 'Bonds', 'Placas de nombre': 'Name plates', 'Celebraciones': 'Celebrations',
    'Judías de entrenamiento': 'Training beans',
    'Supertécnica (tiro)': 'Hissatsu (shot)', 'Supertécnica (defensa)': 'Hissatsu (block)',
    'Supertécnica (regate)': 'Hissatsu (dribble)', 'Supertécnica (portero)': 'Hissatsu (keeper)',
    'Supertécnica (especial)': 'Hissatsu (special)', 'Keshin': 'Keshin', 'Armadura Keshin': 'Keshin armour',
    'Miximax': 'Miximax', 'Tótem': 'Totem', 'Aura': 'Aura', 'Modo': 'Mode', 'Transformación': 'Transformation',
    'Pasiva': 'Passive', 'Otro': 'Other',
    # ------------------------------------------------------------- summary
    'Resumen': 'Overview', 'Tu partida de un vistazo': 'Your save at a glance',
    'Tiempo de juego': 'Play time', 'Jugadores': 'Players', 'Objetos y equipamiento': 'Items and gear',
    'Supertécnicas': 'Hissatsu', 'Keshins': 'Keshins', 'Armaduras keshin': 'Keshin armours',
    'Espíritus normales': 'Normal spirits', 'Espíritus héroe': 'Hero spirits', 'Espíritus basara': 'Basara spirits',
    'Crónica · partidos superados por dificultad': 'Chronicle · matches cleared per difficulty',
    '{h} h {m:02} min': '{h} h {m:02} min', 'Guardado el {date} · {version}': 'Saved on {date} · {version}',
    'versión {major}.{minor}': 'version {major}.{minor}', '  ⚠️ más nueva que la probada': '  ⚠️ newer than tested',
    'en tu plantilla': 'in your squad', '{pct} % del catálogo': '{pct} % of the catalogue',
    # ------------------------------------------------------------- players
    'Selecciona un jugador para cambiar su equipamiento y técnicas · Ctrl/Mayús para seleccionar varios':
        'Select a player to change their gear and techniques · Ctrl/Shift to select several',
    'Selecciona un jugador': 'Select a player', 'Nivel': 'Level', 'Rareza': 'Rarity', 'Máximo': 'Max',
    'Nombre': 'Name', 'Elemento': 'Element', 'Pos.': 'Pos.', 'Entreno': 'Training',
    'ENTRENAMIENTO (JUDÍAS)': 'TRAINING (BEANS)', 'EQUIPAMIENTO': 'GEAR', 'TÉCNICAS EQUIPADAS': 'EQUIPPED TECHNIQUES',
    'Pulsera': 'Bracelet', 'Accesorio': 'Accessory', 'Especial': 'Special',
    'Técnica {n}': 'Technique {n}', 'Sexto sentido': 'Sixth sense', 'Armadura keshin {n}': 'Keshin armour {n}',
    'Hueco sin abrir': 'Slot not opened',
    'Llenar los 3 huecos hasta {cap} judías (límite a nivel {level})':
        'Fill the 3 slots up to {cap} beans (cap at level {level})',
    'Entrenamiento de {name} → {value}': 'Training of {name} → {value}',
    'Entrenar al máximo a {name}': 'Max training for {name}',
    'Nivel de {name} → {value}': 'Level of {name} → {value}', 'Rareza de {name} → {value}': 'Rarity of {name} → {value}',
    '{name} · {slot}: {value}': '{name} · {slot}: {value}', '{name} · técnica: {value}': '{name} · technique: {value}',
    'Nivel < 99': 'Level < 99', 'Nivel 99': 'Level 99',
    'Seleccionar visibles': 'Select visible', 'Nivel 99 a la selección': 'Level 99 for selection',
    'Entrenar al máximo a la selección': 'Max training for selection',
    'Llena los 3 huecos de judías hasta el límite de su nivel (2 × nivel − 18)':
        'Fills the 3 bean slots up to their level cap (2 × level − 18)',
    'Fijar rareza a la selección…': 'Set rarity for selection…', '{name} (avatar)': '{name} (avatar)',
    '{n} jugadores seleccionados': '{n} players selected',
    'Usa los botones de abajo para editarlos a la vez': 'Use the buttons below to edit them all at once',
    'Nivel 99 a {n} jugadores': 'Level 99 for {n} players', '{n} jugadores a nivel 99': '{n} players to level 99',
    'Entrenar al máximo a {n} jugadores': 'Max training for {n} players',
    '{n} jugadores entrenados al máximo': '{n} players fully trained',
    'Rareza de {n} jugadores': 'Rarity of {n} players', 'Rareza para {n} jugadores:': 'Rarity for {n} players:',
    '{n} jugadores → {value}': '{n} players → {value}',
    # ------------------------------------------------------------- items / techniques
    'Técnicas': 'Techniques', 'Supertécnicas, keshins, armaduras, miximax, tótems, pasivas y modos':
        'Hissatsu, keshins, armours, miximax, totems, passives and modes',
    'Objetos': 'Items', 'Equipamiento, consumibles, tácticas y coleccionables · doble clic para editar':
        'Gear, consumables, tactics and collectibles · double-click to edit',
    'Tipo': 'Type', 'Cantidad': 'Quantity', 'Máx.': 'Max', 'Obtenida': 'Owned', 'Potencia': 'Power', 'TP': 'TP',
    'Todos los tipos': 'All types', 'Obtener todas las visibles': 'Get all visible',
    'Añadir las que faltan (×1)': 'Add missing ones (×1)',
    'Añade una unidad de cada objeto visible que no tengas': 'Adds one of every visible item you do not have',
    'Fijar cantidad…': 'Set quantity…', 'Máximo a todas las visibles': 'Max for all visible',
    'Fijar cantidad': 'Set quantity', 'Cantidad para todos los visibles:': 'Quantity for all visible:',
    '{n} actualizados': '{n} updated', 'Añadir los que faltan': 'Add missing',
    'Fijar cantidad {n}': 'Set quantity {n}', 'técnicas': 'techniques', 'objetos': 'items',
    # ------------------------------------------------------------- spirits
    'Espíritus': 'Spirits',
    'Normales por rareza, héroe y basara · doble clic en una cantidad para editarla · pasa el ratón por encima para ver la descripción':
        'Normal spirits by rarity, hero and basara · double-click a quantity to edit · hover for the description',
    'Fijar cantidad de espíritus': 'Set spirit quantity', 'Rareza (normales):': 'Rarity (normal):',
    'Cantidad:': 'Quantity:', 'Normales': 'Normal', '{tier} / Cant.': '{tier} / Qty',
    '{n} espíritus actualizados': '{n} spirits updated', 'Añadir espíritus que faltan': 'Add missing spirits',
    'Espíritus: fijar {n} ({tier})': 'Spirits: set {n} ({tier})',
    # ------------------------------------------------------------- chronicle
    'Clic en una dificultad para marcar ese partido hasta ahí · selecciona varios (Ctrl/Mayús o arrastrando) y aplica abajo':
        'Click a difficulty to mark that match up to it · select several (Ctrl/Shift or drag) and apply below',
    'Rival': 'Opponent', 'Ruta': 'Route', 'Ruta {n}': 'Route {n}', 'Todas': 'All', 'Quitar selección': 'Clear selection',
    'Superar hasta': 'Clear up to', 'Ninguna': 'None', 'ninguna': 'none', 'Aplicar a la selección': 'Apply to selection',
    '· {n} seleccionados': '· {n} selected', '· ninguno seleccionado': '· none selected',
    'Crónica: {n} partido(s) → {value}': 'Chronicle: {n} match(es) → {value}', '{n} partidos → {value}': '{n} matches → {value}',
    # ------------------------------------------------------------- save page
    'Partida': 'Save', 'Avatar, fichas, base de datos de personajes y copias de seguridad':
        'Avatar, token spirits, character database and backups',
    'AVATAR': 'AVATAR', 'Apodo (dorsal)': 'Nickname (shirt)', 'Cambiar nombre': 'Rename',
    'ESPÍRITUS FICHA': 'TOKEN SPIRITS',
    'Las judías de entrenamiento están en Objetos → «Judías de entrenamiento».':
        'Training beans are under Items → «Training beans».',
    'BASE DE DATOS DE PERSONAJES': 'CHARACTER DATABASE',
    'Marcar todos los personajes como conocidos': 'Mark every character as known',
    '{known} de {total} personajes conocidos': '{known} of {total} characters known',
    'COPIAS DE SEGURIDAD': 'BACKUPS', 'Se crean al guardar y al restaurar, en {path}': 'Made on every save and restore, in {path}',
    '↺  Restaurar la copia seleccionada': '↺  Restore selected backup',
    'Todavía no hay copias: se crea una cada vez que guardas.': 'No backups yet: one is made every time you save.',
    'Cierra INAZUMA ELEVEN Victory Road antes de restaurar.': 'Close INAZUMA ELEVEN Victory Road before restoring.',
    'Restaurar copia': 'Restore backup',
    '¿Restaurar la partida del {date}?\n\nLa partida actual se guardará antes como copia de seguridad.':
        'Restore the save from {date}?\n\nThe current save will be backed up first.',
    '\nLos cambios sin guardar del editor se perderán.': '\nUnsaved changes in the editor will be lost.',
    'No se pudo restaurar la copia:\n{error}': 'Could not restore the backup:\n{error}', '✔  Copia restaurada': '✔  Backup restored',
    'Renombrar avatar → {name}': 'Rename avatar → {name}', 'Avatar renombrado a {name}': 'Avatar renamed to {name}',
    'Espíritus ficha → {n}': 'Token spirits → {n}', 'Todos los personajes marcados como conocidos': 'Every character marked as known',
    'IDIOMA': 'LANGUAGE', 'Idioma de la interfaz': 'Interface language',
    'Se aplicará la próxima vez que abras el editor.': 'It will apply the next time you open the editor.',
    'Buscar actualizaciones al abrir': 'Check for updates on start',
    # ------------------------------------------------------------- welcome
    'No se ha encontrado ninguna partida': 'No save found',
    'El editor busca en ~/.local/share/Steam/userdata/<cuenta>/2799860/remote/':
        'The editor looks in Steam/userdata/<account>/2799860/remote/',
    '1. Abre el juego en Steam y guarda la partida al menos una vez.': '1. Open the game on Steam and save at least once.',
    '2. Cierra el juego y vuelve a abrir el editor.': '2. Close the game and open the editor again.',
    '3. Si tu partida está en otro sitio, ábrela a mano con el botón de abajo (el archivo se llama «{name}»).':
        '3. If your save is somewhere else, open it with the button below (the file is called «{name}»).',
    '📂  Abrir partida…': '📂  Open save…',
}

# equipment / technique slot titles (players.EQUIP_SLOTS / SKILL_SLOTS)
EN.update({f'Técnica {i}': f'Technique {i}' for i in range(1, 10)})
EN.update({f'Armadura keshin {i}': f'Keshin armour {i}' for i in range(1, 4)})
