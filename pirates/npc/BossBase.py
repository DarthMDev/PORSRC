from pirates.piratesbase import PLocalizer
from pirates.battle import EnemyGlobals
from pirates.npc.BossNPCList import BOSS_NPC_LIST

class BossBase:

    def __init__(self, repository):
        pass


    def getAvatarType(self):
        pass


    def getLevel(self):
        pass


    def loadBossData(self, uniqueId, avatarType):
        if uniqueId and avatarType:
            self.loadBossDataUid(uniqueId)
        elif avatarType and not uniqueId:
            self.loadBossDataAvatarType(avatarType)
        else:
            self.loadBossDataAvatarType(uniqueId, avatarType)


    def loadBossDataUid(self, uniqueId):
        defaultData = BOSS_NPC_LIST[''].copy()
        self.bossData = BOSS_NPC_LIST.get(uniqueId)
        defaultData.update(self.bossData)
        self.bossData = defaultData
        self.bossData['Name'] = PLocalizer.BossNPCNames[uniqueId]


    def loadBossDataAvatarType(self, avatarType):
        self.bossData = BOSS_NPC_LIST[''].copy()
        self.bossData['AvatarType'] = avatarType
        bossId = max(avatarType.boss - 1, 0)
        print "Faction: %s Track: %s Id: %s Boss: %s" % (avatarType.faction, avatarType.track, avatarType.id, bossId)
        self.bossData['Name'] = PLocalizer.BossNames[avatarType.faction][avatarType.track][avatarType.id][bossId]


    def loadBossDataHybrid(self, uniqueId, avatarType):
        defaultData = BOSS_NPC_LIST[''].copy()
        self.bossData = BOSS_NPC_LIST.get(uniqueId)
        defaultData.update(self.bossData)
        self.bossData = defaultData
        self.bossData['AvatarType'] = avatarType
        self.bossData['Name'] = PLocalizer.BossNPCNames[uniqueId]


    def _getBossName(self):
        return self.bossData['Name']


    def _getBossLevel(self):
        return self.bossData['Level']

    def getNameText(self):
        return self.bossData['Name'] or 'Unknown Boss'
