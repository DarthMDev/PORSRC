from panda3d.core import Connection, Datagram
from pirates.makeapirate.PCPickANamePattern import PCPickANamePattern
from pirates.piratesbase import PiratesGlobals
from pirates.pirate.HumanDNA import HumanDNA
from otp.settings.Settings import Settings
from otp.distributed import OtpDoGlobals
from direct.distributed.DistributedObjectGlobalUD import DistributedObjectGlobalUD
from direct.directnotify.DirectNotifyGlobal import directNotify
from direct.distributed.PyDatagram import *
from direct.fsm.FSM import FSM
from sys import platform
import traceback
import hashlib
import urllib
import urllib2
import hmac
import json
import time
import math
import sys
import os

sys.path.append('../deployment')
try:
    import challenge

except ImportError:
    class challenge:
        @staticmethod
        def solve(*args):
            return 'whatever'

NAME_TYPED = 0
NAME_TYPED_INVALID = 1
NAME_PICKED = 2

NAME_PEN = 0
NAME_REJ = 1
NAME_APR = 2
NAME_STATES = {NAME_PEN: 'PENDING', NAME_REJ: 'OPEN', NAME_APR: 'APPROVED'}

def rejectConfig(issue, securityIssue=True, retarded=True):
    print
    print
    print 'Lemme get this straight....'
    print 'You are trying to use remote account database type...'
    print 'However,', issue + '!!!!'
    if securityIssue:
        print 'Do you want this server to get hacked?'
    if retarded:
        print '"Either down\'s or autism"\n  - JohnnyDaPirate, 2015'
    print 'Go fix that!'
    exit()

def entropy(string):
    prob = [float(string.count(c)) / len(string) for c in dict.fromkeys(list(string))]
    entropy = -sum([p * math.log(p) / math.log(2.0) for p in prob])
    return entropy

def entropyIdeal(length):
    prob = 1.0 / length
    return -length * prob * math.log(prob) / math.log(2.0)

# Account db type can be:
# 1. developer - This is for general development with username as token.
# 2. remote - This decodes the token. Used for production.

accountDBType = config.GetString('accountdb-type', 'developer')

if sys.platform == 'linux2':
    accountDBType = 'remotePOR'

accountServerTokenLink = config.GetString('account-server-token-link', '')
accountServerSecret = config.GetString('account-server-secret', 'dev')

__keyfile = '../deployment/site/loginsecret.key'
if os.path.isfile(__keyfile) and config.GetBool('want-login-secret-from-file', True):
    with open(__keyfile, 'rb') as f:
        accountServerSecret = f.read().strip()

accountServerHashAlgo = config.GetString('account-server-hash-algo', 'sha256')

hashAlgo = getattr(hashlib, accountServerHashAlgo, None)
if not hashAlgo:
    rejectConfig('%s is not a valid hash algo' % accountServerHashAlgo, securityIssue=False)

hashSize = len(hashAlgo().digest())

if accountDBType == 'remote':
    if accountServerSecret == 'dev':
        rejectConfig('you have not changed the secret in config/local.prc')

    if len(accountServerSecret) < 16:
        rejectConfig('the secret is too small! Make it 16+ bytes', retarded=False)

    secretLength = len(accountServerSecret)
    ideal = entropyIdeal(secretLength) / 2
    entropy = entropy(accountServerSecret)
    if entropy < ideal:
        rejectConfig('the secret entropy is too low! For %d bytes,'
                     ' it should be %d. Currently it is %d' % (secretLength, ideal, entropy),
                     retarded=False)

def flip(a):
    # This is SIMPLE OBFUSCATION not ENCRYPTION
    return ''.join(chr(~ord(x) & 0xFF) for x in a)

class CSMOperation(FSM):
    notify = directNotify.newCategory('CSMOperation')
    TARGET_CONNECTION = False

    def __init__(self, csm, target):
        FSM.__init__(self, self.__class__.__name__)

        self.target = target
        self.csm = csm

    def enterKill(self, reason=''):
        if self.TARGET_CONNECTION:
            self.csm.killConnection(self.target, reason)
        else:
            self.csm.killAccount(self.target, reason)
        self.demand('Off')

    def enterOff(self):
        if self.target in self.csm.connection2fsm:
            del self.csm.connection2fsm[self.target]
        if self.target in self.csm.account2fsm:
            del self.csm.account2fsm[self.target]

