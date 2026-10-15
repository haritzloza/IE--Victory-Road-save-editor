"""Catalog of everything obtainable in the game, built from the user's install."""
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List

from .gamedata import GameData

ITEM_DIR = 'data/common/gamedata/item/'
CHARA_DIR = 'data/common/gamedata/character/'
SKILL_DIR = 'data/common/gamedata/skill/'

# item_config list -> inventory array in the save
ITEM_ARRAYS = {
    'CONSUME': 'invConsume', 'SHOES': 'invShoes', 'MISANGA': 'invMisanga',
    'ACCESSORY': 'invAccessory', 'SPECIAL': 'invSpecial', 'COSTUME': 'invCostume',
    'FASHION': 'invFashion', 'EMBLEM': 'invTeamItem', 'SPECIAL_TACTICS': 'invTeamItem',
    'SYNERGY_FLAG': 'invTeamItem', 'CRAFT_OBJ': 'invCraftObj', 'ANIMAL': 'invAnimal',
    'TITLE': 'invTitle', 'SPECIAL_SKILL': 'invSkill', 'KIZUNA_LINK': 'invKizunaLink',
    'NAME_PLATE': 'invNamePlate', 'PERFORMANCE': 'invPerformance',
}

CATEGORY_LABELS = {
    'CONSUME': 'Consumibles', 'SHOES': 'Botas', 'MISANGA': 'Pulseras',
    'ACCESSORY': 'Accesorios', 'SPECIAL': 'Especiales', 'COSTUME': 'Ropa',
    'FASHION': 'Equipaciones', 'EMBLEM': 'Emblemas', 'SPECIAL_TACTICS': 'Tácticas especiales',
    'SYNERGY_FLAG': 'Banderas de sinergia', 'CRAFT_OBJ': 'Objetos de construcción',
    'ANIMAL': 'Animales', 'TITLE': 'Títulos', 'KIZUNA_LINK': 'Vínculos',
    'NAME_PLATE': 'Placas de nombre', 'PERFORMANCE': 'Celebraciones',
}

# invSkill entries by code prefix
SKILL_KINDS = [
    (r'^whs', 'Supertécnica (tiro)'), (r'^whd', 'Supertécnica (defensa)'),
    (r'^who', 'Supertécnica (regate)'), (r'^whk', 'Supertécnica (portero)'),
    (r'^rh', 'Supertécnica (especial)'),
    (r'^wk[sodk]', 'Keshin'), (r'^wa[sodk]', 'Armadura Keshin'), (r'^wmm', 'Miximax'),
    (r'^ws[sodk]', 'Tótem'), (r'^wap', 'Aura'), (r'^mode_change', 'Modo'),
    (r'^wkt', 'Transformación'), (r'^(b?mps|b?cps|ss_ps|ss|abl_)', 'Pasiva'),
]

# Chronicle progress keeps one byte per board piece: bit k (1..6) of the clear
# flags = difficulty k beaten, same bit in the lock flags = difficulty k locked.
CHRONICLE_DIFFICULTIES = 6
CHRONICLE_DIFFICULTY_NAMES = [
    'Batalla de crónica', 'Batalla de desbloqueo de ruta', 'Batalla de objetos inusuales',
    'Batalla heroica', 'Batalla heroica+', 'Batalla legendaria',
]

ELEMENTS = {1: 'Viento', 2: 'Bosque', 3: 'Fuego', 4: 'Montaña'}
POSITIONS = {1: 'PR', 2: 'DL', 3: 'MC', 4: 'DF'}

SPIRIT_KINDS = {0: 'normal', 1: 'normal', 2: 'normal', 3: 'normal', 4: 'hero', 5: 'basara'}


@dataclass
class Item:
    id: int
    category: str          # ITEM_<category>_INFO
    name: str
    code: str
    max_stack: int
    array: str
    kind: str = ''         # finer kind for skills
    desc: str = ''
    icon: str = ''         # icons.IconStore key


