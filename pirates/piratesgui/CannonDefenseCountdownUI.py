from panda3d.core import NodePath, TextNode, Vec3, Vec4
# File: C (Python 2.4)

from direct.gui.DirectGui import *
from direct.interval.IntervalGlobal import *
from pirates.piratesbase import PiratesGlobals
from pirates.piratesgui import PiratesGuiGlobals
from pirates.piratesbase import PLocalizer

class CannonDefenseCountdownUI(NodePath):

    def __init__(self):
        NodePath.__init__(self, 'CountDown')


    def setTime(self, value):
        if value < 0:
            return None

        number = TextNode('Number')
        number.setFont(PiratesGlobals.getInterfaceFont())
        number.setTextColor(PiratesGuiGlobals.TextFG1)
        number.setAlign(TextNode.ACenter)
        number.setShadow(0.050000, 0.050000)
        number.setShadowColor(0, 0, 0, 1)
        if value > 0:
            number.setText(str(value))
        else:
            number.setText(PLocalizer.CannonDefenseHelp['BeginGame'])
        numberNode = self.attachNewNode(number)
        numberNode.setTransparency(1)
        numberNode.setDepthTest(False)
        numberNode.setDepthWrite(False)
        seq = Sequence(Parallel(numberNode.scaleInterval(1, Vec3(0, 0, 0), Vec3(0.299, 0.299, 0.299)), numberNode.colorScaleInterval(1, Vec4(1, 1, 1, 0), Vec4(1, 1, 1, 1))), Func(numberNode.remove_node))
        seq.start()