class AccountDB:
    notify = directNotify.newCategory('AccountDB')

    def __init__(self, csm):
        self.csm = csm
        
        if not simbase.air.hasMongo():
            self.notify.info('Loading YAML account bridge.')
            self.accountBridgeFile = Settings(config.GetString('yaml-account-bridge-filename', ''))
            self.accountBridge = self.accountBridgeFile.read()
        else:
            self.accountBridge = None

    def lookupAccountId(self, user):
        user = str(user)

        if simbase.air.hasMongo():
            document = self.csm.air.dbAstronCursor.objects.find_one({'fields.ACCOUNT_ID': user})
        
            if document: 
                return document['_id']
        elif user in self.accountBridge:
            return int(self.accountBridge[user])
    
    def lookup(self, username, accessLevel, callback):
        accountId = self.lookupAccountId(username)

        response = {'success': True,
                    'userId': username,
                    'accountId': accountId}

        if accessLevel is not None:
            response['accessLevel'] = accessLevel

        callback(response)
        return response

    def storeAccountID(self, userId, accountId, callback):
        if not simbase.air.hasMongo():
            self.accountBridge[str(userId)] = str(accountId)
            self.accountBridgeFile.write(self.accountBridge)

        callback(True)

    def getNameStatus(self, username, callback):
        # Returns approved. Subclasses MUST override this and return appropriated value.
        callback(NAME_APR)

class DeveloperAccountDB(AccountDB):
    notify = directNotify.newCategory('DeveloperAccountDB')

    def lookup(self, username, callback):
        return AccountDB.lookup(self, username, 700, callback)

class RemoteAccountDB(AccountDB):
    notify = directNotify.newCategory('RemoteAccountDB')
    namesUrl = config.GetString('account-db-names-url', 'http://api.piratesonline.co/names/')
    
    @staticmethod
    def post(air, url, **data):
        headers = {'User-Agent' : 'PiratesUberAgent'}
        
        innerData = json.dumps(data)
        hmac = hashlib.sha512(innerData + air.getApiKey()).hexdigest()
        
        data = 'data=%s' % urllib.quote(innerData)
        data += '&hmac=%s' % urllib.quote(hmac)
        
        success = True
        error = None
        res = {}
        
        try:
            req = urllib2.Request(url, data, headers)
            res = json.loads(urllib2.urlopen(req).read())
            success = res['success']
            error = res.get('error')
            
        except Exception as e:
            if hasattr(e, 'read'):
                with open('../e.html', 'wb') as f:
                    f.write(e.read())
                
            success = False
            error = str(e)
                
        return (success, error), res

    @staticmethod
    def decodeToken(token, maxAge=300):
        error = lambda issue: {'success': False, 'reason': 'The account server rejected your token: %s' % issue}

        if len(token) != 216:
            return error('Invalid size')

        try:
            token = token.decode('base64')

        except:
            return error('Bad token')

        size = ord(token[0])
        token = token[1:size + 1]

        if len(token) <= hashSize:
            return error('Bad padding')

        hash, data = token[:hashSize], token[hashSize:]

        signature = hashAlgo(data + accountServerSecret).digest()
        value = 0
        for x, y in zip(signature, hash):
            value |= ord(x) ^ ord(y)

        if value:
            return error('Bad hash')

        data = flip(data)
        try:
            data = json.loads('{%s}' % data)

        except:
            return error('Bad data')

        now = time.time()
        ts = data.get('timestamp', -1)
        if ts == -1:
            if config.GetBool('token-allow-no-timestamp', False):
                ts = now
                
            else:
                return error('No timestamp')
            
        expiration = ts + maxAge
        if now > expiration:
            elapsed = now - expiration
            return error('Token expired %.1f seconds ago' % elapsed)

        data['success'] = True
        return data

    def lookup(self, token, callback):
        data = RemoteAccountDB.decodeToken(token)
        if not data['success']:
            callback(data)
            return data

        return AccountDB.lookup(self, str(data['username']),
                                data['accessLevel'],
                                callback)

class RemotePORAccountDB(AccountDB):
    notify = directNotify.newCategory('RemotePORAccountDB')
    
    def __init__(self, csm):
        AccountDB.__init__(self, csm)
        self.accessLevel = 100
    
    def getSecretToken(self):
        return config.GetString('account-server-token', '')

    def post(self, url, data):
        data['secrettoken'] = self.getSecretToken()

        headers = {'User-Agent': 'POR-ClientServicesManagerUD'}
        data = urllib.urlencode(data)
        response = None

        try:
            request = urllib2.Request(url, data, headers)
            response = json.loads(urllib2.urlopen(request).read())
        except Exception as e:
            self.notify.warning('Exception happened in post (%s): %s' % (url, traceback.format_exc()))

        return response
    
    def getNameStatus(self, name, callback):
        response = self.post(config.GetString('account-server-names-link', ''), {'name': name})
        
        if not response:
            self.notify.warning('No response from server while querying name %s!' % name)
            callback(NAME_PEN)
            return

        if response['status'] == 'error':
            self.notify.warning('Error while querying name %s from the server! %s [Code %s]' % (name, response['message'], response['code']))
            callback(NAME_PEN)
            return
        
        callback(int(response['nameStatus']))

    def decodeToken(self, token, maxAge=300):
        error = lambda issue: {'success': False, 'reason': 'The account server rejected your token: %s' % issue}

        if len(token) != 55:
            return error('Invalid size')

        if not accountServerTokenLink:
            return error('Server token link missing')

        try:
            data = urllib.urlencode({'udtoken': token})
            request = urllib2.Request(accountServerTokenLink, data)
            response = urllib2.urlopen(request).read()
            response = json.loads(response)
            user = response['user']
            accessLevel = int(response['access'])
        except:
            return error("Couldn't contact server")
        
        accountId = self.lookupAccountId(user)

        return {'success': True, 'userId': user, 'accountId': accountId, 'accessLevel': accessLevel}

    def lookup(self, token, callback):
        try:
            data = self.decodeToken(token)
        except:
            data = {'success': False, 'reason': 'Something went wrong.'}

        callback(data)
        return data