@dataclass
class Spirit:
    param_id: int
    name: str
    kind: str              # normal / hero / basara
    rank: int              # chara_param column 9 (0-3 normal rarities)
    variant: int = 0       # hero/basara cards of the same character
    element: str = ''
    position: str = ''
    desc: str = ''
    face: str = ''         # icons.IconStore key


@dataclass
class ChronicleMatch:
    route: int
    order: int
    flag_index: int
    game_id: int
    title: str
    difficulties: int


@dataclass
class Catalog:
    items: Dict[int, Item] = field(default_factory=dict)
    spirits: Dict[int, Spirit] = field(default_factory=dict)
    chronicle: List[ChronicleMatch] = field(default_factory=list)
    chara_names: Dict[int, str] = field(default_factory=dict)   # param id -> name
    chara_flag_index: Dict[int, int] = field(default_factory=dict)  # param id -> database flag bit
    chara_faces: Dict[int, str] = field(default_factory=dict)  # param id -> face icon key
    chara_positions: Dict[int, int] = field(default_factory=dict)  # param id -> 1 GK, 2 FW, 3 MF, 4 DF

    def variants(self, sp: Spirit) -> int:
        """How many spirit cards of the same kind share this character's name."""
        if not hasattr(self, '_variant_count'):
            self._variant_count = Counter((s.kind, s.name) for s in self.spirits.values())
        return self._variant_count[(sp.kind, sp.name)]


def _u(v):
    return v & 0xFFFFFFFF


