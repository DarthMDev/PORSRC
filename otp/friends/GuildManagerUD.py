from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectGlobalUD import DistributedObjectGlobalUD
from direct.fsm.FSM import FSM
from otp.otpbase import OTPUtils

GUILDRANK_VETERAN = 4
GUILDRANK_GM = 3
GUILDRANK_OFFICER = 2
GUILDRANK_MEMBER = 1

class OperationFSM(FSM):
    HAS_DELAY = True

    def __init__(self, mgr, sender, callback=None):
        FSM.__init__(self, 'OperationFSM-%s' % sender)
        self.mgr = mgr
        self.air = mgr.air
        self.sender = sender
        self.callback = callback
        self.deleted = False
        
        if self.HAS_DELAY:
            self.mgr.operations[self.sender] = self
    
    def fsmName(self, name):
        return 'OperationFSM-%s-%s' % (id(self), name)
    
    def deleteOperation(self):
        if not self.deleted:
            if self.HAS_DELAY:
                taskMgr.doMethodLater(0.25, self.__deleteOperation, self.fsmName('deleteOperation'))
            
            self.deleted = True
    
    def __deleteOperation(self, task):
        if self.sender in self.mgr.operations:
            del self.mgr.operations[self.sender]

    def enterOff(self):
        self.deleteOperation()
    
    def enterError(self, message=None):
        self.mgr.notify.warning("An error has occurred in a '%s'. Message: %s" % (self.__class__.__name__, message))
        self.deleteOperation()

class RetrievePirateOperation(OperationFSM):
    
    def enterStart(self):
        self.air.dbInterface.queryObject(self.air.dbId, self.sender, self.__retrievedPirate)
    
    def __retrievedPirate(self, dclass, fields):
        if dclass != self.air.dclassesByName['DistributedPlayerPirateUD']:
            self.demand('Error', 'Sender is not a pirate.')
            return

        self.pirate = fields
        self.demand('RetrievedPirate')
    
    def enterRetrievedPirate(self):
        pass

class RetrievePirateGuildOperation(RetrievePirateOperation):

    def enterRetrievedPirate(self):
        self.guildId = self.pirate['setGuildId'][0]
        
        if not self.guildId:
            self.demand('Off')
            return
        
        self.air.dbInterface.queryObject(self.air.dbId, self.guildId, self.__retrievedGuild)
    
    def __retrievedGuild(self, dclass, fields):
        if dclass != self.air.dclassesByName['DistributedGuildUD']:
            self.demand('Error', 'Guild ID is not linked to a guild.')
            return

        self.guild = fields
        self.demand('RetrievedGuild')
    
    def enterRetrievedGuild(self):
        pass

class UpdatePirateExtension(object):

    def enterUpdatePirate(self):
        self.changedFields = {
            'setGuildId': [self.guildId],
            'setGuildName': [self.name]
        }

        self.air.dbInterface.updateObject(self.air.dbId, self.sender, self.air.dclassesByName['DistributedPlayerPirateUD'], self.changedFields, callback=self.__updatedPirate)
    
    def __updatedPirate(self, fields):
        dclass = self.air.dclassesByName['DistributedPlayerPirateUD']

        for key, value in self.changedFields.iteritems():
            self.air.send(dclass.aiFormatUpdate(key, self.sender, self.sender, self.air.ourChannel, value))

        self.mgr.d_guildStatusUpdate(self.sender, self.guildId, self.name, GUILDRANK_GM)
        self.demand('Off')

class CreateGuildOperation(RetrievePirateOperation, UpdatePirateExtension):
    name = 'Pirate Guild'

    def enterRetrievedPirate(self):
        guildId = self.pirate['setGuildId'][0]

        if False and guildId:
            self.demand('Off')
            return
        
        self.air.dbInterface.createObject(self.air.dbId, self.air.dclassesByName['DistributedGuildUD'], {'setName': [self.name]}, self.__createdGuild)
    
    def __createdGuild(self, doId):
        if not doId:
            self.demand('Error', "Couldn't create guild object on the database.")
            return

        self.guildId = doId
        self.demand('UpdatePirate')

class PirateOnlineOperation(RetrievePirateGuildOperation, UpdatePirateExtension):
    HAS_DELAY = False
    
    def enterRetrievedGuild(self):
        self.name = self.guild['setName'][0]
        self.demand('UpdatePirate')