class LoginAccountFSM(CSMOperation):
    notify = directNotify.newCategory('LoginAccountFSM')
    TARGET_CONNECTION = True

    def enterStart(self, token):
        self.token = token
        self.demand('QueryAccountDB')

    def enterQueryAccountDB(self):
        self.csm.accountDB.lookup(self.token, self.__handleLookup)

    def __handleLookup(self, result):
        if not result.get('success'):
            self.csm.air.writeServerEvent('tokenRejected', self.target, self.token)
            self.demand('Kill', result.get('reason', 'The account server rejected your token.'))
            return

        self.userId = result.get('userId', 0)
        self.accountId = result.get('accountId', 0)
        self.accessLevel = result.get('accessLevel', 0)

        if self.accountId:
            self.demand('RetrieveAccount')
        else:
            self.demand('CreateAccount')

    def enterRetrieveAccount(self):
        self.csm.air.dbInterface.queryObject(
            self.csm.air.dbId, self.accountId, self.__handleRetrieve)

    def __handleRetrieve(self, dclass, fields):
        if dclass != self.csm.air.dclassesByName['AccountUD']:
            self.demand('Kill', 'Your account object was not found in the database!')
            return

        self.account = fields
        self.demand('SetAccount')

    def enterCreateAccount(self):
        self.account = {
            'ACCOUNT_AV_SET': [0] * 6,
            'ACCOUNT_AV_SET_DEL': [],
            'CREATED': time.ctime(time.mktime(time.gmtime())),
            'LAST_LOGIN': time.ctime(time.mktime(time.gmtime())),
            'ACCOUNT_ID': str(self.userId)
        }
        
        if self.accessLevel is not None:
            self.account['ACCESS_LEVEL'] = self.accessLevel

        self.csm.air.dbInterface.createObject(
            self.csm.air.dbId,
            self.csm.air.dclassesByName['AccountUD'],
            self.account,
            self.__handleCreate)

    def __handleCreate(self, accountId):
        if self.state != 'CreateAccount':
            self.notify.warning('Received a create account response outside of the CreateAccount state.')
            return

        if not accountId:
            self.notify.warning('Database failed to construct an account object!')
            self.demand('Kill', 'Your account object could not be created in the game database.')
            return

        self.accountId = accountId
        self.csm.air.writeServerEvent('accountCreated', accountId)
        self.demand('StoreAccountID')

    def enterStoreAccountID(self):
        self.csm.accountDB.storeAccountID(
            self.userId,
            self.accountId,
            self.__handleStored)

    def __handleStored(self, success=True):
        if not success:
            self.demand('Kill', 'The account server could not save your user ID!')
            return

        self.demand('SetAccount')

    def enterSetAccount(self):
        # If necessary, update their account information:
        if self.accessLevel:
            self.csm.air.dbInterface.updateObject(
                self.csm.air.dbId,
                self.accountId,
                self.csm.air.dclassesByName['AccountUD'],
                {'ACCESS_LEVEL': self.accessLevel})

        # If there's anybody on the account, kill them for redundant login:
        datagram = PyDatagram()
        datagram.addServerHeader(
            self.csm.GetAccountConnectionChannel(self.accountId),
            self.csm.air.ourChannel,
            CLIENTAGENT_EJECT)
        datagram.addUint16(100)
        datagram.addString('This account has been logged in from elsewhere.')
        self.csm.air.send(datagram)

        # Next, add this connection to the account channel.
        datagram = PyDatagram()
        datagram.addServerHeader(
            self.target,
            self.csm.air.ourChannel,
            CLIENTAGENT_OPEN_CHANNEL)
        datagram.addChannel(self.csm.GetAccountConnectionChannel(self.accountId))
        self.csm.air.send(datagram)

        # Now set their sender channel to represent their account affiliation:
        datagram = PyDatagram()
        datagram.addServerHeader(
            self.target,
            self.csm.air.ourChannel,
            CLIENTAGENT_SET_CLIENT_ID)
        # Account ID in high 32 bits, 0 in low (no avatar):
        datagram.addChannel(self.accountId << 32)
        self.csm.air.send(datagram)

        # Un-sandbox them!
        datagram = PyDatagram()
        datagram.addServerHeader(
            self.target,
            self.csm.air.ourChannel,
            CLIENTAGENT_SET_STATE)
        datagram.addUint16(2)  # ESTABLISHED
        self.csm.air.send(datagram)

        # Update the last login timestamp:
        self.csm.air.dbInterface.updateObject(
            self.csm.air.dbId,
            self.accountId,
            self.csm.air.dclassesByName['AccountUD'],
            {'LAST_LOGIN': time.ctime(time.mktime(time.gmtime())),
             'ACCOUNT_ID': str(self.userId)})

        # We're done.
        self.csm.air.writeServerEvent('accountLogin', self.target, self.accountId, self.userId)
        self.csm.sendUpdateToChannel(self.target, 'acceptLogin', [self.userId])
        self.demand('Off')