def build(g: GameData, lang='es') -> Catalog:
    cat = Catalog()
    item_text = g.texts('item_text', lang)
    skill_text = g.texts('skill_text', lang)
    chara_text = g.texts('chara_text', lang)
    chara_desc = g.texts('chara_description_text', lang)

    # skill / aura names by skill id
    skill_names = {}
    for r in g.table(SKILL_DIR, 'skill_config_')['m_skillInfoList']:
        skill_names[r['skillID']] = skill_text.get(r['skillNameId'])
    keshin_icons = {}
    for e in g.table(SKILL_DIR, 'aura_skill_config_'):
        if e.name == 'AURA_CMD_INFO':
            skill_names.setdefault(_u(e.raw[0]), skill_text.get(_u(e.raw[2])))
            if re.match(r'wk[sodk]', str(e.values[1])):  # keshin icons: aura_fs/k<number*10>
                keshin_icons[_u(e.raw[0])] = f'file:k{e.raw[16] * 10:06d}_l'
    for e in g.table(SKILL_DIR, 'passive_skill_config_'):
        if e.name == 'PASSIVE_SKILL_INFO':
            nm = next((skill_text.get(_u(v)) for v in e.raw[1:6] if skill_text.get(_u(v))), None)
            if nm:
                skill_names.setdefault(_u(e.raw[0]), nm)

    for e in g.table(ITEM_DIR, 'item_config_'):
        m = re.fullmatch(r'ITEM_(\w+)_INFO', e.name)
        if not m or m.group(1) not in ITEM_ARRAYS or len(e.raw) < 12:
            continue
        c = m.group(1)
        code = e.values[11] if isinstance(e.values[11], str) else ''
        if code.startswith('test'):
            continue
        array = ITEM_ARRAYS[c]
        if c == 'SPECIAL_SKILL':
            name = skill_names.get(_u(e.raw[16])) if len(e.raw) > 16 else None
            kind = next((k for p, k in SKILL_KINDS if re.match(p, code)), 'Otro')
        else:
            name = item_text.get(_u(e.raw[2]))
            kind = CATEGORY_LABELS.get(c, c)
            if re.match(r'tr\d', code):  # training beans have their own inventory
                kind, array = 'Judías de entrenamiento', 'invEquipToken'
        if not name:
            continue
        if c == 'SPECIAL_SKILL':
            icon = keshin_icons.get(_u(e.raw[16]), '') if len(e.raw) > 16 else ''
        else:
            icon = f'item:{code}'
        cat.items[_u(e.raw[0])] = Item(_u(e.raw[0]), c, name, code, e.raw[7], array, kind,
                                       (item_text.get(_u(e.raw[3])) or '') if c != 'SPECIAL_SKILL' else '', icon)

    base = {_u(e.raw[0]): e for e in g.table(CHARA_DIR, 'chara_base_') if e.name == 'CHARA_BASE_INFO'}
    seen = {}
    for e in g.table(CHARA_DIR, 'chara_param_'):
        if e.name != 'CHARA_PARAM_INFO':
            continue
        b = base.get(_u(e.raw[1]))
        name = chara_text.get(_u(b.raw[3])) if b else None
        if not name:
            continue
        pid = _u(e.raw[0])
        cat.chara_names[pid] = name
        cat.chara_flag_index[pid] = b.raw[2]
        cat.chara_positions[pid] = e.raw[3]
        has_face = f'data/dx11/menu/200_icon/10_icon_chr/face/{b.values[1]}_l.g4tx' in g.index
        if has_face:
            cat.chara_faces[pid] = f'face:{b.values[1]}'
        if e.raw[12] == 1 and e.raw[9] in SPIRIT_KINDS and has_face:  # no face = test/minigame entry
            kind = SPIRIT_KINDS[e.raw[9]]
            key = (kind, _u(e.raw[1]))
            n = seen.get(key, 0)
            seen[key] = n + 1
            # Normal spirits: the game only hands out the first param of a
            # character (later ones are story-specific copies).
            if kind == 'normal' and n:
                continue
            desc = next((chara_desc[_u(v)] for v in b.raw if _u(v) in chara_desc), '')
            cat.spirits[pid] = Spirit(pid, name, kind, e.raw[9], n, ELEMENTS.get(e.raw[2], ''),
                                      POSITIONS.get(e.raw[3], ''), desc.replace('\\n', ' '), cat.chara_faces[pid])

    team_text = g.texts('team_text', lang)
    teams = {_u(e.raw[0]): team_text[_u(e.raw[3])] for e in g.table('data/common/gamedata/team/', 'team_config_')
             if e.name == 'SOCCER_TEAM_INFO' and _u(e.raw[3]) in team_text}
    games = {}
    sg = g.table('data/common/gamedata/soccer/', 'soccer_game_config_')
    diff_rows = [e for e in sg if e.name == 'SOCCER_GAME_DIFFICULTY']
    refs = [e for e in sg if e.name == 'SOCCER_GAME_INFO_REF_DIFFICULTY']
    infos = [e for e in sg if e.name == 'SOCCER_GAME_INFO']
    for info, ref in zip(infos, refs):
        title = info.values[4] if isinstance(info.values[4], str) else ''
        if not title:
            a, n = ref.raw
            title = next((teams[_u(d.raw[1])] for d in diff_rows[a:a + n] if _u(d.raw[1]) in teams), '')
        games[_u(info.raw[0])] = (title, CHRONICLE_DIFFICULTIES)
    route = g.table('data/common/gamedata/vsroute/', 'chronicle_vs_route_config_')
    events = route['m_pieceEventInfoList']
    pieces = route['m_pieceInfoList']
    for ri, r in enumerate(route['m_chronicleVsRouteInfoList']):
        start, count = r['pieceInfo']
        order = 0
        for p in pieces[start:start + count]:
            if p['eventType'] != 0:
                continue
            a, n = p['eventInfoRef']
            gid = next((ev['paramCrc1'] for ev in events[a:a + n] if ev['paramCrc1'] in games), None)
            if gid is None:
                continue
            title, nd = games[gid]
            order += 1
            cat.chronicle.append(ChronicleMatch(ri, order, p['statusFlagIndex'], gid, title, nd))
    return cat

