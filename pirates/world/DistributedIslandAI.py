from panda3d.core import NodePath
from direct.distributed.DistributedCartesianGridAI import DistributedCartesianGridAI
from direct.distributed.GridParent import GridParent
from direct.directnotify import DirectNotifyGlobal
from direct.task import Task
from pirates.world.DistributedGameAreaAI import DistributedGameAreaAI
from pirates.battle.Teamable import Teamable
from pirates.piratesbase import PiratesGlobals
from pirates.world import WorldGlobals
from pirates.world.LocationConstants import *
import random

# Treasure
from pirates.interact.DistributedSearchableContainerAI import DistributedSearchableContainerAI
from pirates.treasuremap.DistributedBuriedTreasureAI import DistributedBuriedTreasureAI

# Minigame
from pirates.minigame.DistributedPotionCraftingTableAI import DistributedPotionCraftingTableAI
from pirates.minigame.DistributedRepairBenchAI import DistributedRepairBenchAI
from pirates.minigame.DistributedFishingSpotAI import DistributedFishingSpotAI

# Holiday
from pirates.holiday.DistributedHolidayObjectAI import DistributedHolidayObjectAI

# World
from DistributedDinghyAI import DistributedDinghyAI
from DistributedGATunnelAI import DistributedGATunnelAI