class CreateAvatarFSM(CSMOperation):
    notify = directNotify.newCategory('CreateAvatarFSM')
    pattern = PCPickANamePattern('', 'm')

    def enterStart(self, dna, index, allegiance, name):
        # Basic sanity-checking:
        if index >= 6:
            self.demand('Kill', 'Invalid index specified!')
            return
        if not PiratesGlobals.ALLEGIANCE_PIRATE <= allegiance <= PiratesGlobals.ALLEGIANCE_FRENCH:
            self.demand('Kill', 'Invalid allegiance specified!')
            return

        self.index = index

        if not HumanDNA.isValidNetString(dna):
            self.demand('Kill', 'Invalid DNA!')
            return

        self.dna = dna
        self.allegiance = allegiance

        self.name = name.strip()

        dna = HumanDNA()
        dna.makeFromNetString(self.dna)
        judged = self._judgeName(self.name, dna.gender)

        if judged == NAME_TYPED_INVALID:
            self.demand('Kill', 'Your name has been rejected!')
            return

        if judged == NAME_TYPED:
            self.name = 'Pirate'
            self.wishName = name.strip()
            self.csm.accountDB.getNameStatus(self.wishName, self.__handleNameRetrieved)
        else:
            self.name = name.strip()
            self.nameState = 'CLOSED'
            self.wishName = ''
            self.demand('RetrieveAccount')

    def __handleNameRetrieved(self, approved):
        self.nameState = NAME_STATES.get(approved, 'PENDING')
        
        if approved == NAME_APR:
            self.name = self.wishName
            self.wishName = ''
        
        self.demand('RetrieveAccount')
    
    def enterRetrieveAccount(self):
        self.csm.air.dbInterface.queryObject(
            self.csm.air.dbId, self.target, self.__handleRetrieve)

    def __handleRetrieve(self, dclass, fields):
        if dclass != self.csm.air.dclassesByName['AccountUD']:
            self.demand('Kill', 'Your account object was not found in the database!')
            return

        self.account = fields

        self.avList = self.account['ACCOUNT_AV_SET']
        # Sanitize:
        self.avList = self.avList[:6]
        self.avList += [0] * (6-len(self.avList))

        # Make sure the index is open:
        if self.avList[self.index]:
            self.demand('Kill', 'This avatar slot is already taken by another avatar!')
            return

        # Okay, there's space. Let's create the avatar!
        self.demand('CreateAvatar')

    def enterCreateAvatar(self):
        pirateFields = {
          'setName': (self.name,),
          'WishNameState': (self.nameState,),
          'WishName': (self.wishName,),
          'setDNAString': (self.dna,),
          'setDISLid': (self.target,),
          'setAllegiance': (self.allegiance,)
        }
        self.csm.air.dbInterface.createObject(
            self.csm.air.dbId,
            self.csm.air.dclassesByName['DistributedPlayerPirateUD'],
            pirateFields,
            self.__handleCreate)

    def __handleCreate(self, avId):
        if not avId:
            self.demand('Kill', 'Database failed to create the new avatar object!')
            return

        self.avId = avId
        self.demand('StoreAvatar')

    def enterStoreAvatar(self):
        # Associate the avatar with the account...
        self.avList[self.index] = self.avId
        self.csm.air.dbInterface.updateObject(
            self.csm.air.dbId,
            self.target,
            self.csm.air.dclassesByName['AccountUD'],
            {'ACCOUNT_AV_SET': self.avList},
            {'ACCOUNT_AV_SET': self.account['ACCOUNT_AV_SET']},
            self.__handleStoreAvatar)

    def __handleStoreAvatar(self, fields):
        if fields:
            self.demand('Kill', 'Database failed to associate the new avatar to your account!')
            return

        self.csm.air.writeServerEvent('avatarCreated', self.avId, self.target, self.dna.encode('hex'), self.index)
        self.csm.sendUpdateToAccountId(self.target, 'createAvatarResp', [self.avId])
        self.demand('Off')

    @classmethod
    def _judgeName(cls, name, gender):
        if CreateAvatarFSM.pattern._compute(name, gender) is None:
            if not name:
                return NAME_TYPED_INVALID # Empty string

            return NAME_TYPED

        return NAME_PICKED

class AvatarOperationFSM(CSMOperation):
    POST_ACCOUNT_STATE = 'Off'  # This needs to be overridden.
    
    def getId(self, identifier):
        return '%s-%s' % (id(self), identifier)

    def enterRetrieveAccount(self):
        # Query the account:
        self.csm.air.dbInterface.queryObject(
            self.csm.air.dbId, self.target, self.__handleRetrieve)

    def __handleRetrieve(self, dclass, fields):
        if dclass != self.csm.air.dclassesByName['AccountUD']:
            self.demand('Kill', 'Your account object was not found in the database!')
            return

        self.account = fields

        self.avList = self.account['ACCOUNT_AV_SET']
        # Sanitize:
        self.avList = self.avList[:6]
        self.avList += [0] * (6-len(self.avList))

        self.demand(self.POST_ACCOUNT_STATE)

