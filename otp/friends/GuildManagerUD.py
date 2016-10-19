from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectGlobalUD import DistributedObjectGlobalUD
from direct.fsm.FSM import FSM
from otp.otpbase import OTPUtils
from otp.uberdog.RejectCode import RejectCode

GUILDRANK_VETERAN = 4
GUILDRANK_GM = 3
GUILDRANK_OFFICER = 2
GUILDRANK_MEMBER = 1

class OperationFSM(FSM):
    DELAY = 0.25

    def __init__(self, mgr, sender, target=None, callback=None):
        FSM.__init__(self, 'OperationFSM-%s' % sender)
        self.mgr = mgr
        self.air = mgr.air
        self.sender = sender
        self.target = target
        self.callback = callback
        self.deleted = False
        
        if self.DELAY:
            self.mgr.operations[self.sender] = self
    
    def fsmName(self, name):
        return 'OperationFSM-%s-%s' % (id(self), name)
    
    def deleteOperation(self):
        if not self.deleted:
            if self.DELAY:
                taskMgr.doMethodLater(self.DELAY, self.__deleteOperation, self.fsmName('deleteOperation'))
            
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
        self.members = [list(member) for member in fields['setMembers'][0]]
        self.demand('RetrievedGuild')
    
    def enterRetrievedGuild(self):
        pass
    
    def getMember(self, avId):
        for i, member in enumerate(self.members):
            if member[0] == avId:
                return i, member
    
    def isMember(self, avId):
        for i, member in enumerate(self.members):
            if member[0] == avId:
                return True
        
        return False
    
    def updateMembers(self, members):
        self.air.dbInterface.updateObject(self.air.dbId, self.guildId, self.air.dclassesByName['DistributedGuildUD'], {'setMembers': [members]})

class UpdatePirateExtension(object):

    def enterUpdatePirate(self, guildId, guildName, rank):
        dclass = self.air.dclassesByName['DistributedPlayerPirateUD']
        
        self.air.send(dclass.aiFormatUpdate('setGuildId', self.sender, self.sender, self.air.ourChannel, [guildId]))
        self.air.send(dclass.aiFormatUpdate('setGuildName', self.sender, self.sender, self.air.ourChannel, [guildName]))
        self.mgr.d_guildStatusUpdate(self.sender, guildId, guildName, rank)
        self.demand('Off')

class CreateGuildOperation(RetrievePirateOperation, UpdatePirateExtension):
    name = 'Pirate Guild'
    rank = GUILDRANK_GM

    def enterRetrievedPirate(self):
        guildId = self.pirate['setGuildId'][0]

        if guildId:
            self.demand('Off')
            return
        
        name = self.pirate['setName'][0]
        fields = {
            'setName': [self.name],
            'setMembers': [[[self.sender, GUILDRANK_GM, name, 0, 0]]]
        }
        self.air.dbInterface.createObject(self.air.dbId, self.air.dclassesByName['DistributedGuildUD'], fields, self.__createdGuild)
    
    def __createdGuild(self, doId):
        if not doId:
            self.demand('Error', "Couldn't create guild object on the database.")
            return

        self.demand('UpdatePirate', doId, self.name, GUILDRANK_GM)

class PirateOnlineOperation(RetrievePirateGuildOperation, UpdatePirateExtension):
    DELAY = 0.0
    
    def enterRetrievedGuild(self):
        guildName = self.guild['setName'][0]
        pirateName = self.pirate['setName'][0]
        i, member = self.getMember(self.sender)
        
        if not member:
            self.demand('Off')
            return

        if member[2] != pirateName:
            member[2] = pirateName
            self.members[i] = member
            self.updateMembers(self.members)

        self.demand('UpdatePirate', self.guildId, guildName, GUILDRANK_GM)

class RemoveMemberOperation(RetrievePirateGuildOperation, UpdatePirateExtension):
    
    def enterRetrievedGuild(self):
        i, senderMember = self.getMember(self.sender)
        
        if not senderMember:
            self.demand('Off')
            return

        j, targetMember = self.getMember(self.target)
        
        if not targetMember:
            self.demand('Off')
            return

        senderRank = senderMember[1]
        targetRank = targetMember[1]
        selfKick = self.sender == self.target
        
        if not selfKick and senderRank not in (GUILDRANK_OFFICER, GUILDRANK_GM):
            self.demand('Off')
            return
        
        if targetRank == GUILDRANK_GM and len(self.members) > 1:
            self.demand('Off')
            return
        
        if senderRank == GUILDRANK_OFFICER and not selfKick:
            senderTime = senderMember[3]
            senderKickNum = senderMember[4]
            currentTime = int(time.time())
            
            if senderTime != 0 and senderTime > currentTime and senderKickNum == 5:
                self.mgr.d_notifyGuildKicksMaxed(self.sender)
                self.demand('Off')
                return
            
            if senderTime == 0 or senderTime <= currentTime:
                senderMember[3] = currentTime + 86400 # One day
                senderMember[4] = 1
            else:
                senderMember[4] += 1

            self.members[i] = senderMember

        del self.members[j]
        self.updateMembers(self.members)
        self.demand('UpdatePirate', 0, '', 0)