class DistributedIslandAI(DistributedCartesianGridAI, DistributedGameAreaAI, Teamable):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedIslandAI')

    def __init__(self, mainWorld, islandModel):
        air = mainWorld.air

        cellWidth = WorldGlobals.ISLAND_TM_CELL_SIZE
        gridSize = WorldGlobals.LARGE_ISLAND_GRID_SIZE
        gridRadius = WorldGlobals.ISLAND_TM_GRID_RADIUS
        zoneId = WorldGlobals.ISLAND_GRID_STARTING_ZONE

        DistributedCartesianGridAI.__init__(self, air, zoneId, gridSize, gridRadius, cellWidth)
        DistributedGameAreaAI.__init__(self, air, islandModel)
        Teamable.__init__(self)

        self.mainWorld = mainWorld
        self.zoneSphereSize = [0, 0, 0]
        self.zoneSphereCenter = [0, 0]

        self.islandModel = islandModel

        self.undockable = False
        self.portCollisionSpheres = []
        self.feastFireEnabled = False
        self.fireworkShowEnabled = [False, 0]
        self.nextEvent = 0

        self.__fspots = 0
        self.__dinghyIdx = 0

        self.jail = None

    def announceGenerate(self):
        DistributedCartesianGridAI.announceGenerate(self)
        DistributedGameAreaAI.announceGenerate(self)
        if config.GetBool('want-island-events', True):
            self.__runIslandEvents()
            self.runEvents = taskMgr.doMethodLater(15, self.__runIslandEvents, 'runEvents')

    def delete(self):
        DistributedCartesianGridAI.delete(self)
        DistributedGameAreaAI.delete(self)
        if hasattr(self, 'runEvents'):
            taskMgr.remove(self.runEvents)

    def __runIslandEvents(self, task=None):
        self.nextEvent -= 15
        if self.nextEvent <= 0:
            if self.getUniqueId() == LocationIds.DEL_FUEGO_ISLAND:
                self.makeLavaErupt()
                self.nextEvent = random.randint(5, 10) * 60
        return Task.again

    def setIslandTransform(self, x, y, z, h):
        self.setXYZH(x, y, z, h)

    def d_setIslandTransform(self, x, y, z, h):
        self.sendUpdate('setIslandTransform', [x, y, z, h])

    def b_setIslandTransform(self, x, y, z, h):
        self.setIslandTransform(x, y, z, h)
        self.d_setIslandTransform(x, y, z, h)

    def getIslandTransform(self):
        x, y, z = self.getPos()
        h = self.getH()
        return [x, y, z, h]

    def setZoneSphereSize(self, r0, r1, r2):
        self.zoneSphereSize = [r0, r1, r2]

    def d_setZoneSphereSize(self, r0, r1, r2):
        self.sendUpdate('setZoneSphereSize', [r0, r1, r2])

    def b_setZoneSphereSize(self, r0, r1, r2):
        self.setZoneSphereSize(r0, r1, r2)
        self.d_setZoneSphereSize(r0, r1, r2)

    def getZoneSphereSize(self):
        return self.zoneSphereSize

    def setZoneSphereCenter(self, x, y):
        self.zoneSphereCenter = [x, y]

    def d_setZoneSphereCenter(self, x, y):
        self.sendUpdate('setZoneSphereCenter', [x, y])

    def b_setZoneSphereCenter(self, x, y):
        self.setZoneSphereCenter(x, y)
        self.d_setZoneSphereCenter(x, y)

    def getZoneSphereCenter(self):
        return self.zoneSphereCenter

    def setIslandModel(self, path):
        self.islandModel = path

    def d_setIslandModel(self, path):
        self.sendUpdate('setModelPath', [path])

    def b_setIslandModel(self, path):
        self.setIslandModel(path)
        self.d_setIslandModel(path)

    def getIslandModel(self):
        return self.islandModel

    def setUndockable(self, undockable):
        self.undockable = undockable

    def d_setUndockable(self, undockable):
        self.sendUpdate('setUndockable', [undockable])

    def b_setUndockable(self, undockable):
        self.setUndockable(undockable)
        self.d_setUndockable(undockable)

    def getUndockable(self):
        return self.undockable

    def setPortCollisionSpheres(self, spheres):
        self.portCollisionSpheres = spheres

    def d_setPortCollisionSpheres(self, spheres):
        self.sendUpdate('setPortCollisionSpheres', [spheres])

    def b_setPortCollisionSpheres(self, spheres):
        self.setPortCollisionSpheres(spheres)
        self.d_setPortCollisionSpheres(spheres)

    def getPortCollisionSpheres(self):
        return self.portCollisionSpheres

    def getPortCollisionSpheres(self):
        return self.portCollisionSpheres

    def makeLavaErupt(self):
        self.sendUpdate('makeLavaErupt')

    def setFeastFireEnabled(self, enabled):
        self.feastFireEnabled = enabled

    def d_setFeastFireEnabled(self, enabled):
        self.sendUpdate('setFeastFireEnabled', [enabled])

    def b_setFeastFireEnabled(self, enabled):
        self.setFeastFireEnabled(enabled)
        self.d_setFeastFireEnabled(enabled)

    def getFeastFireEnabled(self):
        return self.feastFireEnabled

    def setFireworkShowEnabled(self, enabled, showType):
        self.fireworkShowEnabled = [enabled, showType]

    def d_setFireworkShowEnabled(self, enabled, showType):
        self.sendUpdate('setFireworkShowEnabled', [enabled, showType])

    def b_setFireworkShowEnabled(self, enabled, showType):
        self.setFireworkShowEnabled(enabled, showType)
        self.d_setFireworkShowEnabled(enabled, showType)

    def getFireworkShowEnabled(self):
        return self.fireworkShowEnabled

    def createObject(self, objType, parent, objKey, object):
        genObj = None

        if objType == 'Object Spawn Node':
            if object['Spawnables'] == 'Buried Treasure':
                genObj = DistributedBuriedTreasureAI.makeFromObjectKey(self.air, objKey, object)
                self.generateChild(genObj)

        elif objType == 'PotionTable' and config.GetBool('want-potion-game', 0):
            genObj = DistributedPotionCraftingTableAI.makeFromObjectKey(self.air, objKey, object)
            self.generateChild(genObj)

        elif objType == 'Dinghy':
            genObj = DistributedDinghyAI.makeFromObjectKey(self.air, objKey, object)
            genObj.setLocationId(self.__dinghyIdx)
            self.__dinghyIdx += 1
            self.generateChild(genObj)

        elif objType == 'FishingSpot' and config.GetBool('want-fishing-game', 0):
            self.notify.debug('Generated a fishing spot')
            genObj = DistributedFishingSpotAI.makeFromObjectKey(self.air, objKey, object)
            genObj.setIndex(self.__fspots)
            self.__fspots += 1
            self.generateChild(genObj)

        elif objType == 'Searchable Container' and config.GetBool('want-searchables', 0):
            genObj = DistributedSearchableContainerAI.makeFromObjectKey(self.air, objKey, object)
            self.generateChild(genObj)

        elif objType == 'Building Exterior':
            genObj = self.air.worldCreator.createBuilding(self, objKey, object)

        elif objType == 'RepairBench' and config.GetBool('want-repair-game', 0):
            genObj = DistributedRepairBenchAI.makeFromObjectKey(self.air, objKey, object)
            self.generateChild(genObj)

        elif objType == 'Holiday' and config.GetBool('want-holiday-objects', 0):
            genObj = DistributedHolidayObjectAI.makeFromObjectKey(self.air, objKey, object)
            self.generateChild(genObj)

        elif objType == 'Island Game Area' and config.GetBool('want-link-tunnels', 0):
            genObj = DistributedGATunnelAI.makeFromObjectKey(self.air, objKey, object)
            self.generateChild(genObj)

        else:
            genObj = DistributedGameAreaAI.createObject(self, objType, parent, objKey, object)

        return genObj

    def generateChild(self, obj, zoneId=None):
        if zoneId is None:
            zoneId = self.getZoneFromXYZ(obj.getPos())

        obj.generateWithRequiredAndId(self.air.allocateChannel(), self.doId, zoneId)
        if obj.posControlledByIsland(): # This method must be defined in your AI
            cell = GridParent.getCellOrigin(self, zoneId)
            pos = obj.getPos()

            if obj.getUniqueId()=="1177359488.0dxschafe0":
                print("Cell is " + str(cell))
                print("Zone is " + str(zoneId))
                print ("Pos is " + str(pos))
                print("Self pos is " + str(self.getPos()))

            obj.reparentTo(cell)
            obj.setPos(self, pos)

            if obj.getUniqueId()=="1177359488.0dxschafe0":
                print("New pos is" + str(obj.getPos()))

            obj.sendUpdate('setPos', obj.getPos())
            obj.sendUpdate('setHpr', obj.getHpr())