class GetAvatarsFSM(AvatarOperationFSM):
    notify = directNotify.newCategory('GetAvatarsFSM')
    POST_ACCOUNT_STATE = 'QueryAvatars'

    def enterStart(self):
        self.demand('RetrieveAccount')

    def enterQueryAvatars(self):
        self.pendingAvatars = set()
        self.avatarFields = {}

        for avId in self.avList:
            if not avId:
                continue 

            self.pendingAvatars.add(avId)

            def response(dclass, fields, avId=avId):
                if self.state != 'QueryAvatars':
                    return
                if dclass != self.csm.air.dclassesByName['DistributedPlayerPirateUD']:
                    self.demand('Kill', "One of the account's avatars is invalid!")
                    return
                self.avatarFields[avId] = fields
                self.pendingAvatars.remove(avId)

                if not self.pendingAvatars:
                    self.demand('UpdateAvatarsNameState')

            self.csm.air.dbInterface.queryObject(
                self.csm.air.dbId,
                avId,
                response)
        
        taskMgr.doMethodLater(5, self.demand, self.getId('demand-off-timeout'), extraArgs=['SendAvatars'])

    def enterUpdateAvatarsNameState(self):
        for avId, fields in self.avatarFields.items():
            if fields.get('WishNameState', [''])[0] != 'PENDING':
                continue
            
            wishName = fields.get('WishName', [''])[0]
            
            def callback(nameStatus):
                wishNameState = NAME_STATES[nameStatus]
                
                if wishNameState in ('PENDING', 'CLOSED', 'OPEN'):
                    return

                self.avatarFields[avId]['WishNameState'] = (wishNameState,)

                if wishNameState == 'APPROVED':
                    self.avatarFields[avId]['setName'] = (wishName,)

                self.csm.air.dbInterface.updateObject(self.csm.air.dbId, avId, self.csm.air.dclassesByName['DistributedPlayerPirateUD'], self.avatarFields[avId])

            self.csm.accountDB.getNameStatus(wishName, callback)

        taskMgr.doMethodLater(0, self.demand, self.getId('demand-send-avatars'), extraArgs=['SendAvatars'])
    
    def enterSendAvatars(self):
        potentialAvs = []
        
        taskMgr.remove(self.getId('demand-off-timeout'))
        taskMgr.remove(self.getId('demand-send-avatars'))

        for avId, fields in self.avatarFields.items():
            index = self.avList.index(avId)
            wishNameState = fields.get('WishNameState', [''])[0]
            wishName = fields.get('WishName', [''])[0]
            name = fields['setName'][0]
            nameState = 0

            if wishNameState == 'OPEN':
                nameState = 1
            elif wishNameState == 'PENDING':
                nameState = 2
            elif wishNameState == 'APPROVED':
                nameState = 3
            elif wishNameState == 'REJECTED':
                nameState = 4

            potentialAvs.append([avId, name, fields['setDNAString'][0],
                                 index, nameState, wishName])

        self.csm.sendUpdateToAccountId(self.target, 'setAvatars', [potentialAvs])
        self.demand('Off')

    def enterOff(self):
        if self.target in self.csm.connection2fsm:
            del self.csm.connection2fsm[self.target]
        if self.target in self.csm.account2fsm:
            del self.csm.account2fsm[self.target]

class UnloadAvatarFSM(CSMOperation):
    notify = directNotify.newCategory('UnloadAvatarFSM')

    def enterStart(self, avId):
        self.avId = avId

        # We don't even need to query the account, we know the avatar is being played!
        self.demand('UnloadAvatar')

    def enterUnloadAvatar(self):
        channel = self.csm.GetAccountConnectionChannel(self.target)

        # Clear off POSTREMOVE:
        datagram = PyDatagram()
        datagram.addServerHeader(
            channel,
            self.csm.air.ourChannel,
            CLIENTAGENT_CLEAR_POST_REMOVES)
        self.csm.air.send(datagram)

        # Remove avatar channel:
        datagram = PyDatagram()
        datagram.addServerHeader(
            channel,
            self.csm.air.ourChannel,
            CLIENTAGENT_CLOSE_CHANNEL)
        datagram.addChannel(self.csm.GetPuppetConnectionChannel(self.avId))
        self.csm.air.send(datagram)

        # Reset sender channel:
        datagram = PyDatagram()
        datagram.addServerHeader(
            channel,
            self.csm.air.ourChannel,
            CLIENTAGENT_SET_CLIENT_ID)
        datagram.addChannel(self.target<<32)
        self.csm.air.send(datagram)

        # Unload avatar object:
        datagram = PyDatagram()
        datagram.addServerHeader(
            self.avId,
            channel,
            STATESERVER_OBJECT_DELETE_RAM)
        datagram.addUint32(self.avId)
        self.csm.air.send(datagram)

        # Done!
        self.csm.air.writeServerEvent('avatarUnload', self.avId)
        self.demand('Off')