class GuildManagerUD(DistributedObjectGlobalUD):
    notify = DirectNotifyGlobal.directNotify.newCategory("GuildManagerUD")
    
    def __init__(self, air):
        DistributedObjectGlobalUD.__init__(self, air)
        self.operations = {}
        self.accept('pirateOnline', self.pirateOnline)
    
    def hasOperation(self, avId):
        return avId in self.operations

    def createGuild(self):
        avId = self.air.getAvatarIdFromSender()
        
        if avId not in self.operations:
            CreateGuildOperation(self, avId).demand('Start')
    
    def d_guildStatusUpdate(self, avId, guildId, guildName, guildRank):
        self.sendUpdateToAvatarId(avId, 'guildStatusUpdate', [guildId, guildName, guildRank])
    
    def pirateOnline(self, doId):
        PirateOnlineOperation(self, doId).demand('Start')
    
    def online(self):
        pass

    def guildRejectInvite(self, todo0, todo1):
        pass

    def invitationFrom(self, todo0, todo1, todo2, todo3):
        pass

    def requestInvite(self, todo0):
        pass

    def memberList(self):
        pass

    def acceptInvite(self):
        pass

    def declineInvite(self):
        pass

    def setWantName(self, todo0):
        pass

    def removeMember(self, todo0):
        pass

    def changeRank(self, todo0, todo1):
        pass

    def changeRankAvocate(self, todo0):
        pass

    def requestLeaderboardTopTen(self):
        pass

    def guildStatusUpdate(self, todo0, todo1, todo2):
        pass

    def guildNameReject(self, todo0):
        pass

    def guildNameChange(self, todo0, todo1):
        pass

    def receiveMember(self, todo0):
        pass

    def receiveMembersDone(self):
        pass

    def guildAcceptInvite(self, todo0):
        pass

    def guildDeclineInvite(self, todo0):
        pass

    def updateRep(self, todo0, todo1):
        pass

    def leaderboardTopTen(self, todo0):
        pass

    def recvAvatarOnline(self, todo0, todo1, todo2, todo3):
        pass

    def recvAvatarOffline(self, todo0, todo1):
        pass

    def sendChat(self, todo0, todo1, todo2):
        pass

    def sendSC(self, todo0):
        pass

    def sendSCQuest(self, todo0, todo1, todo2):
        pass

    def recvChat(self, todo0, todo1, todo2, todo3):
        pass

    def recvSC(self, todo0, todo1):
        pass

    def recvSCQuest(self, todo0, todo1, todo2, todo3):
        pass

    def sendTokenRequest(self):
        pass

    def recvTokenGenerated(self, todo0):
        pass

    def recvTokenInviteValue(self, todo0, todo1):
        pass

    def sendTokenForJoinRequest(self, todo0, todo1):
        pass

    def recvTokenRedeemMessage(self, todo0):
        pass

    def recvTokenRedeemedByPlayerMessage(self, todo0):
        pass

    def sendTokenRValue(self, todo0, todo1):
        pass

    def sendPermToken(self):
        pass

    def sendNonPermTokenCount(self):
        pass

    def recvPermToken(self, todo0):
        pass

    def recvNonPermTokenCount(self, todo0):
        pass

    def sendClearTokens(self, todo0):
        pass

    def sendAvatarBandId(self, todo0, todo1, todo2):
        pass

    def recvMemberAdded(self, todo0, todo1, todo2):
        pass

    def notifyGuildKicksMaxed(self):
        pass

    def recvMemberRemoved(self, todo0, todo1, todo2, todo3):
        pass

    def recvMemberUpdateName(self, todo0, todo1):
        pass

    def recvMemberUpdateRank(self, todo0, todo1, todo2, todo3, todo4, todo5):
        pass

    def recvMemberUpdateBandId(self, todo0, todo1, todo2):
        pass

    def avatarOnline(self, todo0, todo1):
        pass

    def avatarOffline(self, todo0):
        pass

    def reflectTeleportQuery(self, todo0, todo1, todo2, todo3, todo4):
        pass

    def teleportQuery(self, todo0, todo1, todo2, todo3, todo4):
        pass

    def reflectTeleportResponse(self, todo0, todo1, todo2, todo3, todo4):
        pass

    def teleportResponse(self, todo0, todo1, todo2, todo3, todo4):
        pass

    def requestGuildMatesList(self, todo0, todo1, todo2):
        pass

    def updateAvatarName(self, todo0, todo1):
        pass

    def avatarDeleted(self, todo0):
        pass