class MemberListOperation(RetrievePirateGuildOperation):
    DELAY = 1.5
    
    def enterRetrievedGuild(self):
        memberInfo = []
        
        for member in self.members:
            avId, rank, name, _, _ = member
            online = avId in self.air.piratesFriendsManager.onlinePirates
            bandManagerId = 0
            bandId = 0
            
            memberInfo.append([avId, name, rank, online, bandManagerId, bandId])
        
        self.mgr.d_receiveMembers(self.sender, memberInfo)
        self.demand('Off')

class RequestInviteOperation(RetrievePirateGuildOperation):
    DELAY = 1.5
    
    def enterRetrievedGuild(self):
        if self.isMember(self.target):
            self.mgr.d_guildRejectInvite(self.sender, RejectCode.ALREADY_IN_GUILD)
            self.demand('Off')
            return
    
        self.air.dbInterface.queryObject(self.air.dbId, self.target, self.__retrievedPirate)
    
    def __retrievedPirate(self, dclass, fields):
        if dclass != self.air.dclassesByName['DistributedPlayerPirateUD']:
            self.demand('Error', 'Sender is not a pirate.')
            return

        if fields['setGuildId'][0]:
            self.mgr.d_guildRejectInvite(self.sender, RejectCode.ALREADY_IN_GUILD)
            self.demand('Off')
            return
        
        self.mgr.addInvitation(self.sender, self.target, self.pirate['setName'][0], self.guildId, self.guild['setName'][0])
        self.demand('Off')
    
class GuildManagerUD(DistributedObjectGlobalUD):
    notify = DirectNotifyGlobal.directNotify.newCategory("GuildManagerUD")
    
    def __init__(self, air):
        DistributedObjectGlobalUD.__init__(self, air)
        self.operations = {}
        self.invites = {}
        self.accept('pirateOnline', self.pirateOnline)
    
    def hasOperation(self, avId):
        return avId in self.operations

    def createGuild(self):
        avId = self.air.getAvatarIdFromSender()
        
        if avId not in self.operations:
            CreateGuildOperation(self, avId).demand('Start')
    
    def d_guildStatusUpdate(self, avId, guildId, guildName, guildRank):
        self.sendUpdateToAvatarId(avId, 'guildStatusUpdate', [guildId, guildName, guildRank])
    
    def d_notifyGuildKicksMaxed(self, avId):
        self.sendUpdateToAvatarId(avId, 'notifyGuildKicksMaxed', [])
    
    def d_receiveMembers(self, avId, members):
        self.sendUpdateToAvatarId(avId, 'receiveMembers', [members])
    
    def d_guildAcceptInvite(self, avId):
        self.sendUpdateToAvatarId(avId, 'guildAcceptInvite', [])
    
    def d_guildRejectInvite(self, avId, reason):
        self.sendUpdateToAvatarId(avId, 'guildRejectInvite', [reason])
    
    def d_invitationFrom(self, avId, fromId, fromName, guildId, guildName):
        self.sendUpdateToAvatarId(avId, 'invitationFrom', [fromId, fromName, guildId, guildName])
    
    def pirateOnline(self, doId):
        PirateOnlineOperation(self, doId).demand('Start')
    
    def removeMember(self, targetId):
        avId = self.air.getAvatarIdFromSender()
        
        if targetId and avId not in self.operations:
            RemoveMemberOperation(self, avId, targetId).demand('Start')
    
    def requestMembers(self):
        avId = self.air.getAvatarIdFromSender()

        if avId not in self.operations:
            MemberListOperation(self, avId).demand('Start')
    
    def isInInvite(self, avId):
        return avId in self.invites.keys() or avId in self.invites.values()
    
    def requestInvite(self, targetId):
        avId = self.air.getAvatarIdFromSender()
        
        if targetId == avId or self.isInInvite(targetId):
            self.d_guildRejectInvite(avId, RejectCode.BUSY)
            return
        
        if targetId not in self.air.piratesFriendsManager.onlinePirates:
            self.d_guildRejectInvite(avId, RejectCode.INVITEE_NOT_ONLINE)
            return
        
        if self.isInInvite(avId):
            return
        
        if avId not in self.operations:
            RequestInviteOperation(self, avId, targetId).demand('Start')
    
    def addInvitation(self, sender, target, pirateName, guildId, guildName):
        self.invites[sender] = target
        self.d_invitationFrom(target, sender, pirateName, guildId, guildName)
    