class LoadAvatarFSM(AvatarOperationFSM):
    notify = directNotify.newCategory('LoadAvatarFSM')
    POST_ACCOUNT_STATE = 'GetTargetAvatar'

    def enterStart(self, avId):
        self.avId = avId
        self.demand('RetrieveAccount')

    def enterGetTargetAvatar(self):
        # Make sure the target avatar is part of the account:
        if self.avId not in self.avList:
            self.demand('Kill', 'Tried to play an avatar not in the account!')
            return

        self.csm.air.dbInterface.queryObject(self.csm.air.dbId, self.avId,
                                             self.__handleAvatar)

    def __handleAvatar(self, dclass, fields):
        if dclass != self.csm.air.dclassesByName['DistributedPlayerPirateUD']:
            self.demand('Kill', "One of the account's avatars is invalid!")
            return

        self.avatar = fields
        self.demand('LoadInventory')

    def __getGMTag(self, accessLevel):
        if accessLevel == 0:
            return ("red", "System Admin")
        if accessLevel == 150:
            return ("green", "POR Youtuber")
        elif accessLevel > 100 and accessLevel <= 400:
            return ("red", "Game Master")
        if accessLevel > 500:
            return ("green", "Developer")

    def enterLoadInventory(self):
        channel = self.csm.GetAccountConnectionChannel(self.target)

        # First, give them a POSTREMOVE to unload the avatar, just in case they
        # disconnect while we're working.
        datagramCleanup = PyDatagram()
        datagramCleanup.addServerHeader(self.avId, channel, STATESERVER_OBJECT_DELETE_RAM)
        datagramCleanup.addUint32(self.avId)
        datagram = PyDatagram()
        datagram.addServerHeader(channel, self.csm.air.ourChannel, CLIENTAGENT_ADD_POST_REMOVE)
        datagram.addString(datagramCleanup.getMessage())
        self.csm.air.send(datagram)

        # Inventory post-remove event handler:
        datagram = PyDatagram()
        datagram.addServerHeader(channel, self.csm.air.ourChannel, CLIENTAGENT_ADD_POST_REMOVE)
        datagram.addString(self.csm.air.prepareMessage('UD_avExit', [self.avId]).getMessage())
        self.csm.air.send(datagram)

        # Activate the avatar on the DBSS:
        access = self.account.get('ACCESS_LEVEL', 100)
        if access == 100:
            self.csm.air.sendActivate(
                self.avId, 0, 0, self.csm.air.dclassesByName['DistributedPlayerPirateUD'],
                {'setAdminAccess': [self.account.get('ACCESS_LEVEL', 100)],
                 'setName': self.avatar['setName']})
        else:
            gmTag = self.__getGMTag(access)
            self.csm.air.sendActivate(
                self.avId, 0, 0, self.csm.air.dclassesByName['DistributedPlayerPirateUD'],
                {'setAdminAccess': [self.account.get('ACCESS_LEVEL', 100)],
                 'setName': self.avatar['setName'],
                 'setGMNametag': gmTag})
        # Next, add them to the avatar channel:
        datagram = PyDatagram()
        datagram.addServerHeader(
            channel,
            self.csm.air.ourChannel,
            CLIENTAGENT_OPEN_CHANNEL)
        datagram.addChannel(self.csm.GetPuppetConnectionChannel(self.avId))
        self.csm.air.send(datagram)

        # Now set their sender channel to represent their account affiliation:
        datagram = PyDatagram()
        datagram.addServerHeader(
            channel,
            self.csm.air.ourChannel,
            CLIENTAGENT_SET_CLIENT_ID)
        datagram.addChannel(self.target<<32 | self.avId)
        self.csm.air.send(datagram)

        self.acceptOnce('inventory-loaded-%d' % self.avId, self.gotInventory)
        self.csm.air.inventoryMgr.initiateAvatarInventory(self.avId, self.avatar.get('setInventoryId', [0])[0])

    def gotInventory(self, obj):
        if obj:
            dg = PyDatagram()
            dg.addServerHeader(obj.inventoryId, self.csm.air.ourChannel, STATESERVER_OBJECT_SET_OWNER)
            dg.addChannel(self.target << 32 | self.avId)
            self.csm.air.send(dg)

            self.demand('SetAvatar')

    def enterSetAvatar(self):
        channel = self.csm.GetAccountConnectionChannel(self.target)

        # Finally, grant ownership and shut down.
        datagram = PyDatagram()
        datagram.addServerHeader(
            self.avId,
            self.csm.air.ourChannel,
            STATESERVER_OBJECT_SET_OWNER)
        datagram.addChannel(self.target<<32 | self.avId)
        self.csm.air.send(datagram)

        self.csm.air.writeServerEvent('avatarChosen', self.avId, self.target)
        self.demand('Off')

