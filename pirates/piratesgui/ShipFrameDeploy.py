from panda3d.core import VBase4, Vec4
# File: S (Python 2.4)

from direct.gui.DirectGui import *
from pirates.piratesbase import PiratesGlobals
from pirates.piratesbase import PLocalizer
from pirates.piratesgui import PiratesGuiGlobals
from pirates.piratesgui.ShipFrameSelect import ShipFrameSelect
from pirates.piratesgui.ShipSnapshot import ShipSnapshot
from pirates.ship import ShipGlobals

class ShipFrameDeploy(ShipFrameSelect):

    def __init__(self, parent, **kw):
        optiondefs = (('avatarName', '', None),)
        self.defineoptions(kw, optiondefs)
        ShipFrameSelect.__init__(self, parent)
        self.initialiseoptions(ShipFrameDeploy)


    def enableStats(self, shipName = '', shipClass = 0, mastInfo = [], hp = 0, sp = 0, cargo = 0, crew = 0, time = 0):
        hullInfo = ShipGlobals.getShipConfig(shipClass)
        self.shipClass = shipClass
        self.snapShot = ShipSnapshot(self, None, self['siegeTeam'], shipName, shipClass, mastInfo, hp, hullInfo['hp'], sp, hullInfo['sp'], cargo, hullInfo['maxCargo'], crew, hullInfo['maxCrew'], time, pos = self['snapShotPos'])
        typeStr = self['avatarName']
        if self['shipType'] is ShipFrameSelect.STBand:
            self.button['text'] = PLocalizer.BoardShip
        elif self['shipType'] is ShipFrameSelect.STGuild:
            self.button['text'] = PLocalizer.BoardShip
        elif self['shipType'] is ShipFrameSelect.STFriend:
            self.button['text'] = PLocalizer.BoardShip
        elif self['shipType'] is ShipFrameSelect.STPublic:
            self.button['text'] = PLocalizer.BoardShip
        else:
            typeStr = ''
        stateStr = PLocalizer.ShipAtSea
        if hp <= 0:
            self.button['state'] = DGG.DISABLED
            stateStr = 'red%s' % (PLocalizer.ShipSunk,)
            self['shipColorScale'] = VBase4(0.800000, 0.299, 0.299, 1)
        elif crew >= hullInfo['maxCrew']:
            self.button['state'] = DGG.DISABLED
            stateStr = 'red%s' % (PLocalizer.ShipFull,)
            self['shipColorScale'] = VBase4(0.4, 0.4, 0.4, 1)
        else:
            self.button['state'] = DGG.NORMAL
        if typeStr:
            self.typeLabel['text'] = 'smallCaps(%s)' % typeStr



    def enableStatsOV(self, shipOV):
        self.snapShot = ShipSnapshot(self, shipOV, self['siegeTeam'], pos = self['snapShotPos'])
        typeStr = ''
        if self['siegeTeam']:
            hp = shipOV.maxHp
            sp = shipOV.maxSp
        else:
            hp = shipOV.Hp
            sp = shipOV.Sp
        if hp <= 0:
            self.button['state'] = DGG.DISABLED
            self.button['text'] = PLocalizer.DeployShip
            stateStr = 'Ired%s' % PLocalizer.ShipSunk
            self['shipColorScale'] = VBase4(1, 0.4, 0.4, 1)
            self.button['image3_color'] = VBase4(*PiratesGuiGlobals.ButtonColor3[2])
            self.button['geom3_color'] = VBase4(0.4, 0.4, 0.4, 0.4)
            self.button['text3_color'] = VBase4(0.4, 0.4, 0.4, 0.4)
            self.button['helpText'] = PLocalizer.ShipSunk
        elif len(shipOV.crew) >= shipOV.maxCrew:
            self.button['state'] = DGG.DISABLED
            self.button['text'] = PLocalizer.BoardShip
            self.button['helpText'] = PLocalizer.ShipFull
            stateStr = 'red%s' % (PLocalizer.ShipFull,)
            self['shipColorScale'] = VBase4(0.4, 0.4, 0.4, 1)
        elif localAvatar.getActiveShipId() and shipOV.doId != localAvatar.getActiveShipId():
            self.button['state'] = DGG.DISABLED
            self.button['text'] = PLocalizer.DeployShip
            self.button['helpText'] = PLocalizer.OtherShipOut
            stateStr = 'Ired%s' % PLocalizer.OtherShipOut
            self['shipColorScale'] = VBase4(0.4, 0.4, 0.4, 1)
        elif shipOV.state in 'Off':
            self.button['state'] = DGG.NORMAL
            self.button['text'] = PLocalizer.DeployShip
            stateStr = PLocalizer.ShipInBottle
            self.button['helpText'] = PLocalizer.ShipInBottle
        else:
            self.button['state'] = DGG.NORMAL
            self.button['text'] = PLocalizer.BoardShip
            stateStr = PLocalizer.ShipAtSea
            self.button['helpText'] = PLocalizer.ShipAtSea

        if typeStr:
            self.typeLabel['text'] = 'smallCaps(%s)' % typeStr



    def addCrewMemberName(self, name):
        if name not in self.snapShot['crewNames']:
            self.snapShot['crewNames'] += [
                name]
