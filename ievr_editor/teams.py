"""Saved teams (section 0x07, ``m_InfoPermanent/teamSetList``).

16 team sets x 3 teams; a team has a name, formation, kit, emblem, captain and
29 member entries ``(charaStHdl, uniformNo, scPosNo)``. ``scPosNo`` 0-10 are
the starting eleven (formation slots), 11-19 the bench, 20+ unused entries.
"""
from typing import List, Optional

from . import l5bin
from .editor import Editor, Row

TEAM_SECTION = 0x07
STARTERS = 11
MAX_MEMBERS = 20  # 11 starters + 9 substitutes


class Team:
    def __init__(self, items, set_index: int, team_index: int):
        self.items = items
        self.set_index, self.team_index = set_index, team_index
        self.row = Row(items)

    @property
    def name(self) -> str:
        return l5bin.find(self.items, 'teamName').data.split(b'\0')[0].decode('utf-8', 'replace')

    @property
    def formation_id(self) -> int:
        return self.row['formationId']

    @property
    def captain(self) -> int:
        return self.row['captainStHdl']

    def members(self) -> List[Row]:
        return [Row(el) for el in l5bin.find(self.items, 'memberList').elements]

    def at(self, pos: int) -> Optional[Row]:
        """Member entry occupying formation slot / bench position ``pos``."""
        return next((m for m in self.members() if m['charaStHdl'] and m['scPosNo'] == pos), None)

    def handles(self):
        return {m['charaStHdl'] for m in self.members() if m['charaStHdl']}

    # edits -------------------------------------------------------------------
    def swap(self, pos_a: int, pos_b: int):
        """Exchange the players at two positions (either may be an empty bench spot)."""
        a, b = self.at(pos_a), self.at(pos_b)
        if a:
            a['scPosNo'] = pos_b
        if b:
            b['scPosNo'] = pos_a

    def put(self, pos: int, handle: int):
        """Place player ``handle`` at ``pos``; if they are already in the team the two swap places."""
        current = next((m for m in self.members() if m['charaStHdl'] == handle), None)
        if current is not None:
            self.swap(current['scPosNo'], pos)
            return
        m = self.at(pos)
        if m is not None:  # replace whoever is there
            if self.captain == m['charaStHdl']:
                self.row['captainStHdl'] = handle
            m['charaStHdl'] = handle
            return
        free = next((m for m in self.members() if not m['charaStHdl']), None)
        if free is None or self.row['memberNum'] >= MAX_MEMBERS:
            raise ValueError('team is full')
        free['charaStHdl'] = handle
        free['scPosNo'] = pos
        self.row['memberNum'] = self.row['memberNum'] + 1

    def set_captain(self, handle: int):
        if handle in self.handles():
            self.row['captainStHdl'] = handle

    def set_formation(self, formation_id: int):
        self.row['formationId'] = formation_id


def teams(editor: Editor) -> List[Team]:
    """Every team with at least one member."""
    root = l5bin.get(editor.save.section(TEAM_SECTION).items, 'm_InfoPermanent/teamSetList')
    out = []
    for si, el in enumerate(l5bin.find(root.items, 'm_buffer').elements):
        for ti, items in enumerate(l5bin.find(el, 'teamInfoList').elements):
            t = Team(items, si, ti)
            if t.row['memberNum']:
                out.append(t)
    return out