class DeleteAvatarFSM(AvatarOperationFSM):
    notify = directNotify.newCategory('DeleteAvatarFSM')
    POST_ACCOUNT_STATE = 'ProcessDelete'

    def enterStart(self, avId):
        self.avId = avId
        self.demand('RetrieveAccount')

    def enterProcessDelete(self):
        if self.avId not in self.avList:
            self.demand('Kill', 'Tried to delete an avatar not in the account!')
            return

        index = self.avList.index(self.avId)
        self.avList[index] = 0

        avsDeleted = list(self.account.get('ACCOUNT_AV_SET_DEL', []))
        avsDeleted.append([self.avId, int(time.time())])

        self.csm.air.dbInterface.updateObject(
            self.csm.air.dbId,
            self.target, # i.e. the account ID
            self.csm.air.dclassesByName['AccountUD'],
            {'ACCOUNT_AV_SET': self.avList,
             'ACCOUNT_AV_SET_DEL': avsDeleted},
            {'ACCOUNT_AV_SET': self.account['ACCOUNT_AV_SET'],
             'ACCOUNT_AV_SET_DEL': self.account['ACCOUNT_AV_SET_DEL']},
            self.__handleDelete)

    def __handleDelete(self, fields):
        if fields:
            self.demand('Kill', 'Database failed to mark the avatar deleted!')
            return

        self.csm.air.writeServerEvent('avatarDeleted', self.avId, self.target)
        self.csm.sendUpdateToAccountId(self.target, 'avDeleted', [self.avId])
        self.demand('Off')

class AcknowledgeNameFSM(AvatarOperationFSM):
    notify = directNotify.newCategory('AcknowledgeNameFSM')
    POST_ACCOUNT_STATE = 'GetTargetAvatar'

    def enterStart(self, avId):
        self.avId = avId
        self.demand('RetrieveAccount')

    def enterGetTargetAvatar(self):
        # Make sure the target avatar is part of the account:
        if self.avId not in self.avList:
            self.demand('Kill', 'Tried to acknowledge name on an avatar not in the account!')
            return

        self.csm.air.dbInterface.queryObject(self.csm.air.dbId, self.avId,
                                             self.__handleAvatar)

    def __handleAvatar(self, dclass, fields):
        if dclass != self.csm.air.dclassesByName['DistributedPlayerPirateUD']:
            self.demand('Kill', "One of the account's avatars is invalid!")
            return

        # Process the WishNameState change.
        wns = fields['WishNameState'][0]
        wn = fields['WishName'][0]
        name = fields['setName'][0]

        if wns == 'APPROVED':
            wns = ''
            name = wn
            wn = ''
        elif wns == 'REJECTED':
            wns = 'OPEN'
            wn = ''
        else:
            self.demand('Kill', 'Tried to acknowledge name on an avatar in %s state!' % wns)
            return

        # Push the change back through:
        self.csm.air.dbInterface.updateObject(
            self.csm.air.dbId,
            self.avId,
            self.csm.air.dclassesByName['DistributedPlayerPirateUD'],
            {'WishNameState': (wns,),
             'WishName': (wn,),
             'setName': (name,)})

        self.demand('Off')

class NewNameFSM(AvatarOperationFSM):
    notify = directNotify.newCategory('AcknowledgeNameFSM')
    POST_ACCOUNT_STATE = 'GetTargetAvatar'

    def enterStart(self, avId, name):
        self.avId = avId
        self.name = name.strip()
        self.demand('RetrieveAccount')

    def enterGetTargetAvatar(self):
        # Make sure the target avatar is part of the account:
        if self.avId not in self.avList:
            self.demand('Kill', 'Tried to acknowledge name on an avatar not in the account!')
            return

        self.csm.air.dbInterface.queryObject(self.csm.air.dbId, self.avId,
                                             self.__handleAvatar)

    def __handleAvatar(self, dclass, fields):
        if dclass != self.csm.air.dclassesByName['DistributedPlayerPirateUD']:
            self.demand('Kill', "One of the account's avatars is invalid!")
            return

        wns = fields['WishNameState'][0]

        if wns != 'OPEN':
            self.demand('Kill', 'Tried to update name on an avatar in %s state!' % wns)
            return

        dna = HumanDNA()
        dna.makeFromNetString(fields['setDNAString'][0])

        judged = CreateAvatarFSM._judgeName(self.name, dna.gender)
        
        if judged == NAME_TYPED_INVALID:
            self.demand('Kill', 'Your name has been rejected!')
            return

        if judged == NAME_TYPED:
            self.name, self.wishName = 'Pirate', self.name
            state = 'PENDING'
        elif judged == NAME_PICKED:
            self.wishName, state = '', ''

        if state == 'PENDING':
            self.csm.accountDB.getNameStatus(self.wishName, self.__gotNameResponse)
        else:
            self.__handleNameChange('CLOSED', '', self.name)
    
    def __gotNameResponse(self, status):
        if status == NAME_REJ:
            self.__handleNameChange('REJECTED', self.wishName, self.name)
        elif status == NAME_APR:
            self.__handleNameChange('CLOSED', '', self.wishName)
        else:
            self.__handleNameChange('PENDING', self.wishName, self.name)
    
    def __handleNameChange(self, nameState, wishName, name):        
        # Push the change back through:
        self.csm.air.dbInterface.updateObject(
            self.csm.air.dbId,
            self.avId,
            self.csm.air.dclassesByName['DistributedPlayerPirateUD'],
            {'WishNameState': (nameState,),
             'WishName': (wishName,),
             'setName': (name,)})

        self.csm.sendUpdateToAccountId(self.target, 'newNameResp', [])
        self.demand('Off')

class ClientServicesManagerUD(DistributedObjectGlobalUD):
    notify = directNotify.newCategory('ClientServicesManagerUD')
    KEY = flip(config.GetString('csmud-secret', 'dev'))

    def announceGenerate(self):
        DistributedObjectGlobalUD.announceGenerate(self)

        self.connection2fsm = {}
        self.account2fsm = {}

        if accountDBType == 'developer':
            self.accountDB = DeveloperAccountDB(self)
        elif accountDBType == 'remote':
            self.accountDB = RemoteAccountDB(self)
        elif accountDBType == 'remotePOR':
            self.accountDB = RemotePORAccountDB(self)
        else:
            self.notify.error('Invalid accountdb-type: ' + accountDBType)

        self.challenges = {}

    def requestChallenge(self):
        sender = self.air.getMsgSender()

        if sender in self.challenges:
            self.killConnection(sender, 'Client requested challenge twice.')
            return

        data = os.urandom(32)
        self.challenges[sender] = data
        self.sendUpdateToChannel(sender, 'challenge', [data])

    def killConnection(self, connId, reason):
        datagram = PyDatagram()
        datagram.addServerHeader(
            connId,
            self.air.ourChannel,
            CLIENTAGENT_EJECT)
        datagram.addUint16(122)
        datagram.addString(reason)
        self.air.send(datagram)

    def killConnectionFSM(self, connId):
        fsm = self.connection2fsm.get(connId)

        if not fsm:
            self.notify.warning('Tried to kill connection %d for duplicate FSM, but none exists!' % connId)
            return

        self.killConnection(connId, 'An operation is already underway: ' + fsm.name)

    def killAccount(self, accountId, reason):
        self.killConnection(self.GetAccountConnectionChannel(accountId), reason)

    def killAccountFSM(self, accountId):
        fsm = self.account2fsm.get(accountId)
        if not fsm:
            self.notify.warning('Tried to kill account %d for duplicate FSM, but none exists!' % accountId)
            return

        self.killAccount(accountId, 'An operation is already underway: ' + fsm.name)

    def runAccountFSM(self, fsmtype, *args):
        sender = self.air.getAccountIdFromSender()

        if not sender:
            self.killAccount(sender, 'Client is not logged in.')

        if sender in self.account2fsm:
            self.killAccountFSM(sender)
            return

        self.account2fsm[sender] = fsmtype(self, sender)
        self.account2fsm[sender].request('Start', *args)

    def login(self, resp, cookie, sig):
        sender = self.air.getMsgSender()

        if sender >> 32:
            return

        if sender in self.connection2fsm:
            self.killConnectionFSM(sender)
            return

        data = self.challenges.pop(sender, '')
        if resp != challenge.solve(self.KEY, cookie, data):
            self.killConnection(sender, 'Invalid challenge response.')
            return

        digest = hmac.new(self.KEY, cookie, hashlib.sha512).digest()
        if len(sig) != len(digest):
            self.killConnection(sender, 'Invalid signature.')
            return

        value = 0
        for x, y in zip(sig, digest):
            value |= ord(x) ^ ord(y)

        if value:
            self.killConnection(sender, 'Invalid signature.')
            return

        self.connection2fsm[sender] = LoginAccountFSM(self, sender)
        self.connection2fsm[sender].request('Start', cookie)

    def requestAvatars(self):
        self.runAccountFSM(GetAvatarsFSM)

    def createAvatar(self, dna, index, allegiance, name):
        self.runAccountFSM(CreateAvatarFSM, dna, index, allegiance, name)

    def deleteAvatar(self, avId):
        self.runAccountFSM(DeleteAvatarFSM, avId)

    def chooseAvatar(self, avId):
        currentAvId = self.air.getAvatarIdFromSender()
        accountId = self.air.getAccountIdFromSender()
        if currentAvId and avId:
            self.killAccount(accountId, 'A Pirate is already chosen!')
            return
        elif not currentAvId and not avId:
            # This isn't really an error, the client is probably just making sure
            # none of its Toons are active.
            return

        if avId:
            self.runAccountFSM(LoadAvatarFSM, avId)
        else:
            self.runAccountFSM(UnloadAvatarFSM, currentAvId)

    def acknowledgeName(self, avId):
        self.runAccountFSM(AcknowledgeNameFSM, avId)

    def newName(self, avId, name):
        self.runAccountFSM(NewNameFSM, avId, name)
